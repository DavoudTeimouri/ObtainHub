use crate::core::{ConfigManager, StateManager};
use crate::cli::UpdateArgs;
use crate::utils::retry::{execute_with_retry, RetryConfig};
use anyhow::{Context, Result};
use minreq;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::time::{Duration, SystemTime};
use tracing::{info, warn};
use urlencoding;
use indicatif::{ProgressBar, ProgressStyle};
use dialoguer::{MultiSelect, Select, theme::ColorfulTheme};

use crate::commands::install::{fetch_published_checksum, GitHubRelease as InstallGitHubRelease, GitHubAsset as InstallGitHubAsset, select_asset as install_select_asset};
use sha2::{Digest, Sha256};

fn calculate_sha256_bytes(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hex::encode(hasher.finalize())
}

#[derive(Deserialize, Serialize, Debug)]
struct GitHubRelease {
    #[serde(default = "default_tag_name")]
    tag_name: String,
    name: Option<String>,
    prerelease: bool,
    draft: bool,
    assets: Vec<GitHubAsset>,
    zipball_url: String,
    tarball_url: String,
}

fn default_tag_name() -> String {
    "unknown".to_string()
}

#[derive(Deserialize, Serialize, Debug, Clone)]
struct GitHubAsset {
    name: String,
    browser_download_url: String,
    size: u64,
    content_type: Option<String>,
}

async fn fetch_latest_release(repo: &str, token: Option<&str>, retry_config: &RetryConfig) -> Result<Option<GitHubRelease>> {
    let url = format!("https://api.github.com/repos/{}/releases/latest", repo);
    let token_clone = token.map(|s| s.to_string());

    let result = execute_with_retry(retry_config, || {
        let url = url.clone();
        let token = token_clone.clone();
        async move {
            let mut req = minreq::get(&url).with_header("User-Agent", "ObtainHub/3.0.0");
            if let Some(token) = token {
                req = req.with_header("Authorization", &format!("Bearer {token}"));
            }
            let resp = req.send()?;

            if resp.status_code == 404 {
                return Ok(None);
            }

            if resp.status_code == 403 {
                return Err(anyhow::anyhow!(
                    "GitHub API rate limited or access denied (403). Set a token: ohub config set github_token <token>"
                ));
            }

            if !(resp.status_code >= 200 && resp.status_code < 300) {
                return Err(anyhow::anyhow!("GitHub API error: {}", resp.status_code));
            }

            let release: GitHubRelease = resp.json()?;
            Ok(Some(release))
        }
    }, "fetch_latest_release").await?;

    Ok(result)
}

#[cfg(windows)]
fn enumerate_all_installed_software() -> Result<Vec<crate::core::state::InstalledRepo>> {
    use std::collections::HashSet;
    use winreg::enums::*;
    use winreg::RegKey;

    let mut results = Vec::new();
    let mut seen = HashSet::new();

    for &root in &[HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER] {
        for &view in &[KEY_WOW64_64KEY, KEY_WOW64_32KEY] {
            let hklm = RegKey::predef(root);
            let uninstall_path = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall";

            if let Ok(uninstall_key) = hklm.open_subkey_with_flags(uninstall_path, KEY_READ | view) {
                for subkey_name in uninstall_key.enum_keys().flatten() {
                    if let Ok(subkey) = uninstall_key.open_subkey_with_flags(&subkey_name, KEY_READ | view) {
                        let display_name: Option<String> = subkey.get_value("DisplayName").ok();
                        let display_version: Option<String> = subkey.get_value("DisplayVersion").ok();
                        let uninstall_string: Option<String> = subkey.get_value("UninstallString").ok();

                        if let Some(name) = display_name {
                            if name.contains("ObtainHub") {
                                continue;
                            }

                            let key = format!("{}|{}", name, display_version.clone().unwrap_or_default());
                            if seen.insert(key) {
                                results.push(crate::core::state::InstalledRepo {
                                    repo: name.clone(),
                                    version: display_version.unwrap_or_else(|| "unknown".to_string()),
                                    install_path: PathBuf::from(uninstall_string.unwrap_or_default()),
                                    installed_at: chrono::Utc::now(),
                                    updated_at: None,
                                    checksum: None,
                                    metadata: serde_json::Value::Null,
                                    previous_version: None,
                                    previous_install_path: None,
                                    dependencies: Vec::new(),
                                    is_dependency: false,
                                });
                            }
                        }
                    }
                }
            }
        }
    }

    Ok(results)
}

