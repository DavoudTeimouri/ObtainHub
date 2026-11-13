use axum::{Json, response::IntoResponse, extract::State, http::StatusCode};
use serde::{Serialize, Deserialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

/// Base64 (RFC 4648) of UTF-16LE — used for PowerShell `-EncodedCommand` so
/// passwords never appear in a process command line.
fn base64_utf16le(s: &str) -> String {
    let bytes: Vec<u8> = s.encode_utf16().flat_map(|u| u.to_le_bytes()).collect();
    const TBL: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::new();
    for chunk in bytes.chunks(3) {
        let b = [chunk[0], *chunk.get(1).unwrap_or(&0), *chunk.get(2).unwrap_or(&0)];
        let n = ((b[0] as u32) << 16) | ((b[1] as u32) << 8) | b[2] as u32;
        out.push(TBL[((n >> 18) & 63) as usize] as char);
        out.push(TBL[((n >> 12) & 63) as usize] as char);
        out.push(if chunk.len() > 1 { TBL[((n >> 6) & 63) as usize] as char } else { '=' });
        out.push(if chunk.len() > 2 { TBL[(n & 63) as usize] as char } else { '=' });
    }
    out
}

/// Application info for web API.
#[derive(Serialize)]
pub struct AppInfo {
    pub repo: String,
    pub name: String,
    pub version: String,
    pub install_path: String,
    pub installed_at: String,
    pub updated_at: Option<String>,
    pub status: String,
    pub update_available: bool,
    pub latest_version: Option<String>,
}

/// List all managed applications.
///
/// Returns a JSON array of all apps tracked in state.json.
pub async fn list_apps(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
) -> impl IntoResponse {
    let mut state = app_state.state_manager.lock().await;
    state.reload().ok();
    let apps: Vec<AppInfo> = state.get().installed.values().map(|app| {
        AppInfo {
            repo: app.repo.clone(),
            name: app.repo.split('/').next_back().unwrap_or(&app.repo).to_string(),
            version: app.version.clone(),
            install_path: app.install_path.display().to_string(),
            installed_at: app.installed_at.to_rfc3339(),
            updated_at: app.updated_at.map(|dt| dt.to_rfc3339()),
            status: "Installed".to_string(),
            update_available: app.update_available,
            latest_version: app.latest_version.clone(),
        }
    }).collect();
    Json(apps)
}

/// Config info for web API.
#[derive(Serialize)]
pub struct ConfigInfo {
    pub install_dir: String,
    pub download_dir: String,
    pub shim_dir: String,
    pub parallel_downloads: usize,
    pub timeout_seconds: u64,
    pub update_check_interval_hours: u64,
    pub auto_cleanup: bool,
    pub verify_checksums: bool,
    pub download_bandwidth_limit: Option<u64>,
    pub proxy: Option<String>,
    pub http_retries: u32,
    pub http_retry_delay_ms: u64,
    pub http_retry_backoff: f64,
    pub schedule_enabled: bool,
    pub schedule_interval_hours: u64,
    pub schedule_notify_on_update: bool,
    pub schedule_run_on_startup: bool,
    pub groups: Vec<String>,
    pub token_source: String,
    /// Whether a GitHub token is configured (value itself is never exposed).
    pub has_token: bool,
    /// Whether the WebUI was started with `--auth` (drives UI field locking).
    pub auth_required: bool,
}

/// Get current configuration (token masked).
///
/// Returns the current configuration with sensitive values masked.
pub async fn get_config(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
) -> impl IntoResponse {
    let config_manager = app_state.config_manager.lock().await;
    let config = config_manager.get();
    let token_source = config_manager.token_source().to_string();

    Json(ConfigInfo {
        install_dir: config.install_dir.display().to_string(),
        download_dir: config.download_dir.display().to_string(),
        shim_dir: config.shim_dir.display().to_string(),
        parallel_downloads: config.parallel_downloads,
        timeout_seconds: config.timeout_seconds,
        update_check_interval_hours: config.update_check_interval_hours,
        auto_cleanup: config.auto_cleanup,
        verify_checksums: config.verify_checksums,
        download_bandwidth_limit: config.download_bandwidth_limit,
        proxy: config.proxy.clone(),
        http_retries: config.http_retries,
        http_retry_delay_ms: config.http_retry_delay_ms,
        http_retry_backoff: config.http_retry_backoff,
        schedule_enabled: config.schedule.enabled,
        schedule_interval_hours: config.schedule.interval_hours,
        schedule_notify_on_update: config.schedule.notify_on_update,
        schedule_run_on_startup: config.schedule.run_on_startup,
        groups: config.groups.keys().cloned().collect(),
        token_source,
        has_token: config_manager.github_token().is_some(),
        // UI locks until sign-in only when --auth is set. A configured GitHub
        // token is an alternative Bearer credential, not a UI lock.
        auth_required: app_state.auth_enabled,
    })
}

/// Partial config update request. All fields optional — only provided fields
/// are changed.
#[derive(Deserialize, Default)]
pub struct ConfigUpdate {
    pub install_dir: Option<String>,
    pub download_dir: Option<String>,
    pub shim_dir: Option<String>,
    pub parallel_downloads: Option<usize>,
    pub timeout_seconds: Option<u64>,
    pub update_check_interval_hours: Option<u64>,
    pub auto_cleanup: Option<bool>,
    pub verify_checksums: Option<bool>,
    pub proxy: Option<Option<String>>,
    pub download_bandwidth_limit: Option<Option<u64>>,
    pub http_retries: Option<u32>,
    pub http_retry_delay_ms: Option<u64>,
    pub http_retry_backoff: Option<f64>,
    pub schedule_enabled: Option<bool>,
    pub schedule_interval_hours: Option<u64>,
    pub schedule_notify_on_update: Option<bool>,
    pub schedule_run_on_startup: Option<bool>,
}

/// Update configuration values. Requires auth when --auth is set.
pub async fn put_config(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
    Json(payload): Json<ConfigUpdate>,
) -> impl IntoResponse {
    let mut config_manager = app_state.config_manager.lock().await;
    let config = config_manager.get_mut();

    if let Some(v) = payload.install_dir {
        config.install_dir = std::path::PathBuf::from(v);
    }
    if let Some(v) = payload.download_dir {
        config.download_dir = std::path::PathBuf::from(v);
    }
    if let Some(v) = payload.shim_dir {
        config.shim_dir = std::path::PathBuf::from(v);
    }
    if let Some(v) = payload.parallel_downloads {
        config.parallel_downloads = v;
    }
    if let Some(v) = payload.timeout_seconds {
        config.timeout_seconds = v;
    }
    if let Some(v) = payload.update_check_interval_hours {
        config.update_check_interval_hours = v;
    }
    if let Some(v) = payload.auto_cleanup {
        config.auto_cleanup = v;
    }
    if let Some(v) = payload.verify_checksums {
        config.verify_checksums = v;
    }
    if let Some(v) = payload.proxy {
        config.proxy = v;
    }
    if let Some(v) = payload.download_bandwidth_limit {
        config.download_bandwidth_limit = v;
    }
    if let Some(v) = payload.http_retries {
        config.http_retries = v;
    }
    if let Some(v) = payload.http_retry_delay_ms {
        config.http_retry_delay_ms = v;
    }
    if let Some(v) = payload.http_retry_backoff {
        config.http_retry_backoff = v;
    }
    if let Some(v) = payload.schedule_enabled {
        config.schedule.enabled = v;
    }
    if let Some(v) = payload.schedule_interval_hours {
        config.schedule.interval_hours = v;
    }
    if let Some(v) = payload.schedule_notify_on_update {
        config.schedule.notify_on_update = v;
    }
    if let Some(v) = payload.schedule_run_on_startup {
        config.schedule.run_on_startup = v;
    }

    if let Err(e) = config_manager.save() {
        return (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({
            "error": format!("Failed to save config: {e}")
        }))).into_response();
    }

    (StatusCode::OK, Json(serde_json::json!({"status": "updated"}))).into_response()
}

