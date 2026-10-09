use crate::core::{ConfigManager, StateManager};
use crate::cli::InstallArgs;
use anyhow::{Result, Context};
use minreq;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::fs;
use walkdir::WalkDir;
use zip::ZipArchive;
use flate2::read::GzDecoder;
use tar::Archive;
use sha2::{Sha256, Digest};
use tracing::{info, debug, warn};
use indicatif::{ProgressBar, ProgressStyle};
use chrono;
use tempfile;
use std::io::{BufReader, BufWriter, Write};

#[derive(Deserialize, Serialize, Debug)]
struct GitHubRelease {
    tag_name: String,
    name: Option<String>,
    prerelease: bool,
    draft: bool,
    assets: Vec<GitHubAsset>,
    zipball_url: String,
    tarball_url: String,
}

#[derive(Deserialize, Serialize, Debug, Clone)]
struct GitHubAsset {
    name: String,
    browser_download_url: String,
    size: u64,
    content_type: Option<String>,
}

#[derive(Deserialize, Serialize, Debug)]
struct GitHubRepoInfo {
    full_name: String,
    default_branch: String,
    description: Option<String>,
}

pub async fn execute(args: InstallArgs, config: &ConfigManager, state_manager: &mut StateManager) -> Result<()> {
    info!("Installing: {}", args.repo);
    
    // Handle --file (local file install)
    if let Some(file_path) = &args.file {
        return install_from_file(&args, file_path, config, state_manager).await;
    }
    
    // Handle --url (direct URL install)
    if let Some(url) = &args.url {
        return install_from_url(&args, url, config, state_manager).await;
    }

    // Dry run - show what would be installed
    if args.dry_run {
        println!("DRY RUN: Would install {}", args.repo);
        if let Some(version) = &args.version {
            println!("  Version: {}", version);
        } else {
            println!("  Version: latest");
        }
        println!("  Target directory: {}", config.get().install_dir.join(&args.repo).display());
        println!("  Force reinstall: {}", args.force);
        println!("  Skip deps: {}", args.skip_deps);
        return Ok(());
    }
    
    let token = config.get().github_token.as_deref();
    let install_dir = config.get().install_dir.join(&args.repo);
    
    // Check if already installed
    if install_dir.exists() && !args.force {
        if let Some(existing) = state_manager.get_installed(&args.repo) {
            return Err(anyhow::anyhow!(
                "Repository '{}' already installed at {}. Use --force to reinstall.",
                args.repo,
                existing.install_path.display()
            ));
        }
    }
    
    // Get repo info
    let repo_info = fetch_repo_info(&args.repo, token).await?;
    
    // Determine version to install
    let (release, version) = if let Some(version) = &args.version {
        let release = fetch_release_by_tag(&args.repo, version, token).await?;
        (release, version.clone())
    } else {
        let release = fetch_latest_release(&args.repo, token).await?;
        let version = release.tag_name.clone();
        (release, version)
    };
    
    info!("Installing {}@{}", args.repo, version);
    
    // Find appropriate asset
    let asset = select_asset(&release)?;
    debug!("Selected asset: {} ({} bytes)", asset.name, asset.size);
    
    // Create install directory
    fs::create_dir_all(&install_dir)?;
    
    // Download asset with progress
    let asset_path = install_dir.join(&asset.name);
    download_with_progress(&asset.browser_download_url, &asset_path, token, config.get().timeout_seconds).await?;
    
    // Verify checksum against the release's published digest, when one exists
    if config.get().verify_checksums {
        if let Some(expected) = fetch_published_checksum(&release, &asset.name, token).await? {
            let actual = calculate_sha256(&asset_path)?;
            if !expected.eq_ignore_ascii_case(&actual) {
                return Err(anyhow::anyhow!(
                    "Checksum mismatch for {}: expected {}, got {}",
                    asset.name, expected, actual
                ));
            }
            info!("Checksum verified for {}", asset.name);
        } else {
            warn!("No published checksum for {} — skipping verification", asset.name);
        }
    }
    
    // Extract asset
    let extracted_path = extract_asset(&asset_path, &install_dir, &asset.name)?;
    
    // Move contents to install_dir if extracted to subdirectory
    let final_path = finalize_install(&extracted_path, &install_dir)?;

    // Create installed repo record
    let version_clone = version.clone();
    let installed_repo = crate::core::state::InstalledRepo {
        repo: args.repo.clone(),
        version: version_clone,
        install_path: final_path.clone(),
        installed_at: chrono::Utc::now(),
        updated_at: None,
        checksum: Some(calculate_sha256(&asset_path)?),
        metadata: serde_json::json!({
            "repo_info": repo_info,
            "asset_name": asset.name,
            "asset_size": asset.size,
        }),
    };

    // Update state
    state_manager.add_installed(installed_repo);
    state_manager.save()?;
    
    // Cleanup asset file
    fs::remove_file(&asset_path)?;
    
    println!("Successfully installed {}@{} to {}", args.repo, version, final_path.display());
    Ok(())
}

