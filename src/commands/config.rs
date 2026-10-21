use crate::core::{ConfigManager, StateManager};
use crate::cli::{ConfigArgs, ConfigAction};
use anyhow::Result;
use tracing::info;
use std::path::{Path, PathBuf};
use std::fs;
use std::io::{Read, Write};
use zip::CompressionMethod;
use zip::write::FileOptions;
use dirs;

pub async fn execute(args: ConfigArgs, config: &mut ConfigManager, state: &mut StateManager) -> Result<()> {
    match args.action {
        ConfigAction::Show => {
            // The token is not printed, even masked - it is a secret.
            let mut shown = config.get().clone();
            if shown.github_token.is_some() {
                shown.github_token = Some("[stored]".to_string());
            }
            println!("{}", toml::to_string_pretty(&shown)?);
        }
        ConfigAction::Set { key, value } => {
            // Never echo the token: it lands in shell history and CI logs.
            let secret = key == "github_token";
            if secret {
                info!("Setting config: {}", key);
            } else {
                info!("Setting config: {} = {}", key, value);
            }
            set_config_value(config, &key, &value)?;
            config.save()?;
            if secret {
                println!("Set {} = [stored]", key);
            } else {
                println!("Set {} = {}", key, value);
            }
        }
        ConfigAction::Get { key } => {
            info!("Getting config: {}", key);
            if let Some(value) = get_config_value(config, &key)? {
                println!("{} = {}", key, value);
            } else {
                println!("Key '{}' not found", key);
            }
        }
        ConfigAction::Reset => {
            info!("Resetting config to defaults");
            config.reset()?;
            println!("Config reset to defaults");
        }
        ConfigAction::Edit => {
            info!("Opening config in editor");
            let editor = std::env::var("EDITOR").unwrap_or_else(|_| "vi".to_string());
            let config_path = config.path().to_path_buf();
            let status = std::process::Command::new(editor).arg(&config_path).status()?;
            if status.success() {
                // Reload config after edit
                let content = std::fs::read_to_string(&config_path)?;
                config.config = toml::from_str(&content)?;
                println!("Config reloaded from {}", config_path.display());
            } else {
                eprintln!("Editor exited with error");
            }
        }
        ConfigAction::Path => {
            let config_path = config.path();
            let state_path = dirs::data_dir()
                .unwrap_or_else(|| dirs::home_dir().unwrap_or_default())
                .join("obtainhub")
                .join("state.json");
            println!("Config: {}", config_path.display());
            println!("State:  {}", state_path.display());
        }
        ConfigAction::Move { path } => {
            let target = PathBuf::from(path);
            fs::create_dir_all(&target)?;
            let config_path = config.path();
            let state_path = dirs::data_dir()
                .unwrap_or_else(|| dirs::home_dir().unwrap_or_default())
                .join("obtainhub")
                .join("state.json");
            
            fs::copy(config_path, target.join("config.toml"))?;
            if state_path.exists() {
                fs::copy(&state_path, target.join("state.json"))?;
            }
            println!("Config and state moved to {}", target.display());
        }
        ConfigAction::Repair => {
            println!("Repairing config and state files...");
            config.repair()?;
            state.repair()?;
            println!("Repair complete.");
        }
        ConfigAction::Backup { file } => {
            let backup_path = PathBuf::from(file);
            println!("Creating config backup at {}...", backup_path.display());
            create_config_backup(&backup_path, config, state)?;
            println!("Backup created successfully.");
        }
        ConfigAction::Restore { file, force } => {
            let backup_path = PathBuf::from(file);
            if !backup_path.exists() {
                return Err(anyhow::anyhow!("Backup file not found: {}", backup_path.display()));
            }
            println!("Restoring config from {}...", backup_path.display());
            restore_config_backup(&backup_path, config, state, force)?;
            println!("Restore complete.");
        }
        ConfigAction::Auth { token_source } => {
            println!("GitHub token source: {:?}", token_source);
            println!("Token: [{}]", config.token_source());
        }
    }
    Ok(())
}