/// Set the GitHub token. Stored in OS credential store when available,
/// otherwise in config.toml. Requires auth when --auth is set.
#[derive(Deserialize)]
pub struct TokenSet {
    pub token: String,
}

pub async fn post_github_token(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
    Json(payload): Json<TokenSet>,
) -> impl IntoResponse {
    let token = payload.token;
    let mut config_manager = app_state.config_manager.lock().await;

    let stored = crate::core::credentials::store_token(&token).unwrap_or(false);
    if !stored {
        config_manager.get_mut().github_token = Some(token);
        if let Err(e) = config_manager.save() {
            return (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({
                "error": format!("Failed to save token: {e}")
            }))).into_response();
        }
    }

    (StatusCode::OK, Json(serde_json::json!({
        "status": "token_set",
        "source": if stored { "credential_store" } else { "config_file" }
    }))).into_response()
}

/// Remove the GitHub token. Requires auth when --auth is set.
pub async fn delete_github_token(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
) -> impl IntoResponse {
    let _removed = crate::core::credentials::delete_token();
    let mut config_manager = app_state.config_manager.lock().await;
    config_manager.get_mut().github_token = None;
    let _ = config_manager.save();

    (StatusCode::OK, Json(serde_json::json!({"status": "token_removed"}))).into_response()
}

/// Add an app/repo to management. Requires auth when --auth is set.
#[derive(Deserialize)]
pub struct AppAdd {
    pub repo: String,
    #[serde(default = "default_add_type")]
    #[allow(dead_code)]
    pub add_type: String,
    #[serde(default)]
    pub install_path: Option<String>,
    #[serde(default)]
    pub version: Option<String>,
}

fn default_add_type() -> String { "github".to_string() }

/// Body for scanning a folder for executables.
#[derive(Deserialize)]
pub struct ScanFolderBody {
    pub path: String,
}

