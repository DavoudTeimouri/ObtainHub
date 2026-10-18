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
use dialoguer::{Select, MultiSelect, Confirm, theme::ColorfulTheme, Input};
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

    let theme = ColorfulTheme::default();

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

    // Sync state.json versions with actual registry scan versions for managed repos
    // (fixes stale versions from previous runs that overwrote with GitHub tags)
    if args.all || args.candidates {
        for m in &matched {
            if let Some(tracked) = state.get_installed(&m.repo) {
                if tracked.version != m.version {
                    let mut corrected = tracked.clone();
                    corrected.version = m.version.clone();
                    state.add_installed(corrected.clone());
                    state.save()?;
                }
            }
        }
    }

    if args.repo.is_none() && !args.candidates {
        if !args.quiet {
            println!("Checking ObtainHub self-update...");
        }
        check_self_update(config, args.quiet, &retry_config).await?;
    }

    let mut outdated = Vec::new();
    let mut current = Vec::new();
    let mut errors = Vec::new();

    if !args.quiet && !matched.is_empty() {
        println!("Checking {} managed repositories for updates...", matched.len());
    }
    for repo in matched {
        if let Some(ref target) = args.repo {
            if &repo.repo != target {
                continue;
            }
        }
        if repo.repo.to_lowercase().contains("obtainhub") {
            continue;
        }
        match fetch_latest_release(&repo.repo, token, &retry_config).await {
            Ok(Some(release)) => {
                let latest_version = release.tag_name;
                if normalize_version(&latest_version) != normalize_version(&repo.version) {
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

    if args.candidates {
        if !skipped.is_empty() {
            let mut sorted_skipped: Vec<&crate::core::state::InstalledRepo> = skipped.iter().collect();
            sorted_skipped.sort_by(|a, b| a.repo.to_lowercase().cmp(&b.repo.to_lowercase()));

            let pb = ProgressBar::new(sorted_skipped.len() as u64);
            pb.set_style(
                ProgressStyle::default_bar()
                    .template("{spinner} [{bar:40}] {pos}/{len} {msg}")
                    .unwrap()
                    .progress_chars("█▉▊▋▌▍▎▏  "),
            );
            pb.set_message("Finding candidate repositories...");

            let mut all_candidates_map: HashMap<String, (Vec<String>, crate::core::state::InstalledRepo)> = HashMap::new();

            for entry in &sorted_skipped {
                let name = entry.repo.clone();
                match find_candidate_repos(&name, token, &retry_config).await {
                    Ok(candidates) => {
                        all_candidates_map.insert(name.clone(), (candidates, (**entry).clone()));
                    }
                    Err(e) => {
                        all_candidates_map.insert(name.clone(), (Vec::new(), (**entry).clone()));
                        if !args.quiet {
                            eprintln!("Warning: Failed to find candidates for '{}': {}", name, e);
                        }
                    }
                }
                pb.inc(1);
            }
            pb.finish_with_message("Candidate search complete.");

            if !all_candidates_map.is_empty() {
                println!("\nUnmanaged applications and candidate repositories:");
                for (name, (candidates, _)) in &all_candidates_map {
                    if candidates.is_empty() {
                        println!("  {} - no candidate repositories found", name);
                    } else {
                        println!("  {}:", name);
                        for candidate in candidates {
                            println!("    - {}", candidate);
                        }
                    }
                }

                let all_app_names: Vec<String> = all_candidates_map.keys().cloned().collect();

                if !all_app_names.is_empty() {
                    let selections = MultiSelect::with_theme(&theme)
                        .with_prompt("Select apps to manage with ObtainHub (Space to select, Enter to confirm)")
                        .items(&all_app_names)
                        .interact_opt()?;

                    if let Some(selected_indices) = selections {
                        for idx in selected_indices {
                            let app_name = &all_app_names[idx];
                            let (candidates, skipped_entry) = all_candidates_map.get(app_name).unwrap();

                            match candidates.as_slice() {
                                cands if !cands.is_empty() => {
                                    let choice = Select::with_theme(&theme)
                                        .with_prompt(format!("Choose repository for '{}'", app_name))
                                        .items(cands)
                                        .default(0)
                                        .interact_opt()?;

                                    if let Some(repo_idx) = choice {
                                        let selected_repo = &cands[repo_idx];
                                        let selected_repo = selected_repo.clone();
                                        // Use real install_path and version from the skipped entry if available
                                        let mut new_repo = crate::core::state::InstalledRepo {
                                            repo: selected_repo.clone(),
                                            version: skipped_entry.version.clone(),
                                            install_path: skipped_entry.install_path.clone(),
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

                                        let pb = ProgressBar::new_spinner();
                                        pb.set_style(
                                            ProgressStyle::default_spinner()
                                                .template("{spinner} {msg}")
                                                .unwrap()
                                                .tick_chars("⠁⠂⠄⡀⢀⠠⠐⠈ "),
                                        );
                                        pb.set_message(format!("Checking latest version for {}...", selected_repo));
                                        pb.enable_steady_tick(Duration::from_millis(80));

                                        match fetch_latest_release(&selected_repo, token, &retry_config).await {
                                            Ok(Some(release)) => {
                                                // Keep the installed version from registry scan;
                                                // do NOT overwrite with latest release tag
                                                state.add_installed(new_repo.clone());
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
                                _ => {
                                    println!("\nNo candidate repositories found for '{}'.", app_name);
                                    let manual: Option<String> = match Input::<String>::new()
                                        .with_prompt(format!("Enter GitHub owner/repo for '{}' (or leave empty to skip)", app_name))
                                        .allow_empty(true)
                                        .interact_text() {
                                        Ok(s) if !s.trim().is_empty() => Some(s.trim().to_string()),
                                        _ => None,
                                    };

                                    if let Some(repo_input) = manual {
                                        let repo_input = repo_input.trim();
                                        if !repo_input.is_empty() {
                                            if repo_input.contains('/') {
                                                let selected_repo = repo_input.to_string();
                                                let mut new_repo = crate::core::state::InstalledRepo {
                                                    repo: selected_repo.clone(),
                                                    version: skipped_entry.version.clone(),
                                                    install_path: skipped_entry.install_path.clone(),
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

                                                let pb = ProgressBar::new_spinner();
                                                pb.set_style(
                                                    ProgressStyle::default_spinner()
                                                        .template("{spinner} {msg}")
                                                        .unwrap()
                                                        .tick_chars("⠁⠂⠄⡀⢀⠠⠐⠈ "),
                                                );
                                                pb.set_message(format!("Checking latest version for {}...", selected_repo));
                                                pb.enable_steady_tick(Duration::from_millis(80));

                                                match fetch_latest_release(&selected_repo, token, &retry_config).await {
                                                    Ok(Some(release)) => {
                                                        // Keep the installed version from registry scan;
                                                        // do NOT overwrite with latest release tag
                                                        state.add_installed(new_repo.clone());
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
                                            } else {
                                                println!("Invalid format. Expected 'owner/repo'.");
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

        let tracked = state.list_installed();
        let matched = tracked.into_iter().cloned().collect::<Vec<_>>();
        if !args.quiet && !matched.is_empty() {
            println!("\nChecking {} managed repositories for updates...", matched.len());
        }
        let mut already_checked: std::collections::HashSet<String> = std::collections::HashSet::new();
        for repo in matched {
            if let Some(ref target) = args.repo {
                if &repo.repo != target {
                    continue;
                }
            }
            if repo.repo.to_lowercase().contains("obtainhub") {
                continue;
            }
            if already_checked.contains(&repo.repo) {
                continue;
            }
            already_checked.insert(repo.repo.clone());
            match fetch_latest_release(&repo.repo, token, &retry_config).await {
                Ok(Some(release)) => {
                    let latest_version = release.tag_name;
                    if normalize_version(&latest_version) != normalize_version(&repo.version) {
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

    if args.all && !skipped.is_empty() {
        let mut sorted_skipped: Vec<&crate::core::state::InstalledRepo> = skipped.iter().collect();
        sorted_skipped.sort_by(|a, b| a.repo.to_lowercase().cmp(&b.repo.to_lowercase()));

        println!("\nUnmanaged applications found on this system:");
        for (i, entry) in sorted_skipped.iter().enumerate() {
            println!("  {}. {}", i + 1, entry.repo);
        }

        let all_app_names: Vec<String> = sorted_skipped.iter().map(|e| e.repo.clone()).collect();
        let skipped_by_name: HashMap<String, crate::core::state::InstalledRepo> = sorted_skipped.iter()
            .map(|e| (e.repo.clone(), (**e).clone()))
            .collect();
        let selections = MultiSelect::with_theme(&theme)
            .with_prompt("Select apps to manage with ObtainHub (Space to select, Enter to confirm)")
            .items(&all_app_names)
            .interact_opt()?;

        if let Some(selected_indices) = selections {
            for idx in selected_indices {
                let app_name = &all_app_names[idx];

                match find_candidate_repos(app_name, token, &retry_config).await {
                    Ok(candidates) if !candidates.is_empty() => {
                        let mut sorted_candidates: Vec<&String> = candidates.iter().collect();
                        sorted_candidates.sort();

                        let choice = Select::with_theme(&theme)
                            .with_prompt(format!("Choose repository for '{}'", app_name))
                            .items(&sorted_candidates)
                            .default(0)
                            .interact_opt()?;

                        if let Some(repo_idx) = choice {
                            let selected_repo = sorted_candidates[repo_idx].clone();
                            let skipped_entry = skipped_by_name.get(app_name);
                            let mut new_repo = crate::core::state::InstalledRepo {
                                repo: selected_repo.clone(),
                                version: skipped_entry.map(|e| e.version.clone()).unwrap_or_else(|| "unknown".to_string()),
                                install_path: skipped_entry.map(|e| e.install_path.clone()).unwrap_or_default(),
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

                            let pb = ProgressBar::new_spinner();
                            pb.set_style(
                                ProgressStyle::default_spinner()
                                    .template("{spinner} {msg}")
                                    .unwrap()
                                    .tick_chars("⠁⠂⠄⡀⢀⠠⠐⠈ "),
                            );
                            pb.set_message(format!("Checking latest version for {}...", selected_repo));
                            pb.enable_steady_tick(Duration::from_millis(80));

                            match fetch_latest_release(&selected_repo, token, &retry_config).await {
                                Ok(Some(release)) => {
                                    // Keep the installed version from registry scan;
                                    // do NOT overwrite with latest release tag
                                    state.add_installed(new_repo.clone());
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
                    Ok(_) => {
                        println!("\nNo candidate repositories found for '{}'.", app_name);
                        let skipped_entry = skipped_by_name.get(app_name);
                        let manual: Option<String> = match Input::<String>::new()
                            .with_prompt(format!("Enter GitHub owner/repo for '{}' (or leave empty to skip)", app_name))
                            .allow_empty(true)
                            .interact_text() {
                            Ok(s) if !s.trim().is_empty() => Some(s.trim().to_string()),
                            _ => None,
                        };

                        if let Some(repo_input) = manual {
                            let repo_input = repo_input.trim();
                            if !repo_input.is_empty() {
                                if repo_input.contains('/') {
                                    let selected_repo = repo_input.to_string();
                                    let mut new_repo = crate::core::state::InstalledRepo {
                                        repo: selected_repo.clone(),
                                        version: skipped_entry.map(|e| e.version.clone()).unwrap_or_else(|| "unknown".to_string()),
                                        install_path: skipped_entry.map(|e| e.install_path.clone()).unwrap_or_default(),
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

                                    let pb = ProgressBar::new_spinner();
                                    pb.set_style(
                                        ProgressStyle::default_spinner()
                                            .template("{spinner} {msg}")
                                            .unwrap()
                                            .tick_chars("⠁⠂⠄⡀⢀⠠⠐⠈ "),
                                    );
                                    pb.set_message(format!("Checking latest version for {}...", selected_repo));
                                    pb.enable_steady_tick(Duration::from_millis(80));

                                    match fetch_latest_release(&selected_repo, token, &retry_config).await {
                                        Ok(Some(release)) => {
                                            // Keep the installed version from registry scan;
                                            // do NOT overwrite with latest release tag
                                            state.add_installed(new_repo.clone());
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
                                } else {
                                    println!("Invalid format. Expected 'owner/repo'.");
                                }
                            }
                        }
                    }
                    Err(_) => {
                        println!("\nNo candidate repositories found for '{}'.", app_name);
                    }
                }
            }
        }

        let tracked = state.list_installed();
        let matched = tracked.into_iter().cloned().collect::<Vec<_>>();
        if !args.quiet && !matched.is_empty() {
            println!("\nChecking {} managed repositories for updates...", matched.len());
        }
        let mut already_checked: std::collections::HashSet<String> = std::collections::HashSet::new();
        for repo in matched {
            if let Some(ref target) = args.repo {
                if &repo.repo != target {
                    continue;
                }
            }
            if repo.repo.to_lowercase().contains("obtainhub") {
                continue;
            }
            if already_checked.contains(&repo.repo) {
                continue;
            }
            already_checked.insert(repo.repo.clone());
            match fetch_latest_release(&repo.repo, token, &retry_config).await {
                Ok(Some(release)) => {
                    let latest_version = release.tag_name;
                    if normalize_version(&latest_version) != normalize_version(&repo.version) {
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

    Ok(())
}

async fn fetch_latest_release(repo: &str, token: Option<&str>, retry_config: &RetryConfig) -> Result<Option<GitHubRelease>> {
    let url = format!("https://api.github.com/repos/{}/releases/latest", repo);
    let token_clone = token.map(|s| s.to_string());

    let result = execute_with_retry(retry_config, || {
        let url = url.clone();
        let token = token_clone.clone();
        async move {
            let has_token = token.is_some();
            let mut req = minreq::get(&url).with_header("User-Agent", "ObtainHub/3.0.0");
            if let Some(token) = token {
                req = req.with_header("Authorization", &format!("Bearer {}", token));
            }
            let resp = req.send()?;

            if resp.status_code == 403 {
                if !has_token {
                    return Err(anyhow::anyhow!("Rate limited or access denied. Set GitHub token with 'ohub config set github_token <token>'"));
                }
                return Err(anyhow::anyhow!("GitHub API rate limited or access denied. Check your GitHub token."));
            }

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
                        let publisher: Option<String> = subkey.get_value("Publisher").ok();
                        let uninstall_string: Option<String> = subkey.get_value("UninstallString").ok();

                        let install_location: Option<String> = subkey.get_value("InstallLocation").ok();

                        if let Some(name) = display_name {
                            if name.contains("ObtainHub") {
                                continue;
                            }

                            // Best source: InstallLocation (folder path, often set by MSI)
                            // Fall back: extract directory from UninstallString
                            let install_path = install_location
                                .map(PathBuf::from)
                                .or_else(|| {
                                    uninstall_string.as_deref().and_then(|s| {
                                        let s = s.trim().trim_matches('"');
                                        PathBuf::from(s).parent().map(|p| p.to_path_buf())
                                    })
                                })
                                .unwrap_or_default();

                            let key = format!("{}|{}", name, display_version.clone().unwrap_or_default());
                            if seen.insert(key) {
                                results.push(crate::core::state::InstalledRepo {
                                    repo: name.clone(),
                                    version: display_version.unwrap_or_else(|| "unknown".to_string()),
                                    install_path,
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

fn partition_gitHub_managed(
    all: &[crate::core::state::InstalledRepo],
    tracked: &[&crate::core::state::InstalledRepo],
) -> (Vec<crate::core::state::InstalledRepo>, Vec<crate::core::state::InstalledRepo>) {
    let mut matched = Vec::new();
    let mut skipped = Vec::new();

    for entry in all {
        let name = entry.repo.to_ascii_lowercase();

        if name.contains("obtainhub") {
            continue;
        }

        if let Some(tracked) = tracked.iter().find(|r| {
            let n = r.repo.to_ascii_lowercase();
            n == name || name.ends_with(&n) || n.ends_with(&name)
        }) {
            matched.push(crate::core::state::InstalledRepo {
                repo: tracked.repo.clone(),
                // Use the registry scan version (actual installed version from Windows),
                // not potentially stale state.json version from previous runs
                version: entry.version.clone(),
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
            skipped.push(entry.clone());
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
    let cleaned = clean_app_name(name);

    // Build multiple search term candidates to maximize hit rate
    let mut search_terms: Vec<&str> = Vec::new();

    // 1. Full cleaned name
    if !cleaned.is_empty() {
        search_terms.push(cleaned.as_str());
    }

    // 2. First word of cleaned name (e.g. "OnionHop version" -> "OnionHop")
    if let Some(first) = cleaned.split_whitespace().next() {
        if !search_terms.iter().any(|&t| t == first) {
            search_terms.push(first);
        }
    }

    // 3. Original name with digits/dots removed (e.g. "OnionHop V3 version 3.8.6" -> "OnionHop  version ")
    let stripped: String = name.chars().filter(|c| !c.is_ascii_digit() && *c != '.').collect();
    let stripped = stripped.trim();
    if !stripped.is_empty() && !search_terms.iter().any(|&t| t == stripped) {
        search_terms.push(stripped);
    }

    // 4. Original name (last resort)
    if !search_terms.iter().any(|&t| t == name) {
        search_terms.push(name);
    }

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
                let resp = req.send()?;

                // Non-2xx means rate limit, auth error, etc. - return empty candidates
                if !(resp.status_code >= 200 && resp.status_code < 300) {
                    return Ok(Vec::new());
                }

                let body = resp.as_bytes().to_vec();
                if body.is_empty() {
                    return Ok(Vec::new());
                }
                let resp: serde_json::Value = serde_json::from_slice(&body)?;
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
                // Only propagate error if this was the last term tried
                if !term.eq(name) {
                    continue;
                }
                return Err(e);
            }
        }
    }

    Ok(all_candidates)
}

fn normalize_version(v: &str) -> String {
    let v = v.trim();
    let v = v.strip_prefix('v').or_else(|| v.strip_prefix('V')).unwrap_or(v);
    v.to_string()
}

fn clean_app_name(name: &str) -> String {
    let mut cleaned = name.to_string();

    // Remove version-like tokens and common noise words
    let noise_words = ["version", "edition", "x64", "x86", "64bit", "32bit", "64-bit", "32-bit"];

    cleaned = cleaned.split(char::is_whitespace)
        .filter(|part| {
            let lower = part.to_lowercase();
            // Skip common noise words
            if noise_words.iter().any(|&w| lower == w) {
                return false;
            }
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
        assert!(!skipped.iter().any(|e| e.repo == "ObtainHub 3.0.1"), "self must not be listed as skipped");
    }

    #[test]
    fn partition_matches_tracked_repo() {
        let tracked = vec![entry("BurntSushi/ripgrep")];
        let tracked_refs: Vec<&crate::core::state::InstalledRepo> = tracked.iter().collect();
        let all = vec![entry("ripgrep"), entry("7-Zip")];
        let (matched, skipped) = partition_gitHub_managed(&all, &tracked_refs);
        assert_eq!(matched.len(), 1);
        assert_eq!(matched[0].repo, "BurntSushi/ripgrep");
        assert_eq!(skipped.len(), 1);
        assert_eq!(skipped[0].repo, "7-Zip");
    }

    #[test]
    fn clean_app_name_strips_version() {
        assert_eq!(clean_app_name("OnionHop V3 3.8.6"), "OnionHop");
        assert_eq!(clean_app_name("OnionHop V3 version 3.8.6"), "OnionHop");
        assert_eq!(clean_app_name("Aether-GUI"), "Aether-GUI");
        assert_eq!(clean_app_name("Obsidian"), "Obsidian");
        assert_eq!(clean_app_name("7-Zip"), "7-Zip");
        assert_eq!(clean_app_name("Notepad++ x64"), "Notepad++");
        assert_eq!(clean_app_name("App Edition 2.0"), "App");
    }
}
