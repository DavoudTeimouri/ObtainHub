use crate::core::{ConfigManager, StateManager, find_entry_for_repo, scan_uninstall_entries};
use crate::cli::ListArgs;
use anyhow::Result;
use tracing::info;
use comfy_table::{Table, Cell};
use std::path::PathBuf;

pub async fn execute(args: ListArgs, _config: &ConfigManager, state: &mut StateManager) -> Result<()> {
    info!("Listing installed repositories");

    if state.list_installed().is_empty() {
        println!("No repositories installed.");
        return Ok(());
    }

    // Windows knows where each app really lives. The path in state.json is
    // where ObtainHub put the files it downloaded, which is not the same
    // place once the app's own installer has run (OnionHop lands in
    // AppData\Local\Programs, not in our repos\ folder).
    let registry = scan_uninstall_entries();

    // Resolve every app against the registry, and collect the ones whose
    // recorded path is wrong so it can be corrected below.
    let mut rows: Vec<(String, String, PathBuf, String, Option<String>, Option<String>)> = Vec::new();
    let mut fixes: Vec<crate::core::state::InstalledRepo> = Vec::new();
    for repo in state.list_installed() {
        let path = find_entry_for_repo(&registry, &repo.repo, Some(&repo.version))
            .and_then(|e| e.install_dir())
            .unwrap_or_else(|| repo.install_path.clone());
        if path != repo.install_path {
            let mut fixed = repo.clone();
            fixed.install_path = path.clone();
            fixes.push(fixed);
        }
        rows.push((
            repo.repo.clone(),
            repo.version.clone(),
            path,
            repo.installed_at.format("%Y-%m-%d %H:%M:%S UTC").to_string(),
            repo.updated_at.map(|u| u.format("%Y-%m-%d %H:%M:%S UTC").to_string()),
            repo.checksum.clone(),
        ));
    }

    // Write the real path back to state.json so the TUI, `ohub uninstall`
    // and the next `ohub list` all agree on where the app lives.
    if !fixes.is_empty() {
        for fixed in fixes {
            state.add_installed(fixed);
        }
        state.save()?;
    }

    if args.detail {
        for (repo, version, path, installed, updated, checksum) in &rows {
            println!("Repository: {}", repo);
            println!("  Version: {}", version);
            println!("  Path: {}", path.display());
            println!("  Installed: {}", installed);
            if let Some(updated) = updated {
                println!("  Updated: {}", updated);
            }
            if let Some(checksum) = checksum {
                println!("  Checksum: {}", checksum);
            }
            println!();
        }
    } else {
        let mut table = Table::new();
        table.set_header(vec!["Repository", "Version", "Path", "Installed"]);

        for (repo, version, path, installed, _, _) in &rows {
            table.add_row(vec![
                Cell::new(repo),
                Cell::new(version),
                Cell::new(path.display().to_string()),
                Cell::new(installed.clone()),
            ]);
        }

        println!("{}", table);
    }

    Ok(())
}