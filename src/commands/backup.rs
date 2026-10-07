use crate::core::{ConfigManager, StateManager};
use crate::cli::BackupArgs;
use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::Write;
use std::path::Path;
use tracing::info;
use zip::write::FileOptions;
use zip::CompressionMethod;
use sha2::Digest;
use walkdir::WalkDir;

#[derive(Serialize, Deserialize, Debug)]
struct BackupData {
    version: u32,
    created_at: chrono::DateTime<chrono::Utc>,
    config: crate::core::config::Config,
    installed_repos: Vec<crate::core::state::InstalledRepo>,
    repo_archives: Vec<RepoArchive>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
struct RepoArchive {
    repo: String,
    archive_name: String,
    size: u64,
    sha256: String,
}

pub async fn execute(args: BackupArgs, config: &ConfigManager, state: &StateManager) -> Result<()> {
    info!("Creating backup");
    
    let output_path = args.output.unwrap_or_else(|| {
        let timestamp = chrono::Utc::now().format("%Y%m%d_%H%M%S");
        format!("obtainhub-backup-{}.zip", timestamp)
    });
    
    let installed = state.list_installed();
    
    // Collect repo archives if requested
    let mut repo_archives = Vec::new();
    if args.include_repos {
        for entry in &installed {
            if entry.install_path.exists() {
                println!("Archiving {}...", entry.repo);
                let archive_name = format!("{}.zip", entry.repo.replace('/', "_"));
                let archive_path = std::env::temp_dir().join(&archive_name);
                
                // Create zip of repo directory
                create_zip_archive(&entry.install_path, &archive_path)?;
                
                // Calculate SHA256
                let sha256 = calculate_sha256(&archive_path)?;
                let size = fs::metadata(&archive_path)?.len();
                
                repo_archives.push(RepoArchive {
                    repo: entry.repo.clone(),
                    archive_name: archive_name.clone(),
                    size,
                    sha256,
                });
            }
        }
    }
    
    // Create main backup zip
    let backup_data = BackupData {
        version: 1,
        created_at: chrono::Utc::now(),
        config: config.get().clone(),
        installed_repos: installed.iter().cloned().cloned().collect(),
        repo_archives: repo_archives.clone(),
    };
    
    let json_data = serde_json::to_string_pretty(&backup_data)?;
    let json_path = std::env::temp_dir().join("backup_metadata.json");
    fs::write(&json_path, &json_data)?;
    
    // Create the final zip with metadata and repo archives
    let output_file = fs::File::create(&output_path)?;
    let mut zip = zip::ZipWriter::new(output_file);
    let options = FileOptions::default()
        .compression_method(CompressionMethod::Deflated)
        .unix_permissions(0o644);
    
    // Add metadata
    zip.start_file("metadata.json", options)?;
    zip.write_all(json_data.as_bytes())?;
    
    // Add repo archives if included
    for ra in &repo_archives {
        let temp_archive = std::env::temp_dir().join(&ra.archive_name);
        if temp_archive.exists() {
            zip.start_file(&format!("repos/{}", ra.archive_name), options)?;
            let mut file = fs::File::open(&temp_archive)?;
            std::io::copy(&mut file, &mut zip)?;
            fs::remove_file(&temp_archive)?;
        }
    }
    
    zip.finish()?;
    
    println!("Backup created: {}", output_path);
    println!("  Config: included");
    println!("  Installed repos: {}", installed.len());
    println!("  Repo archives: {}", repo_archives.len());
    
    Ok(())
}

fn create_zip_archive(source_dir: &Path, output_path: &Path) -> Result<()> {
    let output_file = fs::File::create(output_path)?;
    let mut zip = zip::ZipWriter::new(output_file);
    let options = FileOptions::default()
        .compression_method(CompressionMethod::Deflated)
        .unix_permissions(0o644);
    
    for entry in WalkDir::new(source_dir) {
        let entry = entry?;
        let path = entry.path();
        let relative = path.strip_prefix(source_dir)?;
        
        if path.is_dir() {
            continue;
        }
        
        zip.start_file(relative.to_string_lossy().to_string(), options)?;
        let mut file = fs::File::open(path)?;
        std::io::copy(&mut file, &mut zip)?;
    }
    
    zip.finish()?;
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