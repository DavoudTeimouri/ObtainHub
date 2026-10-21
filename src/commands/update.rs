use crate::core::{ConfigManager, StateManager, run_installer};
use crate::cli::{Arch, UpdateArgs};
use crate::utils::retry::{execute_with_retry, RetryConfig};
use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::time::SystemTime;
use tracing::info;
use indicatif::{ProgressBar, ProgressStyle};
use dialoguer::{Select, theme::ColorfulTheme};

use crate::commands::install::{fetch_published_checksum, GitHubRelease as InstallGitHubRelease, GitHubAsset as InstallGitHubAsset, select_asset as install_select_asset};
use sha2::{Digest, Sha256};

fn calculate_sha256_bytes(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hex::encode(hasher.finalize())
}

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

#[derive(Deserialize, Serialize, Debug, Clone)]
pub(crate) struct GitHubRelease {
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
pub(crate) struct GitHubAsset {
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
                // Interactive asset selection: only .exe (setup) and .msi, correct architecture
                let selected_asset = select_installer_asset(&release, &args.arch, args.quiet)?;
                match install_release(repo_name, &latest_version, &release, token, config, state, Some(selected_asset), args.quiet, Some(current_version.to_string()), &args.arch).await {
                    Ok(_) => {
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

/// Interactive asset selection for update: only .exe (setup) and .msi files,
/// matched to the requested architecture. MSI preferred over EXE. Other file
/// types (.zip, .tar.gz, etc.) are hidden. Falls back to all installers if no
/// arch-specific match is found (asset naming varies across repos).
pub(crate) fn select_installer_asset(
    release: &GitHubRelease,
    arch: &Arch,
    quiet: bool,
) -> Result<GitHubAsset> {
    // Filter: only .exe and .msi files, matching the requested architecture
    let arch_matching: Vec<&GitHubAsset> = release
        .assets
        .iter()
        .filter(|a| {
            let name = a.name.to_lowercase();
            let is_installer = name.ends_with(".exe") || name.ends_with(".msi");
            is_installer && crate::core::registries::matches_arch(&name, arch)
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

    // Quiet (scheduled) runs must not block on a prompt - take the preferred asset.
    if quiet {
        return Ok(sorted[0].clone());
    }

    let theme = ColorfulTheme::default();
    let items: Vec<String> = sorted
        .iter()
        .map(|a| format!("{} ({} bytes)", a.name, a.size))
        .collect();

    let choice = Select::with_theme(&theme)
        .with_prompt(format!(
            "Select installer asset for {} (arch: {:?})",
            release.tag_name, arch
        ))
        .items(&items)
        .default(0)
        .interact_opt()?;

    match choice {
        Some(idx) => Ok(sorted[idx].clone()),
        None => anyhow::bail!("No asset selected for update"),
    }
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
            let selected = install_select_asset(install_rel, arch)?;
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
                    if !quiet {
                        println!("  Already downloaded: {} ({} bytes)", asset.name, existing_size);
                    }
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
        let mut req = crate::core::registries::github_get(download_url);
        if let Some(token) = token {
            req = req.with_header("Authorization", format!("Bearer {token}"));
        }

        let response = req.send()?;
        total_size = response
            .as_bytes()
            .len() as u64;
        let bytes = response.as_bytes().to_vec();

        let pb = if quiet {
            ProgressBar::hidden()
        } else {
            ProgressBar::new(total_size)
        };
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
    let mut detected_uninstaller: Option<String> = None;
    let mut detected_install_dir: Option<std::path::PathBuf> = None;
    if is_installer {
        if !quiet {
            println!("  Running installer: {}", asset.name);
        }

        // Snapshot the uninstall registry so we can tell where the app landed
        // and how to remove it later.
        let before = crate::core::scan_uninstall_entries();

        run_installer(&asset_path)?;
        // Verify installer ran: check app exe was updated
        if !asset_path.exists() {
            return Err(anyhow::anyhow!(
                "Installer ran but {} is missing afterwards",
                asset.name
            ));
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
            .trim_end_matches(['_', ' '])
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

