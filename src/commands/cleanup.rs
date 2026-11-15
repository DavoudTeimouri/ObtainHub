use crate::core::{ConfigManager, StateManager};
use crate::cli::{CleanupArgs, CleanupAction};
use anyhow::Result;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};
use tracing::info;
use walkdir::WalkDir;

pub async fn execute(args: CleanupArgs, config: &ConfigManager, state: &mut StateManager) -> Result<()> {
    let (dry_run, force) = match args.action {
        CleanupAction::All { dry_run, force } => (dry_run, force),
        CleanupAction::Tasks { dry_run, force } => (dry_run, force),
        CleanupAction::Downloads { dry_run, force } => (dry_run, force),
        CleanupAction::Cache { dry_run, force } => (dry_run, force),
        CleanupAction::Repos { dry_run, force } => (dry_run, force),
    };

    info!("Cleanup: dry_run={}, force={}", dry_run, force);

    let config_data = config.get();
    let download_dir = &config_data.download_dir;
    let install_dir = &config_data.install_dir;
    let mut cleaned_any = false;

    let run_tasks = matches!(args.action, CleanupAction::All { .. } | CleanupAction::Tasks { .. });
    let run_downloads = matches!(args.action, CleanupAction::All { .. } | CleanupAction::Downloads { .. });
    let run_cache = matches!(args.action, CleanupAction::All { .. } | CleanupAction::Cache { .. });
    let run_repos = matches!(args.action, CleanupAction::All { .. } | CleanupAction::Repos { .. });

    // Clean up leftover scheduled tasks
    if run_tasks {
        if dry_run {
            println!("[DRY RUN] Would check/remove orphaned scheduled tasks");
        } else {
            #[cfg(windows)]
            {
                let task_name = "ObtainHubScheduledCheck";
                let output = std::process::Command::new("schtasks")
                    .args(["/Query", "/TN", task_name, "/FO", "LIST"])
                    .output();
                if let Ok(result) = output {
                    if result.status.success() {
                        let ohub_in_state = state.get_installed("DavoudTeimouri/ObtainHub").is_some();
                        if !ohub_in_state {
                            let _ = std::process::Command::new("schtasks")
                                .args(["/Delete", "/TN", task_name, "/F"])
                                .status();
                            println!("Removed orphaned Windows Task Scheduler task: {}", task_name);
                            cleaned_any = true;
                        }
                    }
                }
            }

            #[cfg(unix)]
            {
                let output = std::process::Command::new("crontab")
                    .arg("-l")
                    .output();
                if let Ok(result) = output {
                    if result.status.success() {
                        let stdout = String::from_utf8_lossy(&result.stdout);
                        if stdout.contains("ObtainHub scheduled check") {
                            let ohub_in_state = state.get_installed("DavoudTeimouri/ObtainHub").is_some();
                            if !ohub_in_state {
                                let lines: Vec<&str> = stdout.lines()
                                    .filter(|l| !l.contains("ObtainHub scheduled check"))
                                    .collect();
                                let new_crontab = lines.join("\n") + "\n";
                                let _ = std::process::Command::new("crontab")
                                    .arg("-")
                                    .stdin(std::process::Stdio::piped())
                                    .spawn()
                                    .and_then(|mut child| {
                                        use std::io::Write;
                                        child.stdin.as_mut().unwrap().write_all(new_crontab.as_bytes())?;
                                        child.wait()
                                    });
                                println!("Removed orphaned cron job");
                                cleaned_any = true;
                            }
                        }
                    }
                }
            }
        }
    }

    // Clean up incomplete downloads (.part files) and old version archives
    if run_downloads && download_dir.exists() {
        // Remove .part files
        let part_files: Vec<_> = WalkDir::new(download_dir)
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|e| {
                e.file_type().is_file() &&
                e.file_name().to_string_lossy().ends_with(".part")
            })
            .collect();

        for part_file in part_files {
            let path = part_file.path();
            if !dry_run {
                match fs::remove_file(path) {
                    Ok(_) => {
                        println!("Removed incomplete download: {}", path.display());
                        cleaned_any = true;
                    }
                    Err(e) => eprintln!("Failed to remove {}: {}", path.display(), e),
                }
            } else {
                println!("[DRY RUN] Would remove incomplete download: {}", path.display());
            }
        }

        // Remove old versioned archives, keeping newest per app
        cleanup_download_folder(download_dir, dry_run, &mut cleaned_any)?;
    }

    // Clean up empty folders under app install directories
    if run_repos && install_dir.exists() {
        let installed = state.list_installed();
        let mut repo_dirs: Vec<PathBuf> = installed
            .iter()
            .filter_map(|e| {
                let p = PathBuf::from(&e.install_path);
                if p.is_dir() { Some(p) } else { p.parent().map(|pp| pp.to_path_buf()) }
            })
            .collect();
        repo_dirs.sort();
        repo_dirs.dedup();

        for repo_dir in repo_dirs {
            remove_empty_dirs_recursive(&repo_dir, install_dir, dry_run, &mut cleaned_any)?;
        }
    }

    // Clean up old manifest cache entries (older than 30 days)
    if run_cache {
        let now = SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs();
        let thirty_days = 30 * 24 * 60 * 60;

        let mut cache = state.get_mut().metadata
            .remove("manifest_cache")
            .and_then(|v| serde_json::from_value::<std::collections::HashMap<String, serde_json::Value>>(v).ok())
            .unwrap_or_default();

        let to_remove: Vec<String> = cache.iter()
            .filter_map(|(key, entry)| {
                if let Some(cached_at) = entry.get("cached_at").and_then(|v| v.as_u64()) {
                    if now.saturating_sub(cached_at) > thirty_days {
                        Some(key.clone())
                    } else {
                        None
                    }
                } else if let Some(cached_at) = entry.as_u64() {
                    if now.saturating_sub(cached_at) > thirty_days {
                        Some(key.clone())
                    } else {
                        None
                    }
                } else {
                    None
                }
            })
            .collect();

        for key in &to_remove {
            cache.remove(key);
        }

        if !to_remove.is_empty() {
            state.get_mut().metadata.insert("manifest_cache".to_string(), serde_json::to_value(cache)?);
            state.save()?;
            if !dry_run {
                println!("Cleaned {} old manifest cache entries", to_remove.len());
                cleaned_any = true;
            } else {
                println!("[DRY RUN] Would clean {} old manifest cache entries", to_remove.len());
            }
        }
    }

    if !cleaned_any && !dry_run {
        println!("Nothing to clean up.");
    }

    Ok(())
}

