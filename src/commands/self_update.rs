use crate::core::{ConfigManager, StateManager};
use crate::cli::SelfUpdateArgs;
use anyhow::{Context, Result};
use minreq;
use semver::Version;
use std::env;
use std::fs;
use std::path::Path;
use tracing::info;

const REPO_OWNER: &str = "DavoudTeimouri";
const REPO_NAME: &str = "ObtainHub";
const CURRENT_VERSION: &str = env!("CARGO_PKG_VERSION");

pub async fn execute(args: SelfUpdateArgs, _config: &ConfigManager, _state: &StateManager) -> Result<()> {
    info!("Checking for self-update");

    let current_version = Version::parse(CURRENT_VERSION)?;

    // Fetch latest release from GitHub
    let url = format!("https://api.github.com/repos/{}/{}/releases/latest", REPO_OWNER, REPO_NAME);
    let resp = minreq::get(&url)
        .with_header("User-Agent", "ohub")
        .with_header("Accept", "application/vnd.github.v3+json")
        .send()
        .context("Failed to fetch latest release")?;

    if !(resp.status_code >= 200 && resp.status_code < 300) {
        return Err(anyhow::anyhow!("GitHub API error: {}", resp.status_code));
    }

    let release: serde_json::Value = resp.json()?;
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
    let assets = release["assets"].as_array().context("No assets in release")?;
    let target = get_target_triple();
    
    let asset = assets.iter().find(|a| {
        let name = a["name"].as_str().unwrap_or("");
        name.contains(&target) && name.ends_with(".zip")
    }).or_else(|| {
        // Fallback: any zip
        assets.iter().find(|a| a["name"].as_str().unwrap_or("").ends_with(".zip"))
    }).context("No suitable release asset found for current platform")?;

    let download_url = asset["browser_download_url"].as_str().context("No download URL")?;
    let asset_name = asset["name"].as_str().context("No asset name")?;

    if !args.quiet {
        println!("Downloading {} ({})...", asset_name, latest_version_str);
    }

    // Download to temp file
    let tmp_dir = env::temp_dir();
    let download_path = tmp_dir.join(asset_name);
    
    let mut resp = minreq::get(download_url)
        .with_header("User-Agent", "ohub")
        .send()
        .context("Failed to download release asset")?;

    let bytes = resp.as_bytes();
    fs::write(&download_path, bytes).context("Failed to write download")?;

    if !args.quiet {
        println!("Extracting...");
    }

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