use crate::core::{ConfigManager, StateManager};
use crate::cli::UninstallArgs;
use anyhow::Result;
use tracing::info;
use std::fs;

pub async fn execute(args: UninstallArgs, config: &mut ConfigManager, state: &mut StateManager) -> Result<()> {
    info!("Uninstalling: {}", args.repo);
    let installed = state.list_installed();
    let repo_entry = installed.iter().find(|r| r.repo == args.repo);
    
    let entry = match repo_entry {
        Some(e) => e,
        None => {
            return Err(anyhow::anyhow!("Repository '{}' is not installed", args.repo));
        }
    };
    
    // Confirmation unless --yes
    if !args.yes {
        println!("About to uninstall {}@{} from {}", args.repo, entry.version, entry.install_path.display());
        if args.purge {
            println!("  Also removing config and data (--purge)");
        }
        print!("Continue? [y/N] ");
        use std::io::{stdout, Write};
        stdout().flush()?;
        let mut input = String::new();
        std::io::stdin().read_line(&mut input)?;
        if !input.trim().eq_ignore_ascii_case("y") {
            println!("Cancelled.");
            return Ok(());
        }
    }
    
    // Remove installation directory
    if entry.install_path.exists() {
        fs::remove_dir_all(&entry.install_path)?;
        println!("Removed installation directory: {}", entry.install_path.display());
    }
    
    // Remove from state
    state.remove_installed(&args.repo);
    state.save()?;
    
    if args.purge {
        // No per-repo config files exist — state is one state.json plus group membership.
        state.get_mut().metadata.remove(&args.repo);
        state.save()?;
        
        let cfg = config.get_mut();
        let mut dropped = Vec::new();
        for (group, members) in cfg.groups.iter_mut() {
            let before = members.len();
            members.retain(|m| m != &args.repo);
            if members.len() != before {
                dropped.push(group.clone());
            }
        }
        config.save()?;
        
        println!("  Purged metadata and group entries{}", 
            if dropped.is_empty() { String::new() } 
            else { format!(" (groups: {})", dropped.join(", ")) });
    }
    
    println!("Successfully uninstalled {}", args.repo);
    Ok(())
}