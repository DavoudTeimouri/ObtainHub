use axum::{Json, response::IntoResponse, extract::{State, Path}, http::StatusCode};
use serde::{Serialize, Deserialize};
use anyhow::Context;
use std::collections::HashMap;
use std::io::Write;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};
use uuid::Uuid;
use crate::core::rate_limit::{download_rate_limit_wait_seconds, DOWNLOAD_RATE_LIMIT_MAX_RETRIES};

/// One tracked download job. `cancel` is runtime-only, never serialized.
#[derive(Serialize, Clone)]
pub struct DownloadJob {
    pub id: String,
    pub url: String,
    pub label: String,
    pub dest: String,
    pub total: u64,
    pub downloaded: u64,
    pub status: String,
    pub speed: Option<u64>,
    pub eta: Option<u64>,
    pub error: Option<String>,
    #[serde(skip)]
    pub cancel: Arc<AtomicBool>,
}

/// Live download registry shared by all handlers.
pub type DownloadRegistry = Arc<Mutex<HashMap<String, DownloadJob>>>;

/// Start a new download.
#[derive(Deserialize)]
pub struct StartDownloadRequest {
    pub url: String,
    pub dest: String,
    pub label: Option<String>,
    pub token: Option<String>,
}

#[derive(Serialize)]
pub struct StartDownloadResponse {
    pub id: String,
    pub status: String,
}

const CHUNK_SIZE: u64 = 256 * 1024;

/// After this many consecutive empty chunks, print a stall notification.
const STALL_NOTIFY_THRESHOLD: u32 = 5;
/// Initial backoff between empty-chunk retries.
const INITIAL_BACKOFF_MS: u64 = 1000;
/// Maximum backoff between empty-chunk retries.
const MAX_BACKOFF_MS: u64 = 30_000;
/// Maximum consecutive empty chunks before giving up (prevents indefinite stall).
const MAX_EMPTY_CHUNK_RETRIES: u32 = 60;
/// Maximum consecutive chunk fetch errors (timeouts, resets) before giving up.
const MAX_CHUNK_FETCH_RETRIES: u32 = 60;

/// Extract a safe file name from the requested dest (both path separators),
/// falling back to the URL's last segment. Only this name is joined onto the
/// configured download dir — a no-auth localhost server must not become an
/// arbitrary-file-write primitive.
fn dest_file_name(dest: &str, url: &str) -> String {
    dest.rsplit(['/', '\\'])
        .next()
        .filter(|s| !s.is_empty())
        .or_else(|| {
            url.rsplit('/')
                .next()
                .and_then(|s| s.split(['?', '#']).next())
                .filter(|s| !s.is_empty() && *s != "/")
        })
        .unwrap_or("download")
        .to_string()
}

pub async fn start_download(
    State(app_state): State<Arc<super::AppState>>,
    Json(req): Json<StartDownloadRequest>,
) -> impl IntoResponse {
    let file_name = dest_file_name(&req.dest, &req.url);

    let (download_dir, bandwidth_limit) = {
        let config_manager = app_state.config_manager.lock().await;
        let c = config_manager.get();
        (c.download_dir.clone(), c.download_bandwidth_limit)
    };
    let dest = download_dir.join(&file_name);
    if let Some(parent) = dest.parent() {
        let _ = std::fs::create_dir_all(parent);
    }

    let label = req.label.unwrap_or_else(|| file_name.clone());
    let id = Uuid::new_v4().to_string();
    let job_id = id.clone();
    let job = DownloadJob {
        id: id.clone(),
        url: req.url.clone(),
        label,
        dest: dest.display().to_string(),
        total: 0,
        downloaded: 0,
        status: "starting".to_string(),
        speed: None,
        eta: None,
        error: None,
        cancel: Arc::new(AtomicBool::new(false)),
    };
    let cancel = job.cancel.clone();
    app_state.downloads.lock().unwrap().insert(id.clone(), job);

    let registry = app_state.downloads.clone();
    let url = req.url;
    let token = req.token;
    tokio::task::spawn_blocking(move || {
        run_download(registry, id, url, dest, token, cancel, bandwidth_limit, None);
    });

    (StatusCode::OK, Json(StartDownloadResponse { id: job_id, status: "started".to_string() })).into_response()
}

