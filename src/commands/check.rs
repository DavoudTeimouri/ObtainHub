use crate::core::{ConfigManager, StateManager};
use crate::cli::CheckArgs;
use crate::utils::retry::{execute_with_retry, RetryConfig};
use anyhow::Result;
use minreq;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::time::Duration;
use tracing::info;
use comfy_table::{Table, Cell};
use urlencoding;
use dialoguer::{Select, MultiSelect, theme::ColorfulTheme, Input};
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
    let mut log_lines: Vec<String> = Vec::new();

    // Say what the scan does before doing it - "--all" and "--candidates"
    // read the whole uninstall registry, which is not obvious from the name.
    if !args.quiet {
        if args.all {
            println!("=== ohub check --all : full system scan ===");
            println!();
            println!("What it does:");
            println!("  Finds every program installed on this PC and sorts them into");
            println!("  'already managed by ObtainHub' and 'not managed yet'.");
            println!("  Managed apps get their version refreshed from the Windows registry");
            println!("  and are then checked for updates. Unmanaged apps are listed so you");
            println!("  can pick the ones you want ObtainHub to look after.");
            println!();
            println!("  Example: you installed OnionHop by hand. This finds it, finds its");
            println!("  GitHub repo, and adds it to `ohub list` - so from then on");
            println!("  `ohub update` can update it for you.");
            println!();
            println!("  Use `ohub check` on its own to only check apps you already manage,");
            println!("  and `ohub check --candidates` to only look for repos to adopt.");
            println!();
        } else if args.candidates {
            println!("=== ohub check --candidates : find GitHub repos for apps you do not manage ===");
            println!();
            println!("What it does:");
            println!("  Reads every program installed on this PC, then looks for a GitHub");
            println!("  repository for the ones ObtainHub does not manage yet, so you can");
            println!("  decide which apps to hand over to `ohub update`.");
            println!();
            println!("  Use `ohub check --all` to also check the apps you already manage.");
            println!();
        }
    }

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
        let (matched, skipped) = partition_git_hub_managed(&all, &tracked);

        pb.finish_with_message(format!("Scanned {} installed programs.", all.len()));
        if !skipped.is_empty() {
            println!("  {} of them are not managed by ObtainHub.", skipped.len());
        }
        (matched, skipped)
    } else {
        (state.list_installed().into_iter().cloned().collect(), Vec::new())
    };

    // Counts for the closing summary; `matched` is consumed by the loop below.
    let managed_count = matched.len();
    let unmanaged_count = skipped.len();

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
        check_self_update(config, state, args.quiet, &retry_config).await?;
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
                if crate::core::normalize_version(&latest_version) != crate::core::normalize_version(&repo.version) {
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
            sorted_skipped.sort_by_key(|a| a.repo.to_lowercase());

            // ---- Vendor exclusion: let user skip known non-GitHub vendors ----
            let mut vendors: Vec<String> = Vec::new();
            for entry in &sorted_skipped {
                let v = extract_vendor(&entry.repo);
                if !vendors.iter().any(|x| x == &v) {
                    vendors.push(v);
                }
            }
            vendors.sort();
            let default_excluded: Vec<bool> = vendors
                .iter()
                .map(|v| {
                    matches!(
                        v.as_str(),
                        "Microsoft" | "Adobe" | "Oracle" | "Apple" | "Intel" | "NVIDIA" | "AMD"
                    )
                })
                .collect();
            let excluded_vendors: Vec<String> = if !vendors.is_empty() {
                let selections = MultiSelect::with_theme(&theme)
                    .with_prompt("Exclude vendors from GitHub candidate search (Space to select, Enter to confirm)")
                    .items(&vendors)
                    .defaults(&default_excluded)
                    .interact_opt()?;
                match selections {
                    Some(idx) => idx.iter().map(|i| vendors[*i].clone()).collect(),
                    None => Vec::new(),
                }
            } else {
                Vec::new()
            };
            let excluded_set: std::collections::HashSet<String> = excluded_vendors.iter().cloned().collect();

            // Filter out apps from excluded vendors
            sorted_skipped.retain(|entry| !excluded_set.contains(&extract_vendor(&entry.repo)));

            if sorted_skipped.is_empty() {
                println!("All unmanaged apps are from excluded vendors. Nothing to search.");
            } else {
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
                                        let new_repo = crate::core::state::InstalledRepo {
                                            repo: selected_repo.clone(),
                                            version: skipped_entry.version.clone(),
                                            install_path: skipped_entry.install_path.clone(),
                                            uninstaller: skipped_entry.uninstaller.clone(),
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
                                                let new_repo = crate::core::state::InstalledRepo {
                                                    repo: selected_repo.clone(),
                                                    version: skipped_entry.version.clone(),
                                                    install_path: skipped_entry.install_path.clone(),
                                                    uninstaller: skipped_entry.uninstaller.clone(),
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
        }
    }

    if args.all && !skipped.is_empty() {
        let mut sorted_skipped: Vec<&crate::core::state::InstalledRepo> = skipped.iter().collect();
        sorted_skipped.sort_by_key(|a| a.repo.to_lowercase());

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
                            let new_repo = crate::core::state::InstalledRepo {
                                repo: selected_repo.clone(),
                                version: skipped_entry.map(|e| e.version.clone()).unwrap_or_else(|| "unknown".to_string()),
                                install_path: skipped_entry.map(|e| e.install_path.clone()).unwrap_or_default(),
                                uninstaller: skipped_entry.and_then(|e| e.uninstaller.clone()),
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
                                    let new_repo = crate::core::state::InstalledRepo {
                                        repo: selected_repo.clone(),
                                        version: skipped_entry.map(|e| e.version.clone()).unwrap_or_else(|| "unknown".to_string()),
                                        install_path: skipped_entry.map(|e| e.install_path.clone()).unwrap_or_default(),
                                        uninstaller: skipped_entry.and_then(|e| e.uninstaller.clone()),
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
                    if crate::core::normalize_version(&latest_version) != crate::core::normalize_version(&repo.version) {
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
            for (repo, current_ver, latest_ver) in &outdated {
                table.add_row(vec![Cell::new(repo), Cell::new(current_ver), Cell::new(latest_ver)]);
            }
            println!("{}", table);
            if args.notes {
                print_release_notes(&outdated, token, &retry_config).await;
            }
        }
        return Ok(());
    }

    if !outdated.is_empty() {
        println!("Outdated ({}):", outdated.len());
        let mut table = Table::new();
        table.set_header(vec!["Repository", "Current", "Latest"]);
        for (repo, current_ver, latest_ver) in &outdated {
            table.add_row(vec![Cell::new(repo), Cell::new(current_ver), Cell::new(latest_ver)]);
            log_lines.push(format!("  {repo} {current_ver} -> {latest_ver}"));
        }
        println!("{}", table);
        println!();
        if args.notes {
            print_release_notes(&outdated, token, &retry_config).await;
        }
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
            log_lines.push(format!("  ERROR {repo}: {error}"));
        }
        println!();
    }

    // One closing line so the result is obvious without reading the tables.
    if !args.outdated_only {
        let summary = if args.all || args.candidates {
            format!(
                "Summary: {} managed by ObtainHub, {} not managed, {} outdated, {} up to date.",
                managed_count,
                unmanaged_count,
                outdated.len(),
                current.len()
            )
        } else {
            format!(
                "Summary: {} checked, {} outdated, {} up to date.",
                managed_count,
                outdated.len(),
                current.len()
            )
        };
        log_lines.push(summary.clone());
        if !args.quiet {
            println!("{summary}");
            if (args.all || args.candidates) && unmanaged_count > 0 && !args.candidates {
                println!(
                    "  The {} unmanaged app(s) are listed above - pick the ones you want to manage.",
                    unmanaged_count
                );
            }
            println!();
        }
    }

    // A scheduled run leaves a record behind: the report goes to the log file
    // even when the console output is suppressed.
    if let Some(log_path) = &args.log {
        if let Some(parent) = std::path::Path::new(log_path).parent() {
            fs::create_dir_all(parent)?;
        }
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(log_path)?;
        writeln!(file, "--- {} ---", chrono::Utc::now().format("%Y-%m-%d %H:%M:%S UTC"))?;
        for line in &log_lines {
            writeln!(file, "{line}")?;
        }
    }

    // Offer to update the outdated apps straight away.
    if !outdated.is_empty() && !args.quiet && !args.outdated_only {
        let count = outdated.len();
        let proceed = if args.yes {
            true
        } else {
            let theme = dialoguer::theme::ColorfulTheme::default();
            dialoguer::Confirm::with_theme(&theme)
                .with_prompt(format!("Update {count} outdated app(s) now?"))
                .default(false)
                .interact_opt()?
                .unwrap_or(false)
        };
        if proceed {
            let update_args = crate::cli::UpdateArgs {
                repo: None,
                prerelease: args.prerelease,
                dry_run: false,
                force: false,
                skip_deps: false,
                arch: args.arch,
                yes: args.yes,
                reset: false,
                interactive: false,
                notes: false,
                quiet: false,
                log: None,
            };
            if let Err(e) =
                crate::commands::update::execute(update_args, config, state, &retry_config).await
            {
                eprintln!("Update failed: {e}");
            }
        }
    }

    Ok(())
}

/// Print the release notes of the given repos - the `check --notes` output.
async fn print_release_notes(
    repos: &[(String, String, String)],
    token: Option<&str>,
    retry_config: &RetryConfig,
) {
    for (repo, _, _) in repos {
        let block = crate::core::registries::release_notes_block(repo, token, retry_config).await;
        print!("{block}");
    }
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
                req = req.with_header("Authorization", format!("Bearer {}", token));
            }
            let resp = req.send()?;

            if resp.status_code == 403 {
                return Err(anyhow::anyhow!(
                    "GitHub API rate limited or access denied (403). Set a token: ohub config set github_token <token>"
                ));
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

    let mut results = Vec::new();
    let mut seen = HashSet::new();

    for entry in crate::core::scan_uninstall_entries() {
        // Read the whole entry before moving `display_name` out of it.
        let install_path = entry.install_dir().unwrap_or_default();
        let uninstaller = if entry.uninstall_string.is_empty() {
            None
        } else {
            Some(entry.uninstall_string.clone())
        };

        let name = entry.display_name;
        if name.contains("ObtainHub") {
            continue;
        }

        let key = format!("{}|{}", name, entry.display_version);
        if !seen.insert(key) {
            continue;
        }

        results.push(crate::core::state::InstalledRepo {
            repo: name,
            version: if entry.display_version.is_empty() {
                "unknown".to_string()
            } else {
                entry.display_version.clone()
            },
            install_path,
            installed_at: chrono::Utc::now(),
            updated_at: None,
            checksum: None,
            metadata: serde_json::Value::Null,
            previous_version: None,
            previous_install_path: None,
            dependencies: Vec::new(),
            is_dependency: false,
            uninstaller,
        });
    }

    Ok(results)
}

#[cfg(not(windows))]
fn enumerate_all_installed_software() -> Result<Vec<crate::core::state::InstalledRepo>> {
    Ok(Vec::new())
}

fn partition_git_hub_managed(
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
                // Prefer the stored uninstaller; fall back to the registry scan
                // for entries tracked before uninstallers were recorded.
                uninstaller: tracked
                    .uninstaller
                    .clone()
                    .or_else(|| entry.uninstaller.clone()),
            });
        } else {
            skipped.push(entry.clone());
        }
    }

    (matched, skipped)
}