/// Scan a folder for executable files. Returns a list of {name, path}.
pub async fn scan_folder(
    Json(body): Json<ScanFolderBody>,
) -> impl IntoResponse {
    let folder_path = PathBuf::from(&body.path);
    if !folder_path.exists() || !folder_path.is_dir() {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"error": "Not a valid directory"})),
        )
            .into_response();
    }

    let mut executables: Vec<serde_json::Value> = Vec::new();
    for entry in WalkDir::new(&folder_path).into_iter().filter_map(|e| e.ok()) {
        let path = entry.path();
        if !path.is_file() {
            continue;
        }
        let is_exe = path.extension().map(|e| e == "exe").unwrap_or(false);
        if !is_exe {
            continue;
        }
        let name = path
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string();
        executables.push(serde_json::json!({
            "name": name,
            "path": path.display().to_string(),
        }));
    }
    Json(executables).into_response()
}

/// Add an app/repo to management. Requires auth when --auth is set.
pub async fn post_app(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
    Json(payload): Json<AppAdd>,
) -> impl IntoResponse {
    let repo = payload.repo;
    let add_type = payload.add_type.clone();
    let install_path = payload.install_path.clone();
    let version = payload.version.clone();
    let mut state_manager = app_state.state_manager.lock().await;

    // Check if already managed
    if state_manager.get_installed(&repo).is_some() {
        return (StatusCode::CONFLICT, Json(serde_json::json!({
            "error": format!("{repo} is already managed")
        }))).into_response();
    }

    // For folder adds, repo is the exe name and install_path is the exe path.
    // Use file time instead of "just now", skip registry detection (no registry entry for portable apps).
    if add_type == "folder" {
        let install_dir = install_path
            .map(|p| std::path::PathBuf::from(p))
            .unwrap_or_default();
        let installed_at = if install_dir.exists() {
            crate::commands::add::file_time(&install_dir)
        } else {
            chrono::Utc::now()
        };
        let installed = crate::core::state::InstalledRepo {
            repo: repo.clone(),
            version: version.unwrap_or_else(|| "unknown".to_string()),
            install_path: install_dir,
            installed_at,
            updated_at: None,
            checksum: None,
            metadata: serde_json::Value::Null,
            previous_version: None,
            previous_install_path: None,
            dependencies: Vec::new(),
            is_dependency: false,
            uninstaller: None,
            ..Default::default()
        };
        state_manager.add_installed(installed);

        if let Err(e) = state_manager.save() {
            return (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({
                "error": format!("Failed to save state: {e}")
            }))).into_response();
        }

        return (StatusCode::OK, Json(serde_json::json!({"status": "added", "repo": repo})))
            .into_response();
    }

    // Add as installed with placeholder data - user will need to install via CLI
    let installed = crate::core::state::InstalledRepo {
        repo: repo.clone(),
        version: "0.0.0".to_string(),
        install_path: std::path::PathBuf::new(),
        installed_at: chrono::Utc::now(),
        updated_at: None,
        checksum: None,
        metadata: serde_json::Value::Null,
        previous_version: None,
        previous_install_path: None,
        dependencies: Vec::new(),
        is_dependency: false,
        uninstaller: None,
        ..Default::default()
    };
    state_manager.add_installed(installed);

    if let Err(e) = state_manager.save() {
        return (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({
            "error": format!("Failed to save state: {e}")
        }))).into_response();
    }

    // Detect installed software from the Windows uninstall registry so the
    // WebUI shows the real version and install path instead of placeholders.
    // Best-effort: if no registry entry matches, we keep the placeholder data.
    let detected = crate::core::winreg::scan_uninstall_entries()
        .iter()
        .find_map(|e| {
            crate::core::winreg::find_entry_for_repo(
                std::slice::from_ref(e),
                &repo,
                None,
            ).map(|found| (e.clone(), found.clone()))
        });
    if let Some((entry, found)) = detected {
        let mut corrected = state_manager.get_installed(&repo).cloned().unwrap_or_default();
        corrected.version = if found.display_version.is_empty() {
            corrected.version
        } else {
            found.display_version.clone()
        };
        corrected.install_path = found.install_dir().unwrap_or_default();
        corrected.uninstaller = Some(entry.uninstall_string.clone());
        state_manager.add_installed(corrected);
        let _ = state_manager.save();
    }

    (StatusCode::OK, Json(serde_json::json!({"status": "added", "repo": repo})))
        .into_response()
}

/// Scan for unmanaged installed software and find candidate GitHub repos.
/// Returns a list of CandidateInfo — one per unmanaged app with candidate repos.
pub async fn candidates(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
) -> impl IntoResponse {
    let cm = app_state.config_manager.lock().await;
    let rc = crate::utils::retry::RetryConfig::from_config(&cm);
    let sm = app_state.state_manager.lock().await;
    let result = crate::commands::check::scan_candidates(&cm, &sm, &rc).await;
    match result {
        Ok(candidates) => (StatusCode::OK, Json(candidates)).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({
            "error": format!("{e:#}")
        }))).into_response(),
    }
}

