use crate::core::{ConfigManager, StateManager};
use crate::cli::UpdateArgs;
use crate::utils::retry::{execute_with_retry, RetryConfig};
use anyhow::Result;
use minreq;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::time::Duration;
use tracing::{info, warn};
use urlencoding;
use indicatif::{ProgressBar, ProgressStyle};
use dialoguer::{MultiSelect, Select, theme::ColorfulTheme};

use crate::commands::install::{fetch_published_checksum, GitHubRelease as InstallGitHubRelease, GitHubAsset as InstallGitHubAsset, select_asset as install_select_asset};
use sha2::{Digest, Sha256};

fn calculate_sha256_bytes(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hex::encode(hasher.finalize())
}

#[derive(Deserialize, Serialize, Debug)]
struct GitHubRelease {
    #[serde(default = "default_tag_name")]
    tag_name: String,
    name: Option<String>,
    prerelease: bool,
    draft: bool,
    assets: Vec<GitHubAsset>,
    zipball_url: String,
    tarball_url: String,
}

fn default_tag_name() -> String {
    "unknown".to_string()
}

#[derive(Deserialize, Serialize, Debug)]
struct GitHubAsset {
    name: String,
    browser_download_url: String,
    size: u64,
    content_type: Option<String>,
}

async fn fetch_latest_release(repo: &str, token: Option<&str>, retry_config: &RetryConfig) -> Result<Option<GitHubRelease>> {
    let url = format!("https://api.github.com/repos/{}/releases/latest", repo);
    let token_clone = token.map(|s| s.to_string());

    let result = execute_with_retry(retry_config, || {
        let url = url.clone();
        let token = token_clone.clone();
        async move {
            let mut req = minreq::get(&url).with_header("User-Agent", "ObtainHub/3.0.0");
            if let Some(token) = token {
                req = req.with_header("Authorization", &format!("Bearer {}", token));
            }
            let resp = req.send()?;

            if resp.status_code == 404 {
                return Ok(None);
            }

            if !(resp.status_code >= 200 && resp.status_code < 300) {
                return Err(anyhow::anyhow!("GitHub API error: {}", resp.status_code));
            }

            let release: GitHubRelease = resp.json()?;
            Ok(Some(release))
        }
    }, "fetch_latest_release").await?;

    Ok(result)
}

#[cfg(windows)]
fn enumerate_all_installed_software() -> Result<Vec<crate::core::state::InstalledRepo>> {
    use std::collections::HashSet;
    use winreg::enums::*;
    use winreg::RegKey;

    let mut results = Vec::new();
    let mut seen = HashSet::new();

    for &root in &[HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER] {
        for &view in &[KEY_WOW64_64KEY, KEY_WOW64_32KEY] {
            let hklm = RegKey::predef(root);
            let uninstall_path = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall";

            if let Ok(uninstall_key) = hklm.open_subkey_with_flags(uninstall_path, KEY_READ | view) {
                for subkey_name in uninstall_key.enum_keys().flatten() {
                    if let Ok(subkey) = uninstall_key.open_subkey_with_flags(&subkey_name, KEY_READ | view) {
                        let display_name: Option<String> = subkey.get_value("DisplayName").ok();
                        let display_version: Option<String> = subkey.get_value("DisplayVersion").ok();
                        let uninstall_string: Option<String> = subkey.get_value("UninstallString").ok();

                        if let Some(name) = display_name {
                            if name.contains("ObtainHub") {
                                continue;
                            }

                            let key = format!("{}|{}", name, display_version.clone().unwrap_or_default());
                            if seen.insert(key) {
                                results.push(crate::core::state::InstalledRepo {
                                    repo: name.clone(),
                                    version: display_version.unwrap_or_else(|| "unknown".to_string()),
                                    install_path: PathBuf::from(uninstall_string.unwrap_or_default()),
                                    installed_at: chrono::Utc::now(),
                                    updated_at: None,
                                    checksum: None,
                                    metadata: serde_json::Value::Null,
                                    previous_version: None,
                                    previous_install_path: None,
                                    dependencies: Vec::new(),
                                    is_dependency: false,
                                });
                            }
                        }
                    }
                }
            }
        }
    }

    Ok(results)
}

