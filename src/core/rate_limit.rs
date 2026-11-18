/// HTTP 429 rate limit handling for downloads.
///
/// Extracted into a shared module so both the CLI (`core/download.rs`) and
/// WebUI (`webui/downloads.rs`) use identical retry behaviour instead of
/// duplicating the logic.
use minreq::Response;

/// Maximum consecutive 429 responses before giving up.
pub const DOWNLOAD_RATE_LIMIT_MAX_RETRIES: u32 = 10;

/// Calculate wait time from rate limit headers.
///
/// Prefers `Retry-After` (seconds), falls back to `X-RateLimit-Reset`
/// (unix timestamp). Returns `None` if headers are missing or invalid.
pub fn download_rate_limit_wait_seconds(resp: &Response) -> Option<u64> {
    if let Some(retry_after) = resp.headers.get("retry-after") {
        if let Ok(secs) = retry_after.as_str().trim().parse::<u64>() {
            return Some(secs.max(1).min(3600));
        }
    }
    if let Some(reset) = resp.headers.get("x-ratelimit-reset") {
        if let Ok(reset_ts) = reset.as_str().trim().parse::<u64>() {
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .ok()?
                .as_secs();
            if reset_ts > now {
                return Some((reset_ts - now).max(1).min(3600));
            }
        }
    }
    None
}
