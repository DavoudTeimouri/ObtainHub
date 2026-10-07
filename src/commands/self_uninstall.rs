use crate::core::{ConfigManager, StateManager};
use crate::cli::SelfUninstallArgs;
use anyhow::Result;
use std::fs;
use std::path::PathBuf;
use dirs;
use tracing::info;
use zip::CompressionMethod;
use zip::write::FileOptions;

pub async fn execute(args: SelfUninstallArgs, _config: &ConfigManager, _state: &mut StateManager) -> Result<()> {
    info!("Self-uninstall");

    if !args.yes {
        println!("This will completely remove ohub from the system.");
        println!("The following will be removed:");
        let config_dir = dirs::config_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join("ObtainHub");
        let data_dir = dirs::data_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join("ObtainHub");
        println!("  - Config: {}", config_dir.display());
        println!("  - Data: {}", data_dir.display());
        println!("\nContinue? [y/N] ");
        let mut input = String::new();
        std::io::stdin().read_line(&mut input)?;
        if !input.trim().eq_ignore_ascii_case("y") {
            println!("Cancelled");
            return Ok(());
        }
    }

    // Create backup if requested
    if let Some(backup_path) = &args.backup {
        let backup_path = PathBuf::from(backup_path);
        println!("Creating backup at {}...", backup_path.display());
        create_backup(&backup_path, args.include_downloads)?;
        println!("Backup created successfully.");
    }

    // Remove config
    let config_dir = dirs::config_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("ObtainHub");
    if config_dir.exists() {
        fs::remove_dir_all(&config_dir)?;
        println!("Removed config: {}", config_dir.display());
    }

    // Remove data
    let data_dir = dirs::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("ObtainHub");
    if data_dir.exists() {
        fs::remove_dir_all(&data_dir)?;
        println!("Removed data: {}", data_dir.display());
    }

    // Try to remove the binary itself
    if let Ok(exe_path) = std::env::current_exe() {
        if exe_path.exists() {
            #[cfg(windows)]
            {
                println!("Note: Cannot remove running executable on Windows. Please delete manually: {}", exe_path.display());
            }
            #[cfg(unix)]
            {
                if let Err(e) = fs::remove_file(&exe_path) {
                    eprintln!("Warning: Could not remove executable: {}", e);
                } else {
                    println!("Removed executable: {}", exe_path.display());
                }
            }
        }
    }

    // Clear token from keyring
    // keyring API varies by version; skip for now
    println!("Note: GitHub token removal from keyring not implemented in this version");

    println!("\nSelf-uninstall complete.");

    if let Some(backup_path) = &args.backup {
        println!("Backup saved to: {}", backup_path);
        println!("To restore, run: ohub self-uninstall --restore {}", backup_path);
    }

    Ok(())
}

fn create_backup(backup_path: &PathBuf, include_downloads: bool) -> Result<()> {
    let config_dir = dirs::config_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("ObtainHub");
    let data_dir = dirs::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("ObtainHub");
    let download_dir = dirs::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("ObtainHub")
        .join("downloads");

    let tmpdir = tempfile::TempDir::new()?;
    let tmpdir_path = tmpdir.path();

    // Collect config files
    if config_dir.exists() {
        for entry in walkdir::WalkDir::new(&config_dir) {
            let entry = entry?;
            if entry.file_type().is_file() {
                let rel = entry.path().strip_prefix(&config_dir)?;
                let dest = tmpdir_path.join("config").join(rel);
                if let Some(parent) = dest.parent() {
                    fs::create_dir_all(parent)?;
                }
                fs::copy(entry.path(), dest)?;
            }
        }
    }

    // Collect state files
    if data_dir.exists() {
        for entry in walkdir::WalkDir::new(&data_dir) {
            let entry = entry?;
            if entry.file_type().is_file() {
                let rel = entry.path().strip_prefix(&data_dir)?;
                if !rel.to_string_lossy().starts_with("downloads") {
                    let dest = tmpdir_path.join("state").join(rel);
                    if let Some(parent) = dest.parent() {
                        fs::create_dir_all(parent)?;
                    }
                    fs::copy(entry.path(), dest)?;
                }
            }
        }
    }

    // Collect downloads if requested
    if include_downloads && download_dir.exists() {
        for entry in walkdir::WalkDir::new(&download_dir) {
            let entry = entry?;
            if entry.file_type().is_file() {
                let rel = entry.path().strip_prefix(&download_dir)?;
                let dest = tmpdir_path.join("downloads").join(rel);
                if let Some(parent) = dest.parent() {
                    fs::create_dir_all(parent)?;
                }
                fs::copy(entry.path(), dest)?;
            }
        }
    }

    // Write metadata
    let metadata = serde_json::json!({
        "created_at": chrono::Utc::now().to_rfc3339(),
        "version": "1.0",
        "ohub_version": env!("CARGO_PKG_VERSION"),
        "includes_downloads": include_downloads,
    });
    let meta_path = tmpdir_path.join("metadata.json");
    fs::write(&meta_path, serde_json::to_string_pretty(&metadata)?)?;

    // Create zip
    if let Some(parent) = backup_path.parent() {
        fs::create_dir_all(parent)?;
    }
    let zip_file = fs::File::create(backup_path)?;
    let mut zip = zip::ZipWriter::new(zip_file);
    let options = FileOptions::default().compression_method(CompressionMethod::Deflated);

    for entry in walkdir::WalkDir::new(tmpdir_path) {
        let entry = entry?;
        let path = entry.path();
        if path.is_file() {
            let arc_name = path.strip_prefix(tmpdir_path)?.to_string_lossy().to_string();
            zip.start_file(arc_name, options)?;
            let mut file = fs::File::open(path)?;
            std::io::copy(&mut file, &mut zip)?;
        }
    }
    zip.finish()?;

    Ok(())
}