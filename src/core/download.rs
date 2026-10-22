use anyhow::{Context, Result};
use indicatif::{ProgressBar, ProgressStyle};
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};

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

/// Download `d.url` into `d.dest`.
///
/// Every download in the tool goes through here: the registry path, the
/// `install --url` path and `update`. One implementation means the bandwidth
/// limit and the error messages apply to all three.
pub async fn to_file(d: &Download<'_>, config: &ConfigManager) -> Result<()> {
    if let Some(limit_kbps) = config.get().download_bandwidth_limit.filter(|k| *k > 0) {
        let total = match d.size {
            Some(s) if s > 0 => s,
            _ => probe_size(d).await?,
        };
        return paced(d, limit_kbps, total).await;
    }
    plain(d).await
}

/// Fetch a small text file: a digest sidecar, a release notes file.
pub async fn text(url: &str, token: Option<&str>) -> Result<String> {
    let mut req = crate::core::registries::github_get(url);
    if let Some(token) = token {
        req = req.with_header("Authorization", format!("Bearer {token}"));
    }
    let resp = req.send().with_context(|| format!("Failed to request {url}"))?;
    resp.as_str()
        .with_context(|| format!("Failed to read the response from {url}"))
        .map(|s| s.to_string())
}

/// One request for the whole file.
async fn plain(d: &Download<'_>) -> Result<()> {
    let mut req = crate::core::registries::github_get(d.url);
    if let Some(token) = d.token {
        req = req.with_header("Authorization", format!("Bearer {token}"));
    }
    let response = req.send().with_context(|| format!("Failed to request {}", d.url))?;

    let total = response
        .headers
        .get("content-length")
        .and_then(|v| v.parse::<u64>().ok())
        .unwrap_or(0);
    let bytes = response.as_bytes();

    let pb = progress_bar(d, total);
    for chunk in bytes.chunks(8192) {
        pb.inc(chunk.len() as u64);
    }
    pb.finish_with_message(format!("Downloaded {}", d.label));

    std::fs::write(d.dest, bytes)
        .with_context(|| format!("Failed to write {} to {}", d.label, d.dest.display()))?;
    Ok(())
}

/// Download an asset at a limited rate.
///
/// The chunk is as many bytes as the limit allows in one second and the next
/// chunk starts a second later, so the average rate is the configured one. The
/// server has to support Range requests; without them the download cannot be
/// paced and the caller is told so.
async fn paced(d: &Download<'_>, limit_kbps: u64, total: u64) -> Result<()> {
    let chunk_size = limit_kbps.saturating_mul(1024).max(1);
    let mut bytes: Vec<u8> = Vec::with_capacity(total as usize);
    let mut start: u64 = 0;
    let pb = progress_bar(d, total);

    while start < total {
        let end = (start + chunk_size - 1).min(total - 1);
        let mut req = crate::core::registries::github_get(d.url);
        req = req.with_header("Range", format!("bytes={start}-{end}"));
        if let Some(token) = d.token {
            req = req.with_header("Authorization", format!("Bearer {token}"));
        }
        let response = req.send().with_context(|| format!("Failed to request {}", d.url))?;
        if response.status_code != 206 {
            anyhow::bail!(
                "The server at {} does not support range requests, so the download cannot be rate limited",
                d.url
            );
        }
        let chunk = response.as_bytes();
        bytes.extend_from_slice(chunk);
        pb.inc(chunk.len() as u64);
        start = end + 1;
        if start < total {
            tokio::time::sleep(std::time::Duration::from_secs(1)).await;
        }
    }

    pb.finish_with_message(format!("Downloaded {}", d.label));
    std::fs::write(d.dest, &bytes)
        .with_context(|| format!("Failed to write {} to {}", d.label, d.dest.display()))?;
    Ok(())
}

/// Ask the server for the file size with a one byte Range request.
///
/// `minreq` buffers the whole body, so a single request cannot be slowed
/// down after the fact. The size has to be known before the chunks are
/// fetched.
async fn probe_size(d: &Download<'_>) -> Result<u64> {
    let mut req = crate::core::registries::github_get(d.url);
    req = req.with_header("Range", "bytes=0-0");
    if let Some(token) = d.token {
        req = req.with_header("Authorization", format!("Bearer {token}"));
    }
    let response = req.send().with_context(|| format!("Failed to request {}", d.url))?;
    if response.status_code != 206 {
        anyhow::bail!(
            "The server at {} does not support range requests, so the download cannot be rate limited",
            d.url
        );
    }
    let content_range = response
        .headers
        .get("content-range")
        .map(|v| v.as_str())
        .unwrap_or("");
    total_from_content_range(content_range).ok_or_else(|| {
        anyhow::anyhow!(
            "The server at {} did not report the file size, so the download cannot be rate limited",
            d.url
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

fn progress_bar(d: &Download<'_>, total: u64) -> ProgressBar {
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
