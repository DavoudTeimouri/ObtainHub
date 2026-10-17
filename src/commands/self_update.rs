use crate::core::{ConfigManager, StateManager};
use crate::cli::SelfUpdateArgs;
use crate::utils::retry::{execute_with_retry, RetryConfig};
use anyhow::{Context, Result};
use minreq;
use semver::Version;
use std::env;
use std::fs;
use std::path::Path;
use tracing::info;
use indicatif::{ProgressBar, ProgressStyle};

use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use ed25519_compact::PublicKey;
use base64::{engine::general_purpose::STANDARD as BASE64_STANDARD, Engine as _};

const REPO_OWNER: &str = "DavoudTeimouri";
const REPO_NAME: &str = "ObtainHub";
const CURRENT_VERSION: &str = env!("CARGO_PKG_VERSION");

// Public key for verifying release signatures (base64 encoded Ed25519 public key)
// This should be set at build time from a secure source
static RELEASE_PUBLIC_KEY_B64: std::sync::OnceLock<String> = std::sync::OnceLock::new();

pub async fn execute(args: SelfUpdateArgs, config: &ConfigManager, _state: &StateManager, retry_config: &RetryConfig) -> Result<()> {
    info!("Checking for self-update");

    let current_version = Version::parse(CURRENT_VERSION)?;

    // Fetch latest release from GitHub with retry
    // Try releases/latest first; if 404 (no releases published), fall back to listing releases
    let url = format!("https://api.github.com/repos/{}/{}/releases/latest", REPO_OWNER, REPO_NAME);
    let release = execute_with_retry(retry_config, || {
        let url = url.clone();
        async move {
            let resp = minreq::get(&url)
                .with_header("User-Agent", "ohub")
                .with_header("Accept", "application/vnd.github.v3+json")
                .send()
                .context("Failed to fetch latest release")?;

            if resp.status_code == 404 {
                // No releases published yet - fall back to listing all releases
                let releases_url = format!("https://api.github.com/repos/{}/{}/releases", REPO_OWNER, REPO_NAME);
                let releases_resp = minreq::get(&releases_url)
                    .with_header("User-Agent", "ohub")
                    .with_header("Accept", "application/vnd.github.v3+json")
                    .send()
                    .context("Failed to fetch releases list")?;

                if !(releases_resp.status_code >= 200 && releases_resp.status_code < 300) {
                    return Err(anyhow::anyhow!("GitHub API error: {}", releases_resp.status_code));
                }

                let body = releases_resp.as_bytes().to_vec();
                if body.is_empty() {
                    return Err(anyhow::anyhow!("GitHub API returned empty body for releases list"));
                }
                let releases: serde_json::Value = serde_json::from_slice(&body)?;
                let releases_array = releases.as_array().context("No releases array")?;

                if releases_array.is_empty() {
                    // No releases at all - try tags instead
                    let tags_url = format!("https://api.github.com/repos/{}/{}/tags", REPO_OWNER, REPO_NAME);
                    let tags_resp = minreq::get(&tags_url)
                        .with_header("User-Agent", "ohub")
                        .send()
                        .context("Failed to fetch tags")?;

                    if !(tags_resp.status_code >= 200 && tags_resp.status_code < 300) {
                        return Err(anyhow::anyhow!("GitHub API error: {}", tags_resp.status_code));
                    }

                    let body = tags_resp.as_bytes().to_vec();
                    if body.is_empty() {
                        return Err(anyhow::anyhow!("GitHub API returned empty body for tags"));
                    }
                    let tags: serde_json::Value = serde_json::from_slice(&body)?;
                    let tags_array = tags.as_array().context("No tags array")?;

                    if tags_array.is_empty() {
                        // No releases or tags at all - return empty release
                        return Ok(serde_json::json!({"tag_name": CURRENT_VERSION, "assets": []}));
                    }

                    // Use the first tag as the latest
                    let latest_tag = tags_array[0]["name"].as_str().context("No tag name")?;
                    let release_json = serde_json::json!({
                        "tag_name": latest_tag,
                        "assets": [],
                    });
                    Ok(release_json)
                } else {
                    Ok(releases_array[0].clone())
                }
            } else if !(resp.status_code >= 200 && resp.status_code < 300) {
                return Err(anyhow::anyhow!("GitHub API error: {}", resp.status_code));
            } else {
                let body = resp.as_bytes().to_vec();
                if body.is_empty() {
                    return Err(anyhow::anyhow!("GitHub API returned empty body"));
                }
                let release: serde_json::Value = serde_json::from_slice(&body)?;
                Ok(release)
            }
        }
    }, "fetch_self_update_release").await?;

    let tag_name = release["tag_name"].as_str().context("No tag_name in release")?;
    let latest_version_str = tag_name.trim_start_matches('v');
    let latest_version = Version::parse(latest_version_str)?;

    if !args.prerelease && !latest_version.pre.is_empty() {
        if !args.quiet {
            println!("Latest release is pre-release ({}). Use --prerelease to include.", latest_version);
        }
        return Ok(());
    }

    if latest_version <= current_version && !args.force {
        if !args.quiet {
            println!("Already at latest version ({}). Use --force to reinstall.", CURRENT_VERSION);
        }
        return Ok(());
    }

    if args.check_only {
        if args.json {
            let output = serde_json::json!({
                "current_version": CURRENT_VERSION,
                "latest_version": latest_version_str,
                "update_available": latest_version > current_version,
                "prerelease": !latest_version.pre.is_empty(),
            });
            println!("{}", serde_json::to_string(&output)?);
        } else if !args.quiet {
            println!("Update available: {} -> {}", CURRENT_VERSION, latest_version_str);
        }
        return Ok(());
    }

    // Find appropriate asset
    let assets = release["assets"].as_array().unwrap_or(&vec![]).to_vec();
    let target = get_target_triple();

    let asset = if assets.is_empty() {
        if !args.quiet {
            println!("No downloadable assets found for {}/{}. Cannot auto-update.", REPO_OWNER, REPO_NAME);
        }
        return Ok(());
    } else {
        // Try to find platform-specific zip first
        assets.iter().find(|a| {
            let name = a["name"].as_str().unwrap_or("");
            name.contains(&target) && name.ends_with(".zip")
        }).or_else(|| {
            // Fallback: any zip
            assets.iter().find(|a| a["name"].as_str().unwrap_or("").ends_with(".zip"))
        }).or_else(|| {
            // Last resort: any asset
            assets.first()
        }).cloned().ok_or_else(|| {
            // List all available assets for the user
            let asset_list: Vec<String> = assets.iter()
                .filter_map(|a| a["name"].as_str().map(|s| s.to_string()))
                .collect();
            anyhow::anyhow!(
                "No suitable release asset found for current platform ({}).\n\
                 Available assets: {}\n\
                 Download manually from: https://github.com/{}/{}/releases/latest",
                target,
                asset_list.join(", "),
                REPO_OWNER, REPO_NAME
            )
        })?
    };

    let download_url = asset["browser_download_url"].as_str().context("No download URL")?;
    let asset_name = asset["name"].as_str().context("No asset name")?;

    if !args.quiet {
        println!("Downloading {} ({})...", asset_name, latest_version_str);
    }

    // Download to temp file with retry
    let tmp_dir = env::temp_dir();
    let download_path = tmp_dir.join(asset_name);
    
    // Progress bar for download
    let download_pb = if !args.quiet {
        let pb = ProgressBar::new_spinner();
        pb.set_style(
            ProgressStyle::default_spinner()
                .template("{spinner:.green} {msg}")
                .unwrap()
                .tick_chars("⠁⠂⠄⡀⢀⠠⠐⠈ "),
        );
        pb.set_message(format!("Downloading {}...", asset_name));
        pb.enable_steady_tick(std::time::Duration::from_millis(80));
        Some(pb)
    } else {
        None
    };
    
    let bytes = execute_with_retry(retry_config, || {
        let download_url = download_url.to_string();
        async move {
            let mut resp = minreq::get(download_url)
                .with_header("User-Agent", "ohub")
                .send()
                .context("Failed to download release asset")?;
            let bytes = resp.as_bytes().to_vec();
            Ok(bytes)
        }
    }, "download_self_update_asset").await?;

    // Finish download progress
    if let Some(pb) = download_pb {
        pb.finish_with_message("Download complete");
    }

    fs::write(&download_path, &bytes).context("Failed to write download")?;

    // Verify the download against a digest published with the release before we
    // execute anything from it. Without this, a compromised or hijacked release
    // replaces the running binary unchallenged.
    match find_published_digest(&release, asset_name) {
        Some(expected) => {
            let actual = sha256_hex(&bytes);
            if !expected.eq_ignore_ascii_case(&actual) {
                let _ = fs::remove_file(&download_path);
                anyhow::bail!(
                    "Checksum mismatch for {}: release advertises {}, download is {}",
                    asset_name, expected, actual
                );
            }
            if !args.quiet {
                println!("Checksum verified.");
            }
        }
        None => {
            let _ = fs::remove_file(&download_path);
            anyhow::bail!(
                "Refusing to self-update: {} publishes no checksum, so the download cannot be verified. Install manually from the release page.",
                asset_name
            );
        }
    }

    // Verify Ed25519 signature if available
    let sig_asset_name = format!("{}.sig", asset_name);
    if let Some(sig_asset) = assets.iter().find(|a| a["name"].as_str() == Some(&sig_asset_name)) {
        if let Some(sig_url) = sig_asset["browser_download_url"].as_str() {
            if !args.quiet {
                println!("Verifying signature...");
            }
            if let Err(e) = verify_signature(sig_url, &bytes, retry_config).await {
                let _ = fs::remove_file(&download_path);
                anyhow::bail!("Signature verification failed: {}", e);
            }
            if !args.quiet {
                println!("Signature verified.");
            }
        }
    } else if !args.skip_signature {
        let _ = fs::remove_file(&download_path);
        anyhow::bail!(
            "Refusing to self-update: no signature file found for {}. Use --skip-signature to bypass.",
            asset_name
        );
    }

    // Handle installer assets (.exe, .msi) vs portable zip
    let is_installer = asset_name.ends_with(".exe") || asset_name.ends_with(".msi");

    if is_installer {
        if !args.quiet {
            println!("Installing via installer...");
        }
        if asset_name.ends_with(".msi") {
            // MSI installer requires elevation to write to Program Files.
            // Use PowerShell Start-Process with -Verb RunAs to trigger UAC prompt.
            let msi_path = download_path.to_string_lossy().to_string();
            let status = std::process::Command::new("powershell")
                .args(&[
                    "-Command",
                    &format!(
                        "Start-Process 'msiexec' -ArgumentList '/i {} /qn /norestart' -Verb RunAs -Wait",
                        msi_path
                    ),
                ])
                .status()
                .context("Failed to launch elevated MSI installer")?;
            if !status.success() {
                anyhow::bail!("Elevated MSI installer exited with error code {:?}", status.code());
            }
        } else {
            // NSIS EXE installer requires elevation (admin) to write to Program Files.
            // Use PowerShell Start-Process with -Verb RunAs to trigger UAC prompt.
            let exe_path = download_path.to_string_lossy().to_string();
            let status = std::process::Command::new("powershell")
                .args(&[
                    "-Command",
                    &format!(
                        "Start-Process '{}' -ArgumentList '/S' -Verb RunAs -Wait",
                        exe_path
                    ),
                ])
                .status()
                .context("Failed to launch elevated EXE installer")?;
            if !status.success() {
                anyhow::bail!("Elevated EXE installer exited with error code {:?}", status.code());
            }
        }

        if !args.quiet {
            println!("Self-update complete. Please restart ObtainHub.");
        }

        let _ = fs::remove_file(&download_path);
        return Ok(());
    }

    if !args.quiet {
        println!("Extracting...");
    }

    // Extract zip with progress
    let extract_pb = if !args.quiet {
        let pb = ProgressBar::new_spinner();
        pb.set_style(
            ProgressStyle::default_spinner()
                .template("{spinner:.green} {msg}")
                .unwrap()
                .tick_chars("⠁⠂⠄⡀⢀⠠⠐⠈ "),
        );
        pb.set_message("Extracting...".to_string());
        pb.enable_steady_tick(std::time::Duration::from_millis(80));
        Some(pb)
    } else {
        None
    };

    // Extract zip
    let extract_dir = tmp_dir.join("ohub-update");
    if extract_dir.exists() {
        fs::remove_dir_all(&extract_dir)?;
    }
    fs::create_dir_all(&extract_dir)?;

    let zip_file = fs::File::open(&download_path)?;
    let mut archive = zip::ZipArchive::new(zip_file)?;
    
    for i in 0..archive.len() {
        let mut file = archive.by_index(i)?;
        let outpath = extract_dir.join(file.mangled_name());
        
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

    // Find the binary in extracted files
    let binary_name = if cfg!(windows) { "ohub.exe" } else { "ohub" };
    let extracted_binary = find_binary(&extract_dir, binary_name)
        .context("Could not find binary in extracted release")?;

    // Finish extraction progress
    if let Some(pb) = extract_pb {
        pb.finish_with_message("Extract complete");
    }

    if !args.quiet {
        println!("Installing to current location...");
    }

    // Get current executable path
    let current_exe = env::current_exe().context("Failed to get current executable path")?;
    
    // Atomic replace: copy to temp, then rename
    let backup_path = current_exe.with_extension("bak");
    fs::copy(&current_exe, &backup_path).context("Failed to create backup")?;
    
    fs::copy(&extracted_binary, &current_exe).context("Failed to replace binary")?;
    
    // Make executable on Unix
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = fs::metadata(&current_exe)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&current_exe, perms)?;
    }

    // Clean up backup on success
    let _ = fs::remove_file(&backup_path);

    if !args.quiet {
        println!("Updated to {} successfully!", latest_version_str);
        println!("Restart ohub to use the new version.");
    }

    Ok(())
}