/// Parameters for one download run, bundled to keep `download_inner` under
/// clippy's argument limit.
pub(crate) struct DownloadRun<'a> {
    url: &'a str,
    token: Option<&'a str>,
    dest: &'a std::path::Path,
    part_path: &'a std::path::Path,
    registry: &'a DownloadRegistry,
    id: &'a str,
    cancel: &'a AtomicBool,
    bandwidth_limit: Option<u64>,
    /// Overall download timeout in seconds. `None` means no overall timeout.
    overall_timeout_secs: Option<u64>,
    /// Known total size from caller (e.g., GitHub asset size). If None, will probe.
    total_size: Option<u64>,
}

/// Run a chunked ranged download, updating the registry as it progresses.
pub(crate) fn run_download(
    registry: DownloadRegistry,
    id: String,
    url: String,
    dest: PathBuf,
    token: Option<String>,
    cancel: Arc<AtomicBool>,
    bandwidth_limit: Option<u64>,
    overall_timeout_secs: Option<u64>,
) {
    run_download_with_size(registry, id, url, dest, token, cancel, bandwidth_limit, overall_timeout_secs, None);
}

/// Run a chunked ranged download with known total size.
pub(crate) fn run_download_with_size(
    registry: DownloadRegistry,
    id: String,
    url: String,
    dest: PathBuf,
    token: Option<String>,
    cancel: Arc<AtomicBool>,
    bandwidth_limit: Option<u64>,
    overall_timeout_secs: Option<u64>,
    total_size: Option<u64>,
) {
    let part_path = dest.with_extension("part");
    let run = DownloadRun {
        url: &url,
        token: token.as_deref(),
        dest: &dest,
        part_path: &part_path,
        registry: &registry,
        id: &id,
        cancel: &cancel,
        bandwidth_limit,
        overall_timeout_secs,
        total_size,
    };
    let result = download_inner(&run);

    let mut map = registry.lock().unwrap();
    if let Some(job) = map.get_mut(&id) {
        if cancel.load(Ordering::Relaxed) {
            job.status = "cancelled".to_string();
            let _ = std::fs::remove_file(&part_path);
        } else {
            match result {
                Ok(()) => {
                    job.status = "completed".to_string();
                    job.downloaded = job.total;
                    job.speed = None;
                    job.eta = Some(0);
                }
                Err(e) => {
                    job.status = "error".to_string();
                    job.error = Some(format!("{e:#}"));
                    let _ = std::fs::remove_file(&part_path);
                }
            }
        }
    }
    // Cap the registry: drop finished jobs when it grows large.
    if map.len() > 100 {
        let finished: Vec<String> = map.iter()
            .filter(|(_, j)| matches!(j.status.as_str(), "completed" | "error" | "cancelled"))
            .map(|(k, _)| k.clone())
            .collect();
        for k in finished { map.remove(&k); }
    }
}

