//! Launching Windows installers and uninstallers with elevation.
//!
//! Programs under `C:\Program Files` and MSI installs need admin rights.
//! `Start-Process -Verb RunAs` asks Windows for the UAC prompt; `-Wait` blocks
//! until the child exits so callers can trust the exit code.

use anyhow::Result;
use std::path::Path;

/// Resolve powershell.exe. Explicit paths first, then PATH lookup - some
/// systems do not have System32 on PATH.
#[cfg(windows)]
pub fn find_powershell() -> String {
    let candidates = [
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        r"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe",
    ];
    for c in candidates {
        if std::path::Path::new(c).exists() {
            return c.to_string();
        }
    }
    "powershell.exe".to_string()
}

#[cfg(not(windows))]
pub fn find_powershell() -> String {
    "powershell".to_string()
}

/// Run a PowerShell `Start-Process ... -Verb RunAs -Wait` body elevated.
#[cfg(windows)]
pub fn run_elevated(ps_body: &str) -> Result<()> {
    let status = std::process::Command::new(find_powershell())
        .args(&["-Command", ps_body])
        .status()
        .context("Failed to launch elevated program")?;
    if !status.success() {
        anyhow::bail!("Program exited with error code {:?}", status.code());
    }
    Ok(())
}

#[cfg(not(windows))]
pub fn run_elevated(_ps_body: &str) -> Result<()> {
    anyhow::bail!("Elevation is only supported on Windows")
}

/// Escape a path for embedding in a double-quoted Windows command line.
fn win_quote(path: &str) -> String {
    format!("\"{}\"", path.replace('"', ""))
}

/// Run an installer (.exe or .msi) elevated and wait for it to finish.
pub fn run_installer(installer_path: &Path) -> Result<()> {
    let path = installer_path.to_string_lossy().to_string();
    let body = if installer_path
        .extension()
        .and_then(|s| s.to_str())
        .map(|e| e.eq_ignore_ascii_case("msi"))
        .unwrap_or(false)
    {
        format!(
            "Start-Process 'msiexec.exe' -ArgumentList '/i {} /qn /norestart' -Verb RunAs -Wait",
            win_quote(&path)
        )
    } else {
        format!(
            "Start-Process {} -ArgumentList '/S' -Verb RunAs -Wait",
            win_quote(&path)
        )
    };
    run_elevated(&body)
}

/// Run the uninstaller recorded in the Windows uninstall registry.
///
/// Registry values look like:
/// - `"C:\...\unins000.exe"`            (NSIS)
/// - `MsiExec.exe /I{GUID}`             (MSI - needs `/X` to uninstall)
/// - `"C:\...\uninstall.exe" /I`        (Burn bundle - needs `/X`)
///
/// Returns false when the string does not describe something we can run.
pub fn run_uninstaller(uninstall_string: &str) -> Result<bool> {
    let s = uninstall_string.trim();
    if s.is_empty() {
        return Ok(false);
    }

    // MSI: "MsiExec.exe /I{GUID}" -> "msiexec.exe /X{GUID} /qn"
    let lower = s.to_lowercase();
    if lower.contains("msiexec") {
        let guid = s
            .split_whitespace()
            .find(|p| p.starts_with('/') || p.starts_with('{'))
            .unwrap_or("");
        if guid.is_empty() {
            return Ok(false);
        }
        let mode = "/X";
        let body = format!(
            "Start-Process 'msiexec.exe' -ArgumentList '{mode}{} /qn /norestart' -Verb RunAs -Wait",
            guid.trim_start_matches('/').trim_start_matches('I')
        );
        run_elevated(&body)?;
        return Ok(true);
    }

    // NSIS / Burn: "path.exe" possibly followed by "/I" or "/X"
    let mut parts = s.split_whitespace();
    let exe = parts.next().unwrap_or("").trim_matches('"');
    if exe.is_empty() {
        return Ok(false);
    }
    let exe_path = Path::new(exe);
    if !exe_path.exists() {
        return Ok(false);
    }

    // Burn bundles: replace a trailing /I with /X so we uninstall, not install.
    let tail: Vec<&str> = parts.collect();
    let mut args: Vec<String> = Vec::new();
    for a in tail {
        if a.eq_ignore_ascii_case("/I") {
            args.push("/X".to_string());
        } else if !a.eq_ignore_ascii_case("/X") {
            args.push(a.to_string());
        }
    }
    // NSIS uninstallers take /S for silent; Burn takes /X only.
    let arg_str = if args.is_empty() {
        "/S".to_string()
    } else {
        args.join(" ")
    };

    let body = format!(
        "Start-Process {} -ArgumentList '{}' -Verb RunAs -Wait",
        win_quote(exe),
        arg_str
    );
    run_elevated(&body)?;
    Ok(true)
}
