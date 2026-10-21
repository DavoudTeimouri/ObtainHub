use crate::core::{ConfigManager, StateManager};
use crate::cli::RollbackArgs;
use anyhow::Result;
use tracing::info;

pub async fn execute(args: RollbackArgs, config: &ConfigManager, state: &mut StateManager) -> Result<()> {
    info!("Rolling back: {}", args.repo);
    
    // Get the entry first, then release the borrow
    let repo_to_find = args.repo.clone();
    let entry = {
        let installed = state.list_installed();
        installed.iter().find(|r| r.repo == repo_to_find).cloned()
    };
    
    let entry = match entry {
        Some(e) => e,
        None => {
            return Err(anyhow::anyhow!("Repository '{}' is not installed", args.repo));
        }
    };
    
    let prev_version = match &entry.previous_version {
        Some(v) => v.clone(),
        None => {
            return Err(anyhow::anyhow!(
                "No previous version available for '{}'. Cannot rollback.", 
                args.repo
            ));
        }
    };
    
    let prev_path = match &entry.previous_install_path {
        Some(p) => p.clone(),
        None => {
            return Err(anyhow::anyhow!(
                "No previous install path available for '{}'. Cannot rollback.", 
                args.repo
            ));
        }
    };
    
    // Confirmation unless --yes
    if !args.yes {
        println!("About to rollback {} from {} to {}", args.repo, entry.version, prev_version);
        println!("  Will restore from: {}", prev_path.display());
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
    
    // Remove current installation
    if entry.install_path.exists() {
        std::fs::remove_dir_all(&entry.install_path)?;
        println!("Removed current installation: {}", entry.install_path.display());
    }
    
    // Restore previous version if path exists
    if prev_path.exists() {
        // Copy previous installation back
        copy_dir_all(&prev_path, &entry.install_path)?;
        println!("Restored previous version from: {}", prev_path.display());
    } else {
        return Err(anyhow::anyhow!(
            "Previous installation path no longer exists: {}. Cannot rollback automatically.", 
            prev_path.display()
        ));
    }
    
    // Update state
    let repo_entry = crate::core::state::InstalledRepo {
        repo: args.repo.clone(),
        version: prev_version.clone(),
        install_path: entry.install_path.clone(),
        installed_at: entry.installed_at,
        updated_at: Some(chrono::Utc::now()),
        checksum: entry.checksum.clone(),
        metadata: entry.metadata.clone(),
        previous_version: Some(entry.version.clone()),  // Current becomes previous
        previous_install_path: Some(entry.install_path.clone()),
        dependencies: entry.dependencies.clone(),
        is_dependency: entry.is_dependency,
        uninstaller: entry.uninstaller.clone(),
    };
    
    state.add_installed(repo_entry);
    state.save()?;
    
    println!("Successfully rolled back {} to {}", args.repo, prev_version);
    Ok(())
}

fn copy_dir_all(src: &std::path::Path, dst: &std::path::Path) -> Result<()> {
    std::fs::create_dir_all(dst)?;
    for entry in std::fs::read_dir(src)? {
        let entry = entry?;
        let ty = entry.file_type()?;
        if ty.is_dir() {
            copy_dir_all(&entry.path(), &dst.join(entry.file_name()))?;
        } else {
            std::fs::copy(entry.path(), dst.join(entry.file_name()))?;
        }
    }
    Ok(())
}