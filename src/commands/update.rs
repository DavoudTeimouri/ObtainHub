use crate::core::{ConfigManager, StateManager};
use crate::cli::UpdateArgs;
use anyhow::Result;
use minreq;
use serde::{Deserialize, Serialize};
use tracing::info;
use std::path::PathBuf;
use dirs;

#[derive(Deserialize, Serialize, Debug)]
struct GitHubRelease {
    tag_name: String,
    assets: Vec<GitHubAsset>,
    zipball_url: String,
    tarball_url: String,
}

#[derive(Deserialize, Serialize, Debug)]
struct GitHubAsset {
    name: String,
    browser_download_url: String,
    size: u64,
    content_type: Option<String>,
}

pub async fn execute(args: UpdateArgs, config: &ConfigManager, state: &mut StateManager) -> Result<()> {
    info!("Updating repositories");
    
    let token = config.get().github_token.as_deref();
    let installed = state.list_installed();
    
    if installed.is_empty() {
        println!("No repositories installed.");
        return Ok(());
    }
    
    // Collect repo info first to avoid borrow issues
    let repo_infos: Vec<_> = installed.iter().map(|r| (r.repo.clone(), r.version.clone())).collect();
    
    // Determine which repos to update
    let targets: Vec<_> = if let Some(repo_name) = &args.repo {
        repo_infos.iter().filter(|(r, _)| r == repo_name).collect()
    } else {
        repo_infos.iter().collect()
    };
    
    if targets.is_empty() {
        println!("No matching repositories found.");
        return Ok(());
    }
    
    let mut updated = Vec::new();
    let mut already_current = Vec::new();
    let mut errors = Vec::new();
    
    for (repo_name, current_version) in targets {
        println!("Checking {}@{}...", repo_name, current_version);
        
        match fetch_latest_release(repo_name, token).await {
            Ok(release) => {
                let latest_version = release.tag_name.clone();
                if latest_version != *current_version {
                    println!("  Update available: {} -> {}", current_version, latest_version);
                    
                    if args.dry_run {
                        updated.push((repo_name.clone(), current_version.clone(), latest_version));
                        continue;
                    }
                    
                    // Perform update (reinstall with new version)
                    match install_release(repo_name, &latest_version, &release, token, state, args.force, args.skip_deps).await {
                        Ok(_) => {
                            updated.push((repo_name.clone(), current_version.clone(), latest_version.clone()));
                            println!("  Updated to {}", latest_version);
                        }
                        Err(e) => {
                            errors.push((repo_name.clone(), e.to_string()));
                            eprintln!("  Failed: {}", e);
                        }
                    }
                } else {
                    already_current.push(repo_name.clone());
                    println!("  Already at latest version");
                }
            }
            Err(e) => {
                errors.push((repo_name.clone(), e.to_string()));
                eprintln!("  Error checking: {}", e);
            }
        }
    }
    
    // Summary
    println!("\nUpdate Summary:");
    if !updated.is_empty() {
        println!("  Updated ({})", updated.len());
        for (repo, old, new) in &updated {
            println!("    {} {} -> {}", repo, old, new);
        }
    }
    
    if !already_current.is_empty() {
        println!("  Already current ({})", already_current.len());
        for repo in &already_current {
            println!("    {}", repo);
        }
    }
    
    if !errors.is_empty() {
        println!("  Errors ({})", errors.len());
        for (repo, error) in &errors {
            println!("    {}: {}", repo, error);
        }
    }
    
    Ok(())
}

async fn fetch_latest_release(repo: &str, token: Option<&str>) -> Result<GitHubRelease> {
    let url = format!("https://api.github.com/repos/{}/releases/latest", repo);
    let mut req = minreq::get(&url).with_header("User-Agent", "ObtainHub/3.0.0");
    if let Some(token) = token {
        req = req.with_header("Authorization", &format!("Bearer {}", token));
    }
    let resp: GitHubRelease = req.send()?.json()?;
    Ok(resp)
}