fn download_inner(run: &DownloadRun<'_>) -> anyhow::Result<()> {
    let DownloadRun { url, token, dest, part_path, registry, id, cancel, bandwidth_limit, overall_timeout_secs, total_size } = *run;
    let total = total_size.filter(|&s| s > 0).unwrap_or_else(|| probe_size(url, token).unwrap_or(0));
    update_job(registry, id, |j| { j.total = total; j.status = "downloading".to_string(); });

    let mut file = std::fs::File::create(part_path)
        .with_context(|| format!("Failed to create {}", part_path.display()))?;
    let mut start: u64 = 0;
    let window_start = Instant::now();
    let mut window_bytes: u64 = 0;
    let mut consecutive_failures: u32 = 0;
    let mut consecutive_empty_chunks: u32 = 0;
    let mut backoff_ms = INITIAL_BACKOFF_MS;

    // Overall download timeout: abort after this many seconds to prevent
    // a stalled download from hanging forever without reporting an error.
    let started_at = Instant::now();
    let overall_timeout = overall_timeout_secs.map(Duration::from_secs);

    let mut rate_limit_retries = 0u32;

    loop {
        // Check overall timeout before each chunk.
        if let Some(timeout) = overall_timeout {
            if started_at.elapsed() >= timeout {
                update_job(registry, id, |j| {
                    j.status = "error".to_string();
                    j.error = Some(format!("Download timed out after {} seconds", timeout.as_secs()));
                });
                return Err(anyhow::anyhow!(
                    "Download timed out after {} seconds",
                    timeout.as_secs()
                ));
            }
        }
        if cancel.load(Ordering::Relaxed) {
            anyhow::bail!("cancelled");
        }
        let end = if total > 0 { (start + CHUNK_SIZE - 1).min(total - 1) } else { start + CHUNK_SIZE - 1 };

        // Inner loop for 429 rate limit handling and transient chunk errors.
        // Chunk fetch errors (timeouts, connection resets) are retried with
        // backoff instead of failing the whole download — slow connections
        // (e.g. 400 B/s) take minutes per chunk and would otherwise hit the
        // request timeout and die with no retry.
        let mut chunk_fetch_retries = 0u32;
        let resp = loop {
            let mut req = minreq::get(url)
                .with_header("User-Agent", crate::core::USER_AGENT)
                .with_header("Range", format!("bytes={start}-{end}"))
                .with_timeout(300_000);
            if let Some(token) = token {
                req = req.with_header("Authorization", format!("Bearer {}", token));
            }
            match req.send() {
                Ok(resp) => {
                    if resp.status_code == 429 || (resp.status_code >= 500 && resp.status_code < 600) {
                        rate_limit_retries += 1;
                        consecutive_failures += 1;
                        // Always report current progress on retry so the percentage
                        // doesn't disappear from the WebUI.
                        update_job(registry, id, |j| {
                            j.downloaded = start;
                        });
                        if let Some(wait_secs) = download_rate_limit_wait_seconds(&resp) {
                            eprintln!(
                                "Download rate limited ({}) for {url} — waiting {}s (retry {})",
                                resp.status_code, wait_secs, rate_limit_retries
                            );
                            std::thread::sleep(Duration::from_secs(wait_secs));
                            continue;
                        }
                        let backoff = 1000_u64 * 2_u64.pow(rate_limit_retries - 1);
                        let backoff = backoff.min(30_000);
                        eprintln!(
                            "Download limited ({}) for {url} — backing off {}ms (retry {})",
                            resp.status_code, backoff, rate_limit_retries
                        );
                        std::thread::sleep(Duration::from_millis(backoff));
                        continue;
                    }
                    if resp.status_code >= 400 && resp.status_code < 500 {
                        // Permanent client error (403, 404, 416, etc.) — not retryable.
                        anyhow::bail!(
                            "Download failed: server returned HTTP {} for range request {url}",
                            resp.status_code
                        );
                    }
                    break resp;
                }
                Err(e) => {
                    chunk_fetch_retries += 1;
                    consecutive_failures += 1;
                    // Always report current progress on retry so the percentage
                    // doesn't disappear from the WebUI.
                    update_job(registry, id, |j| {
                        j.downloaded = start;
                    });
                    if consecutive_failures % STALL_NOTIFY_THRESHOLD == 0 {
                        eprintln!(
                            "Download stalled at {}/{} bytes ({} consecutive failures): {e}. Retrying in {}s... (press Cancel to stop)",
                            start, total, consecutive_failures, backoff_ms / 1000
                        );
                        update_job(registry, id, |j| {
                            j.status = "stalled".to_string();
                            j.downloaded = start;
                            j.error = Some(format!(
                                "Download stalled at {}/{} bytes ({} consecutive failures): {e}",
                                start, total, consecutive_failures
                            ));
                        });
                    }
                    let delay = Duration::from_millis(backoff_ms);
                    std::thread::sleep(delay);
                    backoff_ms = (backoff_ms as f64 * 1.5) as u64;
                    backoff_ms = backoff_ms.min(MAX_BACKOFF_MS);
                    continue;
                }
            }
        };

        let chunk = resp.as_bytes();
        if chunk.is_empty() {
            // Server returned 206/200 with empty body — transient failure,
            // retry the same range with exponential backoff instead of
            // marking the download complete or hammering in a tight loop.
            consecutive_empty_chunks += 1;
            consecutive_failures += 1;
            // Always report current progress on retry so the percentage
            // doesn't disappear from the WebUI.
            update_job(registry, id, |j| {
                j.downloaded = start;
            });
            if consecutive_failures % STALL_NOTIFY_THRESHOLD == 0 {
                eprintln!(
                    "Download stalled at {}/{} bytes ({} consecutive empty chunks). \\
                     Retrying in {}s... (press Cancel to stop)",
                    start,
                    total,
                    consecutive_failures,
                    backoff_ms / 1000
                );
                update_job(registry, id, |j| {
                    j.status = "stalled".to_string();
                    j.downloaded = start;
                    j.error = Some(format!(
                        "Download stalled at {}/{} bytes ({} consecutive empty chunks)",
                        start, total, consecutive_failures
                    ));
                });
            }
            let delay = Duration::from_millis(backoff_ms);
            std::thread::sleep(delay);
            backoff_ms = (backoff_ms as f64 * 1.5) as u64;
            backoff_ms = backoff_ms.min(MAX_BACKOFF_MS);
            continue;
        }
        consecutive_empty_chunks = 0;
        consecutive_failures = 0;
        backoff_ms = INITIAL_BACKOFF_MS;
        // Reset status from "stalled" back to "downloading" after a successful chunk
        // following a retry (429/5xx/network error/empty chunk).
        update_job(registry, id, |j| {
            if j.status == "stalled" {
                j.status = "downloading".to_string();
                j.error = None;
            }
        });
        file.write_all(chunk)
            .with_context(|| format!("Failed to write chunk to {}", part_path.display()))?;
        start += chunk.len() as u64;
        window_bytes += chunk.len() as u64;

        // Throttle to the configured bandwidth limit.
        if let Some(limit) = bandwidth_limit {
            if limit > 0 {
                std::thread::sleep(Duration::from_secs_f64(chunk.len() as f64 / limit as f64));
            }
        }

        // Update progress ~2x/sec.
        let now = Instant::now();
        let elapsed = now.duration_since(window_start).as_secs_f64();
        if elapsed >= 0.5 || (total > 0 && start >= total) {
            let speed: Option<u64> = if elapsed > 0.0 { Some((window_bytes as f64 / elapsed) as u64) } else { None };
            let eta = speed.map(|s| if s > 0 && total > start { (total - start) / s } else { 0 });
            let downloaded = start;
            let tot = total;
            update_job(registry, id, |j| {
                j.downloaded = downloaded;
                j.speed = speed;
                j.eta = eta;
                if tot > 0 { j.total = tot; }
            });
            window_bytes = 0;
        }

        if total > 0 && start >= total { break; }
        if resp.status_code == 200 { break; } // server ignored Range: whole body received
    }

    file.sync_all().ok();
    drop(file);
    std::fs::rename(part_path, dest)
        .with_context(|| format!("Failed to move {} to {}", part_path.display(), dest.display()))?;
    update_job(registry, id, |j| { j.downloaded = j.total.max(start); });
    Ok(())
}

