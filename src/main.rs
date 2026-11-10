use clap::Parser;
use crate::cli::{Cli, Commands};
use crate::core::{config, state, logger};
use anyhow::{Context, Result};
use std::fs;
use std::process;

mod cli;
mod core;
mod commands;
mod utils;
mod webui;

/// Check if a process with the given PID is still alive.
fn is_process_alive(pid: u32) -> bool {
    if cfg!(windows) {
        // tasklist (read-only probe) — taskkill would risk signaling the process.
        match process::Command::new("tasklist")
            .args(["/FI", &format!("PID eq {pid}"), "/NH"])
            .output()
        {
            Ok(out) => String::from_utf8_lossy(&out.stdout).contains(&pid.to_string()),
            Err(_) => false,
        }
    } else {
        match process::Command::new("kill").args(["-0", &pid.to_string()]).output() {
            Ok(out) => out.status.success(),
            Err(_) => false,
        }
    }
}

/// Write PID file, ignoring errors (best-effort single-instance guard).
fn write_pid_file(pid_file: &std::path::Path) {
    if let Some(parent) = pid_file.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let _ = std::fs::write(pid_file, std::process::id().to_string());
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    // Initialize logging. `--verbose` turns the level up to debug.
    logger::init(cli.verbose)?;

    // The progress bar drops its colours. The TUI keeps its own.
    crate::core::download::set_no_color(cli.no_color);

    // Initialize config and state
    let mut config_manager = config::ConfigManager::new()?;
    let mut state_manager = state::StateManager::new()?;
    
    // Create retry config from config
    let retry_config = crate::utils::retry::RetryConfig::from_config(&config_manager);

    // The request timeout for this run. A command with a --timeout flag
    // overrides it; every HTTP call reads it from here.
    crate::core::registries::set_request_timeout(config_manager.get().timeout_seconds);

    let format = cli.format;
    
    // Handle command
    match cli.command {
        Commands::Search(args) => commands::search::execute(args, &config_manager, &mut state_manager, format).await,
        Commands::Install(args) => commands::install::execute(args, &config_manager, &mut state_manager, &retry_config).await,
        Commands::Check(args) => commands::check::execute(args, &config_manager, &mut state_manager).await,
        Commands::List(args) => commands::list::execute(args, &config_manager, &mut state_manager).await,
        Commands::Update(args) => commands::update::execute(args, &config_manager, &mut state_manager, &retry_config).await,
        Commands::Uninstall(args) => commands::uninstall::execute(args, &mut config_manager, &mut state_manager).await,
        Commands::Tui(args) => commands::tui::execute(args, &mut config_manager, &mut state_manager).await,
        Commands::Config(args) => commands::config::execute(args, &mut config_manager, &mut state_manager).await,
        Commands::Backup(args) => commands::backup::execute(args, &config_manager, &state_manager).await,
        Commands::Restore(args) => commands::restore::execute(args, &mut config_manager, &mut state_manager).await,
        Commands::SelfUpdate(args) => commands::self_update::execute(args, &config_manager, &state_manager, &retry_config).await,
        Commands::Rollback(args) => commands::rollback::execute(args, &config_manager, &mut state_manager, &retry_config).await,
        Commands::Completion(args) => commands::completion::execute(args).await,
        Commands::Doctor(args) => commands::doctor::execute(args, &config_manager, &mut state_manager).await,
        Commands::Info(args) => commands::info::execute(args, &config_manager, &state_manager).await,
        Commands::Remove(args) => commands::remove::execute(args, &config_manager, &mut state_manager).await,
        Commands::Add(args) => commands::add::execute(args, &mut config_manager, &mut state_manager, &retry_config).await,
        Commands::Source(args) => commands::source::execute(args, &mut config_manager, &state_manager).await,
        Commands::SelfUninstall(args) => commands::self_uninstall::execute(args, &config_manager, &mut state_manager).await,
        Commands::Schedule(args) => commands::schedule::execute(args, &mut config_manager, &mut state_manager).await,
        Commands::Log(args) => commands::log::execute(args),
        Commands::Webui(args) => {
            // Parse bind address
            let bind_addr: std::net::SocketAddr = format!("{}:{}", args.bind, args.port)
                .parse()
                .context("Invalid bind address")?;

            // Single instance: check if ohub WebUI is already running via PID file.
            let pid_file = dirs::data_dir()
                .unwrap_or_else(std::env::temp_dir)
                .join("ObtainHub")
                .join("webui.pid");
            if pid_file.exists() {
                if let Ok(pid_str) = fs::read_to_string(&pid_file) {
                    if let Ok(pid) = pid_str.trim().parse::<u32>() {
                        if is_process_alive(pid) {
                            // Previous instance stays running on its port; this
                            // instance binds the next free port (see run_webui).
                            println!("ohub WebUI already running (PID {pid}) — leaving it running; this instance will use the next free port.");
                        } else {
                            // Stale PID file — remove it
                            let _ = fs::remove_file(&pid_file);
                        }
                    }
                }
            }

            // Write PID file
            write_pid_file(&pid_file);

            // Start the WebUI server (blocks until shutdown). Browser opens
            // automatically inside run_webui() on the actual listening port.
            let _ = crate::webui::run_webui(bind_addr, config_manager, state_manager, args.auth).await;

            // Clean up PID file on exit
            let _ = fs::remove_file(&pid_file);
            Ok(())
        }
        Commands::Group(args) => commands::group::execute(args, &mut config_manager, &mut state_manager).await,
        Commands::Shim(args) => commands::shim::execute(args, &config_manager, &state_manager).await,
        Commands::State(args) => commands::state::execute(args, &config_manager, &mut state_manager).await,
        Commands::Apps(args) => commands::apps::execute(args, &config_manager, &state_manager).await,
        Commands::Cleanup(args) => commands::cleanup::execute(args, &config_manager, &mut state_manager).await,
        Commands::Reset(args) => commands::reset::execute(args, &mut config_manager, &mut state_manager).await,
    }
}
