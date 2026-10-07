use crate::core::{ConfigManager, StateManager};
use crate::cli::{ScheduleArgs, ScheduleAction};
use anyhow::Result;
use tracing::info;

pub async fn execute(args: ScheduleArgs, config: &mut ConfigManager, state: &mut StateManager) -> Result<()> {
    info!("Schedule command: {:?}", args.action);

    let config_data = config.get_mut();

    match args.action {
        ScheduleAction::Enable => {
            config_data.schedule.enabled = true;
            config.save()?;
            println!("Scheduled checks enabled");
            
            // Note: Actual Windows Task Scheduler / cron job creation would require
            // platform-specific code. For now, just update config.
            #[cfg(windows)]
            {
                println!("Note: Windows Task Scheduler integration not yet implemented");
            }
            #[cfg(unix)]
            {
                println!("Note: Cron job creation not yet implemented");
            }
        }
        ScheduleAction::Disable => {
            config_data.schedule.enabled = false;
            config.save()?;
            println!("Scheduled checks disabled");
            
            #[cfg(windows)]
            {
                println!("Note: Windows Task Scheduler removal not yet implemented");
            }
            #[cfg(unix)]
            {
                println!("Note: Cron job removal not yet implemented");
            }
        }
        ScheduleAction::Status => {
            println!("Scheduled checks: {}", if config_data.schedule.enabled { "ENABLED" } else { "DISABLED" });
            println!("Interval: {} hours", config_data.schedule.interval_hours);
            println!("Notify on update: {}", config_data.schedule.notify_on_update);
            println!("Run on startup: {}", config_data.schedule.run_on_startup);
            
            if config_data.schedule.enabled {
                if let Some(last_run) = config_data.schedule.last_run {
                    println!("Last run: {}", last_run.format("%Y-%m-%d %H:%M:%S UTC"));
                } else {
                    println!("Last run: never");
                }
            }
        }
        ScheduleAction::Run { prerelease } => {
            println!("[*] Running scheduled check... (prerelease: {})", prerelease);
            // This would trigger the check command for all installed apps
            // For now, just note it's not fully integrated
            println!("Note: Full scheduled check integration pending");
            
            // Update last_run timestamp
            config_data.schedule.last_run = Some(chrono::Utc::now());
            config.save()?;
        }
    }

    Ok(())
}