#[cfg(not(windows))]
fn enumerate_all_installed_software() -> Result<Vec<crate::core::state::InstalledRepo>> {
    Ok(Vec::new())
}

async fn find_candidate_repos(name: &str, token: Option<&str>, retry_config: &RetryConfig) -> Result<Vec<String>> {
    let cleaned = clean_app_name(name);
    let search_terms: Vec<&str> = if cleaned != name {
        vec![cleaned.as_str(), name]
    } else {
        vec![name]
    };

    let mut all_candidates: Vec<String> = Vec::new();
    let mut seen = HashMap::new();

    for term in search_terms {
        if term.is_empty() {
            continue;
        }
        let encoded_name = urlencoding::encode(term);
        let url = format!("https://api.github.com/search/repositories?q={}&per_page=5", encoded_name);
        let token_clone = token.map(|s| s.to_string());

        let result = execute_with_retry(retry_config, || {
            let url = url.clone();
            let token = token_clone.clone();
            async move {
                let mut req = minreq::get(&url).with_header("User-Agent", "ObtainHub/3.0.0");
                if let Some(token) = token {
                    req = req.with_header("Authorization", &format!("Bearer {}", token));
                }
                let resp: serde_json::Value = req.send()?.json()?;
                let items = resp["items"].as_array().unwrap_or(&vec![]).to_vec();
                let mut candidates = Vec::new();
                for item in items {
                    if let Some(full_name) = item["full_name"].as_str() {
                        candidates.push(full_name.to_string());
                    }
                }
                Ok(candidates)
            }
        }, "find_candidate_repos").await;

        match result {
            Ok(candidates) => {
                for c in candidates {
                    if seen.insert(c.clone(), true).is_none() {
                        all_candidates.push(c);
                    }
                }
            }
            Err(e) => {
                if !term.eq(name) {
                    continue;
                }
                return Err(e);
            }
        }
    }

    Ok(all_candidates)
}

fn clean_app_name(name: &str) -> String {
    let mut cleaned = name.to_string();

    cleaned = cleaned.split(char::is_whitespace)
        .filter(|part| {
            let has_digit = part.chars().any(|c| c.is_ascii_digit());
            let has_dot = part.contains('.');
            let has_v_prefix = part.starts_with('v') || part.starts_with('V');
            if has_digit && (has_dot || has_v_prefix) && part.len() <= 10 {
                return false;
            }
            if part.len() == 1 && (*part == "v" || *part == "V") {
                return false;
            }
            true
        })
        .collect::<Vec<&str>>()
        .join(" ")
        .trim()
        .to_string();

    let suffixes = [" for windows", " for mac", " for linux", " portable", " installer", " setup"];
    for suffix in &suffixes {
        if cleaned.to_lowercase().ends_with(suffix) {
            cleaned = cleaned[..cleaned.len() - suffix.len()].trim().to_string();
        }
    }

    cleaned.trim().to_string()
}

