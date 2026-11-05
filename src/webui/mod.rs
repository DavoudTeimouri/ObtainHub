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

/// HTML dashboard served at `/`.
///
/// Shows app status summary, quick links to protected endpoints, and server info.
fn dashboard_html() -> String {
    r#"<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ObtainHub WebUI</title>
<style>
  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; padding: 24px; background: #0f172a; color: #f1f5f9; }
  h1 { margin: 0 0 8px 0; font-size: 24px; }
  .subtitle { color: #94a3b8; margin-bottom: 24px; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
  .card h2 { font-size: 16px; margin: 0 0 12px 0; color: #38bdf8; }
  a { color: #38bdf8; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
  .endpoint { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 13px; background: #0f172a; padding: 4px 8px; border-radius: 4px; display: inline-block; margin: 4px 0; }
  .note { font-size: 13px; color: #94a3b8; margin-top: 8px; }
  .auth { color: #fbbf24; font-weight: bold; }
</style>
</head>
<body>
  <h1>ObtainHub WebUI</h1>
  <p class="subtitle">GitHub package updater &amp; manager for Windows x64</p>

  <div class="card">
    <h2>Endpoints</h2>
    <div class="grid">
      <span class="endpoint">GET /</span> — Dashboard
      <span class="endpoint">GET /apps</span> — Managed apps
      <span class="endpoint endpoint-auth">GET /config</span> — Configuration <span class="auth">[auth]</span>
      <span class="endpoint endpoint-auth">GET/POST /downloads</span> — Downloads <span class="auth">[auth]</span>
      <span class="endpoint endpoint-auth">POST /downloads/{id}/cancel</span> — Cancel download <span class="auth">[auth]</span>
      <span class="endpoint endpoint-auth">POST /update-check</span> — Check for updates <span class="auth">[auth]</span>
    </div>
  </div>

  <div class="card">
    <h2>Quick links</h2>
    <p><a href="/apps">View managed apps</a></p>
    <p class="note">Protected endpoints require <code>Authorization: Bearer &lt;token&gt;</code> when started with <code>--auth</code>.</p>
  </div>
</body>
</html>"#.to_string()
}

/// HTML dashboard handler for `GET /`.
async fn dashboard() -> Html<String> {
    Html(dashboard_html())
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
        .route("/", get(dashboard))
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