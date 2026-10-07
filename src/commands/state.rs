use crate::core::{ConfigManager, StateManager};
use crate::cli::{StateArgs, StateAction};
use anyhow::Result;
use tracing::info;

pub async fn execute(args: StateArgs, _config: &ConfigManager, state: &mut StateManager) -> Result<()> {
    info!("State command: {:?}", args.action);

    match args.action {
        StateAction::Export { file } => {
            let content = serde_json::to_string_pretty(state.get())?;
            if let Some(path) = file {
                std::fs::write(&path, content)?;
                println!("State exported to {}", path);
            } else {
                println!("{}", content);
            }
        }
        StateAction::Import { file, dry_run } => {
            let content = std::fs::read_to_string(&file)?;
            let imported: crate::core::state::State = serde_json::from_str(&content)?;
            
            let count = imported.installed.len();
            
            if dry_run {
                println!("Dry run: would import {} repos from {}", count, file);
                for repo_id in imported.installed.keys() {
                    println!("  - {}", repo_id);
                }
            } else {
                // Merge imported state
                for (repo_id, repo) in imported.installed {
                    state.add_installed(repo);
                }
                state.save()?;
                println!("Imported state from {} ({} repos)", file, count);
            }
        }
        StateAction::Validate => {
            let state_data = state.get();
            let mut issues = 0;
            
            for (repo_id, repo) in &state_data.installed {
                if !repo.install_path.exists() {
                    println!("Missing install path: {} -> {}", repo_id, repo.install_path.display());
                    issues += 1;
                }
                if repo.repo.is_empty() {
                    println!("Empty repo field: {}", repo_id);
                    issues += 1;
                }
            }
            
            if issues == 0 {
                println!("State validation passed: {} repos OK", state_data.installed.len());
            } else {
                println!("State validation failed: {} issues found", issues);
            }
        }
        StateAction::Clean => {
            let mut state_data = state.get_mut();
            let original_count = state_data.installed.len();
            
            state_data.installed.retain(|repo_id, repo| {
                let exists = repo.install_path.exists() && !repo.repo.is_empty();
                if !exists {
                    println!("Removing orphaned entry: {} -> {}", repo_id, repo.install_path.display());
                }
                exists
            });
            
            let removed = original_count - state_data.installed.len();
            if removed > 0 {
                state.save()?;
                println!("Cleaned {} orphaned entries", removed);
            } else {
                println!("No orphaned entries found");
            }
        }
    }

    Ok(())
}