pub async fn execute(args: UpdateArgs, config: &ConfigManager, state: &mut StateManager, retry_config: &RetryConfig) -> Result<()> {
    info!("Updating repositories");

    let token = config.get().github_token.as_deref();

    // Auto-detect unmanaged apps and offer to add them
    if !args.skip_auto_detect {
        let all = enumerate_all_installed_software()?;
        let tracked: Vec<&crate::core::state::InstalledRepo> = state.list_installed().into_iter().collect();
        let unmanaged: Vec<&crate::core::state::InstalledRepo> = all.iter()
            .filter(|entry| {
                let name = entry.repo.to_ascii_lowercase();
                if name.contains("obtainhub") {
                    return false;
                }
                !tracked.iter().any(|r| {
                    let n = r.repo.to_ascii_lowercase();
                    n == name || name.ends_with(&n) || n.ends_with(&name)
                })
            })
            .collect();

        if !unmanaged.is_empty() {
            // Sort by name
            let mut sorted: Vec<&crate::core::state::InstalledRepo> = unmanaged;
            sorted.sort_by(|a, b| a.repo.to_lowercase().cmp(&b.repo.to_lowercase()));

            println!("\nUnmanaged applications found on this system:");
            for (i, entry) in sorted.iter().enumerate() {
                println!("  {}. {}", i + 1, entry.repo);
            }

            let theme = ColorfulTheme::default();
            let names: Vec<String> = sorted.iter().map(|e| e.repo.clone()).collect();
            let selections = MultiSelect::with_theme(&theme)
                .with_prompt("Add unmanaged apps to ObtainHub? (Space to select, Enter to confirm)")
                .items(&names)
                .interact_opt()?;

            if let Some(selected_indices) = selections {
                for idx in selected_indices {
                    let app_name = &names[idx];

                    let candidates = find_candidate_repos(app_name, token, retry_config).await.unwrap_or_default();
                    if !candidates.is_empty() {
                        let choice = Select::with_theme(&theme)
                            .with_prompt(format!("Choose repository for '{}'", app_name))
                            .items(&candidates)
                            .default(0)
                            .interact_opt()?;
                        if let Some(repo_idx) = choice {
                            let selected_repo = &candidates[repo_idx];
                            let mut new_repo = crate::core::state::InstalledRepo {
                                repo: selected_repo.clone(),
                                version: "unknown".to_string(),
                                install_path: PathBuf::new(),
                                installed_at: chrono::Utc::now(),
                                updated_at: None,
                                checksum: None,
                                metadata: serde_json::Value::Null,
                                previous_version: None,
                                previous_install_path: None,
                                dependencies: Vec::new(),
                                is_dependency: false,
                            };
                            state.add_installed(new_repo.clone());
                            state.save()?;
                            println!("Added '{}' (via {}) to managed repositories.", app_name, selected_repo);
                        }
                    } else {
                        println!("No candidate repositories found for '{}'.", app_name);
                    }
                }
            }
        }
    }

    let installed = state.list_installed();

    if installed.is_empty() {
        println!("No repositories installed.");
        return Ok(());
    }

    // Collect repo info first to avoid borrow issues
    let repo_infos: Vec<_> = installed.iter().map(|r| (r.repo.clone(), r.version.clone())).collect();

    // Determine which repos to update
    let targets: Vec<_> = if let Some(repo_name) = &args.repo {
        repo_infos.iter().filter(|(r, _)| r == repo_name).collect()
    } else {
        repo_infos.iter().collect()
    };

    if targets.is_empty() {
        println!("No matching repositories found.");
        return Ok(());
    }

    let mut updated = Vec::new();
    let mut already_current = Vec::new();
    let mut errors = Vec::new();

    for (repo_name, current_version) in targets {
        println!("Checking {}@{}...", repo_name, current_version);

        // First, check if this repo has dependencies that need updating
        if !args.skip_deps {
            let deps = state.get_installed(repo_name).map(|e| e.dependencies.clone()).unwrap_or_default();
            for dep in &deps {
                println!("  Checking dependency {}...", dep);
                if let Some(dep_entry) = state.get_installed(dep) {
                    match fetch_latest_release(dep, token, retry_config).await {
                        Ok(Some(dep_release)) => {
                            let dep_latest = dep_release.tag_name.clone();
                            if dep_latest != dep_entry.version {
                                println!("    Dependency update available: {} -> {}", dep_entry.version, dep_latest);
                                if !args.dry_run {
                                    match install_release(dep, &dep_latest, &dep_release, token, config, state, args.force, true).await {
                                        Ok(_) => println!("    Updated dependency {} to {}", dep, dep_latest),
                                        Err(e) => eprintln!("    Failed to update dependency {}: {}", dep, e),
                                    }
                                }
                            }
                        }
                        Ok(None) => {
                            // No releases found for dependency
                        }
                        Err(e) => eprintln!("    Error checking dependency {}: {}", dep, e),
                    }
                }
            }
        }

        match fetch_latest_release(repo_name, token, retry_config).await {
            Ok(Some(release)) => {
                let latest_version = release.tag_name.clone();
                if latest_version != *current_version {
                    println!("  Update available: {} -> {}", current_version, latest_version);

                    if args.dry_run {
                        updated.push((repo_name.clone(), current_version.clone(), latest_version));
                        continue;
                    }

                    // Perform update (reinstall with new version)
                    match install_release(repo_name, &latest_version, &release, token, config, state, args.force, args.skip_deps).await {
                        Ok(_) => {
                            updated.push((repo_name.clone(), current_version.clone(), latest_version.clone()));
                            println!("  Updated to {}", latest_version);
                        }
                        Err(e) => {
                            errors.push((repo_name.clone(), e.to_string()));
                            eprintln!("  Failed: {}", e);
                        }
                    }
                } else {
                    already_current.push(repo_name.clone());
                    println!("  Already at latest version");
                }
            }
            Ok(None) => {
                // No releases found for this repo
                println!("  No releases found on GitHub");
            }
            Err(e) => {
                errors.push((repo_name.clone(), e.to_string()));
                eprintln!("  Error checking: {}", e);
            }
        }
    }

    // Summary
    println!("\nUpdate Summary:");
    if !updated.is_empty() {
        println!("  Updated ({})", updated.len());
        for (repo, old, new) in &updated {
            println!("    {} {} -> {}", repo, old, new);
        }
    }

    if !already_current.is_empty() {
        println!("  Already current ({})", already_current.len());
        for repo in &already_current {
            println!("    {}", repo);
        }
    }

    if !errors.is_empty() {
        println!("  Errors ({})", errors.len());
        for (repo, error) in &errors {
            println!("    {}: {}", repo, error);
        }
    }

    Ok(())
}