/// Remove an app/repo from management. Requires auth when --auth is set.
pub async fn delete_app(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
    axum::extract::Path(repo): axum::extract::Path<String>,
) -> impl IntoResponse {
    // Catch-all path includes a leading '/', strip it.
    let repo = repo.strip_prefix('/').unwrap_or(&repo);
    let mut state_manager = app_state.state_manager.lock().await;
    let removed = state_manager.remove_installed(repo);

    if removed.is_none() {
        return (StatusCode::NOT_FOUND, Json(serde_json::json!({
            "error": format!("{repo} is not managed")
        }))).into_response();
    }

    if let Err(e) = state_manager.save() {
        return (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({
            "error": format!("Failed to save state: {e}")
        }))).into_response();
    }

    (StatusCode::OK, Json(serde_json::json!({"status": "removed", "repo": repo}))).into_response()
}

/// Add a manifest source. Requires auth when --auth is set.
#[derive(Deserialize)]
pub struct SourceAdd {
    pub name: String,
    pub url: String,
}

pub async fn post_source(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
    Json(payload): Json<SourceAdd>,
) -> impl IntoResponse {
    let mut config_manager = app_state.config_manager.lock().await;
    let config = config_manager.get_mut();

    // Check for duplicate name
    if config.manifest_sources.iter().any(|s| s.name == payload.name) {
        return (StatusCode::CONFLICT, Json(serde_json::json!({
            "error": format!("Source '{}' already exists", payload.name)
        }))).into_response();
    }

    let src = crate::core::config::ManifestSource {
        name: payload.name.clone(),
        url: payload.url.clone(),
        enabled: true,
        headers: HashMap::new(),
        src_type: "github".to_string(),
        hooks: HashMap::new(),
        priority: None,
        auto_sync: false,
        registry_type: "github".to_string(),
        package_name: None,
    };
    config.manifest_sources.push(src);

    if let Err(e) = config_manager.save() {
        return (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({
            "error": format!("Failed to save config: {e}")
        }))).into_response();
    }

    (StatusCode::OK, Json(serde_json::json!({"status": "added", "name": payload.name}))).into_response()
}

/// Remove a manifest source. Requires auth when --auth is set.
pub async fn delete_source(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
    axum::extract::Path(name): axum::extract::Path<String>,
) -> impl IntoResponse {
    // Catch-all path includes a leading '/', strip it.
    let name = name.strip_prefix('/').unwrap_or(&name);
    let mut config_manager = app_state.config_manager.lock().await;
    let config = config_manager.get_mut();
    let len_before = config.manifest_sources.len();
    config.manifest_sources.retain(|s| s.name != name);

    if config.manifest_sources.len() == len_before {
        return (StatusCode::NOT_FOUND, Json(serde_json::json!({
            "error": format!("Source '{name}' not found")
        }))).into_response();
    }

    if let Err(e) = config_manager.save() {
        return (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({
            "error": format!("Failed to save config: {e}")
        }))).into_response();
    }

    (StatusCode::OK, Json(serde_json::json!({"status": "removed", "name": name}))).into_response()
}

/// List manifest sources.
pub async fn list_sources(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
) -> impl IntoResponse {
    let config_manager = app_state.config_manager.lock().await;
    let config = config_manager.get();
    let sources: Vec<serde_json::Value> = config.manifest_sources.iter().map(|s| {
        serde_json::json!({
            "name": s.name,
            "url": s.url,
            "enabled": s.enabled,
            "src_type": s.src_type,
            "registry_type": s.registry_type,
            "package_name": s.package_name,
        })
    }).collect();
    Json(sources)
}

/// Export the full state as JSON (same shape as `ohub state export`).
pub async fn export_state(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
) -> impl IntoResponse {
    let state_manager = app_state.state_manager.lock().await;
    match serde_json::to_value(state_manager.get()) {
        Ok(v) => (StatusCode::OK, Json(v)).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({"error": e.to_string()}))).into_response(),
    }
}

/// Tail of the schedule log (`<data_dir>/obtainhub/schedule.log`).
pub async fn tail_logs(
    State(_app_state): State<std::sync::Arc<crate::webui::AppState>>,
    axum::extract::Query(q): axum::extract::Query<std::collections::HashMap<String, String>>,
) -> impl IntoResponse {
    let lines: usize = q.get("lines").and_then(|v| v.parse().ok()).unwrap_or(100).min(2000);
    let mut path = dirs::data_dir().unwrap_or_else(std::env::temp_dir);
    path.push("obtainhub");
    path.push("schedule.log");
    match std::fs::read_to_string(&path) {
        Ok(content) => {
            let tail: Vec<String> = content.lines().rev().take(lines).collect::<Vec<_>>().into_iter().rev().map(|s| s.to_string()).collect();
            Json(serde_json::json!({"path": path.display().to_string(), "lines": tail}))
        }
        Err(_) => Json(serde_json::json!({"path": path.display().to_string(), "lines": Vec::<String>::new()}))
    }
}

// ---------- GitHub search ----------

#[derive(Deserialize)]
pub struct SearchQuery {
    pub q: String,
    #[serde(default = "default_search_limit")]
    pub limit: usize,
    #[serde(default)]
    pub min_stars: u32,
    #[serde(default)]
    pub active_only: bool,
}

