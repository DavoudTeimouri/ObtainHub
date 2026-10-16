use crate::core::{ConfigManager, StateManager};
use crate::cli::{CheckArgs, SelfUpdateArgs};
use crate::utils::retry::{execute_with_retry, RetryConfig};
use anyhow::Result;
use minreq;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::io::{self, Write};
use std::time::Duration;
use tracing::info;
use comfy_table::{Table, Cell};
use urlencoding;
use dialoguer::{Select, MultiSelect, Confirm, theme::ColorfulTheme};
use indicatif::{ProgressBar, ProgressStyle};

#[derive(Deserialize, Serialize, Debug)]
struct GitHubRelease {
    tag_name: String,
    name: Option<String>,
    prerelease: bool,
    draft: bool,
    assets: Vec<GitHubAsset>,
    zipball_url: String,
    tarball_url: String,
}

#[derive(Deserialize, Serialize, Debug)]
struct GitHubAsset {
    name: String,
    browser_download_url: String,
    size: u64,
    content_type: Option<String>,
}

pub async fn execute(args: CheckArgs, config: &ConfigManager, state: &mut StateManager) -> Result<()> {
    info!("Checking for updates");

    let token = config.get().github_token.as_deref();
    let retry_config = RetryConfig::from_config(config);

    // Create a theme with green check marks and default colors for everything else
    let theme = ColorfulTheme::default();

    // Get all installed software if --all or --candidates
    let (matched, skipped) = if args.all || args.candidates {
        let pb = ProgressBar::new_spinner();
        pb.set_style(
            ProgressStyle::default_spinner()
                .template("{spinner} {msg}")
                .unwrap()
                .tick_chars("⠁⠂⠄⡀⢀⠠⠐⠈ "),
        );
        pb.set_message("Scanning Windows registry for installed programs...");
        pb.enable_steady_tick(Duration::from_millis(80));

        let all = enumerate_all_installed_software()?;
        let tracked = state.list_installed();
        let (matched, skipped) = partition_gitHub_managed(&all, &tracked);
        
        pb.finish_with_message(format!("Scanned {} installed programs.", all.len()));
        if !skipped.is_empty() {
            println!("  {} not managed by ObtainHub (no GitHub origin).", skipped.len());
        }
        (matched, skipped)
    } else {
        (state.list_installed().into_iter().cloned().collect(), Vec::new())
    };

    // Check for self-update if not checking specific repo
    if args.repo.is_none() && !args.candidates {
        if !args.quiet {
            println!("Checking ObtainHub self-update...");
        }
        check_self_update(config, args.quiet, &retry_config).await?;
    }

    let mut outdated = Vec::new();
    let mut current = Vec::new();
    let mut errors = Vec::new();
    let mut candidates_map: HashMap<String, Vec<String>> = HashMap::new();

    // Process tracked (matched) repositories
    if !args.quiet && !matched.is_empty() {
        println!("Checking {} managed repositories for updates...", matched.len());
    }
    for repo in matched {
        if let Some(ref target) = args.repo {
            if &repo.repo != target {
                continue;
            }
        }

        // Skip self-update check here - it's done separately
        if repo.repo.to_lowercase().contains("obtainhub") {
            continue;
        }

        match fetch_latest_release(&repo.repo, token, &retry_config).await {
            Ok(Some(release)) => {
                let latest_version = release.tag_name;
                if latest_version != repo.version {
                    outdated.push((repo.repo.clone(), repo.version.clone(), latest_version));
                } else {
                    current.push(repo.repo.clone());
                }
            }
            Ok(None) => {
                // No releases found for this repo - skip silently or add to errors
                if !args.quiet {
                    errors.push((repo.repo.clone(), "No releases found on GitHub".to_string()));
                }
            }
            Err(e) => {
                errors.push((repo.repo.clone(), e.to_string()));
            }
        }
    }

    // Handle --candidates flag for unmanaged apps - interactive selection
    if args.candidates {
            // Progress bar for finding candidates
            let pb = ProgressBar::new(skipped.len() as u64);
            pb.set_style(
                ProgressStyle::default_bar()
                    .template("{spinner} [{bar:40}] {pos}/{len} {msg}")
                    .unwrap()
                    .progress_chars("█▉▊▋▌▍▎▏  "),
            );
            pb.set_message("Finding candidate repositories...");

            // Track all unmanaged apps with their candidates (including empty)
            let mut all_candidates_map: HashMap<String, Vec<String>> = HashMap::new();
       
            for name in &skipped {
                match find_candidate_repos(name, token, &retry_config).await {
                    Ok(candidates) => {
                        // Show all unmanaged apps, even those with no candidates
                        all_candidates_map.insert(name.clone(), candidates);
                    }
                    Err(e) => {
                        // On error, still show the app with empty candidates
                        all_candidates_map.insert(name.clone(), Vec::new());
                        if !args.quiet {
                            eprintln!("Warning: Failed to find candidates for '{}': {}", name, e);
                        }
                    }
                }
                pb.inc(1);
            }
            pb.finish_with_message("Candidate search complete.");

            // Display all unmanaged apps with their candidates (including empty)
            if !all_candidates_map.is_empty() {
                println!("\nUnmanaged applications and candidate repositories:");
                for (name, candidates) in &all_candidates_map {
                    if candidates.is_empty() {
                        println!("  {} - no candidate repositories found", name);
                    } else {
                        println!("  {}:", name);
                        for candidate in candidates {
                            println!("    - {}", candidate);
                        }
                    }
                }

                // Interactive: let user select which apps to manage (all unmanaged apps)
                let all_app_names: Vec<String> = all_candidates_map.keys().cloned().collect();

                if !all_app_names.is_empty() {
                    let selections = MultiSelect::with_theme(&theme)
                        .with_prompt("Select apps to manage with ObtainHub (Space to select, Enter to confirm)")
                        .items(&all_app_names)
                        .interact_opt()?;

                    if let Some(selected_indices) = selections {
                        for idx in selected_indices {
                            let app_name = &all_app_names[idx];
                            let candidates = all_candidates_map.get(app_name);

                            match candidates {
                                Some(cands) if !cands.is_empty() => {
                                    // Show candidates for this app and let user choose one
                                    let choice = Select::with_theme(&theme)
                                        .with_prompt(format!("Choose repository for '{}'", app_name))
                                        .items(cands)
                                        .default(0)
                                        .interact_opt()?;

                                    if let Some(repo_idx) = choice {
                                        let selected_repo = &cands[repo_idx];
                                        // Add to state.json
                                        let mut new_repo = crate::core::state::InstalledRepo {
                                            repo: selected_repo.clone(),
                                            version: "unknown".to_string(),
                                            install_path: std::path::PathBuf::new(),
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

                                        // Check for updates immediately
                                        let pb = ProgressBar::new_spinner();
                                        pb.set_style(
                                            ProgressStyle::default_spinner()
                                                .template("{spinner} {msg}")
                                                .unwrap()
                                                .tick_chars("⠁⠂⠄⡀⢀⠠⠐⠈ "),
                                        );
                                        pb.set_message(format!("Checking latest version for {}...", selected_repo));
                                        pb.enable_steady_tick(Duration::from_millis(80));

                                        match fetch_latest_release(selected_repo, token, &retry_config).await {
                                            Ok(Some(release)) => {
                                                new_repo.version = release.tag_name.clone();
                                                state.add_installed(new_repo);
                                                state.save()?;
                                                pb.finish_with_message(format!("Latest version: {}", release.tag_name));
                                            }
                                            Ok(None) => {
                                                pb.finish_with_message(format!("No releases found for {}", selected_repo));
                                            }
                                            Err(e) => {
                                                pb.finish_with_message(format!("Could not fetch latest version: {}", e));
                                            }
                                        }
                                    }
                                }
                                Some(_) => {
                                    // Has candidates key but empty list
                                    println!("No candidate repositories found for '{}'. Skipping.", app_name);
                                }
                                None => {
                                    // No candidates found at all
                                    println!("No candidate repositories found for '{}'. Skipping.", app_name);
                                }
                            }
                        }
                    }
                }
            }

            // After --candidates, fall through to show check results for newly added repos
            // Re-fetch matched list to include newly added repos
            let tracked = state.list_installed();
            let matched = tracked.into_iter().cloned().collect::<Vec<_>>();
            if !args.quiet && !matched.is_empty() {
                println!("\nChecking {} managed repositories for updates...", matched.len());
            }
            for repo in matched {
                if let Some(ref target) = args.repo {
                    if &repo.repo != target {
                        continue;
                    }
                }

                // Skip self-update check here - it's done separately
                if repo.repo.to_lowercase().contains("obtainhub") {
                    continue;
                }

                match fetch_latest_release(&repo.repo, token, &retry_config).await {
                    Ok(Some(release)) => {
                        let latest_version = release.tag_name;
                        if latest_version != repo.version {
                            outdated.push((repo.repo.clone(), repo.version.clone(), latest_version));
                        } else {
                            current.push(repo.repo.clone());
                        }
                    }
                    Ok(None) => {
                        if !args.quiet {
                            errors.push((repo.repo.clone(), "No releases found on GitHub".to_string()));
                        }
                    }
                    Err(e) => {
                        errors.push((repo.repo.clone(), e.to_string()));
                    }
                }
            }
        }

    // Handle --all flag - interactive selection for unmanaged apps
    if args.all && !skipped.is_empty() {
        println!("\nChecking unmanaged apps for GitHub repositories...");
        for name in &skipped {
            match find_candidate_repos(name, token, &retry_config).await {
                Ok(candidates) if !candidates.is_empty() => {
                    // Show candidates and let user choose one or skip
                    let mut items = candidates.clone();
                    items.push("--- Skip ---".to_string());
                    let choice = Select::with_theme(&theme)
                        .with_prompt(format!("Choose repository for '{}' (or Skip)", name))
                        .items(&items)
                        .default(0)
                        .interact_opt()?;

                    if let Some(repo_idx) = choice {
                        if repo_idx < candidates.len() {
                            let selected_repo = &candidates[repo_idx];
                            match fetch_latest_release(selected_repo, token, &retry_config).await {
                                Ok(Some(release)) => {
                                    outdated.push((format!("{} (via {})", name, selected_repo), "unknown".to_string(), release.tag_name));
                                }
                                Ok(None) => {
                                    // No releases found - skip silently
                                }
                                Err(_) => {}
                            }
                        }
                    }
                }
                _ => {}
            }
        }
    }

    if args.outdated_only {
        if outdated.is_empty() {
            println!("All repositories are up to date.");
        } else {
            let mut table = Table::new();
            table.set_header(vec!["Repository", "Current", "Latest"]);
            for (repo, current_ver, latest_ver) in outdated {
                table.add_row(vec![Cell::new(&repo), Cell::new(&current_ver), Cell::new(&latest_ver)]);
            }
            println!("{}", table);
        }
        return Ok(());
    }

    // Show all results
    if !outdated.is_empty() {
        println!("Outdated ({}):", outdated.len());
        let mut table = Table::new();
        table.set_header(vec!["Repository", "Current", "Latest"]);
        for (repo, current_ver, latest_ver) in &outdated {
            table.add_row(vec![Cell::new(repo), Cell::new(current_ver), Cell::new(&latest_ver)]);
        }
        println!("{}", table);
        println!();
    }

    if !current.is_empty() {
        println!("Up to date ({})", current.len());
        for repo in &current {
            println!("  {}", repo);
        }
        println!();
    }

    if !errors.is_empty() {
        println!("Errors ({}):", errors.len());
        for (repo, error) in &errors {
            println!("  {}: {}", repo, error);
        }
        println!();
    }

    // Show candidates if any (non-interactive mode)
    if !candidates_map.is_empty() && !args.candidates {
        println!("Candidate repositories for unmanaged apps:");
        for (name, candidates) in candidates_map {
            println!("  {}:", name);
            for candidate in candidates {
                println!("    - {}", candidate);
            }
        }
    }

    Ok(())
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
                // No releases published - return None (not an error)
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

    // Check both 64-bit and 32-bit registry views
    for &root in &[HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER] {
        for &view in &[KEY_WOW64_64KEY, KEY_WOW64_32KEY] {
            let hklm = RegKey::predef(root);
            let uninstall_path = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall";

            if let Ok(uninstall_key) = hklm.open_subkey_with_flags(uninstall_path, KEY_READ | view) {
                for subkey_name in uninstall_key.enum_keys().flatten() {
                    if let Ok(subkey) = uninstall_key.open_subkey_with_flags(&subkey_name, KEY_READ | view) {
                        let display_name: Option<String> = subkey.get_value("DisplayName").ok();
                        let display_version: Option<String> = subkey.get_value("DisplayVersion").ok();
                        let publisher: Option<String> = subkey.get_value("Publisher").ok();
                        let uninstall_string: Option<String> = subkey.get_value("UninstallString").ok();

                        // Skip system components (no DisplayName)
                        if let Some(name) = display_name {
                            // Skip our own entry
                            if name.contains("ObtainHub") {
                                continue;
                            }

                            // Create a unique key to avoid duplicates
                            let key = format!("{}|{}", name, display_version.clone().unwrap_or_default());
                            if seen.insert(key) {
                                results.push(crate::core::state::InstalledRepo {
                                    repo: name.clone(),
                                    version: display_version.unwrap_or_else(|| "unknown".to_string()),
                                    install_path: std::path::PathBuf::from(uninstall_string.unwrap_or_default()),
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
    // Not implemented on non-Windows
    Ok(Vec::new())
}

/// Split enumerated Windows programs into ones ObtainHub actually manages and ones
/// it does not. Only entries present in `state.json` have a known GitHub origin —
/// a `DisplayName` like "NVIDIA Corporation" is not an `owner/repo` and would 404
/// on every lookup while exhausting the GitHub API rate limit.
fn partition_gitHub_managed(
    all: &[crate::core::state::InstalledRepo],
    tracked: &[&crate::core::state::InstalledRepo],
) -> (Vec<crate::core::state::InstalledRepo>, Vec<String>) {
    let mut matched = Vec::new();
    let mut skipped = Vec::new();

    for entry in all {
        let name = entry.repo.to_ascii_lowercase();

        // ObtainingHub manages it.
        if name.contains("obtainhub") {
            continue;
        }

        // Tracked in state -> we know its owner/repo.
        if let Some(tracked) = tracked.iter().find(|r| {
            let n = r.repo.to_ascii_lowercase();
            n == name || name.ends_with(&n) || n.ends_with(&name)
        }) {
            matched.push(crate::core::state::InstalledRepo {
                repo: tracked.repo.clone(),
                version: tracked.version.clone(),
                install_path: entry.install_path.clone(),
                installed_at: entry.installed_at,
                updated_at: entry.updated_at,
                checksum: tracked.checksum.clone(),
                metadata: tracked.metadata.clone(),
                previous_version: tracked.previous_version.clone(),
                previous_install_path: tracked.previous_install_path.clone(),
                dependencies: tracked.dependencies.clone(),
                is_dependency: tracked.is_dependency,
            });
        } else {
            skipped.push(entry.repo.clone());
        }
    }

    (matched, skipped)
}

async fn check_self_update(config: &ConfigManager, quiet: bool, retry_config: &RetryConfig) -> Result<()> {
    use crate::commands::self_update::{execute as self_update_execute};
    use crate::cli::SelfUpdateArgs;
    let args = SelfUpdateArgs {
        check_only: true,
        prerelease: false,
        force: false,
        json: false,
        quiet: true,
        skip_signature: false,
    };
    self_update_execute(args, &ConfigManager::new()?, &StateManager::new()?, retry_config).await
}

async fn find_candidate_repos(name: &str, token: Option<&str>, retry_config: &RetryConfig) -> Result<Vec<String>> {
    let encoded_name = urlencoding::encode(name);
    let url = format!("https://api.github.com/search/repositories?q={}&per_page=5", encoded_name);
    let token_clone = token.map(|s| s.to_string());
    
    execute_with_retry(retry_config, || {
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
    }, "find_candidate_repos").await
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    fn entry(name: &str) -> crate::core::state::InstalledRepo {
        crate::core::state::InstalledRepo {
            repo: name.to_string(),
            version: "1.0".to_string(),
            install_path: std::path::PathBuf::from("/tmp"),
            installed_at: Utc::now(),
            updated_at: None,
            checksum: None,
            metadata: serde_json::Value::Null,
            previous_version: None,
            previous_install_path: None,
            dependencies: Vec::new(),
            is_dependency: false,
        }
    }

    #[test]
    fn partition_skips_self_and_unmanaged() {
        let tracked: Vec<crate::core::state::InstalledRepo> = Vec::new();
        let all = vec![
            entry("ObtainHub 3.0.1"),
            entry("NVIDIA Corporation"),
            entry("7-Zip"),
        ];
        let tracked_refs: Vec<&crate::core::state::InstalledRepo> = tracked.iter().collect();
        let (matched, skipped) = partition_gitHub_managed(&all, &tracked_refs);
        assert!(matched.is_empty(), "nothing should match an empty state");
        assert_eq!(skipped.len(), 2, "NVIDIA + 7-Zip are not managed");
        assert!(!skipped.contains(&"ObtainHub 3.0.1".to_string()), "self must not be listed as skipped");
    }

    #[test]
    fn partition_matches_tracked_repo() {
        let tracked = vec![entry("BurntSushi/ripgrep")];
        let tracked_refs: Vec<&crate::core::state::InstalledRepo> = tracked.iter().collect();
        let all = vec![entry("ripgrep"), entry("7-Zip")];
        let (matched, skipped) = partition_gitHub_managed(&all, &tracked_refs);
        assert_eq!(matched.len(), 1);
        assert_eq!(matched[0].repo, "BurntSushi/ripgrep");
        assert_eq!(skipped, vec!["7-Zip".to_string()]);
    }
}
