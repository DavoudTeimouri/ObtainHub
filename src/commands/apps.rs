use crate::core::{ConfigManager, StateManager};
use crate::cli::{AppsArgs, AppsAction};
use anyhow::Result;
use std::fs;
use std::path::{Path, PathBuf};
use tempfile::TempDir;
use tracing::info;
use zip::write::FileOptions;
use zip::CompressionMethod;

pub async fn execute(args: AppsArgs, config: &ConfigManager, state: &StateManager) -> Result<()> {
    info!("Apps command: {:?}", args.action);

    let config_data = config.get();
    let download_dir = &config_data.download_dir;

    match args.action {
        AppsAction::Backup { app, output, include_downloads } => {
                    let output_path = Path::new(&output);
                    if let Some(parent) = output_path.parent() {
                        fs::create_dir_all(parent)?;
                    }

                    let app_ids = if app.is_empty() { None } else { Some(app) };

                    let tmpdir = TempDir::new()?;
                    let tmpdir_path = tmpdir.path();
                    let mut files_to_zip = Vec::new();

                    if download_dir.exists() {
                        let entries = fs::read_dir(download_dir)?;
                        for entry in entries {
                            let entry = entry?;
                            let path = entry.path();
                            if path.is_dir() {
                                let folder_name = path.file_name().unwrap().to_string_lossy();
                                let should_include = if let Some(ref app_ids) = app_ids {
                                    app_ids.iter().any(|id| folder_name.contains(&id.replace('/', "_")))
                                } else {
                                    true
                                };

                                if should_include {
                                    for file_entry in walkdir::WalkDir::new(&path) {
                                        let file_entry = file_entry?;
                                        if file_entry.file_type().is_file() {
                                            let file_path = file_entry.path();
                                            let rel_path = file_path.strip_prefix(download_dir)?;
                                            let arc_name = format!("apps/{}", rel_path.to_string_lossy());
                                            files_to_zip.push((file_path.to_path_buf(), arc_name));
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Include download folder itself if requested
                    if include_downloads && download_dir.exists() {
                        for file_entry in walkdir::WalkDir::new(download_dir) {
                            let file_entry = file_entry?;
                            if file_entry.file_type().is_file() {
                                let file_path = file_entry.path();
                                let rel_path = file_path.strip_prefix(download_dir)?;
                                let arc_name = format!("downloads/{}", rel_path.to_string_lossy());
                                files_to_zip.push((file_path.to_path_buf(), arc_name));
                            }
                        }
                    }

                    if files_to_zip.is_empty() {
                        println!("No app files found to backup");
                        return Ok(());
                    }

                    // Copy files to temp dir
                    for (src_path, arc_name) in &files_to_zip {
                        let dest = tmpdir_path.join(arc_name);
                        if let Some(parent) = dest.parent() {
                            fs::create_dir_all(parent)?;
                        }
                        fs::copy(src_path, dest)?;
                    }

                    // Create metadata
                    let app_names: std::collections::HashSet<String> = files_to_zip
                        .iter()
                        .filter_map(|(_, arc)| arc.split('/').nth(1))
                        .map(|s| s.to_string())
                        .collect();

                    let metadata = serde_json::json!({
                        "version": "1.0",
                        "ohub_version": env!("CARGO_PKG_VERSION"),
                        "created": chrono::Utc::now().to_rfc3339(),
                        "type": "apps_backup",
                        "apps": app_names,
                        "includes_downloads": include_downloads,
                    });

                    let meta_path = tmpdir_path.join("metadata.json");
                    fs::write(&meta_path, serde_json::to_string_pretty(&metadata)?)?;

                    // Create zip
                    let zip_file = fs::File::create(output_path)?;
                    let mut zip = zip::ZipWriter::new(zip_file);
                    let options = FileOptions::default().compression_method(CompressionMethod::Deflated);

                    for root in walkdir::WalkDir::new(tmpdir_path) {
                        let entry = root?;
                        let path = entry.path();
                        if path.is_file() {
                            let arc_name = path.strip_prefix(tmpdir_path)?.to_string_lossy().to_string();
                            zip.start_file(arc_name, options)?;
                            let mut file = fs::File::open(path)?;
                            std::io::copy(&mut file, &mut zip)?;
                        }
                    }
                    zip.finish()?;

                    println!("Apps backup created: {}", output_path.display());
                }
                AppsAction::Restore { app, input, target_dir, dry_run } => {
                    let input_path = Path::new(&input);
                    if !input_path.exists() {
                        println!("Error: Backup file not found: {}", input_path.display());
                        return Ok(());
                    }

                    let app_ids = if app.is_empty() { None } else { Some(app) };

                    let target_base = target_dir.map(PathBuf::from).unwrap_or_else(|| download_dir.clone());

                    let tmpdir = TempDir::new()?;
                    let tmpdir_path = tmpdir.path();

                    // Extract zip
                    let zip_file = fs::File::open(input_path)?;
                    let mut archive = zip::ZipArchive::new(zip_file)?;
                    for i in 0..archive.len() {
                        let mut file = archive.by_index(i)?;
                        let outpath = tmpdir_path.join(file.mangled_name());
                        if file.is_dir() {
                            fs::create_dir_all(&outpath)?;
                        } else {
                            if let Some(parent) = outpath.parent() {
                                fs::create_dir_all(parent)?;
                            }
                            let mut outfile = fs::File::create(&outpath)?;
                            std::io::copy(&mut file, &mut outfile)?;
                        }
                    }

                    // Read metadata
                    let meta_file = tmpdir_path.join("metadata.json");
                    let metadata: serde_json::Value = if meta_file.exists() {
                        let content = fs::read_to_string(&meta_file)?;
                        serde_json::from_str(&content)?
                    } else {
                        serde_json::json!({})
                    };

                    // Find apps directory in extracted files
                    let apps_dir = tmpdir_path.join("apps");
                    if !apps_dir.exists() {
                        println!("Error: No apps directory in backup");
                        return Ok(());
                    }

                    // Check if backup includes downloads (from metadata)
                    let include_downloads = metadata.get("includes_downloads")
                        .and_then(|v| v.as_bool())
                        .unwrap_or(false);

                    let entries = fs::read_dir(&apps_dir)?;
                    for entry in entries {
                        let entry = entry?;
                        let path = entry.path();
                        if path.is_dir() {
                            let folder_name = path.file_name().unwrap().to_string_lossy();
                            let should_restore = if let Some(ref app_ids) = app_ids {
                                app_ids.iter().any(|id| folder_name.contains(&id.replace('/', "_")))
                            } else {
                                true
                            };

                            if should_restore {
                                let target = target_base.join(&*folder_name);
                                if dry_run {
                                    println!("Would restore: {} -> {}", folder_name, target.display());
                                } else {
                                    if target.exists() {
                                        fs::remove_dir_all(&target)?;
                                    }
                                    fs::create_dir_all(&target)?;
                                    copy_dir_all(&path, &target)?;
                                    println!("Restored: {} -> {}", folder_name, target.display());
                                }
                            }
                        }
                    }

                    // Also restore downloads if present in backup
                    let downloads_dir = tmpdir_path.join("downloads");
                    if downloads_dir.exists() && include_downloads {
                        let target = target_base;
                        if dry_run {
                            println!("Would restore downloads -> {}", target.display());
                        } else {
                            copy_dir_all(&downloads_dir, &target)?;
                            println!("Restored downloads -> {}", target.display());
                        }
                    }

                    if !dry_run {
                        println!("Apps restore complete from: {}", input_path.display());
                    }
        }
    }

    Ok(())
}

fn copy_dir_all(src: &Path, dst: &Path) -> Result<()> {
    if !dst.exists() {
        fs::create_dir_all(dst)?;
    }
    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let ty = entry.file_type()?;
        if ty.is_dir() {
            copy_dir_all(&entry.path(), &dst.join(entry.file_name()))?;
        } else {
            fs::copy(entry.path(), dst.join(entry.file_name()))?;
        }
    }
    Ok(())
}