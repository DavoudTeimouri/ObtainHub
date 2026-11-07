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
    ("/auth/login", &[Method::POST]),
    ("/help", &[Method::GET]),
];

/// Check if the given path and method are publicly accessible.
/// Exact match or child path: `/config` covers `/config/sources` but not
/// `/configuration`.
fn is_public(path: &str, method: &Method) -> bool {
    PUBLIC_ROUTES.iter().any(|(p, methods)| {
        methods.contains(method) && (path == *p || path.starts_with(&format!("{p}/")))
    })
}

/// Auth middleware: validates Bearer token against `config.github_token()`.
///
/// When `auth_enabled` is false, all requests pass through.
/// When true, protected routes require `Authorization: Bearer <token>` matching
/// the configured GitHub token (OS credential store or config file).
/// Public routes are always accessible. `POST /config/github-token` is public
/// only while no token is configured yet (bootstrap); once a token exists it
/// requires auth, so an exposed `--bind 0.0.0.0` server cannot be re-keyed.
pub async fn auth_middleware(
    State(state): State<Arc<AppState>>,
    request: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    let path = request.uri().path().to_string();
    let method = request.method().clone();

    // Public routes are always accessible.
    if is_public(&path, &method) {
        return Ok(next.run(request).await);
    }

    // If auth is not enabled, allow all requests.
    if !state.auth_enabled {
        return Ok(next.run(request).await);
    }

    // Get the configured token (release lock before calling next).
    let configured_token = {
        let config_manager = state.config_manager.lock().await;
        config_manager.github_token()
    };

    // Bootstrap: setting the initial token is allowed only while none is set.
    if path == "/config/github-token" && method == Method::POST && configured_token.is_none() {
        return Ok(next.run(request).await);
    }

    let auth_header = request
        .headers()
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok());
    let token = auth_header.and_then(|h| h.strip_prefix("Bearer "));

    // A valid session token (issued by POST /auth/login) also authenticates.
    // ponytail: guard scoped to a block — holding a std MutexGuard across
    // .await would make the middleware future !Send and break FromFn.
    if let Some(token) = token {
        let valid = { state.sessions.lock().unwrap().contains(token) };
        if valid {
            return Ok(next.run(request).await);
        }
    }

    match (token, configured_token) {
        (Some(token), Some(configured)) if token == configured => Ok(next.run(request).await),
        _ => Err(StatusCode::UNAUTHORIZED),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn public_exact_and_child_paths() {
        assert!(is_public("/", &Method::GET));
        assert!(is_public("/apps", &Method::GET));
        assert!(is_public("/config/sources", &Method::GET));
        assert!(is_public("/static/app.js", &Method::GET));
        // Prefix lookalikes must NOT match.
        assert!(!is_public("/appsfoo", &Method::GET));
        assert!(!is_public("/configuration", &Method::GET));
        // Wrong method on a public path is not public.
        assert!(!is_public("/apps", &Method::POST));
        assert!(!is_public("/config", &Method::PUT));
    }
}