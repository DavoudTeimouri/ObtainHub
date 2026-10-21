use clap::Parser;
use crate::cli::{Cli, Commands};
use crate::core::{config, state, logger};
use anyhow::Result;

mod cli;
mod core;
mod commands;
mod utils;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging
    logger::init()?;
    
    let cli = Cli::parse();
    
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
        Commands::Group(args) => commands::group::execute(args, &mut config_manager, &mut state_manager).await,
        Commands::Shim(args) => commands::shim::execute(args, &config_manager, &state_manager).await,
        Commands::State(args) => commands::state::execute(args, &config_manager, &mut state_manager).await,
        Commands::Apps(args) => commands::apps::execute(args, &config_manager, &state_manager).await,
        Commands::Cleanup(args) => commands::cleanup::execute(args, &config_manager, &mut state_manager).await,
        Commands::Reset(args) => commands::reset::execute(args, &mut config_manager, &mut state_manager).await,
    }
}