fn default_search_limit() -> usize {
    20
}

#[derive(Serialize, Deserialize)]
pub struct RepoItem {
    pub full_name: String,
    pub description: Option<String>,
    pub stargazers_count: u32,
    pub language: Option<String>,
    pub updated_at: String,
    pub published_at: Option<String>,
    pub html_url: String,
}

/// Search GitHub repositories. Requires auth when --auth is set.
pub async fn search_repos(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
    axum::extract::Query(query): axum::extract::Query<SearchQuery>,
) -> impl IntoResponse {
    let (token, timeout) = {
        let cm = app_state.config_manager.lock().await;
        (cm.github_token(), cm.get().timeout_seconds)
    };

    let mut url = format!(
        "https://api.github.com/search/repositories?q={}&per_page={}&page=1&sort=best-match&order=desc",
        urlencoding::encode(&query.q),
        query.limit.clamp(1, 50)
    );
    if query.min_stars > 0 {
        url.push_str(&format!("+stars:>={}", query.min_stars));
    }
    if query.active_only {
        let year_ago = chrono::Utc::now() - chrono::Duration::days(365);
        url.push_str(&format!("+pushed:>={}", year_ago.format("%Y-%m-%d")));
    }

    let token_clone = token;
    let mut req = minreq::get(&url).with_header("User-Agent", crate::core::USER_AGENT);
    if let Some(t) = &token_clone {
        req = req.with_header("Authorization", format!("Bearer {t}"));
    }

    #[derive(Deserialize)]
    struct SearchResponse {
        items: Vec<RepoItem>,
    }

    match req.with_timeout(timeout).send() {
        Ok(resp) if resp.status_code == 200 => match resp.json::<SearchResponse>() {
            Ok(r) => {
                // Fetch published_at from releases API for each item
                // (search API returns pushed_at = last commit, not release publish time)
                let mut items_with_published = Vec::new();
                for item in r.items {
                    let published_at =
                        fetch_latest_release_published_at(&item.full_name, token_clone.as_deref(), timeout).await;
                    items_with_published.push(RepoItem {
                        full_name: item.full_name,
                        description: item.description,
                        stargazers_count: item.stargazers_count,
                        language: item.language,
                        updated_at: item.updated_at,
                        published_at: Some(published_at),
                        html_url: item.html_url,
                    });
                }
                Json(items_with_published).into_response()
            }
            Err(e) => (StatusCode::BAD_GATEWAY, Json(serde_json::json!({"error": format!("Bad GitHub response: {e}")}))).into_response(),
        },
        Ok(resp) if resp.status_code == 403 => (StatusCode::TOO_MANY_REQUESTS, Json(serde_json::json!({"error": "GitHub API rate limited. Add a GitHub token in Configuration → GitHub Token."}))).into_response(),
        Ok(resp) => (StatusCode::BAD_GATEWAY, Json(serde_json::json!({"error": format!("GitHub API returned {}", resp.status_code)}))).into_response(),
        Err(e) => (StatusCode::BAD_GATEWAY, Json(serde_json::json!({"error": format!("Search failed: {e}")}))).into_response(),
    }
}

/// Fetch the `published_at` timestamp from the latest release of a GitHub repo.
/// Falls back to the search result's `updated_at` if the release fetch fails.
async fn fetch_latest_release_published_at(
    full_name: &str,
    token: Option<&str>,
    timeout: u64,
) -> String {
    let url = format!("https://api.github.com/repos/{}/releases/latest", full_name);
    let token_clone = token;
    let mut req = minreq::get(&url).with_header("User-Agent", crate::core::USER_AGENT);
    if let Some(t) = &token_clone {
        req = req.with_header("Authorization", format!("Bearer {t}"));
    }
    match req.with_timeout(timeout).send() {
        Ok(resp) if resp.status_code == 200 => {
            #[derive(Deserialize)]
            struct Release {
                published_at: String,
            }
            match resp.json::<Release>() {
                Ok(r) => r.published_at,
                Err(_) => String::new(),
            }
        }
        _ => String::new(),
    }
}

/// Open a native folder picker dialog and return the selected path.
/// Used for Install Dir / Download Dir / Shim Dir "Open and select" buttons.
/// Windows only.
pub async fn browse_folder(
    State(_app_state): State<std::sync::Arc<crate::webui::AppState>>,
    Json(_body): Json<serde_json::Value>,
) -> impl IntoResponse {
    if !cfg!(windows) {
        return (
            StatusCode::NOT_IMPLEMENTED,
            Json(serde_json::json!({"error": "folder picker available on Windows only"})),
        )
            .into_response();
    }
    let script = r#"
Add-Type -AssemblyName System.Windows.Forms
$fb = New-Object System.Windows.Forms.FolderBrowserDialog
$fb.Description = "Select a folder"
$fb.ShowNewFolderButton = $true
$result = $fb.ShowDialog()
if ($result -eq [System.Windows.Forms.DialogResult]::OK) { $fb.SelectedPath } else { exit 1 }
"#;
    match run_ps(script) {
        PsResult::Ok(path) => {
            if path.is_empty() {
                (StatusCode::BAD_REQUEST, Json(serde_json::json!({"error": "No folder selected"})))
                    .into_response()
            } else {
                (StatusCode::OK, Json(serde_json::json!({"path": path}))).into_response()
            }
        }
        PsResult::Rejected => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({"error": "Folder picker was cancelled or failed"})),
        )
            .into_response(),
        PsResult::NotFound => (
            StatusCode::NOT_IMPLEMENTED,
            Json(serde_json::json!({"error": "PowerShell not available"})),
        )
            .into_response(),
    }
}

