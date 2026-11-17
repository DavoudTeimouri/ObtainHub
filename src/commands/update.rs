use crate::core::{ConfigManager, StateManager, run_installer};
use crate::cli::{Arch, UpdateArgs};
use crate::utils::retry::{execute_with_retry, RetryConfig};
use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};
use tracing::info;
use dialoguer::{Select, theme::ColorfulTheme, Confirm};
use zip::ZipWriter;
use zip::write::FileOptions;
use zip::read::ZipArchive;
use flate2::read::GzDecoder;
use tar::Archive;

use crate::commands::install::{fetch_published_checksum, GitHubAsset, GitHubRelease, select_asset as install_select_asset};

/// Prints progress to stdout (unless quiet) and appends everything to an
/// optional log file, so scheduled runs leave a record behind.
struct Reporter {
    quiet: bool,
    log: Option<std::fs::File>,
}

impl Reporter {
    fn new(quiet: bool, log_path: Option<&str>) -> Self {
        let log = log_path.and_then(|p| {
            if let Some(parent) = std::path::Path::new(p).parent() {
                let _ = std::fs::create_dir_all(parent);
            }
            std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(p)
                .ok()
        });
        Reporter { quiet, log }
    }

    /// Progress message: stdout only when not quiet, always logged.
    fn say(&mut self, msg: &str) {
        if !self.quiet {
            println!("{msg}");
        }
        self.write(msg);
    }

    /// Error message: always on stderr, always logged.
    fn err(&mut self, msg: &str) {
        eprintln!("{msg}");
        self.write(msg);
    }

    fn write(&mut self, msg: &str) {
        use std::io::Write;
        if let Some(f) = &mut self.log {
            let _ = writeln!(f, "{msg}");
        }
    }
}


