use crate::core::{ConfigManager, StateManager};
use crate::cli::{Arch, CheckArgs, GroupArgs, GroupAction, InstallArgs, UninstallArgs, UpdateArgs};
use crate::utils::retry::RetryConfig;
use anyhow::Result;
use tracing::info;

pub async fn execute(
    args: GroupArgs,
    config: &mut ConfigManager,
    state: &mut StateManager,
) -> Result<()> {
    info!("Group command: {:?}", args.action);

    match args.action {
        GroupAction::List => {
            let config_data = config.get();
            if config_data.groups.is_empty() {
                println!("No groups configured.");
            } else {
                for (name, apps) in &config_data.groups {
                    println!("{}: {}", name, apps.join(", "));
                }
            }
        }
        GroupAction::Add { name, apps } => {
            config.get_mut().groups.insert(name.clone(), apps.clone());
            config.save()?;
            println!("Created group '{}' with apps: {}", name, apps.join(", "));
        }
        GroupAction::Remove { name, apps } => {
            if let Some(group_apps) = config.get_mut().groups.get_mut(&name) {
                group_apps.retain(|a| !apps.contains(a));
                config.save()?;
                println!("Removed apps from group '{}': {}", name, apps.join(", "));
            } else {
                println!("Group not found: {name}");
            }
        }
        GroupAction::Delete { name } => {
            if config.get_mut().groups.remove(&name).is_some() {
                config.save()?;
                println!("Deleted group: {name}");
            } else {
                println!("Group not found: {name}");
            }
        }
        GroupAction::Install { name, prerelease } => {
            let Some(apps) = group_apps(config, &name) else {
                println!("Group not found: {name}");
                return Ok(());
            };
            println!("Installing {} app(s) from group '{name}'", apps.len());
            let retry = RetryConfig::from_config(config);
            for repo in apps {
                println!("--- {repo} ---");
                let install_args = InstallArgs {
                    repo: repo.clone(),
                    version: None,
                    tag: None,
                    prerelease,
                    force: false,
                    download_only: false,
                    skip_deps: false,
                    timeout: None,
                    arch: Arch::Auto,
                    yes: false,
                    reset: false,
                    interactive: false,
                    dry_run: false,
                    file: None,
                    url: None,
                    dependencies: Vec::new(),
                };
                if let Err(e) = crate::commands::install::execute(install_args, config, state, &retry).await {
                    println!("  {repo} failed: {e}");
                }
            }
        }
        GroupAction::Update { name, prerelease } => {
            let Some(apps) = group_apps(config, &name) else {
                println!("Group not found: {name}");
                return Ok(());
            };
            println!("Updating {} app(s) from group '{name}'", apps.len());
            let retry = RetryConfig::from_config(config);
            for repo in apps {
                println!("--- {repo} ---");
                let update_args = UpdateArgs {
                    repo: Some(repo.clone()),
                    prerelease,
                    dry_run: false,
                    force: false,
                    skip_deps: false,
                    timeout: None,
                    arch: Arch::Auto,
                    yes: false,
                    reset: false,
                    interactive: false,
                    notes: false,
                    quiet: true,
                    log: None,
                };
                if let Err(e) = crate::commands::update::execute(update_args, config, state, &retry).await {
                    println!("  {repo} failed: {e}");
                }
            }
        }
        GroupAction::Check { name, prerelease } => {
            let Some(apps) = group_apps(config, &name) else {
                println!("Group not found: {name}");
                return Ok(());
            };
            println!("Checking {} app(s) from group '{name}'", apps.len());
            for repo in apps {
                println!("--- {repo} ---");
                let check_args = CheckArgs {
                    repo: Some(repo.clone()),
                    outdated_only: false,
                    prerelease,
                    yes: false,
                    all: false,
                    candidates: false,
                    reset: false,
                    arch: Arch::Auto,
                    timeout: None,
                    notes: false,
                    force: false,
                    quiet: true,
                    dry_run: false,
                    log: None,
                };
                if let Err(e) = crate::commands::check::execute(check_args, config, state).await {
                    println!("  {repo} failed: {e}");
                }
            }
        }
        GroupAction::Uninstall { name, force } => {
            let Some(apps) = group_apps(config, &name) else {
                println!("Group not found: {name}");
                return Ok(());
            };
            println!("Uninstalling {} app(s) from group '{name}'", apps.len());
            for repo in apps {
                println!("--- {repo} ---");
                let uninstall_args = UninstallArgs {
                    repo: repo.clone(),
                    purge: false,
                    yes: false,
                    force,
                };
                if let Err(e) = crate::commands::uninstall::execute(uninstall_args, config, state).await {
                    println!("  {repo} failed: {e}");
                }
            }
        }
    }

    Ok(())
}

/// The repo ids tracked by a group, or None when the group does not exist.
fn group_apps(config: &ConfigManager, name: &str) -> Option<Vec<String>> {
    config.get().groups.get(name).cloned()
}