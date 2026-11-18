use anyhow::{Context, Result};
use indicatif::{ProgressBar, ProgressStyle};
use std::fs::OpenOptions;
use std::io::Write;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use crate::core::config::ConfigManager;
use crate::core::rate_limit::{download_rate_limit_wait_seconds, DOWNLOAD_RATE_LIMIT_MAX_RETRIES};

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
    /// Overall download timeout in seconds. `None` means no overall timeout
    /// (download retries indefinitely on chunk failure). Used to prevent
    /// stalled downloads from hanging forever without reporting an error.
    pub overall_timeout_secs: Option<u64>,
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

/// Maximum consecutive empty chunks before giving up (prevents indefinite stall).
const MAX_EMPTY_CHUNK_RETRIES: u32 = 60;

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
pub async fn to_file(d: &Download<'_>, config: &ConfigManager) -> Result<()> {
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

    let bandwidth_limit = config.get().download_bandwidth_limit;
    streamed(d, &part_path, total, resume_from, bandwidth_limit).await
}

/// Fetch a small text file: a digest sidecar, a release notes file.
pub async fn text(url: &str, token: Option<&str>) -> Result<String> {
    let mut req = minreq::get(url)
        .with_header("User-Agent", crate::core::USER_AGENT)
        .with_header("Accept", "application/vnd.github.v3+json")
        .with_timeout(30_000);
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
    bandwidth_limit: Option<u64>,
) -> Result<()> {
    let pb = progress_bar(d, total, resume_from);
    let mut start = resume_from;
    let mut consecutive_failures: u32 = 0;
    let mut consecutive_empty_chunks: u32 = 0;
    let mut backoff_ms = INITIAL_BACKOFF_MS;

    // Overall download timeout: if set, abort after this many seconds to
    // prevent a stalled download from hanging forever without reporting an error.
    let started_at = std::time::Instant::now();
    let overall_timeout = d.overall_timeout_secs.map(std::time::Duration::from_secs);
    // Default overall timeout if none specified (10 minutes) to prevent indefinite stalls.
    let overall_timeout = overall_timeout.or(Some(std::time::Duration::from_secs(600)));

    // Open the part file for appending (create if missing).
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(part_path)
        .with_context(|| format!("Failed to open {} for writing", part_path.display()))?;

    while start < total {
        // Check overall timeout before each chunk.
        if let Some(timeout) = overall_timeout {
            if started_at.elapsed() >= timeout {
                pb.finish_and_clear();
                return Err(anyhow::anyhow!(
                    "Download timed out after {} seconds",
                    timeout.as_secs()
                ));
            }
        }
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
                        if chunk.is_empty() {
                            // Server returned 206 with empty body — treat as
                            // a transient failure and retry the same range.
                            consecutive_empty_chunks += 1;
                            consecutive_failures += 1;
                            if consecutive_empty_chunks >= MAX_EMPTY_CHUNK_RETRIES {
                                return Err(anyhow::anyhow!(
                                    "Download failed: too many consecutive empty chunks ({} retries) at {}/{} bytes",
                                    MAX_EMPTY_CHUNK_RETRIES, start, total
                                ));
                            }
                            if consecutive_failures % STALL_NOTIFY_THRESHOLD == 0 {
                                eprintln!(
                                    "Download stalled at {}/{} bytes ({} consecutive failures). \\
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
                        consecutive_empty_chunks = 0;
                        file.write_all(&chunk)
                            .with_context(|| format!("Failed to write chunk to {}", part_path.display()))?;
                        pb.inc(chunk.len() as u64);
                        // Advance by bytes actually received, not requested.
                        // A short or empty range response must not skip file data.
                        start += chunk.len() as u64;
                        // Honor the configured bandwidth limit (bytes/sec).
                        if let Some(limit) = bandwidth_limit {
                            if limit > 0 {
                                tokio::time::sleep(Duration::from_secs_f64(chunk.len() as f64 / limit as f64)).await;
                            }
                        }
                    }
                    Err(_e) => {
                        consecutive_failures += 1;

                        // Stall notification: tell the user the download is stuck
                        // and that they can interrupt with Ctrl+C.
                        #[allow(unknown_lints, clippy::manual_is_multiple_of)]
                        if consecutive_failures % STALL_NOTIFY_THRESHOLD == 0 {
                            eprintln!(
                                "Download stalled at {}/{} bytes ({} consecutive failures). \\
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

    let mut rate_limit_retries = 0u32;

    loop {
        let mut req = minreq::get(&url)
            .with_header("User-Agent", crate::core::USER_AGENT)
            .with_header("Range", format!("bytes={start}-{end}"))
            .with_timeout(30_000);
        if let Some(token) = &token {
            req = req.with_header("Authorization", format!("Bearer {}", token));
        }
        let resp = req.send()
            .with_context(|| format!("Failed to request {label} ({url})"))?;

        if resp.status_code == 429 {
            rate_limit_retries += 1;
            if let Some(wait_secs) = download_rate_limit_wait_seconds(&resp) {
                eprintln!(
                    "Download rate limited (429) for {url} — waiting {}s (retry {})",
                    wait_secs, rate_limit_retries
                );
                tokio::time::sleep(Duration::from_secs(wait_secs)).await;
                continue;
            }
            let backoff = 1000_u64 * 2_u64.pow(rate_limit_retries - 1);
            let backoff = backoff.min(30_000);
            eprintln!(
                "Download rate limited (429) for {url} — backing off {}ms (retry {})",
                backoff, rate_limit_retries
            );
            tokio::time::sleep(Duration::from_millis(backoff)).await;
            continue;
        }

        if resp.status_code != 206 {
            anyhow::bail!(
                "Server returned HTTP {} for range request {url} — expected 206 Partial Content",
                resp.status_code
            );
        }

        return Ok(resp.as_bytes().to_vec());
    }
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

    let mut rate_limit_retries = 0u32;

    loop {
        let mut req = minreq::get(&url)
            .with_header("User-Agent", crate::core::USER_AGENT)
            .with_header("Range", "bytes=0-0")
            .with_timeout(30_000);
        if let Some(token) = &token {
            req = req.with_header("Authorization", format!("Bearer {}", token));
        }
        let resp = req.send()
            .with_context(|| format!("Failed to request {url}"))?;

        if resp.status_code == 429 {
            rate_limit_retries += 1;
            if let Some(wait_secs) = download_rate_limit_wait_seconds(&resp) {
                eprintln!(
                    "Download rate limited (429) for {url} — waiting {}s (retry {})",
                    wait_secs, rate_limit_retries
                );
                tokio::time::sleep(Duration::from_secs(wait_secs)).await;
                continue;
            }
            let backoff = 1000_u64 * 2_u64.pow(rate_limit_retries - 1);
            let backoff = backoff.min(30_000);
            eprintln!(
                "Download rate limited (429) for {url} — backing off {}ms (retry {})",
                backoff, rate_limit_retries
            );
            tokio::time::sleep(Duration::from_millis(backoff)).await;
            continue;
        }

        if resp.status_code != 206 {
            anyhow::bail!(
                "Server returned HTTP {} for size probe {url} — expected 206 Partial Content",
                resp.status_code
            );
        }

        let content_range = resp
            .headers
            .get("content-range")
            .map(|v| v.as_str())
            .unwrap_or("");
        return total_from_content_range(content_range).ok_or_else(|| {
            anyhow::anyhow!(
                "The server at {url} did not report the file size, so the download cannot be resumed"
            )
        });
    }
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
            .expect("static progress template is valid")
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