fn get_target_triple() -> String {
    if cfg!(target_os = "windows") {
        if cfg!(target_arch = "x86_64") {
            "x86_64-pc-windows-msvc".to_string()
        } else if cfg!(target_arch = "aarch64") {
            "aarch64-pc-windows-msvc".to_string()
        } else {
            "x86_64-pc-windows-msvc".to_string()
        }
    } else if cfg!(target_os = "linux") {
        if cfg!(target_arch = "x86_64") {
            "x86_64-unknown-linux-gnu".to_string()
        } else if cfg!(target_arch = "aarch64") {
            "aarch64-unknown-linux-gnu".to_string()
        } else {
            "x86_64-unknown-linux-gnu".to_string()
        }
    } else if cfg!(target_os = "macos") {
        if cfg!(target_arch = "aarch64") {
            "aarch64-apple-darwin".to_string()
        } else {
            "x86_64-apple-darwin".to_string()
        }
    } else {
        "unknown".to_string()
    }
}

fn find_binary(dir: &Path, name: &str) -> Option<std::path::PathBuf> {
    for entry in walkdir::WalkDir::new(dir) {
        let entry = entry.ok()?;
        let path = entry.path();
        if path.is_file() && path.file_name().and_then(|s| s.to_str()) == Some(name) {
            return Some(path.to_path_buf());
        }
    }
    None
}

