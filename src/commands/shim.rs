use crate::core::{ConfigManager, StateManager};
use crate::cli::{ShimArgs, ShimAction};
use anyhow::Result;
use std::fs;
use std::path::Path;
#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;
use tracing::info;

pub async fn execute(args: ShimArgs, config: &ConfigManager, state: &StateManager) -> Result<()> {
    info!("Shim command: {:?}", args.action);

    let config_data = config.get();
    let shim_dir = &config_data.shim_dir;

    match args.action {
        ShimAction::List => {
            if !shim_dir.exists() {
                println!("No shims created.");
                return Ok(());
            }
            
            let entries = fs::read_dir(shim_dir)?;
            let mut found = false;
            for entry in entries {
                let entry = entry?;
                let path = entry.path();
                if path.is_file() {
                    if let Some(ext) = path.extension() {
                        if ext == "bat" || ext == "exe" || ext == "sh" {
                            println!("  {}", path.file_name().unwrap().to_string_lossy());
                            found = true;
                        }
                    }
                }
            }
            if !found {
                println!("No shims created.");
            }
        }
        ShimAction::Add { app, name } => {
                    // Find the app in state
                    let app_entry = state.get_installed(&app)
                        .or_else(|| state.list_installed().into_iter().find(|a| a.repo.split('/').last().unwrap_or("") == app));

                    let Some(app_entry) = app_entry else {
                        println!("App not found in ohub state: {}", app);
                        return Ok(());
                    };

                    // Find executable
                    let exe_path = if app_entry.install_path.exists() {
                        find_executable(&app_entry.install_path)
                    } else {
                        None
                    };

                    let Some(exe_path) = exe_path else {
                        println!("Could not find executable for {}. App may not be a portable/extracted app.", app_entry.repo);
                        return Ok(());
                    };

                    let shim_name = name.unwrap_or_else(|| app_entry.repo.split('/').last().unwrap_or("").to_string());
                    fs::create_dir_all(shim_dir)?;

                    // Create .bat shim on Windows, .sh on Unix
                    #[cfg(windows)]
                    {
                        let bat_path = shim_dir.join(format!("{}.bat", shim_name));
                        let bat_content = format!("@echo off\n\"{}\" %*\n", exe_path.display());
                        fs::write(&bat_path, bat_content)?;
                        println!("Created shim: {} -> {}", bat_path.display(), exe_path.display());
                        println!("Add {} to your PATH to use '{}' from anywhere.", shim_dir.display(), shim_name);
                    }
                    #[cfg(unix)]
                    {
                        let sh_path = shim_dir.join(&shim_name);
                        let sh_content = format!("#!/bin/sh\n\"{}\" \"$@\"\n", exe_path.display());
                        fs::write(&sh_path, sh_content)?;
                        let mut perms = fs::metadata(&sh_path)?.permissions();
                        perms.set_mode(0o755);
                        fs::set_permissions(&sh_path, perms)?;
                        println!("Created shim: {} -> {}", sh_path.display(), exe_path.display());
                        println!("Add {} to your PATH to use '{}' from anywhere.", shim_dir.display(), shim_name);
                    }
                }
                ShimAction::Remove { app } => {
                    // Try finding by app name in state
                    if let Some(app_entry) = state.get_installed(&app) {
                        let shim_name = app_entry.repo.split('/').last().unwrap_or("");
                        let bat_path = shim_dir.join(format!("{}.bat", shim_name));
                        if bat_path.exists() {
                            fs::remove_file(&bat_path)?;
                            println!("Removed shim: {}", bat_path.display());
                            return Ok(());
                        }

                        #[cfg(unix)]
                        {
                            let sh_path = shim_dir.join(shim_name);
                            if sh_path.exists() {
                                fs::remove_file(&sh_path)?;
                                println!("Removed shim: {}", sh_path.display());
                                return Ok(());
                            }
                        }
                    }

                    // Also try removing by explicit name
                    let bat_path = shim_dir.join(format!("{}.bat", app));
                    if bat_path.exists() {
                        fs::remove_file(&bat_path)?;
                        println!("Removed shim: {}", bat_path.display());
                        return Ok(());
                    }

                    #[cfg(unix)]
                    {
                        let sh_path = shim_dir.join(&app);
                        if sh_path.exists() {
                            fs::remove_file(&sh_path)?;
                            println!("Removed shim: {}", sh_path.display());
                            return Ok(());
                        }
                    }

                    println!("Shim not found: {}", app);
                }
        ShimAction::Path => {
            println!("{}", shim_dir.display());
        }
    }

    Ok(())
}

fn find_executable(dir: &Path) -> Option<std::path::PathBuf> {
    for entry in fs::read_dir(dir).ok()? {
        let entry = entry.ok()?;
        let path = entry.path();
        if path.is_file() {
            #[cfg(windows)]
            {
                if path.extension().map(|e| e == "exe").unwrap_or(false) {
                    return Some(path);
                }
            }
            #[cfg(unix)]
            {
                use std::os::unix::fs::MetadataExt;
                if let Ok(metadata) = fs::metadata(&path) {
                    if metadata.mode() & 0o111 != 0 {
                        return Some(path);
                    }
                }
            }
        } else if path.is_dir() {
            if let Some(found) = find_executable(&path) {
                return Some(found);
            }
        }
    }
    None
}