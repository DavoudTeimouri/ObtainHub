use crate::core::{ConfigManager, StateManager};
use crate::cli::RemoveArgs;
use anyhow::Result;
use tracing::info;

pub async fn execute(args: RemoveArgs, _config: &ConfigManager, state: &mut StateManager) -> Result<()> {
    info!("Removing {} from management", args.repo);
    
    let install_path = state.get_installed(&args.repo).map(|r| r.install_path.clone());
    
    if let Some(path) = install_path {
        if !args.dry_run {
            if !args.yes {
                println!("Remove {} from management? [y/N] ", args.repo);
                let mut input = String::new();
                std::io::stdin().read_line(&mut input)?;
                if !input.trim().eq_ignore_ascii_case("y") {
                    println!("Cancelled");
                    return Ok(());
                }
            }
            
            state.remove_installed(&args.repo);
            state.save()?;
            println!("Removed {} from management (files kept at {})", args.repo, path.display());
        } else {
            println!("Would remove {} from management (files kept at {})", args.repo, path.display());
        }
    } else {
        println!("Repository {} not found in management", args.repo);
    }
    
    Ok(())
}