async fn check_self_update(
    config: &ConfigManager,
    state: &StateManager,
    _quiet: bool,
    retry_config: &RetryConfig,
) -> Result<()> {
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
    self_update_execute(args, config, state, retry_config).await
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
        if !search_terms.contains(&first) {
            search_terms.push(first);
        }
    }

    // 3. Original name with digits/dots removed (e.g. "OnionHop V3 version 3.8.6" -> "OnionHop  version ")
    let stripped: String = name.chars().filter(|c| !c.is_ascii_digit() && *c != '.').collect();
    let stripped = stripped.trim();
    if !stripped.is_empty() && !search_terms.contains(&stripped) {
        search_terms.push(stripped);
    }

    // 4. Original name (last resort)
    if !search_terms.contains(&name) {
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
                    req = req.with_header("Authorization", format!("Bearer {}", token));
                }
                let resp = req.send()?;

                if resp.status_code == 403 {
                    return Err(anyhow::anyhow!(
                        "GitHub API rate limited or access denied (403). Set a token: ohub config set github_token <token>"
                    ));
                }

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

/// Extract vendor name from an installed program's display name.
/// Uses known vendor keyword matching, falls back to the first word.
fn extract_vendor(name: &str) -> String {
    let known_vendors = [
        "Microsoft", "Adobe", "Oracle", "JetBrains", "Mozilla", "Google",
        "Apple", "Valve", "NVIDIA", "AMD", "Intel", "Epic Games", "Bethesda",
        "Ubisoft", "Electronic Arts", "EA", "Symantec", "McAfee", "VMware",
        "Corel", "CyberLink", "Nero", "WinRAR", "7-Zip", "VLC", "VideoLAN",
    ];
    let lower = name.to_lowercase();
    for v in &known_vendors {
        if lower.contains(&v.to_lowercase()) {
            return v.to_string();
        }
    }
    // Fall back to first word
    name.split(char::is_whitespace)
        .next()
        .unwrap_or(name)
        .to_string()
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
            ..Default::default()
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
        let (matched, skipped) = partition_git_hub_managed(&all, &tracked_refs);
        assert!(matched.is_empty(), "nothing should match an empty state");
        assert_eq!(skipped.len(), 2, "NVIDIA + 7-Zip are not managed");
        assert!(!skipped.iter().any(|e| e.repo == "ObtainHub 3.0.1"), "self must not be listed as skipped");
    }

    #[test]
    fn partition_matches_tracked_repo() {
        let tracked = [entry("BurntSushi/ripgrep")];
        let tracked_refs: Vec<&crate::core::state::InstalledRepo> = tracked.iter().collect();
        let all = vec![entry("ripgrep"), entry("7-Zip")];
        let (matched, skipped) = partition_git_hub_managed(&all, &tracked_refs);
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
