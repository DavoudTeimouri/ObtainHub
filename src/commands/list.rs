use crate::core::{ConfigManager, StateManager, find_entry_for_repo, scan_uninstall_entries};
use crate::cli::ListArgs;
use anyhow::Result;
use tracing::info;
use comfy_table::{Table, Cell};
use std::path::PathBuf;

pub async fn execute(args: ListArgs, _config: &ConfigManager, state: &StateManager) -> Result<()> {
    info!("Listing installed repositories");
    
    let installed = state.list_installed();
    
    if installed.is_empty() {
        println!("No repositories installed.");
        return Ok(());
    }
    
    // Windows knows where each app really lives. The path in state.json is
    // where ObtainHub put the files it downloaded, which is not the same
    // place once the app's own installer has run (OnionHop lands in
    // AppData\Local\Programs, not in our repos\ folder).
    let registry = scan_uninstall_entries();
    
    let resolve = |repo: &crate::core::state::InstalledRepo| -> PathBuf {
        find_entry_for_repo(&registry, &repo.repo)
            .and_then(|e| e.install_dir())
            .unwrap_or_else(|| repo.install_path.clone())
    };
    
    if args.detail {
        for repo in installed {
            println!("Repository: {}", repo.repo);
            println!("  Version: {}", repo.version);
            println!("  Path: {}", resolve(&repo).display());
            println!("  Installed: {}", repo.installed_at.format("%Y-%m-%d %H:%M:%S UTC"));
            if let Some(updated) = repo.updated_at {
                println!("  Updated: {}", updated.format("%Y-%m-%d %H:%M:%S UTC"));
            }
            if let Some(checksum) = &repo.checksum {
                println!("  Checksum: {}", checksum);
            }
            println!();
        }
    } else {
        let mut table = Table::new();
        table.set_header(vec!["Repository", "Version", "Path", "Installed"]);
        
        for repo in installed {
            table.add_row(vec![
                Cell::new(&repo.repo),
                Cell::new(&repo.version),
                Cell::new(resolve(&repo).display().to_string()),
                Cell::new(repo.installed_at.format("%Y-%m-%d").to_string()),
            ]);
        }
        
        println!("{}", table);
    }
    
    Ok(())
}