async fn fetch_repo_info(repo: &str, token: Option<&str>) -> Result<GitHubRepoInfo> {
    let url = format!("https://api.github.com/repos/{}", repo);
    let mut req = minreq::get(&url).with_header("User-Agent", "ObtainHub/3.0.0");
    if let Some(token) = token {
        req = req.with_header("Authorization", &format!("Bearer {}", token));
    }
    let resp: GitHubRepoInfo = req.send()?.json()?;
    Ok(resp)
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

async fn fetch_release_by_tag(repo: &str, tag: &str, token: Option<&str>) -> Result<GitHubRelease> {
    let url = format!("https://api.github.com/repos/{}/releases/tags/{}", repo, tag);
    let mut req = minreq::get(&url).with_header("User-Agent", "ObtainHub/3.0.0");
    if let Some(token) = token {
        req = req.with_header("Authorization", &format!("Bearer {}", token));
    }
    let resp: GitHubRelease = req.send()?.json()?;
    Ok(resp)
}

fn select_asset(release: &GitHubRelease) -> Result<GitHubAsset> {
    // Priority: platform-specific asset > generic archive > zipball
    let target_os = std::env::consts::OS;
    let target_arch = std::env::consts::ARCH;
    
    // Try to find platform-specific asset
    for asset in &release.assets {
        let name = asset.name.to_lowercase();
        if (target_os == "windows" && (name.ends_with(".zip") || name.ends_with(".exe"))) ||
           (target_os == "linux" && (name.ends_with(".tar.gz") || name.ends_with(".tar.xz") || name.ends_with(".AppImage"))) ||
           (target_os == "macos" && (name.ends_with(".tar.gz") || name.ends_with(".dmg") || name.ends_with(".zip"))) {
            if name.contains(target_arch) || name.contains("x86_64") || name.contains("amd64") || name.contains("aarch64") || name.contains("arm64") {
                return Ok(asset.clone());
            }
        }
    }
    
    // Fallback: any archive asset
    for asset in &release.assets {
        let name = asset.name.to_lowercase();
        if name.ends_with(".zip") || name.ends_with(".tar.gz") || name.ends_with(".tar.xz") || name.ends_with(".tgz") {
            return Ok(asset.clone());
        }
    }
    
    // Last resort: use zipball
    let zipball_asset = GitHubAsset {
        name: format!("{}.zip", release.tag_name),
        browser_download_url: release.zipball_url.clone(),
        size: 0, // Unknown until downloaded
        content_type: Some("application/zip".to_string()),
    };
    Ok(zipball_asset)
}

async fn download_with_progress(url: &str, path: &Path, token: Option<&str>, timeout_secs: u64) -> Result<()> {
    let mut req = minreq::get(url).with_header("User-Agent", "ObtainHub/3.0.0");
    if let Some(token) = token {
        req = req.with_header("Authorization", &format!("Bearer {}", token));
    }
    
    let resp = req.with_timeout(timeout_secs).send()?;
    let total_size = resp.headers.get("content-length").and_then(|v| v.parse::<u64>().ok()).unwrap_or(0);
    
    let pb = ProgressBar::new(total_size);
    pb.set_style(ProgressStyle::default_bar()
        .template("{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {bytes}/{total_bytes} ({eta})")
        .unwrap()
        .progress_chars("#>-"));
    
    let mut file = fs::File::create(path)?;
    let mut downloaded = 0u64;
    let body = resp.as_bytes();
    
    for chunk in body.chunks(8192) {
        std::io::Write::write_all(&mut file, chunk)?;
        downloaded += chunk.len() as u64;
        pb.set_position(downloaded);
    }
    
    pb.finish_with_message("Download complete");
    Ok(())
}

/// Look for a published digest for `asset_name` among the release's other assets.
/// Covers the two conventions in wide use: a per-asset `<name>.sha256` and a
/// combined `SHA256SUMS` / `checksums.txt` manifest. Returns None when the
/// release publishes no digest, which is common and not itself an error.
async fn fetch_published_checksum(
    release: &GitHubRelease,
    asset_name: &str,
    token: Option<&str>,
) -> Result<Option<String>> {
    // Per-asset sidecar: <name>.sha256
    let sidecar = format!("{}.sha256", asset_name);
    if let Some(a) = release.assets.iter().find(|a| a.name == sidecar) {
        if let Some(digest) = digest_from_text(&download_text(&a.browser_download_url, token).await?) {
            return Ok(Some(digest));
        }
    }

    // Combined manifest: SHA256SUMS / checksums.txt
    for manifest in ["SHA256SUMS", "checksums.txt"] {
        if let Some(a) = release.assets.iter().find(|a| a.name.eq_ignore_ascii_case(manifest)) {
            if let Ok(text) = download_text(&a.browser_download_url, token).await {
                let digest = digest_from_manifest(&text, asset_name);
                if digest.is_some() {
                    return Ok(digest);
                }
            }
        }
    }

    Ok(None)
}

/// Read a digest from a `<archive>.sha256` file sitting next to a local archive.
/// This is the only verification available for `install --file` / `--url`, where
/// there is no release to consult.
fn local_sidecar_digest(archive_path: &Path) -> Option<String> {
    let sidecar = PathBuf::from(format!("{}.sha256", archive_path.display()));
    let text = std::fs::read_to_string(sidecar).ok()?;
    digest_from_text(&text)
}

async fn download_text(url: &str, token: Option<&str>) -> Result<String> {
    let mut req = minreq::get(url).with_header("User-Agent", "ObtainHub/3.0.0");
    if let Some(token) = token {
        req = req.with_header("Authorization", &format!("Bearer {}", token));
    }
    let resp = req.send()?;
    Ok(resp.as_str()?.to_string())
}

/// A per-asset `.sha256` file holds either a bare digest or `digest  filename`.
fn digest_from_text(text: &str) -> Option<String> {
    text.split_whitespace().next().map(|s| s.to_ascii_lowercase())
}

/// A combined manifest is `digest␠␠filename` per line; find our asset's line.
fn digest_from_manifest(text: &str, asset_name: &str) -> Option<String> {
    for line in text.lines() {
        let mut parts = line.split_whitespace();
        let digest = match parts.next() {
            Some(d) if d.len() == 64 => d,
            _ => continue,
        };
        // sha256sum marks binary mode with a leading '*', e.g. "abc123 *app.zip".
        let name = parts.next().unwrap_or("").trim_start_matches('*');
        // Exact filename only. Matching on the basename would let a "./dist/app.zip"
        // entry answer for a top-level "app.zip" — a different file.
        if name == asset_name {
            return Some(digest.to_ascii_lowercase());
        }
    }
    None
}

fn calculate_sha256(path: &Path) -> Result<String> {
    let mut file = fs::File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buffer = vec![0; 8192];
    loop {
        let n = std::io::Read::read(&mut file, &mut buffer)?;
        if n == 0 { break; }
        hasher.update(&buffer[..n]);
    }
    Ok(hex::encode(hasher.finalize()))
}

fn extract_asset(asset_path: &Path, install_dir: &Path, filename: &str) -> Result<PathBuf> {
    let filename_lower = filename.to_lowercase();
    
    if filename_lower.ends_with(".zip") {
        extract_zip(asset_path, install_dir)
    } else if filename_lower.ends_with(".tar.gz") || filename_lower.ends_with(".tgz") {
        extract_tar_gz(asset_path, install_dir)
    } else if filename_lower.ends_with(".tar.xz") {
        extract_tar_xz(asset_path, install_dir)
    } else {
        // Single binary or unknown - just copy
        let dest = install_dir.join(filename);
        fs::copy(asset_path, &dest)?;
        Ok(dest)
    }
}

/// Join an archive entry name onto the destination, rejecting any name that
/// would escape it. Zip entries are attacker-controlled (we download them from
/// the internet), so `../` traversal must fail closed.
fn safe_join(dest: &Path, name: &str) -> Result<PathBuf> {
    let outpath = dest.join(name);
    // Normalize before comparing: `starts_with` walks components lexically, so the
    // raw `dest/../x` would still appear to start with dest. Rebuilding the path
    // through components() collapses `..` against what came before, so a name that
    // climbs above dest no longer has dest as a prefix.
    let mut normalized = PathBuf::new();
    for c in outpath.components() {
        match c {
            std::path::Component::ParentDir => { normalized.pop(); }
            std::path::Component::CurDir => {}
            other => normalized.push(other.as_os_str()),
        }
    }
    if !normalized.starts_with(dest) {
        anyhow::bail!("Refusing to extract '{}': path escapes install directory", name);
    }
    Ok(outpath)
}

fn extract_zip(asset_path: &Path, install_dir: &Path) -> Result<PathBuf> {
    let file = fs::File::open(asset_path)?;
    let mut archive = ZipArchive::new(file)?;
    
    for i in 0..archive.len() {
        let mut file = archive.by_index(i)?;
        let outpath = safe_join(install_dir, file.name())?;
        
        if file.name().ends_with('/') {
            fs::create_dir_all(&outpath)?;
        } else {
            if let Some(parent) = outpath.parent() {
                fs::create_dir_all(parent)?;
            }
            let mut outfile = fs::File::create(&outpath)?;
            std::io::copy(&mut file, &mut outfile)?;
        }
    }
    Ok(install_dir.to_path_buf())
}

async fn install_from_file(args: &InstallArgs, file_path: &str, config: &ConfigManager, state_manager: &mut StateManager) -> Result<()> {
    let path = std::path::Path::new(file_path);
    if !path.exists() {
        return Err(anyhow::anyhow!("File not found: {}", file_path));
    }
    
    let install_dir = config.get().install_dir.join(&args.repo);
    
    // Check if already installed
    if install_dir.exists() && !args.force {
        if let Some(existing) = state_manager.get_installed(&args.repo) {
            return Err(anyhow::anyhow!(
                "Repository '{}' already installed at {}. Use --force to reinstall.",
                args.repo,
                existing.install_path.display()
            ));
        }
    }
    
    fs::create_dir_all(&install_dir)?;
    
    let filename = path.file_name().and_then(|s| s.to_str()).unwrap_or("unknown");
    
    // Copy file to install dir
    let asset_path = install_dir.join(filename);
    fs::copy(path, &asset_path)?;
    
    // Verify checksum if enabled
    if config.get().verify_checksums {
        // No release object for --file / --url, so there is no published digest.
        // A sidecar the user placed next to the archive is the only thing checkable.
        if let Some(expected) = local_sidecar_digest(&asset_path) {
            let actual = calculate_sha256(&asset_path)?;
            if !expected.eq_ignore_ascii_case(&actual) {
                return Err(anyhow::anyhow!(
                    "Checksum mismatch for {}: expected {}, got {}",
                    filename, expected, actual
                ));
            }
            info!("Checksum verified for {}", filename);
        } else if config.get().verify_checksums {
            warn!("No checksum available for {} — installed unverified", filename);
        }
    }
    
    // Extract asset
    let extracted_path = extract_asset(&asset_path, &install_dir, filename)?;
    
    // Move contents to install_dir if extracted to subdirectory
    let final_path = finalize_install(&extracted_path, &install_dir)?;
    
    // Create installed repo record
    let installed_repo = crate::core::state::InstalledRepo {
        repo: args.repo.clone(),
        version: args.version.clone().unwrap_or_else(|| "local".to_string()),
        install_path: final_path.clone(),
        installed_at: chrono::Utc::now(),
        updated_at: None,
        checksum: Some(calculate_sha256(&asset_path)?),
        metadata: serde_json::json!({
            "source": "file",
            "file_path": file_path,
            "asset_name": filename,
        }),
    };
    
    // Update state
    state_manager.add_installed(installed_repo);
    state_manager.save()?;
    
    // Cleanup asset file
    fs::remove_file(&asset_path)?;
    
    println!("Successfully installed {} from file to {}", args.repo, final_path.display());
    Ok(())
}

async fn install_from_url(args: &InstallArgs, url: &str, config: &ConfigManager, state_manager: &mut StateManager) -> Result<()> {
    let token = config.get().github_token.as_deref();
    let install_dir = config.get().install_dir.join(&args.repo);
    
    // Check if already installed
    if install_dir.exists() && !args.force {
        if let Some(existing) = state_manager.get_installed(&args.repo) {
            return Err(anyhow::anyhow!(
                "Repository '{}' already installed at {}. Use --force to reinstall.",
                args.repo,
                existing.install_path.display()
            ));
        }
    }
    
    fs::create_dir_all(&install_dir)?;
    
    // Extract filename from URL
    let filename = url.split('/').last().unwrap_or("download");
    let asset_path = install_dir.join(filename);
    
    // Download with progress
    download_with_progress(url, &asset_path, token, config.get().timeout_seconds).await?;
    
    // Verify checksum if enabled
    if config.get().verify_checksums {
        // No release object for --file / --url, so there is no published digest.
        // A sidecar the user placed next to the archive is the only thing checkable.
        if let Some(expected) = local_sidecar_digest(&asset_path) {
            let actual = calculate_sha256(&asset_path)?;
            if !expected.eq_ignore_ascii_case(&actual) {
                return Err(anyhow::anyhow!(
                    "Checksum mismatch for {}: expected {}, got {}",
                    filename, expected, actual
                ));
            }
            info!("Checksum verified for {}", filename);
        } else if config.get().verify_checksums {
            warn!("No checksum available for {} — installed unverified", filename);
        }
    }
    
    // Extract asset
    let extracted_path = extract_asset(&asset_path, &install_dir, filename)?;
    
    // Move contents to install_dir if extracted to subdirectory
    let final_path = finalize_install(&extracted_path, &install_dir)?;
    
    // Create installed repo record
    let installed_repo = crate::core::state::InstalledRepo {
        repo: args.repo.clone(),
        version: args.version.clone().unwrap_or_else(|| "url".to_string()),
        install_path: final_path.clone(),
        installed_at: chrono::Utc::now(),
        updated_at: None,
        checksum: Some(calculate_sha256(&asset_path)?),
        metadata: serde_json::json!({
            "source": "url",
            "url": url,
            "asset_name": filename,
        }),
    };
    
    // Update state
    state_manager.add_installed(installed_repo);
    state_manager.save()?;
    
    // Cleanup asset file
    fs::remove_file(&asset_path)?;
    
    println!("Successfully installed {} from URL to {}", args.repo, final_path.display());
    Ok(())
}

fn extract_tar_gz(asset_path: &Path, install_dir: &Path) -> Result<PathBuf> {
    let file = fs::File::open(asset_path)?;
    let decoder = GzDecoder::new(file);
    let mut archive = Archive::new(decoder);
    archive.unpack(install_dir)?;
    Ok(install_dir.to_path_buf())
}

fn extract_tar_xz(asset_path: &Path, install_dir: &Path) -> Result<PathBuf> {
    let file = fs::File::open(asset_path)?;
    let mut reader = BufReader::new(file);
    
    // Decompress to a temp file first
    let temp_dir = tempfile::tempdir()?;
    let temp_tar = temp_dir.path().join("archive.tar");
    let mut writer = BufWriter::new(fs::File::create(&temp_tar)?);
    
    lzma_rs::xz_decompress(&mut reader, &mut writer)?;
    writer.flush()?;
    drop(writer);
    
    // Now extract the tar file
    let tar_file = fs::File::open(&temp_tar)?;
    let mut archive = Archive::new(tar_file);
    archive.unpack(install_dir)?;
    
    Ok(install_dir.to_path_buf())
}

fn finalize_install(extracted_path: &Path, install_dir: &Path) -> Result<PathBuf> {
    // Check if there's a single top-level directory
    let entries: Vec<_> = WalkDir::new(extracted_path)
        .min_depth(1)
        .max_depth(1)
        .into_iter()
        .filter_map(|e| e.ok())
        .collect();
    
    if entries.len() == 1 && entries[0].file_type().is_dir() {
        let subdir = entries[0].path();
        // Move contents up
        for entry in WalkDir::new(subdir).min_depth(1).into_iter().filter_map(|e| e.ok()) {
            let rel_path = entry.path().strip_prefix(subdir).unwrap();
            let dest = install_dir.join(rel_path);
            if entry.file_type().is_dir() {
                fs::create_dir_all(&dest)?;
            } else {
                if let Some(parent) = dest.parent() {
                    fs::create_dir_all(parent)?;
                }
                fs::copy(entry.path(), &dest)?;
            }
        }
        // Remove the now-empty subdirectory
        fs::remove_dir_all(subdir)?;
    }
    
    Ok(install_dir.to_path_buf())
}
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn safe_join_rejects_parent_traversal() {
        let dest = Path::new("/tmp/install");
        for name in ["../escaped.txt", "../../escaped.txt", "a/../../escaped.txt"] {
            let err = safe_join(dest, name).unwrap_err().to_string();
            assert!(err.contains("escapes install directory"), "{}: {}", name, err);
        }
    }

    #[test]
    fn safe_join_rejects_absolute_path() {
        let dest = Path::new("/tmp/install");
        assert!(safe_join(dest, "/etc/passwd").is_err());
    }

    #[test]
    fn safe_join_allows_normal_entries() {
        let dest = Path::new("/tmp/install");
        assert_eq!(safe_join(dest, "app/bin/tool.exe").unwrap(), dest.join("app/bin/tool.exe"));
        assert_eq!(safe_join(dest, "flat.exe").unwrap(), dest.join("flat.exe"));
    }

    #[test]
    fn digest_from_sidecar_handles_both_forms() {
        let bare = "A".repeat(64);
        assert_eq!(digest_from_text(&bare).as_deref(), Some(bare.to_ascii_lowercase().as_str()));
        // `<digest>  <filename>`, as produced by sha256sum
        let with_name = format!("{}  app-1.2.3.tar.gz\n", "b".repeat(64));
        assert_eq!(digest_from_text(&with_name), Some("b".repeat(64)));
    }

    #[test]
    fn digest_from_manifest_matches_by_basename() {
        let text = format!(
            "{}  other.zip\n{}  ./dist/app.zip\n{}  app.zip\n",
            "1".repeat(64),
            "2".repeat(64),
            "3".repeat(64)
        );
        // Exact match only: ./dist/app.zip is a different file from app.zip
        assert_eq!(digest_from_manifest(&text, "app.zip"), Some("3".repeat(64)));
        assert_eq!(digest_from_manifest(&text, "missing.zip"), None);
        // Binary-mode marker '*' is stripped
        let starred = format!("{} *app.zip\n", "4".repeat(64));
        assert_eq!(digest_from_manifest(&starred, "app.zip"), Some("4".repeat(64)));
    }

    #[test]
    fn digest_from_manifest_rejects_differently_nested_file() {
        // A same-basename entry in a subdirectory is a different file and must not
        // answer for the top-level asset.
        let text = format!("{}  dist/app.zip\n", "5".repeat(64));
        assert_eq!(digest_from_manifest(&text, "app.zip"), None);
    }
}