// ---------- App actions (same engines as the CLI commands) ----------

#[derive(Deserialize)]
pub struct AppAction {
    #[serde(default)]
    pub repo: String,
    #[serde(default)]
    pub force: bool,
    #[serde(default)]
    pub purge: bool,
    #[serde(default)]
    pub prerelease: bool,
    #[serde(default)]
    pub candidates: bool,
    #[serde(default)]
    pub reset: bool,
    /// Install path detected from Windows registry scan (Detect Installed → Add)
    #[serde(default)]
    pub install_path: Option<String>,
    /// Version detected from Windows registry scan (Detect Installed → Add)
    #[serde(default)]
    pub version: Option<String>,
    /// Run uninstaller interactively (user sees the UI, can cancel)
    #[serde(default)]
    pub interactive: bool,
    /// Specific asset name to install (when release has multiple assets)
    #[serde(default)]
    pub asset: Option<String>,
}

fn action_result(result: anyhow::Result<()>) -> axum::response::Response {
    match result {
        Ok(()) => (StatusCode::OK, Json(serde_json::json!({"status": "ok"}))).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({"error": format!("{e:#}")}))).into_response(),
    }
}

/// Install a repository (same engine as `ohub install`). Protected.
pub async fn install_app(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
    Json(body): Json<AppAction>,
) -> impl IntoResponse {
    let args = crate::cli::InstallArgs {
        repo: body.repo,
        version: body.version,
        tag: None,
        prerelease: body.prerelease,
        force: body.force,
        download_only: false,
        skip_deps: false,
        timeout: None,
        arch: crate::cli::Arch::Auto,
        yes: true,
        reset: false,
        interactive: false,
        dry_run: false,
        file: None,
        url: None,
        asset: body.asset,
        dependencies: Vec::new(),
    };
    let result = {
        let cm = app_state.config_manager.lock().await;
        let rc = crate::utils::retry::RetryConfig::from_config(&cm);
        let mut sm = app_state.state_manager.lock().await;
        let custom_path = body.install_path.as_deref().map(std::path::PathBuf::from);
        crate::commands::install::execute(args, &cm, &mut sm, &rc, custom_path.as_deref()).await
    };
    action_result(result)
}

/// List available release assets for a repo, so the user can pick one to install.
/// Query: ?repo=owner/repo
pub async fn list_assets(
    axum::extract::Query(params): axum::extract::Query<std::collections::HashMap<String, String>>,
) -> impl IntoResponse {
    let repo = match params.get("repo") {
        Some(r) if !r.is_empty() => r.clone(),
        _ => {
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({"error": "repo query parameter required"})),
            )
                .into_response()
        }
    };
    if !cfg!(windows) {
        return (
            StatusCode::NOT_IMPLEMENTED,
            Json(serde_json::json!({"error": "asset listing available on Windows only"})),
        )
            .into_response();
    }
    let token = None;
    let registry = crate::core::registries::Registry::GitHub(
        crate::core::registries::GitHubRegistry::new(),
    );
    match crate::core::registries::Registry::fetch_latest_release(&registry, &repo, token).await {
        Ok(release) => {
            let assets: Vec<serde_json::Value> = release
                .assets
                .iter()
                .map(|a| {
                    serde_json::json!({
                        "name": a.name,
                        "url": a.browser_download_url,
                        "size": a.size,
                        "content_type": a.content_type,
                    })
                })
                .collect();
            (StatusCode::OK, Json(serde_json::json!({"repo": repo, "assets": assets}))).into_response()
        }
        Err(e) => (
            StatusCode::BAD_GATEWAY,
            Json(serde_json::json!({"error": format!("Failed to fetch release for {repo}: {e}")})),
        )
            .into_response(),
    }
}

/// Uninstall a repository (same engine as `ohub uninstall`). Protected.
pub async fn uninstall_app(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
    Json(body): Json<AppAction>,
) -> impl IntoResponse {
    let args = crate::cli::UninstallArgs {
        repo: body.repo,
        purge: body.purge,
        yes: true,
        force: body.force,
        interactive: body.interactive,
    };
    let result = {
        let mut cm = app_state.config_manager.lock().await;
        let mut sm = app_state.state_manager.lock().await;
        crate::commands::uninstall::execute(args, &mut cm, &mut sm).await
    };
    action_result(result)
}

