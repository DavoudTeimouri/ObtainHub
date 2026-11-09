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
    
    // Check if this repo is a dependency of another repo
    // Clone the list to avoid borrowing issues
    let all_installed: Vec<_> = state.list_installed().into_iter().cloned().collect();
    let dependents: Vec<_> = all_installed
        .iter()
        .filter(|r| r.dependencies.contains(&args.repo))
        .cloned()
        .collect();
    
    if !dependents.is_empty() && !args.force {
        println!("Warning: {} is a dependency of the following repos:", args.repo);
        for dep in &dependents {
            println!("  {}", dep.repo);
        }
        println!("Use --force to uninstall anyway (may break dependents).");
        return Ok(());
    }
    
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
    
    // Run the app's own uninstaller if its installer registered one.
    // This is what actually removes third-party apps from Program Files.
    if let Some(uninstaller) = &entry.uninstaller {
        match crate::core::run_uninstaller(uninstaller, args.interactive) {
            Ok(true) => {
                // After running the uninstaller, check if the app is still
                // detected in the Windows uninstall registry. If it is, the
                // user cancelled or the uninstaller didn't actually remove
                // anything — don't mark it as uninstalled.
                let still_installed = crate::core::winreg::scan_uninstall_entries()
                    .iter()
                    .any(|e| crate::core::winreg::find_entry_for_repo(
                        std::slice::from_ref(e),
                        &args.repo,
                        Some(&entry.version),
                    ).is_some());
                if still_installed {
                    return Err(anyhow::anyhow!(
                        "Uninstall was cancelled or did not complete — {} is still installed",
                        args.repo
                    ));
                }
                println!("Ran uninstaller: {}", uninstaller);
            }
            Ok(false) => println!("Registered uninstaller not runnable: {}", uninstaller),
            Err(e) => eprintln!("Uninstaller failed: {}", e),
        }
    }

    // Remove any leftover installation directory (uninstaller usually does this).
    if entry.install_path.exists() {
        match fs::remove_dir_all(&entry.install_path) {
            Ok(()) => println!("Removed installation directory: {}", entry.install_path.display()),
            Err(e) => eprintln!(
                "Could not remove {}: {} (run the app's uninstaller manually)",
                entry.install_path.display(),
                e
            ),
        }
    }

    // Also clean up the download/staging folder for this repo under ObtainHub's data dir.
    // The install process downloads to <data_dir>/repos/<owner>/<repo> and this
    // folder is not removed by the app's own uninstaller.
    if let Some(data_dir) = dirs::data_dir() {
        let data_dir = data_dir.join("ObtainHub");
        let repo_parts: Vec<&str> = args.repo.split('/').collect();
        if repo_parts.len() == 2 {
            let repo_folder = data_dir.join("repos").join(repo_parts[0]).join(repo_parts[1]);
            if repo_folder.exists() {
                match fs::remove_dir_all(&repo_folder) {
                    Ok(()) => println!("Removed download folder: {}", repo_folder.display()),
                    Err(e) => eprintln!(
                        "Could not remove {}: {}",
                        repo_folder.display(),
                        e
                    ),
                }
            }
        }
    }

    // Remove from state
    state.remove_installed(&args.repo);
    state.save()?;
    
    // Update other repos that had this as dependency
    // Get fresh list after removal
    let mut all_installed: Vec<_> = state.list_installed().into_iter().cloned().collect();
    for repo in &mut all_installed {
        if repo.dependencies.contains(&args.repo) {
            repo.dependencies.retain(|d| d != &args.repo);
        }
    }
    // Re-add all to update dependencies
    for repo in all_installed {
        state.add_installed(repo);
    }
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