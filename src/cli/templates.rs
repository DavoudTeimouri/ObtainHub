//! CLI message templates for consistent output formatting
//! 
//! This module provides standardized message templates for all CLI output
//! to ensure consistency in formatting, terminology, and style.

use std::fmt;

/// Version information template
pub fn version_template() -> String {
    let build_timestamp = option_env!("VERGEN_BUILD_TIMESTAMP").unwrap_or("unknown");
    let rustc_version = option_env!("VERGEN_RUSTC_SEMVER").unwrap_or("unknown");
    format!(
        "{} {}\n\
        GitHub: https://github.com/DavoudTeimouri/ObtainHub\n\
        License: MIT\n\
        Built: {} ({})",
        env!("CARGO_PKG_NAME"),
        env!("CARGO_PKG_VERSION"),
        build_timestamp,
        rustc_version
    )
}

/// Short version template (for --version flag)
pub fn version_short() -> String {
    format!("{} {}", env!("CARGO_PKG_NAME"), env!("CARGO_PKG_VERSION"))
}

/// Error message template
pub fn error_template(context: &str, details: &str) -> String {
    format!("Error: {}\n  Details: {}", context, details)
}

/// Warning message template
pub fn warning_template(message: &str) -> String {
    format!("Warning: {}", message)
}

/// Info message template
pub fn info_template(message: &str) -> String {
    format!("Info: {}", message)
}

/// Success message template
pub fn success_template(message: &str) -> String {
    format!("Success: {}", message)
}

/// Progress message template
pub fn progress_template(step: &str, current: usize, total: usize, item: &str) -> String {
    format!("[{}/{}] {} - {}", current, total, step, item)
}

/// Status message template
pub fn status_template(status: &str, item: &str) -> String {
    format!("{} {}", status, item)
}

/// Repository info template
pub fn repo_info_template(name: &str, version: &str, description: Option<&str>, url: &str) -> String {
    let mut result = format!(
        "Repository: {}\n\
        Version: {}\n\
        URL: {}",
        name, version, url
    );
    if let Some(desc) = description {
        result = format!("{}\nDescription: {}", result, desc);
    }
    result
}

/// Installation result template
pub fn install_result_template(repo: &str, version: &str, path: &str, checksum: Option<&str>) -> String {
    let mut result = format!(
        "Installed: {} v{}\n\
        Location: {}",
        repo, version, path
    );
    if let Some(cs) = checksum {
        result = format!("{}\nChecksum: {}", result, cs);
    }
    result
}

/// Update available template
pub fn update_available_template(repo: &str, current: &str, latest: &str) -> String {
    format!("Update available: {} {} -> {}", repo, current, latest)
}

/// No updates template
pub fn no_updates_template() -> String {
    "All repositories are up to date.".to_string()
}

/// Search result template
pub fn search_result_template(name: &str, owner: &str, stars: u32, description: &str, url: &str) -> String {
    format!(
        "{} ({})\n\
        Stars: {}\n\
        Description: {}\n\
        URL: {}",
        name, owner, stars, description, url
    )
}

/// List item template
pub fn list_item_template(name: &str, version: &str, status: &str, path: Option<&str>) -> String {
    let mut result = format!("{} v{} [{}]", name, version, status);
    if let Some(p) = path {
        result = format!("{} - {}", result, p);
    }
    result
}

/// Uninstall confirmation template
pub fn uninstall_confirm_template(name: &str, version: &str) -> String {
    format!("Uninstall {} v{}? This will remove all files and configuration.", name, version)
}

/// Rollback info template
pub fn rollback_info_template(repo: &str, from_version: &str, to_version: &str) -> String {
    format!("Rolling back {} from {} to {}", repo, from_version, to_version)
}

/// Configuration template
pub fn config_template(key: &str, value: &str) -> String {
    format!("{} = {}", key, value)
}

/// Dry run template
pub fn dry_run_template(action: &str, target: &str) -> String {
    format!("DRY RUN: Would {} {}", action, target)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_version_short() {
        let v = version_short();
        assert!(v.contains("obtainhub"));
        assert!(v.contains("3.0.17"));
    }

    #[test]
    fn test_error_template() {
        let e = error_template("Failed to download", "Connection timeout");
        assert!(e.contains("Error: Failed to download"));
        assert!(e.contains("Connection timeout"));
    }

    #[test]
    fn test_progress_template() {
        let p = progress_template("Installing", 1, 5, "ripgrep");
        assert_eq!(p, "[1/5] Installing - ripgrep");
    }

    #[test]
    fn test_update_available_template() {
        let u = update_available_template("BurntSushi/ripgrep", "14.0.0", "14.1.0");
        assert_eq!(u, "Update available: BurntSushi/ripgrep 14.0.0 -> 14.1.0");
    }
}