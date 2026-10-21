use crate::core::{ConfigManager, StateManager, find_entry_for_repo, scan_uninstall_entries};
use crate::cli::{AddArgs, AddType};
use crate::utils::retry::{execute_with_retry, RetryConfig};
use anyhow::Result;
use std::fs;
use std::path::PathBuf;
use tracing::info;
use walkdir::WalkDir;

pub async fn execute(args: AddArgs, config: &ConfigManager, state: &mut StateManager, retry_config: &RetryConfig) -> Result<()> {
    info!("Adding {} to management (type: {:?})", args.repo, args.add_type);

    let install_dir = config.get().install_dir.clone();
    let repo_name = args.name.unwrap_or_else(|| args.repo.split('/').next_back().unwrap_or(&args.repo).to_string());
    // Prefer the app's real location on disk - Windows knows where its own
    // installer put it. Fall back to ObtainHub's managed folder.
    let install_path = match &args.path {
        Some(p) => PathBuf::from(p),
        None => {
            let entries = scan_uninstall_entries();
            find_entry_for_repo(&entries, &args.repo)
                .and_then(|e| e.install_dir())
                .unwrap_or_else(|| install_dir.join(&repo_name))
        }
    };

    // Handle different add types
    match args.add_type {
        AddType::Github => {
            // Check if GitHub repository exists before adding
            let token = config.get().github_token.as_deref();
            let repo_exists = execute_with_retry(retry_config, || {
                let repo = args.repo.clone();
                let token = token.map(|s| s.to_string());
                async move {
                    let url = format!("https://api.github.com/repos/{}", repo);
                    let mut req = minreq::get(&url).with_header("User-Agent", "ohub");
                    if let Some(token) = token {
                        req = req.with_header("Authorization", format!("Bearer {}", token));
                    }
                    let resp = req.send()?;

                    if resp.status_code == 403 {
                        return Err(anyhow::anyhow!(
                            "GitHub API rate limited or access denied (403). Set a token: ohub config set github_token <token>"
                        ));
                    }

                    Ok(resp.status_code >= 200 && resp.status_code < 300)
                }
            }, "check_repo").await?;

            if !repo_exists {
                anyhow::bail!("Repository '{}' not found on GitHub. Please verify the owner/repo name.", args.repo);
            }

            // Standard GitHub repo add
            // Only ask before creating a folder inside ObtainHub's own tree.
            // A real app folder is expected to exist already.
            if install_path.exists() && !args.yes && install_path.starts_with(&install_dir) {
                println!("Path {} already exists. Add anyway? [y/N] ", install_path.display());
                let mut input = String::new();
                std::io::stdin().read_line(&mut input)?;
                if !input.trim().eq_ignore_ascii_case("y") {
                    println!("Cancelled");
                    return Ok(());
                }
            }
            
            fs::create_dir_all(&install_path)?;
            
            let repo = crate::core::state::InstalledRepo {
                repo: args.repo.clone(),
                version: "unknown".to_string(),
                install_path: install_path.clone(),
                installed_at: chrono::Utc::now(),
                updated_at: None,
                checksum: None,
                metadata: serde_json::Value::Null,
                previous_version: None,
                previous_install_path: None,
                dependencies: Vec::new(),
                is_dependency: false,
                ..Default::default()
            };
            
            state.add_installed(repo);
            state.save()?;
            
            println!("Added {} to management at {}", args.repo, install_path.display());
            println!("Run 'ohub install {}' to download and install the repository", args.repo);
            
            // Also register as source if requested
            if args.as_source {
                println!("Note: --as-source flag noted. Source registration would need config manager mutable access.");
            }
        }
        AddType::Zip => {
            println!("ZIP archive mode: not yet implemented. Use 'ohub install' with --file for zip installs.");
        }
        AddType::Folder => {
            let folder_path = PathBuf::from(&args.repo);

            if !folder_path.exists() {
                anyhow::bail!("Folder '{}' does not exist.", args.repo);
            }

            if !folder_path.is_dir() {
                anyhow::bail!("'{}' is not a directory.", args.repo);
            }

            let shim_dir = &config.get().shim_dir;
            fs::create_dir_all(shim_dir)?;

            // Determine walk depth: recursive or top-level only
            let walker = if args.recursive {
                WalkDir::new(&folder_path).into_iter()
            } else {
                WalkDir::new(&folder_path).max_depth(1).into_iter()
            };

            let mut added_repos: Vec<crate::core::state::InstalledRepo> = Vec::new();
            let mut found_count = 0;

            for entry in walker.filter_map(|e| e.ok()) {
                let path = entry.path();

                if !path.is_file() {
                    continue;
                }

                let is_executable: bool = {
        #[cfg(windows)]
        {
            path.extension().map(|e| e == "exe").unwrap_or(false)
        }
        #[cfg(unix)]
        {
            use std::os::unix::fs::MetadataExt;
            match fs::metadata(path) {
                Ok(metadata) => metadata.mode() & 0o111 != 0,
                Err(_) => false,
            }
        }
    };

                if !is_executable {
                    continue;
                }

                let exe_name = path
                    .file_stem()
                    .unwrap_or_default()
                    .to_string_lossy()
                    .to_string();
                let shim_name = exe_name.clone();

                // Create shim
                #[cfg(windows)]
                {
                    let bat_path = shim_dir.join(format!("{}.bat", shim_name));
                    let bat_content = format!("@echo off\n\"{}\" %*\n", path.display());
                    fs::write(&bat_path, bat_content)?;
                    println!("Created shim: {} -> {}", bat_path.display(), path.display());
                }

                #[cfg(unix)]
                {
                    use std::os::unix::fs::PermissionsExt;
                    let sh_path = shim_dir.join(&shim_name);
                    let sh_content = format!("#!/bin/sh\n\"{}\" \"$@\"\n", path.display());
                    fs::write(&sh_path, &sh_content)?;
                    let mut perms = fs::metadata(&sh_path)?.permissions();
                    perms.set_mode(0o755);
                    fs::set_permissions(&sh_path, perms)?;
                    println!("Created shim: {} -> {}", sh_path.display(), path.display());
                }

                // Build metadata for linked repo / folder info
                let metadata = if let Some(repo_link) = &args.repo_arg {
                    serde_json::json!({
                        "linked_repo": repo_link,
                        "folder_path": folder_path.display().to_string(),
                        "exe_path": path.display().to_string(),
                        "app_type": "portable_folder"
                    })
                } else {
                    serde_json::json!({
                        "folder_path": folder_path.display().to_string(),
                        "exe_path": path.display().to_string(),
                        "app_type": "portable_folder"
                    })
                };

                added_repos.push(crate::core::state::InstalledRepo {
                    repo: format!("folder/{}", exe_name),
                    version: "unknown".to_string(),
                    install_path: path.to_path_buf(),
                    installed_at: chrono::Utc::now(),
                    updated_at: None,
                    checksum: None,
                    metadata,
                    previous_version: None,
                    previous_install_path: None,
                    dependencies: Vec::new(),
                    is_dependency: false,
                    ..Default::default()
                });

                println!("Added '{}' to management.", exe_name);
                found_count += 1;
            }

            // Save state once for all added repos
            for repo_entry in added_repos {
                state.add_installed(repo_entry);
            }
            state.save()?;

            if found_count == 0 {
                println!("No executable files found in '{}'.", args.repo);
            } else {
                println!(
                    "Found {} executable(s). Add {} to your PATH to use them from anywhere.",
                    found_count,
                    shim_dir.display()
                );
            }
        }
    }
    
    Ok(())
}