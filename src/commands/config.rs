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
            println!("{}", toml::to_string_pretty(config.get())?);
        }
        ConfigAction::Set { key, value } => {
            info!("Setting config: {} = {}", key, value);
            set_config_value(config, &key, &value)?;
            config.save()?;
            println!("Set {} = {}", key, value);
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
            
            fs::copy(&config_path, target.join("config.toml"))?;
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
            let cfg = config.get();
            match &cfg.github_token {
                Some(_) => println!("Token: [stored]"),
                None => println!("Token: [not set]"),
            }
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

    let config_toml = toml::to_string_pretty(config.get())?;
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
            if force || config.get().github_token.is_none() {
                config.config = toml::from_str(&content)?;
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
    let cfg = config.get_mut();
    match key {
        "github_token" => cfg.github_token = Some(value.to_string()),
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
        "github_token" => cfg.github_token.as_ref().map(|v| v.clone()),
        "install_dir" => Some(cfg.install_dir.display().to_string()),
        "parallel_downloads" => Some(cfg.parallel_downloads.to_string()),
        "timeout_seconds" => Some(cfg.timeout_seconds.to_string()),
        "update_check_interval_hours" => Some(cfg.update_check_interval_hours.to_string()),
        "auto_cleanup" => Some(cfg.auto_cleanup.to_string()),
        "proxy" => cfg.proxy.as_ref().map(|v| v.clone()),
        "verify_checksums" => Some(cfg.verify_checksums.to_string()),
        _ => return Err(anyhow::anyhow!("Unknown config key: {}", key)),
    };
    Ok(value)
}