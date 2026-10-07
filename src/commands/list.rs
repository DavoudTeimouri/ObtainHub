use crate::core::{ConfigManager, StateManager};
use crate::cli::ListArgs;
use anyhow::Result;
use tracing::info;
use comfy_table::{Table, Cell, Attribute};

pub async fn execute(args: ListArgs, config: &ConfigManager, state: &StateManager) -> Result<()> {
    info!("Listing installed repositories");
    
    let installed = state.list_installed();
    
    if installed.is_empty() {
        println!("No repositories installed.");
        return Ok(());
    }
    
    if args.detail {
        for repo in installed {
            println!("Repository: {}", repo.repo);
            println!("  Version: {}", repo.version);
            println!("  Path: {}", repo.install_path.display());
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
                Cell::new(&repo.install_path.display().to_string()),
                Cell::new(&repo.installed_at.format("%Y-%m-%d").to_string()),
            ]);
        }
        
        println!("{}", table);
    }
    
    Ok(())
}