fn update_job(registry: &DownloadRegistry, id: &str, f: impl FnOnce(&mut DownloadJob)) {
    if let Ok(mut map) = registry.lock() {
        if let Some(job) = map.get_mut(id) {
            f(job);
        }
    }
}

/// List active downloads.
pub async fn list_downloads(
    State(app_state): State<Arc<super::AppState>>,
) -> impl IntoResponse {
    let map = app_state.downloads.lock().unwrap();
    let mut jobs: Vec<DownloadJob> = map.values().cloned().collect();
    jobs.sort_by(|a, b| a.label.cmp(&b.label));
    Json(jobs)
}

/// Cancel a download by ID.
pub async fn cancel_download(
    State(app_state): State<Arc<super::AppState>>,
    Path(id): Path<String>,
) -> impl IntoResponse {
    let mut map = app_state.downloads.lock().unwrap();
    match map.get_mut(&id) {
        Some(job) if matches!(job.status.as_str(), "starting" | "downloading") => {
            job.cancel.store(true, Ordering::Relaxed);
            job.status = "cancelling".to_string();
            (StatusCode::OK, Json(serde_json::json!({"status": "cancelled", "id": id}))).into_response()
        }
        Some(_) => (StatusCode::CONFLICT, Json(serde_json::json!({"error": "download already finished"}))).into_response(),
        None => (StatusCode::NOT_FOUND, Json(serde_json::json!({"error": "unknown download id"}))).into_response(),
    }
}

