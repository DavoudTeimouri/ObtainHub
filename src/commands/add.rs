use crate::core::{ConfigManager, StateManager};
use crate::cli::{AddArgs, AddType};
use crate::utils::retry::{execute_with_retry, RetryConfig};
use anyhow::Result;
use std::fs;
use std::path::PathBuf;
use tracing::info;

pub async fn execute(args: AddArgs, config: &ConfigManager, state: &mut StateManager, retry_config: &RetryConfig) -> Result<()> {
    info!("Adding {} to management (type: {:?})", args.repo, args.add_type);

    let install_dir = config.get().install_dir.clone();
    let repo_name = args.name.unwrap_or_else(|| args.repo.split('/').last().unwrap_or(&args.repo).to_string());
    let install_path = args.path.map(PathBuf::from).unwrap_or_else(|| install_dir.join(&repo_name));

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
                        req = req.with_header("Authorization", &format!("Bearer {}", token));
                    }
                    let resp = req.send()?;
                    Ok(resp.status_code >= 200 && resp.status_code < 300)
                }
            }, "check_repo").await?;

            if !repo_exists {
                anyhow::bail!("Repository '{}' not found on GitHub. Please verify the owner/repo name.", args.repo);
            }

            // Standard GitHub repo add
            if install_path.exists() && !args.yes {
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
            println!("Local folder mode: not yet implemented. Path: {:?}", args.repo);
            if args.recursive {
                println!("Recursive scan: enabled");
            }
            if let Some(repo_link) = args.repo_arg {
                println!("Linked GitHub repo for updates: {}", repo_link);
            }
        }
    }
    
    Ok(())
}