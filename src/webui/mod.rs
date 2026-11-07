use axum::{routing::get, Router, middleware, response::Html};
use std::net::SocketAddr;
use std::path::PathBuf;
use std::fs;
use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::{info, warn};
use anyhow::Context;

mod routes;
mod downloads;
mod auth;


/// Shared state for the WebUI server.
///
/// `ConfigManager` and `StateManager` are wrapped in `tokio::sync::Mutex` so
/// that all HTTP handlers see the same in-memory state. Mutating through a
/// clone (which the previous code did) wrote to disk but left the original
/// `Arc` stale, so `GET /apps` and `GET /config` never reflected writes.
pub struct AppState {
    pub config_manager: Arc<Mutex<crate::core::config::ConfigManager>>,
    pub state_manager: Arc<Mutex<crate::core::state::StateManager>>,
    /// Require Bearer token auth on protected endpoints when true.
    pub auth_enabled: bool,
    /// Live download jobs, shared with the download handlers.
    pub downloads: downloads::DownloadRegistry,
    /// Session tokens issued by POST /auth/login (Windows admin sign-in).
    pub sessions: std::sync::Arc<std::sync::Mutex<std::collections::HashSet<String>>>,
}

/// Embedded static file content (compiled into the binary).
const INDEX_HTML: &str = include_str!("static/index.html");
const STYLE_CSS: &str = include_str!("static/style.css");
const APP_JS: &str = include_str!("static/app.js");

/// HTML dashboard handler for `GET /`. Always public (no auth required).
/// Serves the professional static index.html embedded in the binary.
async fn spa() -> Html<String> {
    Html(INDEX_HTML.to_string())
}

