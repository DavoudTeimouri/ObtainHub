use crate::core::{ConfigManager, StateManager};
use crate::cli::CheckArgs;
use anyhow::Result;
use minreq;
use serde::{Deserialize, Serialize};
use tracing::info;
use comfy_table::{Table, Cell};

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

#[derive(Deserialize, Serialize, Debug)]
struct GitHubAsset {
    name: String,
    browser_download_url: String,
    size: u64,
    content_type: Option<String>,
}

pub async fn execute(args: CheckArgs, config: &ConfigManager, state: &StateManager) -> Result<()> {
    info!("Checking for updates");

    let token = config.get().github_token.as_deref();

    // If --all flag is set, enumerate all installed software from Windows registry
    let installed = if args.all {
        let all = enumerate_all_installed_software()?;
        let tracked = state.list_installed();
        let (matched, skipped) = partition_gitHub_managed(&all, &tracked);
        println!("Scanned {} installed programs.", all.len());
        if !skipped.is_empty() {
            println!("  {} not managed by ObtainHub (no GitHub origin) — skipped.", skipped.len());
        }
        matched
    } else {
        state.list_installed().into_iter().cloned().collect()
    };

    if installed.is_empty() {
        println!("No repositories installed.");
        return Ok(());
    }
    
    let mut outdated = Vec::new();
    let mut current = Vec::new();
    let mut errors = Vec::new();
    
    for repo in installed {
        // Skip if checking specific repo
        if let Some(ref target) = args.repo {
            if &repo.repo != target {
                continue;
            }
        }
        
        match fetch_latest_release(&repo.repo, token).await {
            Ok(release) => {
                let latest_version = release.tag_name;
                if latest_version != repo.version {
                    outdated.push((repo.repo.clone(), repo.version.clone(), latest_version));
                } else {
                    current.push(repo.repo.clone());
                }
            }
            Err(e) => {
                errors.push((repo.repo.clone(), e.to_string()));
            }
        }
    }
    
    if args.outdated_only {
        if outdated.is_empty() {
            println!("All repositories are up to date.");
        } else {
            let mut table = Table::new();
            table.set_header(vec!["Repository", "Current", "Latest"]);
            for (repo, current_ver, latest_ver) in outdated {
                table.add_row(vec![Cell::new(&repo), Cell::new(&current_ver), Cell::new(&latest_ver)]);
            }
            println!("{}", table);
        }
        return Ok(());
    }
    
    // Show all results
    if !outdated.is_empty() {
        println!("Outdated ({}):", outdated.len());
        let mut table = Table::new();
        table.set_header(vec!["Repository", "Current", "Latest"]);
        for (repo, current_ver, latest_ver) in &outdated {
            table.add_row(vec![Cell::new(repo), Cell::new(current_ver), Cell::new(latest_ver)]);
        }
        println!("{}", table);
        println!();
    }
    
    if !current.is_empty() {
        println!("Up to date ({})", current.len());
        for repo in &current {
            println!("  {}", repo);
        }
        println!();
    }
    
    if !errors.is_empty() {
        println!("Errors ({})", errors.len());
        for (repo, error) in &errors {
            println!("  {}: {}", repo, error);
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

#[cfg(windows)]
fn enumerate_all_installed_software() -> Result<Vec<crate::core::state::InstalledRepo>> {
    use std::collections::HashSet;
    use winreg::enums::*;
    use winreg::RegKey;
    
    let mut results = Vec::new();
    let mut seen = HashSet::new();
    
    // Check both 64-bit and 32-bit registry views
    for &root in &[HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER] {
        for &view in &[KEY_WOW64_64KEY, KEY_WOW64_32KEY] {
            let hklm = RegKey::predef(root);
            let uninstall_path = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall";
            
            if let Ok(uninstall_key) = hklm.open_subkey_with_flags(uninstall_path, KEY_READ | view) {
                for subkey_name in uninstall_key.enum_keys().flatten() {
                    if let Ok(subkey) = uninstall_key.open_subkey_with_flags(&subkey_name, KEY_READ | view) {
                        let display_name: Option<String> = subkey.get_value("DisplayName").ok();
                        let display_version: Option<String> = subkey.get_value("DisplayVersion").ok();
                        let publisher: Option<String> = subkey.get_value("Publisher").ok();
                        let uninstall_string: Option<String> = subkey.get_value("UninstallString").ok();
                        
                        // Skip system components (no DisplayName)
                        if let Some(name) = display_name {
                            // Skip our own entry
                            if name.contains("ObtainHub") {
                                continue;
                            }
                            
                            // Create a unique key to avoid duplicates
                            let key = format!("{}|{}", name, display_version.clone().unwrap_or_default());
                            if seen.insert(key) {
                                results.push(crate::core::state::InstalledRepo {
                                    repo: name.clone(),
                                    version: display_version.unwrap_or_else(|| "unknown".to_string()),
                                    install_path: std::path::PathBuf::from(uninstall_string.unwrap_or_default()),
                                    installed_at: chrono::Utc::now(),
                                    updated_at: None,
                                    checksum: None,
                                    metadata: serde_json::Value::Null,
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
    // Not implemented on non-Windows
    Ok(Vec::new())
}
/// Split enumerated Windows programs into ones ObtainHub actually manages and ones
/// it does not. Only entries present in `state.json` have a known GitHub origin —
/// a `DisplayName` like "NVIDIA Corporation" is not an `owner/repo` and would 404
/// on every lookup while exhausting the GitHub API rate limit.
fn partition_gitHub_managed(
    all: &[crate::core::state::InstalledRepo],
    tracked: &[&crate::core::state::InstalledRepo],
) -> (Vec<crate::core::state::InstalledRepo>, Vec<String>) {
    let mut matched = Vec::new();
    let mut skipped = Vec::new();

    for entry in all {
        let name = entry.repo.to_ascii_lowercase();

        // ObtainingHub manages it.
        if name.contains("obtainhub") {
            continue;
        }

        // Tracked in state -> we know its owner/repo.
        if let Some(tracked) = tracked.iter().find(|r| {
            let n = r.repo.to_ascii_lowercase();
            n == name || name.ends_with(&n) || n.ends_with(&name)
        }) {
            matched.push(crate::core::state::InstalledRepo {
                repo: tracked.repo.clone(),
                version: tracked.version.clone(),
                install_path: entry.install_path.clone(),
                installed_at: entry.installed_at,
                updated_at: entry.updated_at,
                checksum: tracked.checksum.clone(),
                metadata: tracked.metadata.clone(),
            });
        } else {
            skipped.push(entry.repo.clone());
        }
    }

    (matched, skipped)
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    fn entry(name: &str) -> crate::core::state::InstalledRepo {
        crate::core::state::InstalledRepo {
            repo: name.to_string(),
            version: "1.0".to_string(),
            install_path: std::path::PathBuf::from("/tmp"),
            installed_at: Utc::now(),
            updated_at: None,
            checksum: None,
            metadata: serde_json::Value::Null,
        }
    }

    #[test]
    fn partition_skips_self_and_unmanaged() {
        let tracked: Vec<crate::core::state::InstalledRepo> = Vec::new();
        let all = vec![
            entry("ObtainHub 3.0.1"),
            entry("NVIDIA Corporation"),
            entry("7-Zip"),
        ];
        let tracked_refs: Vec<&crate::core::state::InstalledRepo> = tracked.iter().collect();
        let (matched, skipped) = partition_gitHub_managed(&all, &tracked_refs);
        assert!(matched.is_empty(), "nothing should match an empty state");
        assert_eq!(skipped.len(), 2, "NVIDIA + 7-Zip are not managed");
        assert!(!skipped.contains(&"ObtainHub 3.0.1".to_string()), "self must not be listed as skipped");
    }

    #[test]
    fn partition_matches_tracked_repo() {
        let tracked = vec![entry("BurntSushi/ripgrep")];
        let tracked_refs: Vec<&crate::core::state::InstalledRepo> = tracked.iter().collect();
        let all = vec![entry("ripgrep"), entry("7-Zip")];
        let (matched, skipped) = partition_gitHub_managed(&all, &tracked_refs);
        assert_eq!(matched.len(), 1);
        assert_eq!(matched[0].repo, "BurntSushi/ripgrep");
        assert_eq!(skipped, vec!["7-Zip".to_string()]);
    }
}