#[cfg(not(windows))]
fn enumerate_all_installed_software() -> Result<Vec<crate::core::state::InstalledRepo>> {
    Ok(Vec::new())
}

async fn find_candidate_repos(name: &str, token: Option<&str>, retry_config: &RetryConfig) -> Result<Vec<String>> {
    let cleaned = clean_app_name(name);

    // Build multiple search term candidates to maximize hit rate
    let mut search_terms: Vec<&str> = Vec::new();

    // 1. Full cleaned name
    if !cleaned.is_empty() {
        search_terms.push(cleaned.as_str());
    }

    // 2. First word of cleaned name (e.g. "OnionHop version" -> "OnionHop")
    if let Some(first) = cleaned.split_whitespace().next() {
        if !search_terms.iter().any(|&t| t == first) {
            search_terms.push(first);
        }
    }

    // 3. Original name with digits/dots removed
    let stripped: String = name.chars().filter(|c| !c.is_ascii_digit() && *c != '.').collect();
    let stripped = stripped.trim();
    if !stripped.is_empty() && !search_terms.iter().any(|&t| t == stripped) {
        search_terms.push(stripped);
    }

    // 4. Original name (last resort)
    if !search_terms.iter().any(|&t| t == name) {
        search_terms.push(name);
    }

    let mut all_candidates: Vec<String> = Vec::new();
    let mut seen = HashMap::new();

    for term in search_terms {
        if term.is_empty() {
            continue;
        }
        let encoded_name = urlencoding::encode(term);
        let url = format!("https://api.github.com/search/repositories?q={}&per_page=5", encoded_name);
        let token_clone = token.map(|s| s.to_string());

        let result = execute_with_retry(retry_config, || {
            let url = url.clone();
            let token = token_clone.clone();
            async move {
                let mut req = minreq::get(&url).with_header("User-Agent", "ObtainHub/3.0.0");
                if let Some(token) = token {
                    req = req.with_header("Authorization", &format!("Bearer {}", token));
                }
                let resp = req.send()?;

                // Non-2xx means rate limit, auth error, etc. - return empty candidates
                if !(resp.status_code >= 200 && resp.status_code < 300) {
                    return Ok(Vec::new());
                }

                let body = resp.as_bytes().to_vec();
                if body.is_empty() {
                    return Ok(Vec::new());
                }
                let resp: serde_json::Value = serde_json::from_slice(&body)?;
                let items = resp["items"].as_array().unwrap_or(&vec![]).to_vec();
                let mut candidates = Vec::new();
                for item in items {
                    if let Some(full_name) = item["full_name"].as_str() {
                        candidates.push(full_name.to_string());
                    }
                }
                Ok(candidates)
            }
        }, "find_candidate_repos").await;

        match result {
            Ok(candidates) => {
                for c in candidates {
                    if seen.insert(c.clone(), true).is_none() {
                        all_candidates.push(c);
                    }
                }
            }
            Err(e) => {
                // Only propagate error if this was the last term tried
                if !term.eq(name) {
                    continue;
                }
                return Err(e);
            }
        }
    }

    Ok(all_candidates)
}

fn normalize_version(v: &str) -> String {
    let v = v.trim();
    let v = v.strip_prefix('v').or_else(|| v.strip_prefix('V')).unwrap_or(v);
    v.to_string()
}

