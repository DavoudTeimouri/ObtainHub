use anyhow::{Context, Result};
use indicatif::{ProgressBar, ProgressStyle};
use std::fs::OpenOptions;
use std::io::Write;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use crate::core::config::ConfigManager;

/// Whether the progress bar drops its colours.
static NO_COLOR: AtomicBool = AtomicBool::new(false);

/// Turn the coloured progress bar into a plain one. Process wide, set once
/// from the `--no-color` flag.
pub fn set_no_color(on: bool) {
    NO_COLOR.store(on, Ordering::Relaxed);
}

/// A download to perform.
pub struct Download<'a> {
    pub url: &'a str,
    pub dest: &'a Path,
    pub token: Option<&'a str>,
    /// Shown on the progress bar and in the error messages.
    pub label: &'a str,
    /// The content length, when the caller knows it. `None` means the server
    /// is asked for it with a Range probe.
    pub size: Option<u64>,
    /// No progress bar. The caller prints its own summary.
    pub quiet: bool,
}

/// How many bytes to fetch per Range request. Large enough to be efficient,
/// small enough that a failure only loses one chunk.
const CHUNK_SIZE: u64 = 1024 * 1024; // 1 MiB

/// After this many consecutive chunk failures, print a stall notification.
const STALL_NOTIFY_THRESHOLD: u32 = 5;

/// Initial backoff between chunk retries.
const INITIAL_BACKOFF_MS: u64 = 1000;

/// Maximum backoff between chunk retries.
const MAX_BACKOFF_MS: u64 = 30_000;

/// Download `d.url` into `d.dest`.
///
/// Every download in the tool goes through here: the registry path, the
/// `install --url` path and `update`. One implementation means the retry,
/// resume and progress behaviour apply to all three.
///
/// Download-manager behaviour:
/// - Writes to `<dest>.download` (a part file) instead of the destination.
/// - On start, resumes from the part file's existing size.
/// - Retries each chunk indefinitely with exponential backoff - the download
///   only stops when it finishes or the user interrupts (Ctrl+C).
/// - Prints a stall notification to stderr after every
///   `STALL_NOTIFY_THRESHOLD` consecutive chunk failures, so the user knows
///   the download is stuck and can stop it if they want.
/// - On success, atomically renames the part file to the destination.
pub async fn to_file(d: &Download<'_>, _config: &ConfigManager) -> Result<()> {
    // The part file caches downloaded parts so a download can be resumed
    // after a crash, network drop, or restart.
    let part_path = part_file_path(d.dest);

    // Make sure the download folder exists. Downloads never created it,
    // so the first download of any repo failed with "no such file or directory".
    if let Some(parent) = part_path.parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("Failed to create download directory {}", parent.display()))?;
    }

    // Total size: caller-provided or probed with a one-byte Range request.
    let total = match d.size {
        Some(s) if s > 0 => s,
        _ => probe_size(d).await?,
    };

    // Resume: if the part file exists, continue from its size.
    let resume_from = if part_path.exists() {
        part_path.metadata()?.len()
    } else {
        0
    };
    if resume_from >= total {
        // Already complete - nothing to do.
        rename_part_to_dest(d, &part_path).await?;
        return Ok(());
    }

    streamed(d, &part_path, total, resume_from).await
}

/// Fetch a small text file: a digest sidecar, a release notes file.
pub async fn text(url: &str, token: Option<&str>) -> Result<String> {
    let mut req = minreq::get(url)
        .with_header("User-Agent", "ObtainHub/3.0.0")
        .with_header("Accept", "application/vnd.github.v3+json");
    if let Some(token) = token {
        req = req.with_header("Authorization", format!("Bearer {token}"));
    }
    let resp = req
        .send()
        .with_context(|| format!("Failed to request {url}"))?;
    resp.as_str()
        .with_context(|| format!("Failed to read the response from {url}"))
        .map(|s| s.to_string())
}

/// Chunked streaming download with retry and resume.
///
/// Each chunk is fetched with its own Range request. A failed chunk is retried
/// indefinitely with exponential backoff - the download only stops when it
/// finishes or the user interrupts (Ctrl+C), which cleans up the part file.
/// After `STALL_NOTIFY_THRESHOLD` consecutive failures, a stall notification
/// is printed to stderr.
async fn streamed(
    d: &Download<'_>,
    part_path: &Path,
    total: u64,
    resume_from: u64,
) -> Result<()> {
    let pb = progress_bar(d, total, resume_from);
    let mut start = resume_from;
    let mut consecutive_failures: u32 = 0;
    let mut backoff_ms = INITIAL_BACKOFF_MS;

    // Open the part file for appending (create if missing).
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(part_path)
        .with_context(|| format!("Failed to open {} for writing", part_path.display()))?;

    while start < total {
        let end = (start + CHUNK_SIZE - 1).min(total - 1);

        // Listen for Ctrl+C between chunks so the user can stop a stuck
        // download and leave a clean part file behind.
        tokio::select! {
            biased;
            result = fetch_chunk(d, start, end) => {
                match result {
                    Ok(chunk) => {
                        consecutive_failures = 0;
                        backoff_ms = INITIAL_BACKOFF_MS;
                        file.write_all(&chunk)
                            .with_context(|| format!("Failed to write chunk to {}", part_path.display()))?;
                        pb.inc(chunk.len() as u64);
                        start = end + 1;
                    }
                    Err(_e) => {
                        consecutive_failures += 1;

                        // Stall notification: tell the user the download is stuck
                        // and that they can interrupt with Ctrl+C.
                        if consecutive_failures % STALL_NOTIFY_THRESHOLD == 0 {
                            eprintln!(
                                "Download stalled at {}/{} bytes ({} consecutive failures). \
                                 Retrying in {}s... (press Ctrl+C to stop)",
                                start,
                                total,
                                consecutive_failures,
                                backoff_ms / 1000
                            );
                        }

                        let delay = Duration::from_millis(backoff_ms);
                        tokio::time::sleep(delay).await;
                        backoff_ms = (backoff_ms as f64 * 1.5) as u64;
                        backoff_ms = backoff_ms.min(MAX_BACKOFF_MS);
                        continue;
                    }
                }
            }
            _ = tokio::signal::ctrl_c() => {
                // User asked to stop. Remove the partial part file so nothing
                // half-downloaded is left behind.
                let _ = std::fs::remove_file(part_path);
                return Err(anyhow::anyhow!("Download cancelled by user"));
            }
        }
    }

    pb.finish_with_message(format!("Downloaded {} ({} bytes)", d.label, total));

    // Atomic move: part file -> destination.
    rename_part_to_dest(d, part_path).await?;
    Ok(())
}