/// Serve embedded static file at `/static/<path>`.
/// Content-Type matters: `<script type="module">` is rejected by browsers
/// unless the MIME type is JavaScript, and CSS should be text/css.
async fn static_file_embedded(
    axum::extract::Path(path): axum::extract::Path<String>,
) -> Result<([(axum::http::header::HeaderName, &'static str); 1], &'static str), axum::http::StatusCode> {
    if path.contains("..") {
        return Err(axum::http::StatusCode::NOT_FOUND);
    }
    let (content, content_type) = match path.as_str() {
        "style.css" => (STYLE_CSS, "text/css; charset=utf-8"),
        "app.js" => (APP_JS, "text/javascript; charset=utf-8"),
        _ => return Err(axum::http::StatusCode::NOT_FOUND),
    };
    Ok(([(axum::http::header::CONTENT_TYPE, content_type)], content))
}

/// Path to the WebUI PID file, used by `ohub self-update` to stop the server
/// before replacing the binary.
fn webui_pid_file() -> PathBuf {
    dirs::data_dir()
        .unwrap_or_else(std::env::temp_dir)
        .join("ObtainHub")
        .join("webui.pid")
}

/// Write the current process ID to the PID file.
fn write_pid_file() -> anyhow::Result<()> {
    if let Some(parent) = webui_pid_file().parent() {
        let _ = fs::create_dir_all(parent);
    }
    fs::write(webui_pid_file(), std::process::id().to_string())?;
    Ok(())
}

/// Remove the PID file on shutdown, but only if it still names this process —
/// a newer WebUI instance may have overwritten it.
fn remove_pid_file() {
    let pid_file = webui_pid_file();
    if let Ok(content) = fs::read_to_string(&pid_file) {
        if content.trim() == std::process::id().to_string() {
            let _ = fs::remove_file(&pid_file);
        }
    }
}

/// Start the WebUI HTTP server.
///
/// Runs an axum server on the given address. The server shares config/state
/// files with the CLI via the existing `ConfigManager` and `StateManager`.
///
/// The `/` route is always public. `GET /apps` is public. API routes that
/// modify state (`PUT /config`, `POST/DELETE /config/github-token`,
/// `POST/DELETE /apps`, `POST/DELETE /config/sources`, `/downloads/*`,
/// `/update-check`) require Bearer token auth when `auth_enabled` is true
/// (`--auth` flag).
pub async fn run_webui(
    addr: SocketAddr,
    config_manager: crate::core::config::ConfigManager,
    state_manager: crate::core::state::StateManager,
    auth_enabled: bool,
) -> anyhow::Result<()> {
    let app_state = Arc::new(AppState {
        config_manager: Arc::new(Mutex::new(config_manager)),
        state_manager: Arc::new(Mutex::new(state_manager)),
        auth_enabled,
        downloads: Arc::new(std::sync::Mutex::new(std::collections::HashMap::new())),
        sessions: Arc::new(std::sync::Mutex::new(std::collections::HashSet::new())),
    });

    // Write PID file so `ohub self-update` can stop the WebUI before updating.
    if let Err(e) = write_pid_file() {
        warn!("Failed to write WebUI PID file: {e}");
    }

    let app = Router::new()
        // Public read-only routes
        .route("/", get(spa))
        .route("/static/*path", get(static_file_embedded))
        .route("/apps", get(routes::list_apps))
        .route("/config", get(routes::get_config))
        .route("/config/sources", get(routes::list_sources))
        // Token setup is public only until a token exists (see auth.rs bootstrap)
        .route("/config/github-token", axum::routing::post(routes::post_github_token))
        // Protected write routes (auth middleware applied below)
        .route("/config", axum::routing::put(routes::put_config))
        .route("/config/github-token", axum::routing::delete(routes::delete_github_token))
        .route("/apps", axum::routing::post(routes::post_app))
        .route("/apps/*repo", axum::routing::delete(routes::delete_app))
        // App actions (same engines as the CLI): repo passed in the JSON body
        // because axum 0.7 wildcards must be the last path segment.
        .route("/apps/install", axum::routing::post(routes::install_app))
        .route("/apps/uninstall", axum::routing::post(routes::uninstall_app))
        .route("/apps/update", axum::routing::post(routes::update_app))
        .route("/apps/check", axum::routing::post(routes::check_app))
        .route("/search", get(routes::search_repos))
        .route("/config/sources", axum::routing::post(routes::post_source))
        .route("/config/sources/*name", axum::routing::delete(routes::delete_source))
        // Protected download routes
        .route("/downloads", axum::routing::get(downloads::list_downloads))
        .route("/downloads", axum::routing::post(downloads::start_download))
        // axum 0.7 path params use `:id` (`{id}` would be a literal segment).
        .route("/downloads/:id/cancel", axum::routing::post(downloads::cancel_download))
        // Protected update check
        .route("/update-check", axum::routing::post(downloads::update_check))
        // Protected diagnostics: full state export and schedule log tail
        .route("/state/export", get(routes::export_state))
        .route("/logs", get(routes::tail_logs))
        .route("/auth/login", axum::routing::post(routes::login))
        .route("/help", get(routes::help_text))
        .with_state(app_state.clone())
        // Apply auth middleware to all routes — public paths are exempted inside the middleware
        .layer(middleware::from_fn_with_state(
            app_state,
            crate::webui::auth::auth_middleware,
        ));

    // Port conflict detection: try to bind, if it fails try the next port.
    let listener = match tokio::net::TcpListener::bind(addr).await {
        Ok(l) => l,
        Err(e) if e.kind() == std::io::ErrorKind::AddrInUse => {
            let alt_port = addr.port().saturating_add(1);
            let alt_addr: SocketAddr = format!("{}:{}", addr.ip(), alt_port).parse()
                .context("Failed to parse alternate address")?;
            warn!("Port {} is in use, trying {}", addr.port(), alt_port);
            tokio::net::TcpListener::bind(alt_addr).await
                .context(format!("Failed to bind WebUI listener on alternate port {alt_port}"))?
        }
        Err(e) => return Err(anyhow::anyhow!("Failed to bind WebUI listener: {e}")),
    };

    let actual_addr = listener.local_addr()?;
    info!("WebUI listening on {actual_addr}");

    let result = axum::serve(listener, app)
        .with_graceful_shutdown(async {
            let _ = tokio::signal::ctrl_c().await;
        })
        .await
        .context("WebUI server error");
    remove_pid_file();
    result
}