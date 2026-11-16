use crate::core::{ConfigManager, StateManager};
use crate::cli::LinkRepoArgs;
use anyhow::Result;
use tracing::info;

pub async fn execute(args: LinkRepoArgs, _config: &ConfigManager, state: &mut StateManager) -> Result<()> {
    // Validate github_repo format (owner/repo)
    if !args.github_repo.contains('/')
        || args.github_repo.starts_with('/')
        || args.github_repo.ends_with('/')
    {
        anyhow::bail!(
            "github_repo must be in owner/repo format (got '{}')",
            args.github_repo
        );
    }

    info!("Linking {} to GitHub repo {}", args.repo, args.github_repo);

    // The app must already be managed under its current name.
    let existing_entry = match state.get_installed(&args.repo) {
        Some(e) => e.clone(),
        None => {
            anyhow::bail!(
                "'{}' is not managed. Add it first with 'ohub add <exe-name>' or 'ohub add --add-type folder <path>'.",
                args.repo
            );
        }
    };

    // Remove old entry (keyed by current repo name), re-add under GitHub repo name.
    state.remove_installed(&args.repo);
    let mut entry = existing_entry.clone();
    entry.repo = args.github_repo.clone();
    state.add_installed(entry);

    if let Err(e) = state.save() {
        // Rollback: restore old entry so a failed save doesn't lose the app.
        let _ = state.add_installed(existing_entry.clone());
        anyhow::bail!("Failed to save state: {}", e);
    }

    println!(
        "Linked '{}' to GitHub repo '{}'. Run 'ohub update {}' to check for releases.",
        args.repo, args.github_repo, args.github_repo
    );

    Ok(())
}