async fn install_release(
    repo: &str,
    version: &str,
    release: &GitHubRelease,
    token: Option<&str>,
    config: &ConfigManager,
    state: &mut StateManager,
    force: bool,
    _skip_deps: bool,
) -> Result<()> {
    // Find suitable asset using install command's logic (considers architecture)
    let install_release = &InstallGitHubRelease {
        tag_name: release.tag_name.clone(),
        name: release.name.clone(),
        prerelease: release.prerelease,
        draft: release.draft,
        assets: release.assets.iter().map(|a| InstallGitHubAsset {
            name: a.name.clone(),
            browser_download_url: a.browser_download_url.clone(),
            size: a.size,
            content_type: a.content_type.clone(),
        }).collect(),
        zipball_url: release.zipball_url.clone(),
        tarball_url: release.tarball_url.clone(),
    };

    let asset = install_select_asset(install_release)?;

    println!("  Downloading {}...", asset.name);

    // Download with progress
    let download_url = &asset.browser_download_url;
    let mut req = minreq::get(download_url).with_header("User-Agent", "ObtainHub/3.0.0");
    if let Some(token) = token {
        req = req.with_header("Authorization", &format!("Bearer {}", token));
    }

    let response = req.send()?;
    let bytes = response.as_bytes();

    if let Some(expected) = fetch_published_checksum(install_release, &asset.name, token).await? {
        let actual = calculate_sha256_bytes(bytes);
        if !expected.eq_ignore_ascii_case(&actual) {
            return Err(anyhow::anyhow!("Checksum mismatch for {}", asset.name));
        }
    }

    // Install using install command's logic
    let install_dir = config.get().install_dir.join(repo);
    std::fs::create_dir_all(&install_dir)?;
    let asset_path = install_dir.join(&asset.name);
    std::fs::write(&asset_path, bytes)?;

    // Update state
    let mut new_repo = crate::core::state::InstalledRepo {
        repo: repo.to_string(),
        version: version.to_string(),
        install_path: asset_path,
        installed_at: chrono::Utc::now(),
        updated_at: Some(chrono::Utc::now()),
        checksum: None,
        metadata: serde_json::Value::Null,
        previous_version: Some(version.to_string()),
        previous_install_path: None,
        dependencies: Vec::new(),
        is_dependency: false,
    };
    state.add_installed(new_repo.clone());
    state.save()?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clean_app_name_strips_version() {
        assert_eq!(clean_app_name("OnionHop V3 3.8.6"), "OnionHop");
        assert_eq!(clean_app_name("Aether-GUI"), "Aether-GUI");
        assert_eq!(clean_app_name("Obsidian"), "Obsidian");
    }
}
