use crate::core::{ConfigManager, StateManager};
use crate::cli::RestoreArgs;
use anyhow::Result;
use serde::Deserialize;
use std::fs;
use std::path::{Path, PathBuf};
use tracing::info;
use zip::ZipArchive;
use sha2::Digest;

#[derive(Deserialize, Debug)]
struct BackupData {
    #[allow(dead_code)]
    version: u32,
    created_at: chrono::DateTime<chrono::Utc>,
    config: crate::core::config::Config,
    installed_repos: Vec<crate::core::state::InstalledRepo>,
    repo_archives: Vec<RepoArchive>,
}

#[derive(Deserialize, Debug, Clone)]
struct RepoArchive {
    repo: String,
    archive_name: String,
    #[allow(dead_code)]
    size: u64,
    sha256: String,
}

pub async fn execute(args: RestoreArgs, config: &mut ConfigManager, state: &mut StateManager) -> Result<()> {
    info!("Restoring from backup: {}", args.file);
    
    let backup_path = Path::new(&args.file);
    if !backup_path.exists() {
        anyhow::bail!("Backup file not found: {}", args.file);
    }
    
    // Open archive twice - once for metadata, once for repo extraction
    // Read metadata first
    let backup_file = fs::File::open(backup_path)?;
    let mut archive = ZipArchive::new(backup_file)?;
    
    let mut metadata_file = archive.by_name("metadata.json")?;
    let mut metadata_content = String::new();
    std::io::Read::read_to_string(&mut metadata_file, &mut metadata_content)?;
    let backup_data: BackupData = serde_json::from_str(&metadata_content)?;
    
    println!("Restoring backup from: {}", backup_data.created_at.format("%Y-%m-%d %H:%M:%S UTC"));
    println!("  Config: included");
    println!("  Installed repos: {}", backup_data.installed_repos.len());
    println!("  Repo archives: {}", backup_data.repo_archives.len());
    
    // Restore config if requested
    if args.config {
        *config.get_mut() = backup_data.config.clone();
        match args.target_config.as_deref() {
            Some(dir) => {
                let path = Path::new(dir).join("config.toml");
                config.save_at(&path)?;
                println!("Config restored to {}", path.display());
            }
            None => {
                config.save()?;
                println!("Config restored");
            }
        }
    }

    // Restore state (installed repos)
    if args.state {
        let state_guard = state.get_mut();
        state_guard.installed.clear();
        for repo in &backup_data.installed_repos {
            state_guard.installed.insert(repo.repo.clone(), repo.clone());
        }
        match args.target_state.as_deref() {
            Some(dir) => {
                let path = Path::new(dir).join("state.json");
                state.save_at(&path)?;
                println!(
                    "State restored to {}: {} repositories",
                    path.display(),
                    backup_data.installed_repos.len()
                );
            }
            None => {
                state.save()?;
                println!("State restored: {} repositories", backup_data.installed_repos.len());
            }
        }
    }

    // Restore repo archives if requested
    if args.repos && !backup_data.repo_archives.is_empty() {
        // Re-open archive for repo extraction
        let backup_file2 = fs::File::open(backup_path)?;
        let mut archive2 = ZipArchive::new(backup_file2)?;

        // The apps go where the config in effect says they go.
        let install_root = restore_install_root(
            args.config,
            args.state,
            &backup_data.config.install_dir,
            &config.get().install_dir,
        );

        fs::create_dir_all(&install_root)?;
        
        for ra in &backup_data.repo_archives {
            println!("Restoring {}...", ra.repo);
            
            // Extract from backup zip
            let repo_zip_name = format!("repos/{}", ra.archive_name);
            let mut repo_zip_entry = archive2.by_name(&repo_zip_name)?;
            
            // Write to temp file
            let temp_zip = std::env::temp_dir().join(&ra.archive_name);
            let mut temp_file = fs::File::create(&temp_zip)?;
            std::io::copy(&mut repo_zip_entry, &mut temp_file)?;
            
            // Verify SHA256
            let sha256 = calculate_sha256(&temp_zip)?;
            if sha256 != ra.sha256 {
                anyhow::bail!("SHA256 mismatch for {}: expected {}, got {}", ra.repo, ra.sha256, sha256);
            }
            
            // Extract repo zip
            let repo_path = install_root.join(ra.repo.replace('/', "_"));
            if repo_path.exists() {
                fs::remove_dir_all(&repo_path)?;
            }
            fs::create_dir_all(&repo_path)?;
            
            extract_zip_archive(&temp_zip, &repo_path)?;
            fs::remove_file(&temp_zip)?;
            
            println!("  Extracted to: {}", repo_path.display());
        }
    }
    
    println!("Restore complete");
    Ok(())
}

/// Where the restored apps go.
///
/// The config in effect decides. When the config or the state is restored,
/// that is the backed up config's install_dir - the paths the restored state
/// points at. Restoring into a directory the tool never looks at would make
/// the apps invisible to `ohub list` and `ohub uninstall`.
fn restore_install_root(
    restore_config: bool,
    restore_state: bool,
    backup_install_dir: &Path,
    current_install_dir: &Path,
) -> PathBuf {
    if restore_config || restore_state {
        backup_install_dir.to_path_buf()
    } else {
        current_install_dir.to_path_buf()
    }
}

fn extract_zip_archive(archive_path: &Path, output_dir: &Path) -> Result<()> {
    let file = fs::File::open(archive_path)?;
    let mut archive = ZipArchive::new(file)?;
    
    for i in 0..archive.len() {
        let mut entry = archive.by_index(i)?;
        let out_path = output_dir.join(entry.name());
        
        if entry.is_dir() {
            fs::create_dir_all(&out_path)?;
        } else {
            if let Some(parent) = out_path.parent() {
                fs::create_dir_all(parent)?;
            }
            let mut out_file = fs::File::create(&out_path)?;
            std::io::copy(&mut entry, &mut out_file)?;
        }
    }
    
    Ok(())
}

fn calculate_sha256(path: &Path) -> Result<String> {
    let mut file = fs::File::open(path)?;
    let mut hasher = sha2::Sha256::new();
    let mut buffer = vec![0; 8192];
    loop {
        let n = std::io::Read::read(&mut file, &mut buffer)?;
        if n == 0 { break; }
        hasher.update(&buffer[..n]);
    }
    Ok(hex::encode(hasher.finalize()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_restored_config_decides_where_the_apps_go() {
        let backup = Path::new("/backup/repos");
        let current = Path::new("/current/repos");
        assert_eq!(
            restore_install_root(true, false, backup, current),
            PathBuf::from("/backup/repos")
        );
    }

    #[test]
    fn a_restored_state_decides_where_the_apps_go() {
        let backup = Path::new("/backup/repos");
        let current = Path::new("/current/repos");
        assert_eq!(
            restore_install_root(false, true, backup, current),
            PathBuf::from("/backup/repos")
        );
    }

    #[test]
    fn without_a_config_or_state_the_current_install_dir_is_used() {
        let backup = Path::new("/backup/repos");
        let current = Path::new("/current/repos");
        assert_eq!(
            restore_install_root(false, false, backup, current),
            PathBuf::from("/current/repos")
        );
    }
}