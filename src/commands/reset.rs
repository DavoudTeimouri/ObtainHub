use crate::core::{ConfigManager, StateManager};
use crate::cli::ResetArgs;
use anyhow::Result;
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

    // Handle token
    if args.move_token.is_some() || !args.keep_token {
        // Clear token from keyring if not keeping
        if !args.keep_token {
            println!("Note: GitHub token removal from keyring not implemented in this version");
        }
    }

    // Reset config
    println!("Resetting configuration...");
    config.reset()?;
    println!("Configuration reset to defaults.");

    // Reset state
    println!("Resetting state...");
    state.clear()?;
    println!("State cleared.");

    // Handle token move if requested
    if let Some(token_path) = args.move_token {
        // This would require reading token before reset
        println!("Note: Token move not implemented in this version");
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

    // Backup config
    let config_toml = toml::to_string_pretty(config.get())?;
    zip.start_file("config.toml", options)?;
    zip.write_all(config_toml.as_bytes())?;

    // Backup state
    let state_json = serde_json::to_string_pretty(state.get())?;
    zip.start_file("state.json", options)?;
    zip.write_all(state_json.as_bytes())?;

    zip.finish()?;
    Ok(())
}