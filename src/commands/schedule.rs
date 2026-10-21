use crate::core::{ConfigManager, StateManager};
use crate::cli::{Arch, CheckArgs, ScheduleArgs, ScheduleAction};
use anyhow::Result;
use std::fs;
use std::path::PathBuf;
use tracing::info;

/// The name of the Windows Task Scheduler task ObtainHub creates.
/// `ohub cleanup tasks` looks for the same name.
#[allow(dead_code)]
const TASK_NAME: &str = "ObtainHubScheduledCheck";

/// Where the scheduled run writes its report.
fn schedule_log_path() -> PathBuf {
    let mut dir = dirs::data_dir().unwrap_or_else(|| dirs::home_dir().unwrap_or_default());
    dir.push("obtainhub");
    let _ = fs::create_dir_all(&dir);
    dir.push("schedule.log");
    dir
}

/// The `schtasks` schedule and modifier for an interval in hours.
/// Only the Windows task-scheduler path calls it.
#[allow(dead_code)]
fn schedule_parts(interval_hours: u64) -> Result<(&'static str, u64)> {
    match interval_hours {
        0 => Err(anyhow::anyhow!(
            "The schedule interval must be at least 1 hour"
        )),
        // /MO with /SC HOURLY accepts 1-23.
        1..=23 => Ok(("HOURLY", interval_hours)),
        24 => Ok(("DAILY", 1)),
        // Multiples of 24 become every N days.
        h if h % 24 == 0 && h / 24 <= 31 => Ok(("DAILY", h / 24)),
        h => Err(anyhow::anyhow!(
            "Unsupported schedule interval of {h} hours - use 1-23 (hourly), 24 (daily), or a multiple of 24 up to 744"
        )),
    }
}

#[cfg(windows)]
fn create_task(interval_hours: u64) -> Result<()> {
    use std::process::Command;

    let exe = std::env::current_exe()?;
    let log = schedule_log_path();
    let action = format!(
        "\"{}\" check --quiet --log \"{}\"",
        exe.display(),
        log.display()
    );
    let (schedule, modifier) = schedule_parts(interval_hours)?;
    let modifier = modifier.to_string();

    // /MO is valid for both HOURLY (every n hours) and DAILY (every n days),
    // so the argument list never changes shape.
    let output = Command::new("schtasks")
        .args([
            "/Create",
            "/TN",
            TASK_NAME,
            "/TR",
            action.as_str(),
            "/SC",
            schedule,
            "/MO",
            modifier.as_str(),
            "/F",
        ])
        .output()?;
    if !output.status.success() {
        anyhow::bail!(
            "Could not create the scheduled task: {}",
            String::from_utf8_lossy(&output.stderr).trim()
        );
    }
    Ok(())
}

#[cfg(not(windows))]
fn create_task(_interval_hours: u64) -> Result<()> {
    anyhow::bail!("Scheduled checks need the Windows Task Scheduler")
}

#[cfg(windows)]
fn delete_task() -> Result<()> {
    use std::process::Command;

    let output = Command::new("schtasks")
        .args(["/Delete", "/TN", TASK_NAME, "/F"])
        .output()?;
    if !output.status.success() {
        let message = String::from_utf8_lossy(&output.stderr).trim().to_string();
        // A task that is already gone is not a failure.
        if !message.to_lowercase().contains("cannot find")
            && !message.to_lowercase().contains("not found")
        {
            anyhow::bail!("Could not remove the scheduled task: {message}");
        }
    }
    Ok(())
}

#[cfg(not(windows))]
fn delete_task() -> Result<()> {
    anyhow::bail!("Scheduled checks need the Windows Task Scheduler")
}

#[cfg(windows)]
fn show_task_status() -> Result<()> {
    use std::process::Command;

    let output = Command::new("schtasks")
        .args(["/Query", "/TN", TASK_NAME, "/FO", "LIST"])
        .output()?;
    if !output.status.success() {
        println!("Task '{TASK_NAME}' is not registered with the Task Scheduler");
        return Ok(());
    }
    print!("{}", String::from_utf8_lossy(&output.stdout));
    Ok(())
}

#[cfg(not(windows))]
fn show_task_status() -> Result<()> {
    Ok(())
}

pub async fn execute(
    args: ScheduleArgs,
    config: &mut ConfigManager,
    state: &mut StateManager,
) -> Result<()> {
    info!("Schedule command: {:?}", args.action);

    match args.action {
        ScheduleAction::Enable => {
            let interval_hours = config.get().schedule.interval_hours;
            create_task(interval_hours)?;
            config.get_mut().schedule.enabled = true;
            config.save()?;
            println!("Scheduled checks enabled every {interval_hours} hours");
            println!("Report: {}", schedule_log_path().display());
        }
        ScheduleAction::Disable => {
            delete_task()?;
            config.get_mut().schedule.enabled = false;
            config.save()?;
            println!("Scheduled checks disabled");
        }
        ScheduleAction::Status => {
            let config_data = config.get();
            println!(
                "Scheduled checks: {}",
                if config_data.schedule.enabled {
                    "ENABLED"
                } else {
                    "DISABLED"
                }
            );
            println!("Interval: {} hours", config_data.schedule.interval_hours);
            println!("Notify on update: {}", config_data.schedule.notify_on_update);
            println!("Run on startup: {}", config_data.schedule.run_on_startup);
            if let Some(last_run) = config_data.schedule.last_run {
                println!("Last run: {}", last_run.format("%Y-%m-%d %H:%M:%S UTC"));
            } else {
                println!("Last run: never");
            }
            show_task_status()?;
        }
        ScheduleAction::Run { prerelease } => {
            // The same thing the scheduled task does, so a manual run and a
            // scheduled run leave the same record behind.
            let log = schedule_log_path();
            let check_args = CheckArgs {
                repo: None,
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
                quiet: false,
                dry_run: false,
                log: Some(log.display().to_string()),
            };
            crate::commands::check::execute(check_args, config, state).await?;
            config.get_mut().schedule.last_run = Some(chrono::Utc::now());
            config.save()?;
            println!("Report written to {}", log.display());
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn intervals_map_to_schtasks_arguments() {
        // /MO with /SC HOURLY only accepts 1-23.
        assert_eq!(schedule_parts(1).unwrap(), ("HOURLY", 1));
        assert_eq!(schedule_parts(23).unwrap(), ("HOURLY", 23));
        // A whole day is every 1 day.
        assert_eq!(schedule_parts(24).unwrap(), ("DAILY", 1));
        // Multiples of 24 become every N days.
        assert_eq!(schedule_parts(48).unwrap(), ("DAILY", 2));
        assert_eq!(schedule_parts(744).unwrap(), ("DAILY", 31));
        // Everything else is refused rather than silently rounded.
        assert!(schedule_parts(0).is_err());
        assert!(schedule_parts(25).is_err());
        assert!(schedule_parts(999).is_err());
    }
}