/// Fetch one byte range `[start..=end]` from the URL.
///
/// Returns the error so the caller (`streamed`) can decide when to notify
/// the user and when to back off. No retry limit - the caller retries
/// indefinitely.
async fn fetch_chunk(d: &Download<'_>, start: u64, end: u64) -> Result<Vec<u8>> {
    let url = d.url.to_string();
    let token = d.token.map(|s| s.to_string());
    let label = d.label.to_string();

    let resp = minreq::get(&url)
        .with_header("User-Agent", "ObtainHub/3.0.0")
        .with_header("Range", format!("bytes={start}-{end}"))
        .with_header("Authorization", format!("Bearer {}", token.unwrap_or_default()))
        .send()
        .with_context(|| format!("Failed to request {label} ({url})"))?;

    if resp.status_code != 206 {
        anyhow::bail!(
            "The server at {url} does not support range requests, so the download cannot be resumed"
        );
    }

    Ok(resp.as_bytes().to_vec())
}

/// Path of the part file that caches downloaded chunks.
fn part_file_path(dest: &Path) -> std::path::PathBuf {
    let mut part = dest.to_path_buf();
    part.set_extension("download");
    part
}

/// Atomically rename the part file to the destination.
async fn rename_part_to_dest(d: &Download<'_>, part_path: &Path) -> Result<()> {
    std::fs::rename(part_path, d.dest)
        .with_context(|| format!("Failed to move {} to {}", part_path.display(), d.dest.display()))?;
    if !d.quiet {
        eprintln!("Downloaded {} to {}", d.label, d.dest.display());
    }
    Ok(())
}

/// Ask the server for the file size with a one byte Range request.
async fn probe_size(d: &Download<'_>) -> Result<u64> {
    let url = d.url.to_string();
    let token = d.token.map(|s| s.to_string());

    let resp = minreq::get(&url)
        .with_header("User-Agent", "ObtainHub/3.0.0")
        .with_header("Range", "bytes=0-0")
        .with_header("Authorization", format!("Bearer {}", token.unwrap_or_default()))
        .send()
        .with_context(|| format!("Failed to request {url}"))?;

    if resp.status_code != 206 {
        anyhow::bail!(
            "The server at {url} does not support range requests, so the download cannot be resumed"
        );
    }

    let content_range = resp
        .headers
        .get("content-range")
        .map(|v| v.as_str())
        .unwrap_or("");
    total_from_content_range(content_range).ok_or_else(|| {
        anyhow::anyhow!(
            "The server at {url} did not report the file size, so the download cannot be resumed"
        )
    })
}

/// `Content-Range: bytes 0-0/12345` -> `12345`.
fn total_from_content_range(value: &str) -> Option<u64> {
    value
        .rsplit('/')
        .next()
        .and_then(|s| s.trim().parse::<u64>().ok())
        .filter(|s| *s > 0)
}

fn progress_bar(d: &Download<'_>, total: u64, already: u64) -> ProgressBar {
    let pb = if d.quiet {
        ProgressBar::hidden()
    } else {
        ProgressBar::new(total)
    };
    // The coloured template is the default one. `indicatif` has no NO_COLOR
    // support, so the plain template is spelled out.
    let template = if NO_COLOR.load(Ordering::Relaxed) {
        "{spinner} [{elapsed_precise}] [{bar:40}] {bytes}/{total_bytes} ({bytes_per_sec}, {eta})"
    } else {
        "{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {bytes}/{total_bytes} ({bytes_per_sec}, {eta})"
    };
    pb.set_style(
        ProgressStyle::default_bar()
            .template(template)
            .unwrap()
            .progress_chars("#>-"),
    );
    pb.set_message(d.label.to_string());
    pb.set_position(already);
    pb
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn content_range_gives_the_total_size() {
        assert_eq!(total_from_content_range("bytes 0-0/12345"), Some(12345));
        assert_eq!(total_from_content_range("bytes 0-1023/1024"), Some(1024));
    }

    #[test]
    fn a_content_range_without_a_total_is_rejected() {
        assert_eq!(total_from_content_range("bytes 0-0/*"), None);
        assert_eq!(total_from_content_range(""), None);
        assert_eq!(total_from_content_range("bytes 0-0/0"), None);
        assert_eq!(total_from_content_range("nonsense"), None);
    }

    #[test]
    fn part_file_path_has_download_extension() {
        let dest = Path::new("/tmp/foo.msi");
        let part = part_file_path(dest);
        assert_eq!(part.extension().unwrap(), "download");
        assert_eq!(part.file_stem().unwrap(), "foo");
    }
}