/// Probe the server for file size.
fn probe_size(url: &str, token: Option<&str>) -> anyhow::Result<u64> {
    let mut rate_limit_retries = 0u32;

    loop {
        let mut req = minreq::get(url)
            .with_header("Range", "bytes=0-0")
            .with_header("User-Agent", crate::core::USER_AGENT)
            .with_timeout(30_000);

        if let Some(token) = token {
            req = req.with_header("Authorization", format!("Bearer {}", token));
        }

        let response = req.send().context("Failed to probe size")?;

        if response.status_code == 429 {
            rate_limit_retries += 1;
            if rate_limit_retries > DOWNLOAD_RATE_LIMIT_MAX_RETRIES {
                anyhow::bail!(
                    "Download rate limit exceeded: too many 429 responses ({} retries) for {url}",
                    DOWNLOAD_RATE_LIMIT_MAX_RETRIES
                );
            }
            if let Some(wait_secs) = download_rate_limit_wait_seconds(&response) {
                eprintln!(
                    "Download rate limited (429) for {url} — waiting {}s (retry {}/{})",
                    wait_secs, rate_limit_retries, DOWNLOAD_RATE_LIMIT_MAX_RETRIES
                );
                std::thread::sleep(Duration::from_secs(wait_secs));
                continue;
            }
            let backoff = 1000_u64 * 2_u64.pow(rate_limit_retries - 1);
            let backoff = backoff.min(30_000);
            eprintln!(
                "Download rate limited (429) for {url} — no Retry-After header, backing off {}ms (retry {}/{})",
                backoff, rate_limit_retries, DOWNLOAD_RATE_LIMIT_MAX_RETRIES
            );
            std::thread::sleep(Duration::from_millis(backoff));
            continue;
        }

        if response.status_code != 206 {
            anyhow::bail!("Server returned HTTP {} for size probe — expected 206 Partial Content", response.status_code);
        }

        let content_range = response
            .headers
            .get("content-range")
            .map(|v| v.as_str())
            .unwrap_or("");

        return total_from_content_range(content_range)
            .ok_or_else(|| anyhow::anyhow!("Server did not report file size"));
    }
}

/// Parse Content-Range header.
fn total_from_content_range(value: &str) -> Option<u64> {
    value
        .rsplit('/')
        .next()
        .and_then(|s| s.trim().parse::<u64>().ok())
        .filter(|s| *s > 0)
}

/// Trigger an update check for all or specific repositories.
pub async fn update_check(
    State(app_state): State<std::sync::Arc<super::AppState>>,
    Json(req): Json<UpdateCheckRequest>,
) -> impl IntoResponse {
    let config_manager = app_state.config_manager.lock().await;
    let token = config_manager.github_token();
    drop(config_manager);

    // If specific repo is requested, check only that one
    if let Some(repo) = req.repo {
        let result = check_single_repo(&repo, req.prerelease, token.as_deref(), &app_state).await;
        return Json(vec![result]);
    }

    // Otherwise check all installed repos
    let state_manager = app_state.state_manager.lock().await;
    let state = state_manager.get();
    let mut results = Vec::new();

    for app in state.installed.values() {
        let result = check_single_repo(&app.repo, req.prerelease, token.as_deref(), &app_state).await;
        results.push(result);
    }

    Json(results)
}

/// GitHub release response for update checking.
#[derive(Deserialize)]
struct GitHubRelease {
    tag_name: String,
    prerelease: bool,
}

