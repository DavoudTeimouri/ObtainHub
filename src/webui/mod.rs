use axum::{routing::get, Router, middleware, response::Html};
use std::net::SocketAddr;
use std::sync::Arc;
use tracing::info;
use anyhow::Context;

mod routes;
mod downloads;
mod auth;

/// Shared state for the WebUI server.
pub struct AppState {
    pub config_manager: Arc<crate::core::config::ConfigManager>,
    pub state_manager: Arc<crate::core::state::StateManager>,
    /// Require Bearer token auth on protected endpoints when true.
    pub auth_enabled: bool,
}

/// Single-page application HTML served at `/`.
const SPA_HTML: &str = include_str!("spa.html");

/// HTML dashboard handler for `GET /`. Always public (no auth required).
async fn spa() -> Html<&'static str> {
    Html(SPA_HTML)
}

/// Start the WebUI HTTP server.
///
/// Runs an axum server on the given address. The server shares config/state
/// files with the CLI via the existing `ConfigManager` and `StateManager`.
pub async fn run_webui(
    addr: SocketAddr,
    config_manager: crate::core::config::ConfigManager,
    state_manager: crate::core::state::StateManager,
    auth_enabled: bool,
) -> anyhow::Result<()> {
    let app_state = Arc::new(AppState {
        config_manager: Arc::new(config_manager),
        state_manager: Arc::new(state_manager),
        auth_enabled,
    });

    let app = Router::new()
        .route("/", get(spa))
        .route(
            "/apps",
            get(routes::list_apps).layer(middleware::from_fn_with_state(
                app_state.clone(),
                crate::webui::auth::auth_middleware,
            )),
        )
        .route(
            "/config",
            get(routes::get_config).layer(middleware::from_fn_with_state(
                app_state.clone(),
                crate::webui::auth::auth_middleware,
            )),
        )
        .route(
            "/downloads",
            get(downloads::list_downloads).layer(middleware::from_fn_with_state(
                app_state.clone(),
                crate::webui::auth::auth_middleware,
            )),
        )
        .route(
            "/downloads",
            axum::routing::post(downloads::start_download).layer(middleware::from_fn_with_state(
                app_state.clone(),
                crate::webui::auth::auth_middleware,
            )),
        )
        .route(
            "/downloads/{id}/cancel",
            axum::routing::post(downloads::cancel_download).layer(middleware::from_fn_with_state(
                app_state.clone(),
                crate::webui::auth::auth_middleware,
            )),
        )
        .route(
            "/update-check",
            axum::routing::post(downloads::update_check).layer(middleware::from_fn_with_state(
                app_state.clone(),
                crate::webui::auth::auth_middleware,
            )),
        )
        .with_state(app_state);

    // Port conflict detection: try to bind, if it fails suggest an alternative.
    let listener = match tokio::net::TcpListener::bind(addr).await {
        Ok(l) => l,
        Err(e) if e.kind() == std::io::ErrorKind::AddrInUse => {
            // Try next available port
            let alt_port = addr.port().saturating_add(1);
            let alt_addr: SocketAddr = format!("{}:{}", addr.ip(), alt_port).parse()
                .context("Failed to parse alternate address")?;
            tracing::warn!("Port {} is in use, trying {}", addr.port(), alt_port);
            tokio::net::TcpListener::bind(alt_addr).await
                .context(format!("Failed to bind WebUI listener on alternate port {alt_port}"))?
        }
        Err(e) => return Err(anyhow::anyhow!("Failed to bind WebUI listener: {e}")),
    };

    let actual_addr = listener.local_addr()?;
    info!("WebUI listening on {actual_addr}");

    axum::serve(listener, app).await.context("WebUI server error")
}