fn clean_app_name(name: &str) -> String {
    let mut cleaned = name.to_string();

    // Remove version-like tokens and common noise words
    let noise_words = ["version", "edition", "x64", "x86", "64bit", "32bit", "64-bit", "32-bit"];

    cleaned = cleaned.split(char::is_whitespace)
        .filter(|part| {
            let lower = part.to_lowercase();
            // Skip common noise words
            if noise_words.iter().any(|&w| lower == w) {
                return false;
            }
            let has_digit = part.chars().any(|c| c.is_ascii_digit());
            let has_dot = part.contains('.');
            let has_v_prefix = part.starts_with('v') || part.starts_with('V');
            if has_digit && (has_dot || has_v_prefix) && part.len() <= 10 {
                return false;
            }
            if part.len() == 1 && (*part == "v" || *part == "V") {
                return false;
            }
            true
        })
        .collect::<Vec<&str>>()
        .join(" ")
        .trim()
        .to_string();

    let suffixes = [" for windows", " for mac", " for linux", " portable", " installer", " setup"];
    for suffix in &suffixes {
        if cleaned.to_lowercase().ends_with(suffix) {
            cleaned = cleaned[..cleaned.len() - suffix.len()].trim().to_string();
        }
    }

    cleaned.trim().to_string()
}