/// Check a single repository for updates using the GitHub API.
async fn check_single_repo(
    repo: &str,
    prerelease: bool,
    token: Option<&str>,
    app_state: &std::sync::Arc<crate::webui::AppState>,
) -> UpdateCheckResponse {
    let url = format!("https://api.github.com/repos/{}/releases/latest", repo);

    let mut req = crate::core::registries::github_get(&url);
    if let Some(token) = token {
        req = req.with_header("Authorization", format!("Bearer {token}"));
    }

    let release = match req.send() {
        Ok(resp) if resp.status_code == 200 => match resp.json::<GitHubRelease>() {
            Ok(r) => r,
            Err(_) => return UpdateCheckResponse {
                repo: repo.to_string(),
                current_version: "unknown".to_string(),
                latest_version: "unknown".to_string(),
                update_available: false,
            },
        },
        Ok(resp) if resp.status_code == 404 => {
            return UpdateCheckResponse {
                repo: repo.to_string(),
                current_version: "unknown".to_string(),
                latest_version: "unknown".to_string(),
                update_available: false,
            };
        }
        _ => {
            return UpdateCheckResponse {
                repo: repo.to_string(),
                current_version: "unknown".to_string(),
                latest_version: "unknown".to_string(),
                update_available: false,
            };
        }
    };

    let latest = release.tag_name.trim_start_matches('v').to_string();

    // Skip prereleases unless requested
    if release.prerelease && !prerelease {
        return UpdateCheckResponse {
            repo: repo.to_string(),
            current_version: "unknown".to_string(),
            latest_version: latest,
            update_available: false,
        };
    }

    // Get current version from state
    let state_manager = app_state.state_manager.lock().await;
    let current_version = state_manager
        .get()
        .installed
        .get(repo)
        .map(|a| a.version.clone())
        .unwrap_or_else(|| "unknown".to_string());
    drop(state_manager);

    let update_available = crate::core::normalize_version(&latest)
        != crate::core::normalize_version(&current_version);

    UpdateCheckResponse {
        repo: repo.to_string(),
        current_version,
        latest_version: latest,
        update_available,
    }
}

// Update check types
#[derive(Deserialize)]
pub struct UpdateCheckRequest {
    pub repo: Option<String>,
    pub prerelease: bool,
}

#[derive(Serialize)]
pub struct UpdateCheckResponse {
    pub repo: String,
    pub current_version: String,
    pub latest_version: String,
    pub update_available: bool,
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::sync::atomic::AtomicUsize;

    #[test]
    fn dest_file_name_strips_windows_and_unix_paths() {
        assert_eq!(dest_file_name("C:\\evil\\path\\big.bin", "http://x/y"), "big.bin");
        assert_eq!(dest_file_name("/etc/passwd", "http://x/y"), "passwd");
        assert_eq!(dest_file_name("", "http://x/y/file.zip?dl=1"), "file.zip");
        assert_eq!(dest_file_name("", "http://x/"), "download");
    }

    /// Serve `body` with HTTP Range support on an ephemeral port; returns the
    /// base URL and a handle to stop. Runs on a plain std thread.
    fn serve_with_ranges(body: &[u8]) -> String {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        let body = body.to_vec();
        std::thread::spawn(move || {
            for stream in listener.incoming() {
                let mut stream = match stream { Ok(s) => s, Err(_) => break };
                let mut buf = [0u8; 8192];
                let n = stream.read(&mut buf).unwrap_or(0);
                let req = String::from_utf8_lossy(&buf[..n]).to_string();
                let range = req.lines().find(|l| l.to_ascii_lowercase().starts_with("range:"));
                let (status, start, end) = if let Some(r) = range {
                    // bytes=start-end
                    let spec = r.split(':').nth(1).unwrap().trim().trim_start_matches("bytes=");
                    let mut it = spec.splitn(2, '-');
                    let s: u64 = it.next().unwrap().parse().unwrap();
                    let e: u64 = it.next().and_then(|v| v.parse().ok()).unwrap_or(body.len() as u64 - 1).min(body.len() as u64 - 1);
                    ("206 Partial Content", s, e)
                } else {
                    ("200 OK", 0, body.len() as u64 - 1)
                };
                let chunk = &body[start as usize..=(end as usize)];
                let head = format!(
                    "HTTP/1.1 {status}\r\nContent-Length: {}\r\nContent-Range: bytes {}-{}/{}\r\nConnection: close\r\n\r\n",
                    chunk.len(), start, end, body.len()
                );
                let _ = stream.write_all(head.as_bytes());
                let _ = stream.write_all(chunk);
            }
        });
        format!("http://{addr}/file.bin")
    }

    fn new_registry() -> DownloadRegistry {
        Arc::new(Mutex::new(HashMap::new()))
    }