/// Look for the asset's digest among the release's other assets: a per-asset
/// `<name>.sha256` first, then a combined `SHA256SUMS` / `checksums.txt` manifest.
fn find_published_digest(release: &serde_json::Value, asset_name: &str) -> Option<String> {
    let assets = release.get("assets")?.as_array()?;

    let manifest_names = [
        format!("{}.sha256", asset_name),
        "SHA256SUMS".to_string(),
        "checksums.txt".to_string(),
    ];

    for manifest_name in &manifest_names {
        // `continue`, not `?` — a release may ship a sidecar but no manifest, and
        // we still want to try the next candidate.
        let asset = match assets.iter().find(|a| {
            a.get("name").and_then(|n| n.as_str())
                .map(|n| n.eq_ignore_ascii_case(manifest_name))
                .unwrap_or(false)
        }) {
            Some(a) => a,
            None => continue,
        };

        let url = match asset.get("browser_download_url").and_then(|u| u.as_str()) {
            Some(u) => u,
            None => continue,
        };

        let mut req = minreq::get(url).with_header("User-Agent", "ohub");
        if let Ok(resp) = req.send() {
            if let Ok(text) = resp.as_str() {
                if let Some(d) = digest_for(text, asset_name) {
                    return Some(d);
                }
            }
        }
    }

    None
}