/// Remove empty directories recursively, stopping at install_dir boundary.
fn remove_empty_dirs_recursive(
    dir: &Path,
    root: &Path,
    dry_run: bool,
    cleaned_any: &mut bool,
) -> Result<()> {
    if !dir.exists() || !dir.is_dir() {
        return Ok(());
    }

    // Recurse into subdirectories first
    let mut subdirs: Vec<PathBuf> = Vec::new();
    if let Ok(entries) = fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                subdirs.push(path);
            }
        }
    }
    for subdir in &subdirs {
        remove_empty_dirs_recursive(subdir, root, dry_run, cleaned_any)?;
    }

    // Check if dir is now empty (after recursive cleanup)
    if dir == root {
        return Ok(());
    }

    let is_empty = fs::read_dir(dir)?.next().is_none();
    if is_empty {
        if !dry_run {
            match fs::remove_dir(dir) {
                Ok(_) => {
                    println!("Removed empty folder: {}", dir.display());
                    *cleaned_any = true;
                }
                Err(e) => eprintln!("Failed to remove {}: {}", dir.display(), e),
            }
        } else {
            println!("[DRY RUN] Would remove empty folder: {}", dir.display());
        }
    }

    Ok(())
}

/// Clean old versioned archives in download folder, keeping newest per app.
fn cleanup_download_folder(
    download_dir: &Path,
    dry_run: bool,
    cleaned_any: &mut bool,
) -> Result<()> {
    // Group files by base name (file name without extension). Different apps
    // like tool.exe and tool2.exe must not share a group.
    let mut groups: std::collections::HashMap<String, Vec<PathBuf>> = std::collections::HashMap::new();

    for entry in fs::read_dir(download_dir)? {
        let entry = entry?;
        let path = entry.path();
        if !path.is_file() {
            continue;
        }
        let base = path
            .file_stem()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string();
        groups.entry(base).or_default().push(path);
    }

    // For each group, keep the file with the most recent modification time
    for (_, mut files) in groups {
        if files.len() <= 1 {
            continue;
        }
        files.sort_by(|a, b| {
            let ma = a.metadata().and_then(|m| m.modified()).unwrap_or(SystemTime::UNIX_EPOCH);
            let mb = b.metadata().and_then(|m| m.modified()).unwrap_or(SystemTime::UNIX_EPOCH);
            mb.cmp(&ma) // newest first
        });
        // Remove all but the newest
        for path in files.into_iter().skip(1) {
            if !dry_run {
                match fs::remove_file(&path) {
                    Ok(_) => {
                        println!("Removed old archive: {}", path.display());
                        *cleaned_any = true;
                    }
                    Err(e) => eprintln!("Failed to remove {}: {}", path.display(), e),
                }
            } else {
                println!("[DRY RUN] Would remove old archive: {}", path.display());
            }
        }
    }

    Ok(())
}