    #[test]
    fn download_inner_retries_on_429_then_succeeds() {
        let body = vec![7u8; 100_000]; // 100KB
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        let body = body.to_vec();
        let attempt = Arc::new(AtomicUsize::new(0));
        let attempt_clone = attempt.clone();
        let body_clone = body.clone();
        std::thread::spawn(move || {
            for stream in listener.incoming() {
                let mut stream = match stream { Ok(s) => s, Err(_) => break };
                let mut buf = [0u8; 8192];
                let _ = stream.read(&mut buf);
                let a = attempt_clone.fetch_add(1, Ordering::Relaxed);
                if a == 0 {
                    // First request: 429 rate limited
                    let head = "HTTP/1.1 429 Too Many Requests\r\nRetry-After: 0\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
                    let _ = stream.write_all(head.as_bytes());
                } else {
                    // Second request: success with full body
                    let head = format!(
                        "HTTP/1.1 206 Partial Content\r\nContent-Length: {}\r\nContent-Range: bytes 0-{}/{}\r\nConnection: close\r\n\r\n",
                        body_clone.len(), body_clone.len() - 1, body_clone.len()
                    );
                    let _ = stream.write_all(head.as_bytes());
                    let _ = stream.write_all(&body_clone);
                }
            }
        });
        let url = format!("http://{addr}/file.bin");
        let dir = tempfile::tempdir().unwrap();
        let dest = dir.path().join("file.bin");
        let part = dest.with_extension("part");
        let registry = new_registry();
        let id = "job_429".to_string();
        let cancel = AtomicBool::new(false);
        let run = DownloadRun {
            url: &url,
            token: None,
            dest: &dest,
            part_path: &part,
            registry: &registry,
            id: &id,
            cancel: &cancel,
            bandwidth_limit: None,
            overall_timeout_secs: Some(300),
            total_size: Some(body.len() as u64),
        };
        registry.lock().unwrap().insert(id.clone(), DownloadJob {
            id: id.clone(),
            url: url.clone(),
            label: "test".to_string(),
            dest: dest.display().to_string(),
            total: 0,
            downloaded: 0,
            status: "starting".to_string(),
            speed: None,
            eta: None,
            error: None,
            cancel: Arc::new(AtomicBool::new(false)),
        });
        let result = download_inner(&run);
        assert!(result.is_ok(), "download should succeed after 429 retry: {result:?}");
        assert_eq!(attempt.load(Ordering::Relaxed), 2, "should retry once after 429");
        let written = std::fs::read(&dest).unwrap();
        assert_eq!(written, body, "file content should match");
    }

    #[test]
    fn download_inner_retries_on_chunk_fetch_error_then_succeeds() {
        let body = vec![7u8; 50_000]; // 50KB
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        let body = body.to_vec();
        let attempt = Arc::new(AtomicUsize::new(0));
        let attempt_clone = attempt.clone();
        let body_clone = body.clone();
        std::thread::spawn(move || {
            for stream in listener.incoming() {
                let mut stream = match stream { Ok(s) => s, Err(_) => break };
                let mut buf = [0u8; 8192];
                let _ = stream.read(&mut buf);
                let a = attempt_clone.fetch_add(1, Ordering::Relaxed);
                if a == 0 {
                    // First request: 503 server error → retry
                    let head = "HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
                    let _ = stream.write_all(head.as_bytes());
                } else {
                    // Second request: success with full body
                    let head = format!(
                        "HTTP/1.1 206 Partial Content\r\nContent-Length: {}\r\nContent-Range: bytes 0-{}/{}\r\nConnection: close\r\n\r\n",
                        body_clone.len(), body_clone.len() - 1, body_clone.len()
                    );
                    let _ = stream.write_all(head.as_bytes());
                    let _ = stream.write_all(&body_clone);
                }
            }
        });
        let url = format!("http://{addr}/file.bin");
        let dir = tempfile::tempdir().unwrap();
        let dest = dir.path().join("file.bin");
        let part = dest.with_extension("part");
        let registry = new_registry();
        let id = "job_chunk_err".to_string();
        let cancel = AtomicBool::new(false);
        let run = DownloadRun {
            url: &url,
            token: None,
            dest: &dest,
            part_path: &part,
            registry: &registry,
            id: &id,
            cancel: &cancel,
            bandwidth_limit: None,
            overall_timeout_secs: None,
            total_size: Some(body.len() as u64),
        };
        registry.lock().unwrap().insert(id.clone(), DownloadJob {
            id: id.clone(),
            url: url.clone(),
            label: "test".to_string(),
            dest: dest.display().to_string(),
            total: 0,
            downloaded: 0,
            status: "starting".to_string(),
            speed: None,
            eta: None,
            error: None,
            cancel: Arc::new(AtomicBool::new(false)),
        });
        let result = download_inner(&run);
        assert!(result.is_ok(), "download should succeed after chunk fetch error retry: {result:?}");
        assert_eq!(attempt.load(Ordering::Relaxed), 2, "should retry once after send error");
        let written = std::fs::read(&dest).unwrap();
        assert_eq!(written, body, "file content should match");
    }

