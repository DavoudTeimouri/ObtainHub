use crate::core::{ConfigManager, StateManager};
use crate::cli::ResetArgs;
use anyhow::{Context, Result};
use std::fs;
use std::path::PathBuf;
use std::io::Write;
use tracing::info;
use zip::CompressionMethod;
use zip::write::FileOptions;

pub async fn execute(args: ResetArgs, config: &mut ConfigManager, state: &mut StateManager) -> Result<()> {
    info!("Reset command");

    // Create backup if requested
    if let Some(backup_path) = &args.backup {
        let backup_path = PathBuf::from(backup_path);
        println!("Creating backup at {}...", backup_path.display());
        create_backup(&backup_path, config, state)?;
        println!("Backup created successfully.");
    }

    // Capture the token BEFORE the reset — config.reset() wipes github_token, so
    // reading it afterwards (as this used to) always found nothing.
    let existing_token = config.get().github_token.clone();

    // Reset config
    println!("Resetting configuration...");
    config.reset()?;
    println!("Configuration reset to defaults.");

    // Reset state
    println!("Resetting state...");
    state.clear()?;
    println!("State cleared.");

    // The token lives in config, not the keyring (keyring is declared but unwired),
    // so the reset above already removed it. --keep-token means "put it back".
    match (&existing_token, args.keep_token, &args.move_token) {
        (Some(token), true, _) => {
            config.get_mut().github_token = Some(token.clone());
            config.save()?;
            println!("GitHub token preserved.");
        }
        (Some(_), false, Some(path)) => {
            let dest = PathBuf::from(path);
            if let Some(parent) = dest.parent() {
                fs::create_dir_all(parent)?;
            }
            fs::write(&dest, existing_token.as_deref().unwrap_or_default())
                .with_context(|| format!("Failed to write token to {}", dest.display()))?;
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                fs::set_permissions(&dest, fs::Permissions::from_mode(0o600))?;
            }
            println!("GitHub token written to {}", dest.display());
        }
        (Some(_), false, None) => {
            println!("GitHub token cleared.");
        }
        (None, _, _) => {
            println!("No GitHub token stored.");
        }
    }

    println!("\nReset complete.");
    Ok(())
}

fn create_backup(path: &PathBuf, config: &ConfigManager, state: &StateManager) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }

    let file = fs::File::create(path)?;
    let mut zip = zip::ZipWriter::new(file);
    let options = FileOptions::default().compression_method(CompressionMethod::Deflated);

    // Backup config — strip the GitHub token. The backup archive is meant to be
    // copied around, and config.toml holds the token in plaintext.
    let mut scrubbed = config.get().clone();
    scrubbed.github_token = None;
    let config_toml = toml::to_string_pretty(&scrubbed)?;
    zip.start_file("config.toml", options)?;
    zip.write_all(config_toml.as_bytes())?;

    // Backup state
    let state_json = serde_json::to_string_pretty(state.get())?;
    zip.start_file("state.json", options)?;
    zip.write_all(state_json.as_bytes())?;

    zip.finish()?;
    Ok(())
}