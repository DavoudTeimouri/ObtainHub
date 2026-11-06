use axum::{
    extract::{Request, State},
    http::{StatusCode, header, Method},
    middleware::Next,
    response::Response,
};
use std::sync::Arc;
use crate::webui::AppState;

/// Paths and methods that are always public (no auth required).
const PUBLIC_ROUTES: &[(&str, &[Method])] = &[
    ("/", &[Method::GET]),
    ("/static", &[Method::GET]),
    ("/apps", &[Method::GET]),
    ("/config", &[Method::GET]),
    ("/config/sources", &[Method::GET]),
    ("/config/github-token", &[Method::POST]),
];

/// Check if the given path and method are publicly accessible.
fn is_public(path: &str, method: &Method) -> bool {
    PUBLIC_ROUTES.iter().any(|(p, methods)| {
        methods.contains(method) && (path == *p || path.starts_with(*p))
    })
}

/// Auth middleware: validates Bearer token against `config.github_token()`.
///
/// When `auth_enabled` is false, all requests pass through.
/// When true, requires `Authorization: Bearer *** header matching the
/// configured GitHub token (from OS credential store or config file).
/// Public routes are always accessible without auth.
pub async fn auth_middleware(
    State(state): State<Arc<AppState>>,
    request: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    // If auth is not enabled, allow all requests.
    if !state.auth_enabled {
        return Ok(next.run(request).await);
    }

    // Public routes are always accessible.
    let path = request.uri().path().to_string();
    let method = request.method().clone();
    if is_public(&path, &method) {
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