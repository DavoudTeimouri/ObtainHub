use axum::{Json, response::IntoResponse, extract::State};
use serde::Serialize;

/// Health check endpoint.
///
/// Returns basic server status for monitoring.
#[derive(Serialize)]
pub struct HealthResponse {
    pub status: &'static str,
    pub version: &'static str,
    pub service: &'static str,
}

pub async fn health() -> impl IntoResponse {
    Json(HealthResponse {
        status: "ok",
        version: env!("CARGO_PKG_VERSION"),
        service: "ohub-webui",
    })
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
}

/// List all managed applications.
///
/// Returns a JSON array of all apps tracked in state.json.
pub async fn list_apps(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
) -> impl IntoResponse {
    let state = app_state.state_manager.get();
    let apps: Vec<AppInfo> = state.installed.values().map(|app| {
        AppInfo {
            repo: app.repo.clone(),
            name: app.repo.split('/').next_back().unwrap_or(&app.repo).to_string(),
            version: app.version.clone(),
            install_path: app.install_path.display().to_string(),
            installed_at: app.installed_at.to_rfc3339(),
            updated_at: app.updated_at.map(|dt| dt.to_rfc3339()),
            status: "installed".to_string(),
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
}

/// Get current configuration (token masked).
///
/// Returns the current configuration with sensitive values masked.
pub async fn get_config(
    State(app_state): State<std::sync::Arc<crate::webui::AppState>>,
) -> impl IntoResponse {
    let config = app_state.config_manager.get();
    
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
        token_source: app_state.config_manager.token_source().to_string(),
    })
}