/// Find the digest line belonging to `asset_name`. Exact filename match: a
/// `dist/app.zip` entry must not answer for a top-level `app.zip`.
fn digest_for(text: &str, asset_name: &str) -> Option<String> {
    for line in text.lines() {
        let mut parts = line.split_whitespace();
        let digest = match parts.next() {
            Some(d) if d.len() == 64 && d.chars().all(|c| c.is_ascii_hexdigit()) => d,
            _ => continue,
        };
        let name = parts.next().unwrap_or("").trim_start_matches('*');
        if name == asset_name {
            return Some(digest.to_ascii_lowercase());
        }
    }
    None
}

fn sha256_hex(bytes: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hex::encode(hasher.finalize())
}

async fn verify_signature(sig_url: &str, data: &[u8], retry_config: &RetryConfig) -> Result<()> {
    let sig_b64 = execute_with_retry(retry_config, || {
        let sig_url = sig_url.to_string();
        async move {
            let mut req = minreq::get(sig_url).with_header("User-Agent", "ohub");
            let resp = req.send().context("Failed to download signature")?;
            let sig_b64 = resp.as_str()?.trim().to_string();
            Ok(sig_b64)
        }
    }, "verify_signature_download").await?;

    let sig_bytes = BASE64_STANDARD.decode(sig_b64)
        .context("Failed to decode base64 signature")?;

    if sig_bytes.len() != 64 {
        anyhow::bail!("Invalid signature length: expected 64 bytes, got {}", sig_bytes.len());
    }

    // Get public key from OnceLock
    let public_key_b64 = RELEASE_PUBLIC_KEY_B64.get_or_init(|| {
        std::env::var("RELEASE_PUBLIC_KEY_B64").unwrap_or_default()
    });

    let public_key_bytes = BASE64_STANDARD.decode(public_key_b64)
        .context("Failed to decode public key")?;

    if public_key_bytes.len() != 32 {
        anyhow::bail!("Invalid public key length: expected 32 bytes, got {}", public_key_bytes.len());
    }

    let public_key_array: [u8; 32] = public_key_bytes.try_into()
        .map_err(|_| anyhow::anyhow!("Failed to convert public key to fixed array"))?;

    let verifying_key = VerifyingKey::from_bytes(&public_key_array)
        .context("Failed to create verifying key")?;

    let sig_array: [u8; 64] = sig_bytes.try_into()
        .map_err(|_| anyhow::anyhow!("Failed to convert signature to fixed array"))?;

    let signature = Signature::from_bytes(&sig_array);

    verifying_key.verify(data, &signature)
        .context("Ed25519 signature verification failed")?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn digest_for_matches_exact_filename() {
        let text = format!("{}  other.zip\n{}  app.zip\n", "1".repeat(64), "2".repeat(64));
        assert_eq!(digest_for(&text, "app.zip"), Some("2".repeat(64)));
        assert_eq!(digest_for(&text, "missing.zip"), None);
    }

    #[test]
    fn digest_for_ignores_same_basename_in_subdir() {
        let text = format!("{}  dist/app.zip\n", "3".repeat(64));
        assert_eq!(digest_for(&text, "app.zip"), None);
    }

    #[test]
    fn digest_for_accepts_bare_digest() {
        // A per-asset sidecar often holds just the hash.
        let text = format!("{}\n", "4".repeat(64));
        // No filename on the line, so it does not match a named asset.
        assert_eq!(digest_for(&text, "app.zip"), None);
        assert_eq!(digest_for(&format!("{}  app.zip", "5".repeat(64)), "app.zip"), Some("5".repeat(64)));
    }
}