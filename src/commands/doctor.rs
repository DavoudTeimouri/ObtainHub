use crate::core::{ConfigManager, StateManager};
use crate::cli::DoctorArgs;
use anyhow::Result;
use std::fs;
use std::path::Path;
use tracing::info;

/// Can we create and remove a file in this directory?
fn is_writable(dir: &Path) -> bool {
    let probe = dir.join(".ohub-write-probe");
    match fs::write(&probe, b"") {
        Ok(()) => {
            let _ = fs::remove_file(&probe);
            true
        }
        Err(_) => false,
    }
}

/// Is this directory listed in PATH?
fn on_path(dir: &Path) -> bool {
    let Ok(path) = std::env::var("PATH") else {
        return false;
    };
    let target = dir.to_string_lossy().to_lowercase();
    path.split(';')
        .chain(path.split(':'))
        .any(|p| p.trim().trim_matches('"').to_lowercase() == target)
}

pub async fn execute(args: DoctorArgs, config: &ConfigManager, state: &mut StateManager) -> Result<()> {
    info!("Running diagnostics");
    
    let mut issues = Vec::new();
    let mut fixes = Vec::new();
    
    println!("=== ObtainHub Diagnostics ===\n");
    
    // Check config
    println!("1. Configuration");
    let config_path = config.path();
    if config_path.exists() {
        println!("   ✓ Config file: {}", config_path.display());
    } else {
        println!("   ✗ Config file missing: {}", config_path.display());
        issues.push("Config file missing".to_string());
    }
    
    let cfg = config.get();
    let dirs = [
        ("Install", cfg.install_dir.clone()),
        ("Download", cfg.download_dir.clone()),
        ("Shim", cfg.shim_dir.clone()),
    ];
    for (label, dir) in dirs {
        print!("   {label} directory: {}", dir.display());
        if !dir.exists() {
            println!(" (missing)");
            issues.push(format!("{label} directory missing: {}", dir.display()));
            if args.fix {
                match fs::create_dir_all(&dir) {
                    Ok(()) => {
                        println!("   \u{2192} Created {label} directory");
                        fixes.push(format!("Created {label} directory"));
                    }
                    Err(e) => println!("   \u{2717} Could not create it: {e}"),
                }
            }
            continue;
        }
        if is_writable(&dir) {
            println!(" \u{2713}");
        } else {
            println!(" \u{2717} (not writable)");
            issues.push(format!("{label} directory not writable: {}", dir.display()));
        }
    }

    match &cfg.proxy {
        Some(proxy) => println!("   Proxy: {proxy}"),
        None => println!("   Proxy: none"),
    }
    
    // Check state
    println!("\n2. State");
    let state_path = state.path();
    if state_path.exists() {
        println!("   ✓ State file: {}", state_path.display());
        let installed: Vec<String> = state.list_installed().iter().map(|r| r.repo.clone()).collect();
        println!("   Tracked repositories: {}", installed.len());
        
        let mut to_remove = Vec::new();
        let mut schema_errors = 0;

        for repo_name in &installed {
            if let Some(repo) = state.get_installed(repo_name) {
                // Schema sanity: every tracked entry needs an id, a version and a path.
                if repo.repo.is_empty() || repo.version.is_empty() || repo.install_path.as_os_str().is_empty() {
                    schema_errors += 1;
                    println!("   ✗ {} has an incomplete entry", repo.repo);
                    issues.push(format!("Incomplete state entry: {}", repo.repo));
                    continue;
                }
                if repo.install_path.exists() {
                    println!("   ✓ {} at {}", repo.repo, repo.install_path.display());
                } else {
                    println!("   ✗ {} missing at {}", repo.repo, repo.install_path.display());
                    issues.push(format!("Missing repo: {}", repo.repo));
                    if args.fix {
                        to_remove.push(repo_name.clone());
                    }
                }
            }
        }

        if schema_errors == 0 {
            println!("   ✓ All tracked entries well-formed");
        }
        
        for repo_name in to_remove {
            state.remove_installed(&repo_name);
            state.save()?;
            println!("   → Removed {} from state", repo_name);
            fixes.push(format!("Removed {} from state", repo_name));
        }
    } else {
        println!("   ⚠ State file missing: {}", state_path.display());
        issues.push("State file missing".to_string());
    }
    
    // Check GitHub token
    println!("\n3. GitHub Authentication");
    match config.get().github_token.as_deref() {
        Some(token) if !token.is_empty() => {
            println!("   ✓ GitHub token configured");

            // Validate the token against GitHub.
            let req = minreq::get("https://api.github.com/user")
                .with_header("User-Agent", "ObtainHub/3.0.0")
                .with_header("Authorization", format!("Bearer {token}"));
            match req.send() {
                Ok(resp) if resp.status_code == 200 => {
                    println!("   ✓ Token accepted by GitHub");
                }
                Ok(resp) if resp.status_code == 401 => {
                    println!("   ✗ Token rejected by GitHub (401)");
                    issues.push("GitHub token is invalid or expired".to_string());
                }
                Ok(resp) => {
                    println!("   ⚠ Token check returned {}", resp.status_code);
                }
                Err(e) => {
                    println!("   ⚠ Could not validate token: {e}");
                }
            }

            // Rate limit budget.
            let req = minreq::get("https://api.github.com/rate_limit")
                .with_header("User-Agent", "ObtainHub/3.0.0")
                .with_header("Authorization", format!("Bearer {token}"));
            match req.send() {
                Ok(resp) if resp.status_code == 200 => {
                    if let Ok(body) = resp.json::<serde_json::Value>() {
                        let core = &body["resources"]["core"];
                        let limit = core["limit"].as_u64().unwrap_or(0);
                        let remaining = core["remaining"].as_u64().unwrap_or(0);
                        println!("   ✓ API rate limit: {remaining}/{limit} remaining");
                        if limit > 0 && remaining == 0 {
                            println!("   ⚠ Rate limit exhausted - requests will fail until reset");
                            issues.push("GitHub API rate limit exhausted".to_string());
                        }
                    }
                }
                Ok(resp) => println!("   ⚠ Rate limit check returned {}", resp.status_code),
                Err(e) => println!("   ⚠ Could not read rate limit: {e}"),
            }
        }
        Some(_) => {
            println!("   ⚠ GitHub token empty (rate limited to 60 req/hr)");
            issues.push("GitHub token is empty".to_string());
        }
        None => {
            println!("   ⚠ No GitHub token (rate limited to 60 req/hr)");
            issues.push("No GitHub token configured".to_string());
        }
    }
    
    // Check network
    println!("\n4. Network Connectivity");
    match minreq::get("https://api.github.com").send() {
        Ok(resp) if resp.status_code == 200 => println!("   ✓ GitHub API reachable"),
        Ok(resp) => {
            println!("   ⚠ GitHub API returned {}", resp.status_code);
            issues.push(format!("GitHub API error: {}", resp.status_code));
        }
        Err(e) => {
            println!("   ✗ Cannot reach GitHub API: {}", e);
            issues.push("No network connectivity to GitHub".to_string());
        }
    }
    
    // Check environment
    println!("\n5. Environment");
    println!("   ohub binary: {}", std::env::current_exe()?.display());
    let install_dir = config.get().install_dir.clone();
    if on_path(&install_dir) {
        println!("   ✓ Install directory is on PATH");
    } else {
        println!("   ⚠ Install directory not on PATH: {}", install_dir.display());
        issues.push(format!("Install directory not on PATH: {}", install_dir.display()));
    }
    let shim_dir = config.get().shim_dir.clone();
    if on_path(&shim_dir) {
        println!("   ✓ Shim directory is on PATH");
    } else {
        println!("   ⚠ Shim directory not on PATH: {}", shim_dir.display());
    }
    
    // Check for updates
    println!("\n6. Version Check");
    let current_version = env!("CARGO_PKG_VERSION");
    println!("   Current version: {}", current_version);
    
    // Summary
    println!("\n=== Summary ===");
    if issues.is_empty() {
        println!("✓ All checks passed!");
    } else {
        println!("⚠ Issues found: {}", issues.len());
        for issue in &issues {
            println!("  - {}", issue);
        }
    }
    
    if !fixes.is_empty() {
        println!("\nFixes applied: {}", fixes.len());
        for fix in &fixes {
            println!("  - {}", fix);
        }
    }
    
    if args.fix && !issues.is_empty() {
        println!("\nSome issues require manual intervention.");
    }

    if args.strict && !issues.is_empty() {
        anyhow::bail!("{} issue(s) found", issues.len());
    }

    Ok(())
}