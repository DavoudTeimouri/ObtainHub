use axum::{Json, response::IntoResponse, extract::{State, Path}};
use serde::{Serialize, Deserialize};
use anyhow::Context;
use uuid::Uuid;

/// Download info for web API.
#[derive(Serialize)]
pub struct DownloadInfo {
    pub id: String,
    pub url: String,
    pub label: String,
    pub dest: String,
    pub total_bytes: u64,
    pub downloaded_bytes: u64,
    pub status: String,
    pub speed_bps: Option<u64>,
}

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

pub async fn start_download(
    State(_app_state): State<std::sync::Arc<super::AppState>>,
    Json(req): Json<StartDownloadRequest>,
) -> impl IntoResponse {
    let _dest = std::path::PathBuf::from(&req.dest);
    let _label = req.label.unwrap_or_else(|| {
        req.url.split('/').next_back().unwrap_or("download").to_string()
    });
    
    // Create parent directory if needed
    if let Some(parent) = _dest.parent() {
        std::fs::create_dir_all(parent).ok();
    }
    
    // Probe size
    let _total_size = probe_size(&req.url, req.token.as_deref()).await.unwrap_or(0);
    
    let _download_id = Uuid::new_v4().to_string();
    
    // For now, just return the ID - actual download tracking would need a registry
    Json(StartDownloadResponse {
        id: Uuid::new_v4().to_string(),
        status: "started".to_string(),
    })
}

/// List active downloads.
pub async fn list_downloads(
    State(_app_state): State<std::sync::Arc<super::AppState>>,
) -> impl IntoResponse {
    // TODO: Track active downloads in a global registry
    Json(Vec::<DownloadInfo>::new())
}

/// Cancel a download by ID.
pub async fn cancel_download(
    State(_app_state): State<std::sync::Arc<super::AppState>>,
    Path(_id): Path<String>,
) -> impl IntoResponse {
    Json(serde_json::json!({"status": "cancelled"}))
}

/// Probe the server for file size.
async fn probe_size(url: &str, token: Option<&str>) -> anyhow::Result<u64> {
    let mut req = minreq::get(url)
        .with_header("Range", "bytes=0-0")
        .with_header("User-Agent", "ObtainHub/3.0.0");
    
    if let Some(token) = token {
        req = req.with_header("Authorization", format!("Bearer {}", token));
    }
    
    let response = req.send().context("Failed to probe size")?;
    
    if response.status_code != 206 {
        anyhow::bail!("Server does not support range requests");
    }
    
    let content_range = response
        .headers
        .get("content-range")
        .map(|v| v.as_str())
        .unwrap_or("");
    
    total_from_content_range(content_range)
        .ok_or_else(|| anyhow::anyhow!("Server did not report file size"))
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