fn create_config_backup(path: &PathBuf, config: &ConfigManager, state: &StateManager) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }

    let file = fs::File::create(path)?;
    let mut zip = zip::ZipWriter::new(file);
    let options = FileOptions::default().compression_method(CompressionMethod::Deflated);

    // The token never goes into a backup file - it lives in the credential
    // store, and a backup is the kind of file people paste into a bug report.
    let mut backup_config = config.get().clone();
    backup_config.github_token = None;
    let config_toml = toml::to_string_pretty(&backup_config)?;
    zip.start_file("config.toml", options)?;
    zip.write_all(config_toml.as_bytes())?;

    let state_json = serde_json::to_string_pretty(state.get())?;
    zip.start_file("state.json", options)?;
    zip.write_all(state_json.as_bytes())?;

    zip.finish()?;
    Ok(())
}

fn restore_config_backup(path: &PathBuf, config: &mut ConfigManager, state: &mut StateManager, force: bool) -> Result<()> {
    let file = fs::File::open(path)?;
    let mut archive = zip::ZipArchive::new(file)?;

    for i in 0..archive.len() {
        let mut file = archive.by_index(i)?;
        let name = file.name().to_string();
        
        if name == "config.toml" {
            let mut content = String::new();
            file.read_to_string(&mut content)?;
            if force || config.github_token().is_none() {
                config.config = toml::from_str(&content)?;
                // A token in the backup goes into the credential store, not
                // back into the config file.
                config.migrate_token_to_credential_store()?;
                config.save()?;
            }
        } else if name == "state.json" {
            let mut content = String::new();
            file.read_to_string(&mut content)?;
            if force {
                *state.get_mut() = serde_json::from_str(&content)?;
                state.save()?;
            }
        }
    }
    Ok(())
}

fn set_config_value(config: &mut ConfigManager, key: &str, value: &str) -> Result<()> {
    if key == "github_token" {
        // The token belongs in the OS credential store, not in a plain text
        // config file. A machine with no credential store keeps it in the
        // config file as before.
        if crate::core::credentials::store_token(value)? {
            config.get_mut().github_token = None;
        } else {
            eprintln!(
                "No OS credential store on this machine - the token stays in the config file."
            );
            config.get_mut().github_token = Some(value.to_string());
        }
        return Ok(());
    }
    let cfg = config.get_mut();
    match key {
        "install_dir" => cfg.install_dir = Path::new(value).to_path_buf(),
        "parallel_downloads" => cfg.parallel_downloads = value.parse()?,
        "timeout_seconds" => cfg.timeout_seconds = value.parse()?,
        "update_check_interval_hours" => cfg.update_check_interval_hours = value.parse()?,
        "auto_cleanup" => cfg.auto_cleanup = value.parse()?,
        "proxy" => cfg.proxy = Some(value.to_string()),
        "verify_checksums" => cfg.verify_checksums = value.parse()?,
        _ => return Err(anyhow::anyhow!("Unknown config key: {}", key)),
    }
    Ok(())
}

fn get_config_value(config: &ConfigManager, key: &str) -> Result<Option<String>> {
    let cfg = config.get();
    let value = match key {
        // Never echo the token: this value lands in shell history, CI logs, and
        // `ohub config list | tee`. `config auth` reports presence instead.
        "github_token" => config.github_token().map(|_| "[stored]".to_string()),
        "install_dir" => Some(cfg.install_dir.display().to_string()),
        "parallel_downloads" => Some(cfg.parallel_downloads.to_string()),
        "timeout_seconds" => Some(cfg.timeout_seconds.to_string()),
        "update_check_interval_hours" => Some(cfg.update_check_interval_hours.to_string()),
        "auto_cleanup" => Some(cfg.auto_cleanup.to_string()),
        "proxy" => cfg.proxy.clone(),
        "verify_checksums" => Some(cfg.verify_checksums.to_string()),
        _ => return Err(anyhow::anyhow!("Unknown config key: {}", key)),
    };
    Ok(value)
}