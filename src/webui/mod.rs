use axum::{routing::get, Router, middleware};
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
        .route("/", get(routes::health))
        .route("/apps", get(routes::list_apps))
        .route("/config", get(routes::get_config))
        .route("/downloads", get(downloads::list_downloads))
        .route("/downloads", axum::routing::post(downloads::start_download))
        .route("/downloads/{id}/cancel", axum::routing::post(downloads::cancel_download))
        .route("/update-check", axum::routing::post(downloads::update_check))
        .route_layer(middleware::from_fn_with_state(
            app_state.clone(),
            crate::webui::auth::auth_middleware,
        ))
        .with_state(app_state);

    let listener = tokio::net::TcpListener::bind(addr).await
        .context("Failed to bind WebUI listener")?;
    info!("WebUI listening on {addr}");
    axum::serve(listener, app).await.context("WebUI server error")
}