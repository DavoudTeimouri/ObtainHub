use crate::core::{ConfigManager, StateManager};
use crate::cli::{AddArgs, AddType};
use anyhow::Result;
use std::fs;
use std::path::PathBuf;
use tracing::info;

pub async fn execute(args: AddArgs, config: &ConfigManager, state: &mut StateManager) -> Result<()> {
    info!("Adding {} to management (type: {:?})", args.repo, args.add_type);
    
    let install_dir = config.get().install_dir.clone();
    let repo_name = args.name.unwrap_or_else(|| args.repo.split('/').last().unwrap_or(&args.repo).to_string());
    let install_path = args.path.map(PathBuf::from).unwrap_or_else(|| install_dir.join(&repo_name));
    
    // Handle different add types
    match args.add_type {
        AddType::Github => {
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