/// Update a repository (same engine as `ohub update <repo>`). Protected.
pub async fn update_app(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
    Json(body): Json<AppAction>,
) -> impl IntoResponse {
    let args = crate::cli::UpdateArgs {
        repo: Some(body.repo),
        prerelease: body.prerelease,
        dry_run: false,
        force: body.force,
        skip_deps: false,
        timeout: None,
        arch: crate::cli::Arch::Auto,
        yes: true,
        reset: false,
        interactive: false,
        notes: false,
        quiet: true,
        log: None,
    };
    let result = {
        let cm = app_state.config_manager.lock().await;
        let rc = crate::utils::retry::RetryConfig::from_config(&cm);
        let mut sm = app_state.state_manager.lock().await;
        crate::commands::update::execute(args, &cm, &mut sm, &rc).await
    };
    action_result(result)
}

/// Check one repository for updates (same engine as `ohub check <repo>`).
/// When `repo` is empty, checks all managed apps. Protected.
pub async fn check_app(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
    Json(body): Json<AppAction>,
) -> impl IntoResponse {
    let repo = if body.repo.is_empty() { None } else { Some(body.repo.clone()) };
    let args = crate::cli::CheckArgs {
        repo,
        outdated_only: false,
        prerelease: body.prerelease,
        yes: true,
        all: body.candidates,
        candidates: body.candidates,
        reset: body.reset,
        arch: crate::cli::Arch::Auto,
        timeout: None,
        notes: false,
        force: false,
        dry_run: false,
        quiet: true,
        log: None,
    };
    let result = {
        let cm = app_state.config_manager.lock().await;
        let mut sm = app_state.state_manager.lock().await;
        crate::commands::check::execute(args, &cm, &mut sm).await
    };
    action_result(result)
}

// ---------- Login (Windows admin credentials) ----------

#[derive(Deserialize)]
pub struct LoginBody {
    pub username: Option<String>,
    pub password: Option<String>,
    /// Sign in as the Windows account running the ohub process (must be admin).
    pub use_current_user: Option<bool>,
}

/// Insert a session token and return it.
fn issue_session(app_state: &std::sync::Arc<crate::webui::AppState>) -> String {
    let token = uuid::Uuid::new_v4().to_string();
    app_state.sessions.lock().unwrap().insert(token.clone());
    token
}

/// Result of running a PowerShell sign-in script.
enum PsResult {
    Ok(String),      // script succeeded, stdout is the user name
    Rejected,        // shell ran but script exited non-zero (bad creds / not admin)
    NotFound,        // neither powershell nor pwsh exists on this machine
}

/// Run an encoded PowerShell sign-in script.
/// Tries the full path to powershell.exe (from `find_powershell`) then `pwsh`.
fn run_ps(script: &str) -> PsResult {
    let encoded = base64_utf16le(script);
    for shell in [crate::commands::self_update::find_powershell(), "pwsh".to_string()] {
        match std::process::Command::new(&shell)
            .args(["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", &encoded])
            .output()
        {
            Ok(out) if out.status.success() => {
                return PsResult::Ok(String::from_utf8_lossy(&out.stdout).trim().to_string())
            }
            Ok(_) => return PsResult::Rejected,   // shell exists, script rejected
            Err(_) => continue,                    // shell not found, try next
        }
    }
    PsResult::NotFound
}

/// Sign in with a Windows admin account on this machine.
///
/// Public route (it IS the login). Two modes:
/// - `{username, password}`: validated against the local SAM via PowerShell
///   `PrincipalContext.ValidateCredentials` (encoded command, password never
///   in a process list).
/// - `{use_current_user: true}`: no password needed; the account running the
///   ohub process must be a local administrator.
///
/// Both issue a session token accepted by the auth middleware.
/// Windows only; elsewhere returns 501.
pub async fn login(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
    Json(body): Json<LoginBody>,
) -> impl IntoResponse {
    if !cfg!(windows) {
        return (StatusCode::NOT_IMPLEMENTED, Json(serde_json::json!({
            "error": "Windows admin sign-in is available on Windows only. Use a Bearer token instead."
        }))).into_response();
    }
    let verified_user = if body.use_current_user == Some(true) {
        let script = "$wi = [System.Security.Principal.WindowsIdentity]::GetCurrent(); $wp = New-Object System.Security.Principal.WindowsPrincipal($wi); if ($wp.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) { $wi.Name; exit 0 } else { exit 1 }";
        match run_ps(script) {
            PsResult::Ok(name) => Some(name),
            PsResult::Rejected => return (StatusCode::FORBIDDEN, Json(serde_json::json!({"error": "Current process is not running as administrator. Right-click ohub and run as administrator, or sign in with a Windows admin username/password below."}))).into_response(),
            PsResult::NotFound => return (StatusCode::NOT_IMPLEMENTED, Json(serde_json::json!({"error": "PowerShell is not available on this machine. Use a GitHub token instead (Sign in → Use GitHub token)."}))).into_response(),
        }
    } else {
        let username = body.username.unwrap_or_default();
        let password = body.password.unwrap_or_default();
        if username.is_empty() || password.is_empty() {
            return (StatusCode::BAD_REQUEST, Json(serde_json::json!({
                "error": "Provide username+password or use_current_user"
            }))).into_response();
        }
        let script = format!(
            "$ctx = New-Object System.DirectoryServices.AccountManagement.PrincipalContext([System.DirectoryServices.AccountManagement.ContextType]::Machine); if ($ctx.ValidateCredentials('{u}', '{p}')) {{ exit 0 }} else {{ exit 1 }}",
            u = username.replace('\'', "''"),
            p = password.replace('\'', "''")
        );
        match run_ps(&script) {
            PsResult::Ok(_) => Some(username),
            PsResult::Rejected => return (StatusCode::UNAUTHORIZED, Json(serde_json::json!({"error": "Invalid Windows username or password"}))).into_response(),
            PsResult::NotFound => return (StatusCode::NOT_IMPLEMENTED, Json(serde_json::json!({"error": "PowerShell is not available on this machine. Use a GitHub token instead (Sign in → Use GitHub token)."}))).into_response(),
        }
    };
    match verified_user {
        Some(user) => {
            let token = issue_session(&app_state);
            (StatusCode::OK, Json(serde_json::json!({"token": token, "user": user}))).into_response()
        }
        None => (StatusCode::UNAUTHORIZED, Json(serde_json::json!({
            "error": "Invalid Windows credentials or current user is not an administrator"
        }))).into_response(),
    }
}