async fn install_release(
    repo: &str,
    version: &str,
    release: &GitHubRelease,
    token: Option<&str>,
    state: &mut StateManager,
    force: bool,
    _skip_deps: bool,
) -> Result<()> {
    // Find suitable asset (prefer zip, then tar.gz, then tar.xz)
    let asset = select_asset(&release.assets)?;
    
    println!("  Downloading {}...", asset.name);
    
    // Download with progress
    let download_url = &asset.browser_download_url;
    let mut req = minreq::get(download_url).with_header("User-Agent", "ObtainHub/3.0.0");
    if let Some(token) = token {
        req = req.with_header("Authorization", &format!("Bearer {}", token));
    }
    
    let response = req.send()?;
    let bytes = response.as_bytes();
    
    // Verify checksum if available
    // TODO: Implement checksum verification
    
    // Determine install path
    let install_dir = dirs::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("ObtainHub/repos")
        .join(repo);
    
    // Clean existing if force
    if force && install_dir.exists() {
        std::fs::remove_dir_all(&install_dir)?;
    }
    
    // Extract
    std::fs::create_dir_all(&install_dir)?;
    extract_archive(&asset.name, &bytes, &install_dir)?;
    
    // Update state
    let repo_entry = crate::core::state::InstalledRepo {
        repo: repo.to_string(),
        version: version.to_string(),
        install_path: install_dir.clone(),
        installed_at: chrono::Utc::now(),
        updated_at: Some(chrono::Utc::now()),
        checksum: None,
        metadata: serde_json::Value::Null,
    };
    
    state.add_installed(repo_entry);
    state.save()?;
    
    Ok(())
}

fn select_asset(assets: &[GitHubAsset]) -> Result<&GitHubAsset> {
    // Prefer zip, then tar.gz, then tar.xz
    for ext in &[".zip", ".tar.gz", ".tar.xz", ".tgz", ".txz"] {
        if let Some(asset) = assets.iter().find(|a| a.name.ends_with(ext)) {
            return Ok(asset);
        }
    }
    // Fallback to first asset
    assets.first().ok_or_else(|| anyhow::anyhow!("No suitable asset found"))
}

fn extract_archive(name: &str, bytes: &[u8], dest: &std::path::Path) -> Result<()> {
    if name.ends_with(".zip") {
        extract_zip(bytes, dest)
    } else if name.ends_with(".tar.gz") || name.ends_with(".tgz") {
        extract_tar_gz(bytes, dest)
    } else if name.ends_with(".tar.xz") || name.ends_with(".txz") {
        extract_tar_xz(bytes, dest)
    } else {
        Err(anyhow::anyhow!("Unsupported archive format: {}", name))
    }
}

fn extract_zip(bytes: &[u8], dest: &std::path::Path) -> Result<()> {
    let cursor = std::io::Cursor::new(bytes);
    let mut archive = zip::ZipArchive::new(cursor)?;
    archive.extract(dest)?;
    Ok(())
}

fn extract_tar_gz(bytes: &[u8], dest: &std::path::Path) -> Result<()> {
    let cursor = std::io::Cursor::new(bytes);
    let decoder = flate2::read::GzDecoder::new(cursor);
    let mut archive = tar::Archive::new(decoder);
    archive.unpack(dest)?;
    Ok(())
}

fn extract_tar_xz(bytes: &[u8], dest: &std::path::Path) -> Result<()> {
    use std::io::{BufWriter, Write};
    use tempfile;
    
    // Decompress to a temp file first
    let temp_dir = tempfile::tempdir()?;
    let temp_tar = temp_dir.path().join("archive.tar");
    let mut writer = BufWriter::new(std::fs::File::create(&temp_tar)?);
    
    lzma_rs::xz_decompress(&mut std::io::Cursor::new(bytes), &mut writer)?;
    writer.flush()?;
    drop(writer);
    
    // Now extract the tar file
    let tar_file = std::fs::File::open(&temp_tar)?;
    let mut archive = tar::Archive::new(tar_file);
    archive.unpack(dest)?;
    
    Ok(())
}