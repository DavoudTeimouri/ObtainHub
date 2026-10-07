use crate::core::{ConfigManager, StateManager};
use crate::cli::DoctorArgs;
use anyhow::Result;
use std::fs;
use std::path::Path;
use tracing::info;

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
    
    let install_dir = config.get().install_dir.clone();
    println!("   Install directory: {}", install_dir.display());
    if !install_dir.exists() {
        println!("   ⚠ Install directory does not exist");
        if args.fix {
            fs::create_dir_all(&install_dir)?;
            println!("   → Created install directory");
            fixes.push("Created install directory".to_string());
        } else {
            issues.push("Install directory missing".to_string());
        }
    }
    
    // Check state
    println!("\n2. State");
    let state_path = state.path();
    if state_path.exists() {
        println!("   ✓ State file: {}", state_path.display());
        let installed: Vec<String> = state.list_installed().iter().map(|r| r.repo.clone()).collect();
        println!("   Tracked repositories: {}", installed.len());
        
        let mut to_remove = Vec::new();
        
        for repo_name in &installed {
            if let Some(repo) = state.get_installed(repo_name) {
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
    if let Some(token) = config.get().github_token.as_ref() {
        if !token.is_empty() {
            println!("   ✓ GitHub token configured");
        } else {
            println!("   ⚠ GitHub token empty (rate limited to 60 req/hr)");
        }
    } else {
        println!("   ⚠ No GitHub token (rate limited to 60 req/hr)");
        issues.push("No GitHub token configured".to_string());
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
    
    // Check dependencies
    println!("\n5. Dependencies");
    println!("   ohub binary: {}", std::env::current_exe()?.display());
    
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
    
    Ok(())
}