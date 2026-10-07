use crate::core::{ConfigManager, StateManager};
use crate::cli::{SourceArgs, SourceAction};
use anyhow::Result;
use minreq::get;
use serde_json::Value;
use std::collections::HashMap;
use tracing::info;

pub async fn execute(args: SourceArgs, config: &mut ConfigManager, _state: &StateManager) -> Result<()> {
    info!("Source command: {:?}", args.action);

    let config_data = config.get_mut();

    match args.action {
        SourceAction::List => {
            if config_data.manifest_sources.is_empty() {
                println!("No custom sources configured.");
            } else {
                for src in &config_data.manifest_sources {
                    println!("{}: {} ({}) [enabled: {}, priority: {}, auto_sync: {}]", 
                        src.name, src.url, src.src_type, src.enabled, src.priority.unwrap_or(0), src.auto_sync);
                }
            }
        }
        SourceAction::Add { name, url, src_type, pre_install, post_install, pre_uninstall, post_uninstall, priority, enabled, auto_sync } => {
            // Validate the source
            let api_url = if url.contains("/releases") && url.contains("api.github.com") {
                url.clone()
            } else if url.contains("github.com") && url.matches('/').count() >= 4 {
                url.replace("https://github.com/", "https://api.github.com/repos/") + "/releases"
            } else {
                format!("https://api.github.com/repos/{}/releases", url)
            };

            let resp = get(&api_url)
                .with_header("Accept", "application/vnd.github.v3+json")
                .with_timeout(20)
                .send()
                .map_err(|e| anyhow::anyhow!("Failed to fetch: {}", e))?;

            if resp.status_code == 404 {
                return Err(anyhow::anyhow!("GitHub repository not found: {}", url));
            }

            if !(200..300).contains(&resp.status_code) {
                return Err(anyhow::anyhow!("HTTP error: {}", resp.status_code));
            }

            let releases: Value = resp.json()?;
            if !releases.is_array() || releases.as_array().unwrap_or(&vec![]).is_empty() {
                return Err(anyhow::anyhow!("No releases found"));
            }

            // Check for assets in first release
            let first = &releases[0];
            if !first.get("assets").map(|a| a.is_array() && !a.as_array().unwrap().is_empty()).unwrap_or(false) {
                return Err(anyhow::anyhow!("Repository has no assets to install from"));
            }

            // Add source
            let headers = HashMap::new();
            let mut hooks = HashMap::new();
            
            if let Some(v) = pre_install { hooks.insert("pre_install".to_string(), v); }
            if let Some(v) = post_install { hooks.insert("post_install".to_string(), v); }
            if let Some(v) = pre_uninstall { hooks.insert("pre_uninstall".to_string(), v); }
            if let Some(v) = post_uninstall { hooks.insert("post_uninstall".to_string(), v); }

            let src = crate::core::config::ManifestSource {
                name: name.clone(),
                url: url.clone(),
                enabled: enabled || true,
                headers,
                src_type,
                hooks,
                priority,
                auto_sync,
            };
            let src_type = src.src_type.clone();
            config_data.manifest_sources.push(src);
            config.save()?;
            println!("Added source: {} ({}) -> {}", name, src_type, url);
        }
        SourceAction::Remove { name } => {
            let len_before = config_data.manifest_sources.len();
            config_data.manifest_sources.retain(|s| s.name != name);
            if config_data.manifest_sources.len() < len_before {
                config.save()?;
                println!("Removed source: {}", name);
            } else {
                println!("Source not found: {}", name);
            }
        }
        SourceAction::Verify { name } => {
            let src = config_data.manifest_sources.iter().find(|s| s.name == name);
            let Some(src) = src else {
                println!("Source not found: {}", name);
                return Ok(());
            };

            let api_url = src.url.trim_end_matches('/');
            let resp = get(api_url).with_timeout(30).send()?;
            
            if resp.status_code == 200 {
                let data: Value = resp.json()?;
                if data.is_array() && !data.as_array().unwrap().is_empty() && data[0].get("assets").is_some() {
                    println!("Source '{}' verified: GitHub releases with assets found", name);
                } else {
                    println!("Source '{}' verified but structure unexpected", name);
                }
            } else {
                println!("Source '{}' verification failed: HTTP {}", name, resp.status_code);
            }
        }
        SourceAction::Update { name } => {
            let src = config_data.manifest_sources.iter().find(|s| s.name == name);
            let Some(src) = src else {
                println!("Source not found: {}", name);
                return Ok(());
            };

            // Re-verify the source
            let api_url = src.url.trim_end_matches('/');
            let resp = get(api_url).with_timeout(30).send()?;
            
            if resp.status_code == 200 {
                let data: Value = resp.json()?;
                if data.is_array() && !data.as_array().unwrap().is_empty() && data[0].get("assets").is_some() {
                    println!("Source '{}' updated and verified", name);
                } else {
                    println!("Source '{}' updated but structure unexpected", name);
                }
            } else {
                println!("Source '{}' update failed: HTTP {}", name, resp.status_code);
            }
        }
        SourceAction::Enable { name } => {
            if let Some(src) = config_data.manifest_sources.iter_mut().find(|s| s.name == name) {
                src.enabled = true;
                config.save()?;
                println!("Enabled source: {}", name);
            } else {
                println!("Source not found: {}", name);
            }
        }
        SourceAction::Disable { name } => {
            if let Some(src) = config_data.manifest_sources.iter_mut().find(|s| s.name == name) {
                src.enabled = false;
                config.save()?;
                println!("Disabled source: {}", name);
            } else {
                println!("Source not found: {}", name);
            }
        }
    }

    Ok(())
}