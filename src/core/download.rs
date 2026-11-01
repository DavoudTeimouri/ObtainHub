use anyhow::{Context, Result};
use indicatif::{ProgressBar, ProgressStyle};
use std::fs::OpenOptions;
use std::io::Write;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};

use crate::core::config::ConfigManager;
use crate::utils::retry::{execute_with_retry, RetryConfig};

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

/// Download `d.url` into `d.dest`.
///
/// Every download in the tool goes through here: the registry path, the
/// `install --url` path and `update`. One implementation means the retry,
/// resume and progress behaviour apply to all three.
///
/// The download is done with Range requests in 1 MiB chunks so a real
/// progress bar can move during the transfer, a failed chunk is retried with
/// exponential backoff, and a partially downloaded file is resumed instead of
/// restarted.
pub async fn to_file(d: &Download<'_>, config: &ConfigManager) -> Result<()> {
    let retry = RetryConfig::from_config(config);

    // Total size: caller-provided or probed with a one-byte Range request.
    let total = match d.size {
        Some(s) if s > 0 => s,
        _ => probe_size(d, &retry).await?,
    };

    // Resume: if the destination already exists, continue from its size.
    let resume_from = if d.dest.exists() {
        d.dest.metadata()?.len()
    } else {
        0
    };
    if resume_from >= total {
        // Already complete - nothing to do.
        return Ok(());
    }

    streamed(d, &retry, total, resume_from).await
}

/// Fetch a small text file: a digest sidecar, a release notes file.
pub async fn text(url: &str, token: Option<&str>) -> Result<String> {
    let retry = RetryConfig::default();
    let body = execute_with_retry(
        &retry,
        move || {
            let url = url.to_string();
            let token = token.map(|s| s.to_string());
            async move {
                let mut req = crate::core::registries::github_get(&url);
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
        },
        "download_text",
    )
    .await?;
    Ok(body)
}

/// Chunked streaming download with retry and resume.
///
/// Each chunk is fetched with its own Range request, wrapped in retry logic.
/// Chunks are appended to the destination file as they arrive, so memory use
/// stays bounded and a partial file survives a crash.
async fn streamed(
    d: &Download<'_>,
    retry: &RetryConfig,
    total: u64,
    resume_from: u64,
) -> Result<()> {
    let pb = progress_bar(d, total, resume_from);
    let mut start = resume_from;

    // Open the destination for appending (create if missing).
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(d.dest)
        .with_context(|| format!("Failed to open {} for writing", d.dest.display()))?;

    while start < total {
        let end = (start + CHUNK_SIZE - 1).min(total - 1);
        let chunk = fetch_chunk(d, retry, start, end).await?;
        file.write_all(&chunk)
            .with_context(|| format!("Failed to write chunk to {}", d.dest.display()))?;
        pb.inc(chunk.len() as u64);
        start = end + 1;
    }

    pb.finish_with_message(format!("Downloaded {} ({} bytes)", d.label, total));
    Ok(())
}

/// Fetch one byte range `[start..=end]` from the URL, with retry.
async fn fetch_chunk(
    d: &Download<'_>,
    retry: &RetryConfig,
    start: u64,
    end: u64,
) -> Result<Vec<u8>> {
    execute_with_retry(
        retry,
        move || {
            let url = d.url.to_string();
            let token = d.token.map(|s| s.to_string());
            let label = d.label.to_string();
            async move {
                let mut req = crate::core::registries::github_get(&url);
                req = req.with_header("Range", format!("bytes={start}-{end}"));
                if let Some(token) = token {
                    req = req.with_header("Authorization", format!("Bearer {token}"));
                }
                let response = req
                    .send()
                    .with_context(|| format!("Failed to request {label} ({url})"))?;
                if response.status_code != 206 {
                    anyhow::bail!(
                        "The server at {url} does not support range requests, so the download cannot be resumed"
                    );
                }
                Ok(response.as_bytes().to_vec())
            }
        },
        "download_chunk",
    )
    .await
}

/// Ask the server for the file size with a one byte Range request, with retry.
async fn probe_size(d: &Download<'_>, retry: &RetryConfig) -> Result<u64> {
    execute_with_retry(
        retry,
        move || {
            let url = d.url.to_string();
            let token = d.token.map(|s| s.to_string());
            async move {
                let mut req = crate::core::registries::github_get(&url);
                req = req.with_header("Range", "bytes=0-0");
                if let Some(token) = token {
                    req = req.with_header("Authorization", format!("Bearer {token}"));
                }
                let response = req
                    .send()
                    .with_context(|| format!("Failed to request {url}"))?;
                if response.status_code != 206 {
                    anyhow::bail!(
                        "The server at {url} does not support range requests, so the download cannot be resumed"
                    );
                }
                let content_range = response
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
        },
        "probe_size",
    )
    .await
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
        "{spinner} [{elapsed_precise}] [{bar:40}] {bytes}/{total_bytes} ({eta})"
    } else {
        "{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {bytes}/{total_bytes} ({eta})"
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
}
