use crate::core::{ConfigManager, StateManager};
use anyhow::{Context, Result};
use indicatif::{ProgressBar, ProgressStyle};
use minreq;
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use std::time::Duration;
use tempfile;
use tokio::time::sleep;
use tracing::{debug, info, warn};

/// Download a file with progress bar, returning the bytes
pub async fn download_with_progress(
    url: &str,
    token: Option<&str>,
    label: &str,
    config: &ConfigManager,
) -> Result<Vec<u8>> {
    let mut req = minreq::get(url).with_header("User-Agent", "ObtainHub/3.0.0");
    if let Some(token) = token {
        req = req.with_header("Authorization", &format!("Bearer {}", token));
    }

    let response = req
        .with_timeout(config.get().timeout_seconds as u64)
        .send()
        .context("Failed to send request")?;

    let total_size = response
        .headers
        .get("content-length")
        .and_then(|v| v.parse::<u64>().ok())
        .unwrap_or(0);

    let pb = ProgressBar::new(total_size);
    pb.set_style(
        ProgressStyle::default_bar()
            .template("{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {bytes}/{total_bytes} ({eta})")
            .unwrap()
            .progress_chars("#>-"),
    );
    pb.set_message(label.to_string());

    // Get bandwidth limit from config (bytes per second, 0 = unlimited)
    let bandwidth_limit = config.get().download_bandwidth_limit.unwrap_or(0);

    let bytes = response.as_bytes();
    let mut downloaded = 0u64;
    let chunk_size = 8192usize;
    let mut last_update = std::time::Instant::now();

    for chunk in bytes.chunks(chunk_size) {
        pb.inc(chunk.len() as u64);
        downloaded += chunk.len() as u64;

        // Bandwidth throttling
        if bandwidth_limit > 0 {
            let elapsed = last_update.elapsed().as_secs_f64();
            let expected_time = downloaded as f64 / bandwidth_limit as f64;
            if expected_time > elapsed {
                let sleep_time = Duration::from_secs_f64(expected_time - elapsed);
                sleep(sleep_time).await;
            }
        }

        last_update = std::time::Instant::now();
    }

    pb.finish_with_message(format!("Downloaded {}", label));
    Ok(bytes.to_vec())
}

/// Verify bytes against a published checksum
pub async fn verify_checksum(
    release: &crate::commands::install::GitHubRelease,
    asset_name: &str,
    bytes: &[u8],
    token: Option<&str>,
    config: &ConfigManager,
) -> Result<()> {
    if let Some(expected) = crate::commands::install::fetch_published_checksum(release, asset_name, token).await? {
        let actual = calculate_sha256_bytes(bytes);
        if !expected.eq_ignore_ascii_case(&actual) {
            anyhow::bail!(
                "Checksum mismatch for {}: expected {}, got {}",
                asset_name, expected, actual
            );
        }
        info!("Checksum verified for {}", asset_name);
    } else if config.get().verify_checksums {
        warn!("No published checksum for {} — skipping verification", asset_name);
    }
    Ok(())
}

/// Calculate SHA256 of bytes
pub fn calculate_sha256_bytes(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hex::encode(hasher.finalize())
}

/// Extract archive bytes to destination directory with zip-slip protection
pub fn extract_archive(name: &str, bytes: &[u8], dest: &Path) -> Result<()> {
    let name_lower = name.to_lowercase();

    if name_lower.ends_with(".zip") {
        extract_zip(bytes, dest)
    } else if name_lower.ends_with(".tar.gz") || name_lower.ends_with(".tgz") {
        extract_tar_gz(bytes, dest)
    } else if name_lower.ends_with(".tar.xz") || name_lower.ends_with(".txz") {
        extract_tar_xz(bytes, dest)
    } else {
        // Single binary or unknown - just copy
        let dest_path = dest.join(name);
        if let Some(parent) = dest_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(&dest_path, bytes)?;
        Ok(())
    }
}

fn extract_zip(bytes: &[u8], dest: &Path) -> Result<()> {
    let cursor = std::io::Cursor::new(bytes);
    let mut archive = zip::ZipArchive::new(cursor)?;
    for i in 0..archive.len() {
        let mut file = archive.by_index(i)?;
        let outpath = dest.join(file.name());

        // Zip-slip guard: reject entries that escape dest
        let mut normalized = PathBuf::new();
        for c in outpath.components() {
            match c {
                std::path::Component::ParentDir => { normalized.pop(); }
                std::path::Component::CurDir => {}
                other => normalized.push(other.as_os_str()),
            }
        }
        if !normalized.starts_with(dest) {
            anyhow::bail!("Refusing to extract '{}': path escapes install directory", file.name());
        }

        if file.name().ends_with('/') {
            std::fs::create_dir_all(&outpath)?;
        } else {
            if let Some(parent) = outpath.parent() {
                std::fs::create_dir_all(parent)?;
            }
            let mut outfile = std::fs::File::create(&outpath)?;
            std::io::copy(&mut file, &mut outfile)?;
        }
    }
    Ok(())
}

fn extract_tar_gz(bytes: &[u8], dest: &Path) -> Result<()> {
    let cursor = std::io::Cursor::new(bytes);
    let decoder = flate2::read::GzDecoder::new(cursor);
    let mut archive = tar::Archive::new(decoder);
    archive.unpack(dest)?;
    Ok(())
}

fn extract_tar_xz(bytes: &[u8], dest: &Path) -> Result<()> {
    use std::io::{BufWriter, Write};

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

/// Download, verify, and extract a release asset in one operation
pub async fn download_verify_extract(
    release: &crate::commands::install::GitHubRelease,
    asset_name: &str,
    token: Option<&str>,
    config: &ConfigManager,
    dest: &Path,
) -> Result<()> {
    info!("Downloading {}...", asset_name);

    // Find the asset
    let asset = release.assets.iter()
        .find(|a| a.name == asset_name)
        .ok_or_else(|| anyhow::anyhow!("Asset not found: {}", asset_name))?;

    // Download
    let bytes = download_with_progress(&asset.browser_download_url, token, asset_name, config).await?;

    // Verify checksum
    verify_checksum(release, asset_name, &bytes, token, config).await?;

    // Extract
    std::fs::create_dir_all(dest)?;
    extract_archive(asset_name, &bytes, dest)?;

    Ok(())
}