async fn fetch_latest_release(repo: &str, token: Option<&str>, retry_config: &RetryConfig) -> Result<Option<GitHubRelease>> {
    let url = format!("https://api.github.com/repos/{}/releases/latest", repo);
    let token_clone = token.map(|s| s.to_string());

    let result = execute_with_retry(retry_config, || {
        let url = url.clone();
        let token = token_clone.clone();
        async move {
            let mut req = crate::core::registries::github_get(&url);
            if let Some(token) = token {
                req = req.with_header("Authorization", format!("Bearer {token}"));
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

/// Fetch a specific release by tag. Used by rollback to re-install an older version.
pub(crate) async fn fetch_release_by_tag(
    repo: &str,
    tag: &str,
    token: Option<&str>,
    retry_config: &RetryConfig,
) -> Result<Option<GitHubRelease>> {
    let url = format!("https://api.github.com/repos/{}/releases/tags/{}", repo, tag);
    let token_clone = token.map(|s| s.to_string());

    let result = execute_with_retry(retry_config, || {
        let url = url.clone();
        let token = token_clone.clone();
        async move {
            let mut req = crate::core::registries::github_get(&url);
            if let Some(token) = token {
                req = req.with_header("Authorization", format!("Bearer {token}"));
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
    }, "fetch_release_by_tag").await?;

    Ok(result)
}

pub async fn execute(args: UpdateArgs, config: &ConfigManager, state: &mut StateManager, retry_config: &RetryConfig) -> Result<()> {
    info!("Updating repositories");

    let token_owned = config.github_token();
    let token = token_owned.as_deref();
    let install_dir = config.get().install_dir.clone();
    let download_dir = config.get().download_dir.clone();
    let mut reporter = Reporter::new(args.quiet, args.log.as_deref());

    if let Some(timeout) = args.timeout {
        crate::core::registries::set_request_timeout(timeout);
    } else {
        // Default 30s timeout so a slow/unresponsive GitHub API cannot hang the update indefinitely.
        crate::core::registries::set_request_timeout(30);
    }
    reporter.say(&format!("Install directory: {}", install_dir.display()));
    reporter.say(&format!("Download directory: {}", download_dir.display()));

    // Cleanup download folder: remove old duplicate downloads
    if let Err(e) = cleanup_download_folder(&download_dir) {
        reporter.err(&format!("Warning: download cleanup failed: {e}"));
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
        reporter.say(&format!("Checking {}@{}...", repo_name, current_version));

        // First, check if this repo has dependencies that need updating
        if !args.skip_deps {
            let deps = state.get_installed(repo_name).map(|e| e.dependencies.clone()).unwrap_or_default();
            for dep in &deps {
                reporter.say(&format!("  Checking dependency {}...", dep));
                if let Some(dep_entry) = state.get_installed(dep) {
                    match fetch_latest_release(dep, token, retry_config).await {
                        Ok(Some(dep_release)) => {
                            let dep_latest = dep_release.tag_name.clone();
                            if crate::core::normalize_version(&dep_latest) != crate::core::normalize_version(&dep_entry.version) {
                                reporter.say(&format!("    Dependency update available: {} -> {}", dep_entry.version, dep_latest));
                                if !args.dry_run {
                                    match install_release(dep, &dep_latest, &dep_release, token, config, state, None, args.quiet, Some(dep_entry.version.clone()), &args.arch).await {
                                        Ok(_) => reporter.say(&format!("    Updated dependency {} to {}", dep, dep_latest)),
                                        Err(e) => reporter.err(&format!("    Failed to update dependency {}: {}", dep, e)),
                                    }
                                }
                            }
                        }
                        Ok(None) => {
                            // No releases found for dependency
                        }
                        Err(e) => reporter.err(&format!("    Error checking dependency {}: {}", dep, e)),
                    }
                }
            }
        }

        // Folder-added apps have repo = exe name (no '/'), not a GitHub repo.
        // They must be linked via /apps/link-repo before updates can find releases.
        if !repo_name.contains('/') {
            reporter.say(&format!(
                "  Not a GitHub repository — run 'ohub link-repo {} <owner/repo>' to link it for updates",
                repo_name
            ));
            continue;
        }
        match fetch_latest_release(repo_name, token, retry_config).await {
            Ok(Some(release)) => {
                let latest_version = release.tag_name.clone();
                let latest_norm = crate::core::normalize_version(&latest_version);
                let current_norm = crate::core::normalize_version(current_version);
                if latest_norm == current_norm {
                    if !args.force {
                        already_current.push(repo_name.clone());
                        reporter.say("  Already at latest version");
                        continue;
                    }
                    // --force reinstalls the version that is already there.
                    reporter.say(&format!("  Force reinstalling {current_version}"));
                } else {
                    reporter.say(&format!("  Update available: {} -> {}", current_version, latest_version));
                }

                if args.dry_run {
                    updated.push((repo_name.clone(), current_version.clone(), latest_version));
                    continue;
                }

                // Perform update (reinstall with new version)
                // Folder-added apps (install_path is an exe) update in place and
                // may distribute as zip/portable archives, not just .exe/.msi installers.
                let is_folder_app = state
                    .get_installed(&repo_name)
                    .map(|e| PathBuf::from(&e.install_path).is_file())
                    .unwrap_or(false);
                let installer_only = !is_folder_app;
                let selected_asset = if let Some(asset_name) = &args.asset {
                    // User-specified asset (from WebUI picker): look it up by name
                    release
                        .assets
                        .iter()
                        .find(|a| a.name == *asset_name)
                        .cloned()
                        .ok_or_else(|| {
                            anyhow::anyhow!(
                                "Asset '{}' not found in release {}",
                                asset_name,
                                release.tag_name
                            )
                        })?
                } else {
                    // Interactive asset selection: only .exe (setup) and .msi, correct architecture.
                    // Get the best installer as default, then offer a list if not quiet.
                    let default = install_select_asset(&release, &args.arch, None, installer_only)?;
                    let installer_assets: Vec<&GitHubAsset> = release
                        .assets
                        .iter()
                        .filter(|a| {
                            let name = a.name.to_lowercase();
                            if installer_only {
                                name.ends_with(".exe") || name.ends_with(".msi")
                            } else {
                                // Folder app: zip/tar.gz archives or executables are eligible.
                                name.ends_with(".exe")
                                    || name.ends_with(".msi")
                                    || name.ends_with(".zip")
                                    || name.ends_with(".tar.gz")
                                    || name.ends_with(".tgz")
                            }
                        })
                        .collect();
                    if args.quiet || installer_assets.is_empty() {
                        default
                    } else {
                        // Sort: .msi first, then .exe, then alphabetical
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
                                "Select installer asset for {} (arch: {:?})",
                                release.tag_name, args.arch
                            ))
                            .items(&items)
                            .default(0)
                            .interact_opt()?;
                        match choice {
                            Some(idx) => sorted[idx].clone(),
                            None => default,
                        }
                    }
                };
                match install_release(repo_name, &latest_version, &release, token, config, state, Some(selected_asset), args.quiet, Some(current_version.to_string()), &args.arch).await {
                    Ok(_) => {
                        // Clear update-available flag and bump version in state.
                        if let Some(entry) = state.get_mut().installed.get_mut(repo_name) {
                            entry.version = latest_version.clone();
                            entry.update_available = false;
                            entry.latest_version = None;
                            entry.updated_at = Some(chrono::Utc::now());
                        }
                        updated.push((repo_name.clone(), current_version.clone(), latest_version.clone()));
                        reporter.say(&format!("  Updated to {}", latest_version));
                    }
                    Err(e) => {
                        errors.push((repo_name.clone(), e.to_string()));
                        reporter.err(&format!("  Failed: {}", e));
                    }
                }
            }
            Ok(None) => {
                // No releases found for this repo
                reporter.say("  No releases found on GitHub");
            }
            Err(e) => {
                errors.push((repo_name.clone(), e.to_string()));
                reporter.err(&format!("  Error checking: {}", e));
            }
        }
    }

    // Summary
    reporter.say("\nUpdate Summary:");
    if !updated.is_empty() {
        reporter.say(&format!("  Updated ({})", updated.len()));
        for (repo, old, new) in &updated {
            reporter.say(&format!("    {} {} -> {}", repo, old, new));
        }
    }

    // Release notes for every repo that was just updated.
    if args.notes && !updated.is_empty() {
        for (repo, _, _) in &updated {
            let block = crate::core::registries::release_notes_block(repo, token, retry_config).await;
            reporter.say(block.trim_end());
        }
    }

    if !already_current.is_empty() {
        reporter.say(&format!("  Already current ({})", already_current.len()));
        for repo in &already_current {
            reporter.say(&format!("    {}", repo));
        }
    }

    if !errors.is_empty() {
        reporter.say(&format!("  Errors ({})", errors.len()));
        for (repo, error) in &errors {
            reporter.say(&format!("    {}: {}", repo, error));
        }
    }

    // Scheduled runs rely on the exit code to report failure.
    if !errors.is_empty() {
        anyhow::bail!("{} update(s) failed", errors.len());
    }

    Ok(())
}

// ponytail: 10 parameters is over the 7-argument comfort line. Bundling them
// into an options struct is the upgrade path once a third caller appears.
#[allow(clippy::too_many_arguments)]
pub(crate) async fn install_release(
    repo: &str,
    version: &str,
    release: &GitHubRelease,
    token: Option<&str>,
    config: &ConfigManager,
    state: &mut StateManager,
    selected_asset: Option<GitHubAsset>,
    quiet: bool,
    previous_version: Option<String>,
    arch: &Arch,
) -> Result<()> {
    // Use interactively selected asset, or fall back to auto-select
    let asset = match selected_asset {
        Some(a) => a,
        None => install_select_asset(release, arch, None, false)?,
    };

    let download_url = &asset.browser_download_url;
    let config_data = config.get();
    let download_dir = &config_data.download_dir;

    // Determine install directory: folder-added apps update in place
    let install_dir = if let Some(existing) = state.get_installed(repo) {
        let existing_path = PathBuf::from(&existing.install_path);
        if existing_path.is_file() {
            // Folder-added app: install into the directory containing the existing exe
            existing_path.parent().unwrap_or(&existing_path).to_path_buf()
        } else if existing_path.is_dir() {
            existing_path
        } else {
            config_data.install_dir.join(repo)
        }
    } else {
        config_data.install_dir.join(repo)
    };

    std::fs::create_dir_all(download_dir)?;
    std::fs::create_dir_all(&install_dir)?;

    // Download to ObtainHub's download folder (not the app folder)
    let download_path = download_dir.join(&asset.name);

    // Get expected size from GitHub API for skip-check
    let mut total_size: u64 = 0;
    let expected_hash = {
        fetch_published_checksum(release, &asset.name, token).await?
    };

    // Skip download if file already exists with matching size AND checksum
    let mut goto_skip_download = false;
    if download_path.exists() {
        let existing_size = std::fs::metadata(&download_path)?.len();
        if existing_size > 0 {
            total_size = existing_size;
            let existing_bytes = std::fs::read(&download_path)?;
            let existing_hash = crate::core::assets::calculate_sha256_bytes(&existing_bytes);
            if let Some(expected) = &expected_hash {
                if expected.eq_ignore_ascii_case(&existing_hash) {
                    if !quiet {
                        println!("  Already downloaded: {} ({} bytes)", asset.name, existing_size);
                    }
                    goto_skip_download = true;
                }
            }
        }
    }

    if !goto_skip_download {
        if download_path.exists() {
            std::fs::remove_file(&download_path)?;
        }

        // Download with progress bar
        crate::core::download::to_file(
            &crate::core::download::Download {
                url: download_url,
                dest: &download_path,
                token,
                label: &asset.name,
                size: Some(asset.size),
                quiet,
                overall_timeout_secs: None,
            },
            config,
        )
        .await?;

        total_size = std::fs::metadata(&download_path)?.len();

        if let Some(expected) = expected_hash {
            let bytes = std::fs::read(&download_path)?;
            let actual = crate::core::assets::calculate_sha256_bytes(&bytes);
            if !expected.eq_ignore_ascii_case(&actual) {
                let _ = std::fs::remove_file(&download_path);
                return Err(anyhow::anyhow!("Checksum mismatch for {}", asset.name));
            }
        }
    }

    // Verify file was actually written (catches locked-file / permission failures)
    if !download_path.exists() {
        return Err(anyhow::anyhow!(
            "Download failed: {} was not written to {}",
            asset.name,
            download_path.display()
        ));
    }
    let written_size = std::fs::metadata(&download_path)?.len();
    if written_size == 0 {
        return Err(anyhow::anyhow!(
            "Download failed: {} is empty (0 bytes) at {}",
            asset.name,
            download_path.display()
        ));
    }
    if written_size != total_size {
        return Err(anyhow::anyhow!(
            "Download failed: {} wrote {} bytes, expected {}",
            asset.name,
            written_size,
            total_size
        ));
    }

    // Check if this is a folder-added app (existing install_path is a file/exe)
    let is_folder_app = state
        .get_installed(repo)
        .map(|e| PathBuf::from(&e.install_path).is_file())
        .unwrap_or(false);

    if is_folder_app {
        return install_folder_app(
            repo, version, &download_path, &install_dir, state, previous_version, quiet,
        ).await;
    }

    // Non-folder app: run installer (.exe/.msi) from download folder
    let is_installer = asset.name.ends_with(".exe") || asset.name.ends_with(".msi");
    let mut detected_uninstaller: Option<String> = None;
    let mut detected_install_dir: Option<PathBuf> = None;
    if is_installer {
        if !quiet {
            println!("  Running installer: {}", asset.name);
        }

        // Snapshot the uninstall registry so we can tell where the app landed
        // and how to remove it later.
        let before = crate::core::scan_uninstall_entries();

        run_installer(&download_path)?;
        if !quiet {
            println!("  Installer ran: {}", asset.name);
        }

        // The installer registers itself; find the entry it added or bumped.
        let after = crate::core::scan_uninstall_entries();
        let hints = vec![
            repo.rsplit('/').next().unwrap_or(repo).to_string(),
            repo.replace('/', "-"),
        ];
        if let Some(entry) = crate::core::detect_install_change(&before, &after, &hints) {
            if !entry.uninstall_string.is_empty() {
                detected_uninstaller = Some(entry.uninstall_string.clone());
            }
            detected_install_dir = entry.install_dir();
            if let Some(dir) = &detected_install_dir {
                if !quiet {
                    println!("  Installed to: {}", dir.display());
                }
            }
        }
    }

    // If the installer ran but didn't register a new install (user cancelled,
    // or silent installer exited 0 without changes), warn but continue —
    // registry detection is best-effort and some installers update in place
    // without creating a new uninstall entry.
    if is_installer && detected_install_dir.is_none() {
        if !quiet {
            eprintln!(
                "  Warning: installer did not register a new installation — update may have been cancelled or applied in place"
            );
        }
    }

    // Update state
    let new_repo = crate::core::state::InstalledRepo {
        repo: repo.to_string(),
        // Store the version without the "v" tag prefix, so it matches what
        // the Windows registry reports and what the old version was.
        version: crate::core::normalize_version(version),
        install_path: detected_install_dir.unwrap_or_else(|| install_dir.clone()),
        installed_at: chrono::Utc::now(),
        updated_at: Some(chrono::Utc::now()),
        checksum: None,
        metadata: serde_json::Value::Null,
        previous_version,
        previous_install_path: None,
        dependencies: Vec::new(),
        is_dependency: false,
        uninstaller: detected_uninstaller,
        ..Default::default()
    };
    state.add_installed(new_repo.clone());
    state.save()?;

    Ok(())
}

/// Install a folder-added app in place with backup and rollback.
/// Downloads to download_dir, asks user to close the app, backs up the folder
/// as a zip file, installs into the folder, verifies success, and restores
/// from backup on failure.
pub(crate) async fn install_folder_app(
    repo: &str,
    version: &str,
    download_path: &Path,
    install_dir: &Path,
    state: &mut StateManager,
    previous_version: Option<String>,
    quiet: bool,
) -> Result<()> {
    // Prompt user to close the running application
    if !quiet {
        println!("\n  === Folder app update: {} ===", repo);
        println!("  Please close the running application before updating.");
        let confirmed = Confirm::new()
            .with_prompt("Close the app and continue with update?")
            .default(false)
            .interact()?;
        if !confirmed {
            return Err(anyhow::anyhow!("Update cancelled by user"));
        }
    }

    // Backup the folder as a zip file before making any changes
    let timestamp = SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs();
    let backup_name = format!("{}-backup-{}.zip", repo, timestamp);
    let backup_path = install_dir
        .parent()
        .unwrap_or(install_dir)
        .join(&backup_name);

    backup_folder_as_zip(install_dir, &backup_path)?;

    let install_result = install_folder_app_inner(download_path, install_dir);

    match install_result {
        Ok(_) => {
            // Verify installation succeeded
            verify_folder_app(install_dir, repo)?;

            // Clean up backup on success
            let _ = std::fs::remove_file(&backup_path);

            // Find the main exe for install_path. For exe-less zip/portable
            // apps, use the install directory itself (files were extracted there).
            let install_path = find_main_exe(install_dir)
                .unwrap_or_else(|| install_dir.to_path_buf());

            // Update state
            let new_repo = crate::core::state::InstalledRepo {
                repo: repo.to_string(),
                version: crate::core::normalize_version(version),
                install_path,
                installed_at: chrono::Utc::now(),
                updated_at: Some(chrono::Utc::now()),
                checksum: None,
                metadata: serde_json::Value::Null,
                previous_version,
                previous_install_path: None,
                dependencies: Vec::new(),
                is_dependency: false,
                uninstaller: None,
                ..Default::default()
            };
            state.add_installed(new_repo.clone());
            state.save()?;

            Ok(())
        }
        Err(e) => {
            // Install failed: restore from backup
            let _ = restore_folder_from_zip(&backup_path, install_dir);
            Err(e)
        }
    }
}

/// Install downloaded files into the folder: extract zip or copy exe/portable.
fn install_folder_app_inner(download_path: &Path, install_dir: &Path) -> Result<()> {
    let name = download_path.file_name().unwrap().to_string_lossy().to_lowercase();
    if name.ends_with(".zip") {
        extract_zip_to_folder(download_path, install_dir)
    } else if name.ends_with(".tar.gz") || name.ends_with(".tgz") {
        extract_tar_gz_to_folder(download_path, install_dir)
    } else {
        // Copy the downloaded file (exe/portable) into the folder, overwriting
        let dest = install_dir.join(download_path.file_name().unwrap());
        fs::copy(download_path, &dest)?;
        Ok(())
    }
}

/// Verify the folder app is still installed correctly after update.
/// Folder apps may be zip/portable distributions without a top-level .exe,
/// so we only require the directory to exist and contain at least one file.
fn verify_folder_app(install_dir: &Path, repo: &str) -> Result<()> {
    if !install_dir.exists() {
        return Err(anyhow::anyhow!(
            "Install directory missing: {}",
            install_dir.display()
        ));
    }

    let mut has_file = false;
    for entry in fs::read_dir(install_dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.is_file() {
            has_file = true;
            break;
        }
    }

    if !has_file {
        return Err(anyhow::anyhow!(
            "No files found in {} after update",
            install_dir.display()
        ));
    }

    Ok(())
}

/// Find the main executable in a folder (returns the first .exe found).
fn find_main_exe(install_dir: &Path) -> Option<PathBuf> {
    for entry in fs::read_dir(install_dir).ok()? {
        let entry = entry.ok()?;
        let path = entry.path();
        if path.is_file() && path.extension().map(|e| e == "exe").unwrap_or(false) {
            return Some(path);
        }
    }
    None
}

/// Zip up an entire folder for backup.
fn backup_folder_as_zip(source_dir: &Path, zip_path: &Path) -> Result<()> {
    let file = fs::File::create(zip_path)?;
    let mut zip = ZipWriter::new(file);
    let options = FileOptions::default()
        .compression_method(zip::CompressionMethod::Deflated)
        .unix_permissions(0o644);

    let base = source_dir.canonicalize().unwrap_or_else(|_| source_dir.to_path_buf());
    let mut stack: Vec<PathBuf> = vec![source_dir.to_path_buf()];

    while let Some(path) = stack.pop() {
        if path.is_dir() {
            for entry in fs::read_dir(&path)? {
                let entry = entry?;
                let entry_path = entry.path();
                if entry_path.is_dir() {
                    stack.push(entry_path);
                } else {
                    let relative = entry_path
                        .strip_prefix(&base)
                        .unwrap_or(&entry_path)
                        .to_path_buf();
                    if let Some(parent) = relative.parent() {
                        let _ = zip.add_directory(parent.to_string_lossy(), options.clone());
                    }
                    let mut f = fs::File::open(&entry_path)?;
                    zip.start_file(relative.to_string_lossy(), options.clone())?;
                    io::copy(&mut f, &mut zip)?;
                }
            }
        }
    }

    zip.finish()?;
    Ok(())
}

/// Restore a folder from a zip backup (clears dest first).
fn restore_folder_from_zip(zip_path: &Path, dest_dir: &Path) -> Result<()> {
    if dest_dir.exists() {
        for entry in fs::read_dir(dest_dir)? {
            let entry = entry?;
            let path = entry.path();
            if path.is_dir() {
                let _ = fs::remove_dir_all(&path);
            } else {
                let _ = fs::remove_file(&path);
            }
        }
    }

    let file = fs::File::open(zip_path)?;
    let mut archive = ZipArchive::new(file)?;

    for i in 0..archive.len() {
        let mut file = archive.by_index(i)?;
        let out_path = dest_dir.join(file.mangled_name());

        if let Some(parent) = out_path.parent() {
            fs::create_dir_all(parent)?;
        }

        if file.name().ends_with('/') {
            fs::create_dir_all(&out_path)?;
        } else {
            let mut out_file = fs::File::create(&out_path)?;
            io::copy(&mut file, &mut out_file)?;
        }
    }

    Ok(())
}

/// Extract a .tar.gz archive into a folder.
fn extract_tar_gz_to_folder(tar_path: &Path, dest_dir: &Path) -> Result<()> {
    let file = fs::File::open(tar_path)?;
    let gz = GzDecoder::new(file);
    let mut archive = Archive::new(gz);
    archive.unpack(dest_dir)?;
    Ok(())
}

/// Extract a zip archive into a folder. Flattens a single root directory
/// if the zip contains everything under one top-level folder (e.g. App-1.2.3/...)
/// so files land directly in dest_dir instead of dest_dir/App-1.2.3/.
fn extract_zip_to_folder(zip_path: &Path, dest_dir: &Path) -> Result<()> {
    let file = fs::File::open(zip_path)?;
    let mut archive = ZipArchive::new(file)?;

    // Detect single root dir: all entries share the same first path component.
    let mut root_dir: Option<String> = None;
    for i in 0..archive.len() {
        let file = archive.by_index(i)?;
        let name = file.mangled_name().to_string_lossy().to_string();
        let mut parts = name.split('/');
        let first = parts.next().unwrap_or("");
        if !first.is_empty() {
            match &root_dir {
                None => root_dir = Some(first.to_string()),
                Some(r) if r != first => { root_dir = None; break; }
                _ => {}
            }
        }
    }

    for i in 0..archive.len() {
        let mut file = archive.by_index(i)?;
        let name = file.mangled_name().to_string_lossy().to_string();
        let out_path = if let Some(ref root) = root_dir {
            if name == *root {
                // Root directory entry itself — maps to dest root, skip.
                continue;
            }
            // Strip the single root dir prefix
            let stripped = name.strip_prefix(&format!("{root}/")).unwrap_or(&name);
            dest_dir.join(stripped)
        } else {
            dest_dir.join(name)
        };

        if let Some(parent) = out_path.parent() {
            fs::create_dir_all(parent)?;
        }

        if file.name().ends_with('/') {
            fs::create_dir_all(&out_path)?;
        } else {
            let mut out_file = fs::File::create(&out_path)?;
            io::copy(&mut file, &mut out_file)?;
        }
    }

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
        // Group by full stem (file name without extension). Different apps
        // like tool.exe and tool2.exe must not share a group.
        let base = path
            .file_stem()
            .unwrap_or_default()
            .to_string_lossy()
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
    use std::io::{Cursor, Write};

    /// A zip whose every entry lives under a single root dir (App-1.2.3/...)
    /// should be flattened so files land directly in dest_dir.
    #[test]
    fn extract_zip_flattens_single_root_dir() {
        let tmp = tempfile::tempdir().unwrap();
        let dest = tmp.path().join("dest");
        std::fs::create_dir_all(&dest).unwrap();

        let zip_bytes = {
            let mut buf = Vec::new();
            {
                let mut zip = zip::write::ZipWriter::new(Cursor::new(&mut buf));
                let opts = zip::write::FileOptions::default();
                zip.add_directory("App-1.2.3/", opts).unwrap();
                zip.start_file("App-1.2.3/app.exe", opts).unwrap();
                zip.write_all(b"fake exe").unwrap();
                zip.start_file("App-1.2.3/README.md", opts).unwrap();
                zip.write_all(b"readme").unwrap();
                zip.finish().unwrap();
            }
            buf
        };

        let zip_path = tmp.path().join("App-1.2.3.zip");
        std::fs::write(&zip_path, &zip_bytes).unwrap();

        extract_zip_to_folder(&zip_path, &dest).unwrap();

        // Files should be at dest/app.exe and dest/README.md, NOT dest/App-1.2.3/...
        assert!(dest.join("app.exe").exists(), "app.exe should be flattened to dest root");
        assert!(
            dest.join("README.md").exists(),
            "README.md should be flattened to dest root"
        );
        assert!(
            !dest.join("App-1.2.3").exists(),
            "single root dir should not be preserved"
        );
    }

    /// A zip with mixed top-level entries (no single root) should not be flattened.
    #[test]
    fn extract_zip_no_root_dir_stays_as_is() {
        let tmp = tempfile::tempdir().unwrap();
        let dest = tmp.path().join("dest");
        std::fs::create_dir_all(&dest).unwrap();

        let zip_bytes = {
            let mut buf = Vec::new();
            {
                let mut zip = zip::write::ZipWriter::new(Cursor::new(&mut buf));
                let opts = zip::write::FileOptions::default();
                zip.start_file("top.exe", opts).unwrap();
                zip.write_all(b"exe").unwrap();
                zip.start_file("sub/deep.txt", opts).unwrap();
                zip.write_all(b"deep").unwrap();
                zip.finish().unwrap();
            }
            buf
        };

        let zip_path = tmp.path().join("mixed.zip");
        std::fs::write(&zip_path, &zip_bytes).unwrap();

        extract_zip_to_folder(&zip_path, &dest).unwrap();

        assert!(dest.join("top.exe").exists());
        assert!(dest.join("sub/deep.txt").exists());
    }
}