pub async fn execute(args: UpdateArgs, config: &ConfigManager, state: &mut StateManager, retry_config: &RetryConfig) -> Result<()> {
    info!("Updating repositories");

    let token = config.get().github_token.as_deref();
    let install_dir = config.get().install_dir.clone();
    let download_dir = config.get().download_dir.clone();
    println!("Install directory: {}", install_dir.display());
    println!("Download directory: {}", download_dir.display());

    // Cleanup download folder: remove old duplicate downloads
    if let Err(e) = cleanup_download_folder(&download_dir) {
        eprintln!("Warning: download cleanup failed: {e}");
    }

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

        // First, check if this repo has dependencies that need updating
        if !args.skip_deps {
            let deps = state.get_installed(repo_name).map(|e| e.dependencies.clone()).unwrap_or_default();
            for dep in &deps {
                println!("  Checking dependency {}...", dep);
                if let Some(dep_entry) = state.get_installed(dep) {
                    match fetch_latest_release(dep, token, retry_config).await {
                        Ok(Some(dep_release)) => {
                            let dep_latest = dep_release.tag_name.clone();
                            if normalize_version(&dep_latest) != normalize_version(&dep_entry.version) {
                                println!("    Dependency update available: {} -> {}", dep_entry.version, dep_latest);
                                if !args.dry_run {
                                    match install_release(dep, &dep_latest, &dep_release, token, config, state, args.force, true, None).await {
                                        Ok(_) => println!("    Updated dependency {} to {}", dep, dep_latest),
                                        Err(e) => eprintln!("    Failed to update dependency {}: {}", dep, e),
                                    }
                                }
                            }
                        }
                        Ok(None) => {
                            // No releases found for dependency
                        }
                        Err(e) => eprintln!("    Error checking dependency {}: {}", dep, e),
                    }
                }
            }
        }

        match fetch_latest_release(repo_name, token, retry_config).await {
            Ok(Some(release)) => {
                let latest_version = release.tag_name.clone();
                let latest_norm = normalize_version(&latest_version);
                let current_norm = normalize_version(current_version);
                if latest_norm != current_norm {
                    println!("  Update available: {} -> {}", current_version, latest_version);

                    if args.dry_run {
                        updated.push((repo_name.clone(), current_version.clone(), latest_version));
                        continue;
                    }

                    // Perform update (reinstall with new version)
                    // Interactive asset selection: only .exe (setup) and .msi, correct architecture
                    let selected_asset = select_installer_asset(&release)?;
                    match install_release(repo_name, &latest_version, &release, token, config, state, args.force, args.skip_deps, Some(selected_asset)).await {
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
            Ok(None) => {
                // No releases found for this repo
                println!("  No releases found on GitHub");
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

/// Interactive asset selection for update: only .exe (setup) and .msi files,
/// matched to current architecture. MSI preferred over EXE. Other file types
/// (.zip, .tar.gz, etc.) are hidden. Falls back to all installers if no
/// arch-specific match is found (asset naming varies across repos).
fn select_installer_asset(release: &GitHubRelease) -> Result<GitHubAsset> {
    let target_arch = std::env::consts::ARCH;

    // Filter: only .exe and .msi files, matching current architecture
    let arch_tokens = [
        target_arch,
        "x86_64", "x64", "amd64", "64-bit", "64bit",
        "aarch64", "arm64",
        "win64", "windows", "win-x64",
    ];

    let arch_matching: Vec<&GitHubAsset> = release
        .assets
        .iter()
        .filter(|a| {
            let name = a.name.to_lowercase();
            let is_installer = name.ends_with(".exe") || name.ends_with(".msi");
            let arch_match = arch_tokens.iter().any(|t| name.contains(t));
            is_installer && arch_match
        })
        .collect();

    // Fallback: all .exe/.msi installers if no arch-specific match found
    let installer_assets: Vec<&GitHubAsset> = if arch_matching.is_empty() {
        release
            .assets
            .iter()
            .filter(|a| {
                let name = a.name.to_lowercase();
                name.ends_with(".exe") || name.ends_with(".msi")
            })
            .collect()
    } else {
        arch_matching
    };

    if installer_assets.is_empty() {
        anyhow::bail!(
            "No installer assets (.exe/.msi) found in release {}",
            release.tag_name
        );
    }

    // Sort: .msi first (preferred), then .exe, then alphabetical
    let mut sorted: Vec<&GitHubAsset> = installer_assets;
    sorted.sort_by(|a, b| {
        let a_msi = a.name.to_lowercase().ends_with(".msi");
        let b_msi = b.name.to_lowercase().ends_with(".msi");
        match b_msi.cmp(&a_msi) {
            std::cmp::Ordering::Equal => a.name.cmp(&b.name),
            other => other,
        }
    });

    let theme = ColorfulTheme::default();
    let items: Vec<String> = sorted
        .iter()
        .map(|a| format!("{} ({} bytes)", a.name, a.size))
        .collect();

    let choice = Select::with_theme(&theme)
        .with_prompt(format!(
            "Select installer asset for {} (arch: {})",
            release.tag_name, target_arch
        ))
        .items(&items)
        .default(0)
        .interact_opt()?;

    match choice {
        Some(idx) => Ok(sorted[idx].clone()),
        None => anyhow::bail!("No asset selected for update"),
    }
}

/// Resolve powershell.exe on Windows. Try explicit common paths first,
/// then fall back to PATH lookup.
#[cfg(windows)]
fn find_powershell() -> String {
    let candidates = [
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        r"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe",
    ];
    for c in candidates {
        if std::path::Path::new(c).exists() {
            return c.to_string();
        }
    }
    "powershell.exe".to_string()
}

#[cfg(not(windows))]
fn find_powershell() -> String {
    "powershell".to_string()
}

/// Run an installer (.exe/.msi) with elevation, waiting for completion.
/// Uses PowerShell Start-Process -Verb RunAs so the installer gets admin rights.
#[cfg(windows)]
fn run_installer(installer_path: &std::path::Path) -> Result<()> {
    let path_str = installer_path.to_string_lossy().to_string();
    let powershell = find_powershell();
    let powershell_cmd = if installer_path.extension().and_then(|s| s.to_str()) == Some("msi") {
        format!(
            "Start-Process 'msiexec' -ArgumentList '/i {} /qn /norestart' -Verb RunAs -Wait",
            path_str
        )
    } else {
        format!("Start-Process '{}' -ArgumentList '/S' -Verb RunAs -Wait", path_str)
    };

    let status = std::process::Command::new(&powershell)
        .args(&["-Command", powershell_cmd.as_str()])
        .status()
        .context("Failed to launch elevated installer")?;
    if !status.success() {
        anyhow::bail!("Installer exited with error code {:?}", status.code());
    }
    Ok(())
}

#[cfg(not(windows))]
fn run_installer(installer_path: &std::path::Path) -> Result<()> {
    let status = std::process::Command::new(installer_path)
        .status()
        .context("Failed to run installer")?;
    if !status.success() {
        anyhow::bail!("Installer exited with error code {:?}", status.code());
    }
    Ok(())
}

async fn install_release(
    repo: &str,
    version: &str,
    release: &GitHubRelease,
    token: Option<&str>,
    config: &ConfigManager,
    state: &mut StateManager,
    force: bool,
    _skip_deps: bool,
    selected_asset: Option<GitHubAsset>,
) -> Result<()> {
    let download_dir = config.get().download_dir.clone();
    println!("  Download directory: {}", download_dir.display());

    // Use interactively selected asset, or fall back to auto-select
    let asset = match selected_asset {
        Some(a) => a,
        None => {
            // Auto-select: convert to install types and use install_select_asset
            let install_rel = &InstallGitHubRelease {
                tag_name: release.tag_name.clone(),
                name: release.name.clone(),
                prerelease: release.prerelease,
                draft: release.draft,
                assets: release.assets.iter().map(|a| InstallGitHubAsset {
                    name: a.name.clone(),
                    browser_download_url: a.browser_download_url.clone(),
                    size: a.size,
                    content_type: a.content_type.clone(),
                }).collect(),
                zipball_url: release.zipball_url.clone(),
                tarball_url: release.tarball_url.clone(),
            };
            let selected = install_select_asset(install_rel)?;
            GitHubAsset {
                name: selected.name,
                browser_download_url: selected.browser_download_url,
                size: selected.size,
                content_type: selected.content_type,
            }
        }
    };

    let download_url = &asset.browser_download_url;

    // Install using install command's logic
    let install_dir = config.get().install_dir.join(repo);
    std::fs::create_dir_all(&install_dir)?;
    let asset_path = install_dir.join(&asset.name);

    // Get expected size from GitHub API for skip-check
    let mut total_size: u64 = 0;
    let expected_hash = {
        let install_rel_for_checksum = &InstallGitHubRelease {
            tag_name: release.tag_name.clone(),
            name: release.name.clone(),
            prerelease: release.prerelease,
            draft: release.draft,
            assets: release.assets.iter().map(|a| InstallGitHubAsset {
                name: a.name.clone(),
                browser_download_url: a.browser_download_url.clone(),
                size: a.size,
                content_type: a.content_type.clone(),
            }).collect(),
            zipball_url: release.zipball_url.clone(),
            tarball_url: release.tarball_url.clone(),
        };
        fetch_published_checksum(install_rel_for_checksum, &asset.name, token).await?
    };

    // Skip download if file already exists with matching size AND checksum
    let mut goto_skip_download = false;
    if asset_path.exists() {
        let existing_size = std::fs::metadata(&asset_path)?.len();
        if existing_size > 0 {
            total_size = existing_size;
            let existing_bytes = std::fs::read(&asset_path)?;
            let existing_hash = calculate_sha256_bytes(&existing_bytes);
            if let Some(expected) = &expected_hash {
                if expected.eq_ignore_ascii_case(&existing_hash) {
                    println!("  Already downloaded: {} ({} bytes)", asset.name, existing_size);
                    goto_skip_download = true;
                }
            }
        }
    }

    if !goto_skip_download {
        // Remove old file with same name before writing new one
        if asset_path.exists() {
            std::fs::remove_file(&asset_path)?;
        }

        // Download with progress bar
        let mut req = minreq::get(download_url).with_header("User-Agent", "ObtainHub/3.0.0");
        if let Some(token) = token {
            req = req.with_header("Authorization", &format!("Bearer {token}"));
        }

        let response = req.send()?;
        total_size = response
            .as_bytes()
            .len() as u64;
        let bytes = response.as_bytes().to_vec();

        let pb = ProgressBar::new(total_size);
        pb.set_style(
            ProgressStyle::default_bar()
                .template("{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {bytes}/{total_bytes} ({eta})")
                .unwrap()
                .progress_chars("#>-"),
        );
        pb.set_message(format!("Downloading {}", asset.name));
        pb.finish_with_message(format!("Downloaded {} ({} bytes)", asset.name, total_size));

        if let Some(expected) = expected_hash {
            let actual = calculate_sha256_bytes(&bytes);
            if !expected.eq_ignore_ascii_case(&actual) {
                return Err(anyhow::anyhow!("Checksum mismatch for {}", asset.name));
            }
        }

        // Write file
        std::fs::write(&asset_path, &bytes)?;
    }

    // Verify file was actually written (catches locked-file / permission failures)
    if !asset_path.exists() {
        return Err(anyhow::anyhow!(
            "Installation failed: {} was not written to {}",
            asset.name,
            asset_path.display()
        ));
    }
    let written_size = std::fs::metadata(&asset_path)?.len();
    if written_size == 0 {
        return Err(anyhow::anyhow!(
            "Installation failed: {} is empty (0 bytes) at {}",
            asset.name,
            asset_path.display()
        ));
    }
    if written_size != total_size {
        return Err(anyhow::anyhow!(
            "Installation failed: {} wrote {} bytes, expected {}",
            asset.name,
            written_size,
            total_size
        ));
    }

    // If it's an installer (.exe/.msi), run it so the app actually gets installed
    let is_installer = asset.name.ends_with(".exe") || asset.name.ends_with(".msi");
    if is_installer {
        println!("  Running installer: {}", asset.name);
        run_installer(&asset_path)?;
        // Verify installer ran: check app exe was updated
        if !asset_path.exists() {
            return Err(anyhow::anyhow!(
                "Installer ran but {} is missing afterwards",
                asset.name
            ));
        }
    }

    // Update state
    let mut new_repo = crate::core::state::InstalledRepo {
        repo: repo.to_string(),
        version: version.to_string(),
        install_path: asset_path,
        installed_at: chrono::Utc::now(),
        updated_at: Some(chrono::Utc::now()),
        checksum: None,
        metadata: serde_json::Value::Null,
        previous_version: Some(version.to_string()),
        previous_install_path: None,
        dependencies: Vec::new(),
        is_dependency: false,
    };
    state.add_installed(new_repo.clone());
    state.save()?;

    Ok(())
}

/// Cleanup download folder: for each base filename, keep only the latest
/// versioned file, remove older duplicates. Prevents download folder from
/// growing unboundedly across repeated updates.
fn cleanup_download_folder(download_dir: &std::path::Path) -> Result<()> {
    if !download_dir.exists() {
        return Ok(());
    }

    // Group files by base name (strip version-like suffixes)
    let mut groups: std::collections::HashMap<String, Vec<std::path::PathBuf>> =
        std::collections::HashMap::new();

    for entry in std::fs::read_dir(download_dir)? {
        let entry = entry?;
        let path = entry.path();
        if !path.is_file() {
            continue;
        }
        let file_name = path.file_name().unwrap_or_default().to_string_lossy().to_string();
        // Base name = strip everything after first version-like token (digits/dots)
        let base = file_name
            .split(|c: char| c.is_ascii_digit() || c == '.' || c == '-')
            .next()
            .unwrap_or(&file_name)
            .trim_end_matches(|c: char| c == '_' || c == ' ')
            .to_string();
        groups.entry(base).or_default().push(path);
    }

    // For each group, keep the file with the most recent modification time
    for (_, mut files) in groups {
        files.sort_by(|a, b| {
            let ma = a.metadata().and_then(|m| m.modified()).unwrap_or(SystemTime::UNIX_EPOCH);
            let mb = b.metadata().and_then(|m| m.modified()).unwrap_or(SystemTime::UNIX_EPOCH);
            mb.cmp(&ma) // newest first
        });
        // Remove all but the newest
        for path in files.into_iter().skip(1) {
            let _ = std::fs::remove_file(&path);
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clean_app_name_strips_version() {
        assert_eq!(clean_app_name("OnionHop V3 3.8.6"), "OnionHop");
        assert_eq!(clean_app_name("Aether-GUI"), "Aether-GUI");
        assert_eq!(clean_app_name("Obsidian"), "Obsidian");
    }
}
