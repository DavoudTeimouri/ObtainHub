use axum::{
    extract::{Request, State},
    http::{StatusCode, header},
    middleware::Next,
    response::Response,
};
use std::sync::Arc;
use crate::webui::AppState;

/// Auth middleware: validates Bearer token against `config.github_token()`.
///
/// When `auth_enabled` is false, all requests pass through.
/// When true, requires `Authorization: Bearer <token>` header matching the
/// configured GitHub token (from OS credential store or config file).
pub async fn auth_middleware(
    State(state): State<Arc<AppState>>,
    request: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    // If auth is not enabled, allow all requests.
    if !state.auth_enabled {
        return Ok(next.run(request).await);
    }

    // Check for Authorization header.
    let auth_header = request
        .headers()
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok());

    let token = match auth_header {
        Some(header) => {
            // Expect "Bearer <token>"
            header.strip_prefix("Bearer ").map(|t| t.to_string())
        }
        None => None,
    };

    match token {
        Some(token) => {
            // Validate against the configured GitHub token.
            let config_manager = state.config_manager.lock().await;
            let config_token = config_manager.github_token();
            if let Some(configured_token) = config_token {
                if token == configured_token {
                    Ok(next.run(request).await)
                } else {
                    Err(StatusCode::UNAUTHORIZED)
                }
            } else {
                // No token configured, but auth is enabled → reject all.
                Err(StatusCode::UNAUTHORIZED)
            }
        }
        None => Err(StatusCode::UNAUTHORIZED),
    }
}