// ---------- Doctor ----------

/// Diagnose the ObtainHub environment and configuration. Public.
pub async fn doctor(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
) -> impl IntoResponse {
    let config = app_state.config_manager.lock().await;
    let cfg = config.get();
    let info = serde_json::json!({
        "version": env!("CARGO_PKG_VERSION"),
        "os": std::env::consts::OS,
        "arch": std::env::consts::ARCH,
        "install_dir": cfg.install_dir.display().to_string(),
        "download_dir": cfg.download_dir.display().to_string(),
        "shim_dir": cfg.shim_dir.display().to_string(),
        "github_token_configured": config.github_token().is_some(),
        "token_source": config.token_source().to_string(),
        "schedule_enabled": cfg.schedule.enabled,
        "schedule_interval_hours": cfg.schedule.interval_hours,
        "parallel_downloads": cfg.parallel_downloads,
        "timeout_seconds": cfg.timeout_seconds,
        "verify_checksums": cfg.verify_checksums,
        "auto_cleanup": cfg.auto_cleanup,
    });
    Json(info)
}

// ---------- Version ----------

/// Return the ObtainHub CLI version. Public.
pub async fn version() -> impl IntoResponse {
    Json(serde_json::json!({
        "version": env!("CARGO_PKG_VERSION"),
    }))
}

// ---------- Help ----------

/// Full `ohub --help` text plus WebUI feature explanations. Public.
pub async fn help_text() -> impl IntoResponse {
    use clap::CommandFactory;
    let cli_help = crate::cli::Cli::command().render_long_help().to_string();
    let webui_help = r#"

================================================================================
ObtainHub WebUI — feature guide
================================================================================

Pages:
  Dashboard   — Overview: app count, stats, recent activity.
  Apps        — List/manage installed apps; search GitHub and install new ones.
               • Installed tab — Check/Update/Uninstall/Remove per app.
               • Find & Install — Search GitHub repos, see last release time,
                 install status badge (Installed / –), Install or Manage button.
               • Sources — Manage package sources (URLs to search).
  Config      — All config values editable (Install Dir, Proxy, Timeouts,
                Schedule, etc.). Click Save Changes to PUT /config.
                GitHub token section — add/remove token for authenticated
                GitHub API access (higher rate limits, private repos).
                Read-only info: Groups, Token Source.
  Downloads   — Active and completed downloads with progress bars, speed, ETA.
  Help        — This page.
  Doctor      — System diagnosis (powershell, pwsh, network, paths).
  State Export— Download full state.json backup.
  Logs        — Server-side log tail.

Buttons that require authentication (when --auth or GitHub token set):
  Check, Update, Uninstall, Remove — require a GitHub token.
  Install from search — no token required.

Loading / concurrency protection:
  A global loading overlay appears while any request is in flight.
  All action buttons are disabled during a request to prevent duplicate
  concurrent submissions.

Single instance:
  Running "ohub webui" a second time detects the running instance,
  reports its PID, and opens the existing WebUI in the browser instead
  of starting a duplicate server.

CLI commands available in WebUI:
  ohub search, ohub list, ohub check, ohub update, ohub install,
  ohub uninstall, ohub remove, ohub add, ohub config, ohub doctor,
  ohub self-update, ohub rollback, ohub source, ohub shim, ohub state.

Add to management types:
  github  — GitHub repository (owner/repo)
  zip     — Direct ZIP URL download
  folder  — Local folder (creates a shim wrapper)
"#;
    let full = format!("{}\n{}", cli_help, webui_help);
    ([(axum::http::header::CONTENT_TYPE, "text/plain; charset=utf-8")], full)
}