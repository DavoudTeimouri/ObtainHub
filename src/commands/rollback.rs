use crate::core::{ConfigManager, StateManager};
use crate::cli::RollbackArgs;
use crate::utils::retry::RetryConfig;
use anyhow::Result;
use tracing::info;

/// Roll a managed app back to its previous version.
///
/// The old version is re-downloaded from its GitHub release tag and installed
/// again, so rollback works for installer-based apps without keeping a local
/// copy of every previous install.
pub async fn execute(
    args: RollbackArgs,
    config: &ConfigManager,
    state: &mut StateManager,
    retry_config: &RetryConfig,
) -> Result<()> {
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
    
    // Confirmation unless --yes
    if !args.yes {
        println!("About to rollback {} from {} to {}", args.repo, entry.version, prev_version);
        println!("  Will re-download and install {prev_version} from GitHub");
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

    let token = config.get().github_token.as_deref();

    // Find the release for the old tag.
    let release = match crate::commands::update::fetch_release_by_tag(
        &args.repo,
        &prev_version,
        token,
        retry_config,
    )
    .await?
    {
        Some(r) => Some(r),
        None => {
            // The stored version has no "v" prefix but the GitHub tag usually
            // does ("3.8.6" vs "v3.8.6"). Try the other form.
            let tagged = format!("v{prev_version}");
            if tagged == prev_version {
                None
            } else {
                crate::commands::update::fetch_release_by_tag(
                    &args.repo,
                    &tagged,
                    token,
                    retry_config,
                )
                .await?
            }
        }
    };

    let release = match release {
        Some(r) => r,
        None => {
            return Err(anyhow::anyhow!(
                "Release {} not found for '{}'. It may have been deleted from GitHub.",
                prev_version,
                args.repo
            ));
        }
    };

    // Pick the installer asset for that release.
    let asset = crate::commands::update::select_installer_asset(&release, &args.arch, args.quiet)?;

    println!("Reinstalling {} {}...", args.repo, prev_version);

    // Install the old version. The version we roll back from becomes the new
    // "previous", so the rollback itself can be undone.
    crate::commands::update::install_release(
        &args.repo,
        &prev_version,
        &release,
        token,
        config,
        state,
        Some(asset),
        args.quiet,
        Some(entry.version.clone()),
        &args.arch,
    )
    .await?;

    if !args.quiet {
        println!("Successfully rolled back {} to {}", args.repo, prev_version);
    }
    Ok(())
}