    #[test]
    fn download_inner_fetches_all_bytes_via_ranges() {
        let body: Vec<u8> = (0..700_000u32).map(|i| (i % 251) as u8).collect();
        let url = serve_with_ranges(&body);
        let dir = tempfile::tempdir().unwrap();
        let dest = dir.path().join("file.bin");
        let part = dest.with_extension("part");
        let registry = new_registry();
        let id = "job1".to_string();
        let cancel = AtomicBool::new(false);
        let run = DownloadRun {
            url: &url,
            token: None,
            dest: &dest,
            part_path: &part,
            registry: &registry,
            id: &id,
            cancel: &cancel,
            bandwidth_limit: None,
            overall_timeout_secs: None,
            total_size: Some(body.len() as u64),
        };

        download_inner(&run).unwrap();

        assert_eq!(std::fs::read(&dest).unwrap(), body);
        assert!(!part.exists());
    }

    #[test]
    fn download_inner_aborts_when_cancelled() {
        let body = vec![7u8; 5_000_000]; // larger than CHUNK_SIZE so cancel can land mid-loop
        let url = serve_with_ranges(&body);
        let dir = tempfile::tempdir().unwrap();
        let dest = dir.path().join("file.bin");
        let part = dest.with_extension("part");
        let registry = new_registry();
        let id = "job2".to_string();
        let cancel = AtomicBool::new(true); // pre-cancelled: first loop iteration bails
        let run = DownloadRun {
            url: &url,
            token: None,
            dest: &dest,
            part_path: &part,
            registry: &registry,
            id: &id,
            cancel: &cancel,
            bandwidth_limit: None,
            overall_timeout_secs: None,
            total_size: Some(body.len() as u64),
        };

        let err = download_inner(&run).unwrap_err();
        assert!(format!("{err}").contains("cancelled"));
        assert!(!dest.exists());
    }

    #[test]
    fn download_inner_times_out_with_overall_timeout() {
        let body = vec![7u8; 100_000]; // 100KB - small enough to complete fast, but timeout fires first
        let url = serve_with_ranges(&body);
        let dir = tempfile::tempdir().unwrap();
        let dest = dir.path().join("file.bin");
        let part = dest.with_extension("part");
        let registry = new_registry();
        let id = "job_timeout".to_string();
        let cancel = AtomicBool::new(false);
        let run = DownloadRun {
            url: &url,
            token: None,
            dest: &dest,
            part_path: &part,
            registry: &registry,
            id: &id,
            cancel: &cancel,
            bandwidth_limit: None,
            overall_timeout_secs: Some(0), // timeout fires before first chunk
            total_size: Some(body.len() as u64),
        };

        // Insert job into registry (normally done by run_download)
        registry.lock().unwrap().insert(id.clone(), DownloadJob {
            id: id.clone(),
            url: url.clone(),
            label: "test".to_string(),
            dest: dest.display().to_string(),
            total: 0,
            downloaded: 0,
            status: "starting".to_string(),
            speed: None,
            eta: None,
            error: None,
            cancel: Arc::new(AtomicBool::new(false)),
        });

        let err = download_inner(&run).unwrap_err();
        assert!(format!("{err}").contains("timed out"));

        // Job status should be "error" with timeout message
        let map = registry.lock().unwrap();
        let job = map.get(&id).unwrap();
        assert_eq!(job.status, "error");
        assert!(job.error.as_ref().unwrap().contains("timed out"));
    }
}
