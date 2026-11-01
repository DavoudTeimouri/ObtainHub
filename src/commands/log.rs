use anyhow::Result;
use std::fs;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;

use crate::cli::LogArgs;

/// Where the scheduled run writes its report.
fn schedule_log_path() -> PathBuf {
    let mut dir = dirs::data_dir().unwrap_or_else(|| std::env::current_dir().unwrap_or_default());
    dir.push("obtainhub");
    dir.push("schedule.log");
    dir
}

/// Show the last N lines of the schedule log.
///
/// The scheduled check (`ohub schedule run`) writes one line per run to
/// `<data_dir>/obtainhub/schedule.log`. `ohub log` reads the tail of it so a
/// user can see what happened without opening the file in an editor.
pub fn execute(args: LogArgs) -> Result<()> {
    let path = schedule_log_path();

    if !path.exists() {
        println!("No log file yet at {}", path.display());
        println!("Run 'ohub schedule enable' to start scheduled checks.");
        return Ok(());
    }

    let file = fs::File::open(&path)?;
    let reader = BufReader::new(file);

    // Collect all lines, then print the last `args.lines`.
    // A plain `for line in reader.lines()` skips read errors instead of
    // looping forever on them (clippy::lines_filter_map_ok).
    let mut lines = Vec::new();
    for line in reader.lines() {
        if let Ok(l) = line {
            lines.push(l);
        }
    }
    let total = lines.len();
    let start = total.saturating_sub(args.lines);

    if total == 0 {
        println!("Log file is empty.");
        return Ok(());
    }

    println!("Last {} of {} lines from {}", args.lines, total, path.display());
    println!("{}", "-".repeat(60));
    for line in lines.into_iter().skip(start) {
        println!("{line}");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn schedue_log_path_has_expected_name() {
        let path = schedule_log_path();
        assert_eq!(path.file_name().unwrap(), "schedule.log");
        assert_eq!(
            path.parent().unwrap().file_name().unwrap(),
            "obtainhub"
        );
    }
}
