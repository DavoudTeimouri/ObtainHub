# ObtainHub

**Windows x64 app manager via GitHub Releases**

ObtainHub (`ohub`) is a CLI tool for managing Windows x64 applications that are distributed via GitHub Releases. It handles downloading, silent installation, updates, and state tracking — all from the command line.

## Features

- **Windows x64 only** — optimized for `.msi`, `.exe` (Inno/NSIS/InstallShield), and `.zip` assets
- **Silent installation** — `msiexec /qn` for MSI, auto-detected flags for EXE
- **Smart asset selection** — prefers x64 > ARM64 > x86, MSI > Setup.exe > ZIP
- **Self-update** — updates itself via GitHub Releases
- **State tracking** — records installed apps, versions, and installer paths in `state.json`
- **Prerelease support** — opt-in with `--prerelease` flag
- **Download-only mode** — fetch installers without executing them
- **Custom sources** — add custom GitHub or manifest sources
- **System app detection** — scan Windows Registry for installed applications
- **GitHub token support** — higher rate limits with `GITHUB_TOKEN` environment variable

## Installation

### Via Installer (Recommended)
Download the latest **ObtainHub-Setup-x64.exe** or **ObtainHub.msi** from [GitHub Releases](https://github.com/DavoudTeimouri/ObtainHub/releases).

```cmd
ObtainHub-Setup-x64.exe /VERYSILENT /NORESTART
```

### Via MSI (Enterprise)
```cmd
msiexec /i ObtainHub.msi /qn /norestart
```

### Manual
Download `ohub.exe` from [GitHub Releases](https://github.com/DavoudTeimouri/ObtainHub/releases) and place it in your PATH.

## Quick Start

```cmd
# Install an app from GitHub Releases
ohub install owner/repo

# Check for updates (don't install)
ohub check

# Update all installed apps
ohub update

# List installed apps
ohub list

# List all apps including system-installed
ohub list --all

# Uninstall an app
ohub uninstall owner/repo

# Self-update ObtainHub
ohub self-update

# Search GitHub repositories
ohub search "text editor" --min-stars 100
```

## Commands Reference

### `ohub install <owner/repo>`
Install an application from GitHub Releases.

```cmd
ohub install owner/repo                    # Latest stable release
ohub install owner/repo --tag v1.2.3       # Specific tag
ohub install owner/repo --prerelease       # Include prereleases
ohub install owner/repo --download-only    # Download only, don't install
ohub install owner/repo --force            # Force reinstall
ohub install owner/repo --yes              # Auto-confirm prompts
```

### `ohub update [owner/repo]`
Update installed applications.

```cmd
ohub update                          # Update all apps
ohub update owner/repo               # Update specific app
ohub update --prerelease             # Include prereleases
ohub update --dry-run                # Show what would be updated
ohub update --yes                    # Auto-confirm prompts
```

### `ohub check [owner/repo]`
Check for available updates without installing.

```cmd
ohub check                           # Check all apps
ohub check owner/repo                # Check specific app
ohub check --prerelease              # Include prereleases
ohub check --json                    # Output as JSON
```

### `ohub list`
List all installed applications.

```cmd
ohub list                            # Tabular output (ohub-managed apps)
ohub list --json                     # JSON output
ohub list --all                      # Include system-installed apps from Windows Registry
```

**Output format:**
```
Name                      Version          ID                              Type
--------------------------------------------------------------------------------
MyApp                     1.2.3            owner/repo                      msi
AnotherApp                2.0.0-beta       owner/another                   exe
```

### `ohub uninstall <owner/repo>`
Uninstall an application and remove from state.

```cmd
ohub uninstall owner/repo              # Uninstall with confirmation
ohub uninstall owner/repo --yes        # Auto-confirm
ohub uninstall owner/repo --keep-data  # Keep downloaded installer files
```

### `ohub source`
Manage custom sources (GitHub repos or manifest URLs).

```cmd
ohub source list                       # List configured sources
ohub source add my-source https://api.github.com/repos/owner/repo
ohub source add my-manifest https://example.com/manifest.json --type manifest
ohub source remove my-source
```

### `ohub search <query>`
Search GitHub repositories for applications with releases.

```cmd
ohub search "text editor" --limit 10 --min-stars 100 --active-only
ohub search "terminal" --min-stars 50 --include-inactive
```

**Options:**
- `--limit <n>` - Maximum results (default: 10)
- `--min-stars <n>` - Filter repositories with at least N stars (default: 0)
- `--active-only` - Only show active, non-archived repos with recent activity (default: enabled)
- `--include-inactive` - Include archived/inactive repositories

**Output format (sorted by stars descending):**
```
Name                                      Stars   Latest Release     Updated     Description
------------------------------------------------------------------------------------------------------------------------
owner/repo                                1,234   Has releases       2024-01-15  A text editor
```

### `ohub config`
Manage configuration.

```cmd
ohub config show                       # Show all config
ohub config get github_token           # Get specific value
ohub config set github_token "ghp_xxx" # Set value
ohub config edit                       # Open in editor (not yet implemented)
```

### `ohub self-update`
Update ObtainHub itself.

```cmd
ohub self-update                       # Check and update
ohub self-update --prerelease          # Include prereleases
ohub self-update --force               # Force update
```

## Global Options

| Option | Description |
|--------|-------------|
| `-v`, `--verbose` | Increase verbosity (use `-vv` for debug) |
| `--version` | Show version |
| `--skip-self-update` | Skip self-update check on startup |

## Configuration

Config file: `%USERPROFILE%\.config\obtainhub\config.json`

```json
{
  "github_token": "",
  "install_dir": "C:\\Users\\<user>\\Applications\\ObtainHub",
  "download_dir": "C:\\Users\\<user>\\Downloads\\ObtainHub",
  "config_dir": "C:\\Users\\<user>\\.config\\obtainhub",
  "state_dir": "C:\\Users\\<user>\\.local\\share\\obtainhub",
  "update_interval_hours": 24,
  "auto_update": true,
  "allow_prerelease": false,
  "prefer_x64": true,
  "allow_x86_fallback": false,
  "auto_attempt_uninstall": false,
  "self_update_enabled": true,
  "sources": []
}
```

### GitHub Token (Optional)
Set a GitHub Personal Access Token to avoid rate limits (60/hr → 5000/hr):

```cmd
ohub config set github_token "ghp_xxx"
```

Or set `GITHUB_TOKEN` or `OBTAINHUB_TOKEN` environment variable:
```cmd
set GITHUB_TOKEN=ghp_xxx
```

When rate limited without a token, you'll see:
```
GitHub API rate limit exceeded. Set a GITHUB_TOKEN environment variable to increase limit from 60 to 5000 requests/hour.
```

## State Tracking

Installed apps are tracked in `%APPDATA%\ObtainHub\state.json` (Windows) or `~/.obtainhub/state.json` (other platforms):

```json
{
  "apps": {
    "owner/repo": {
      "id": "owner/repo",
      "name": "repo",
      "version": "1.2.3",
      "installer_type": "msi",
      "installer_path": "C:\\Users\\<user>\\Downloads\\ObtainHub\\app.msi",
      "source_url": "https://github.com/owner/repo/releases/tag/v1.2.3",
      "tag": "v1.2.3",
      "installed_at": 1700000000,
      "updated_at": 1700000000,
      "requires_manual_uninstall": false
    }
  }
}
```

## System Application Detection

`ohub list --all` scans the Windows Registry for installed applications:

- `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall`
- `HKLM\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall`
- `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall`

This enables `ohub check` to match system-installed apps against GitHub repositories for update detection.

## Asset Selection Logic

When multiple assets exist in a release, ObtainHub selects the best match:

1. **Architecture priority**: x64 > ARM64 > x86 (ARM64/x86 only if explicitly allowed)
2. **Installer priority**: MSI > Setup.exe > ZIP
3. **Exclusions**: Checksums (`.sha256`, `.asc`), signatures, non-Windows packages (`.deb`, `.rpm`, `.dmg`, `.tar.gz`), source archives
4. **Download-only**: ZIP files are never auto-installed

## Manual Uninstall Handling

If an app was installed outside ObtainHub or the installer doesn't support silent uninstall:

```
Notice: MyApp requires manual uninstallation of the previous version.
Installer downloaded to: C:\Users\<user>\Downloads\ObtainHub\app-v2.msi
Options: [1] Attempt auto-uninstall [2] Cancel / Manual uninstall
```

Use `--force` to skip this check, or uninstall manually first.

## Building from Source

### Prerequisites
- Python 3.11+ (x64)
- PyInstaller: `pip install pyinstaller`
- Inno Setup 6 (for .exe installer): https://jrsoftware.org/isinfo.php
- WiX Toolset v4+ (for .msi): https://wixtoolset.org/

### Build Commands
```cmd
# Build everything (exe + installer + MSI + workflow)
python build_dist.py --all

# Build only executable (onefile)
python build_dist.py --onefile

# Build onedir executable
python build_dist.py --onedir

# Build Inno Setup installer (requires exe)
python build_dist.py --installer

# Build MSI with Python msilib (stdlib)
python build_dist.py --msi

# Generate GitHub Actions workflow
python build_dist.py --workflow

# Clean build artifacts
python build_dist.py --clean
```

### Outputs
- `dist/ohub.exe` — Standalone onefile executable
- `dist/ohub/ohub.exe` — Onedir executable (directory layout)
- `installer/ObtainHub-Setup.exe` — Inno Setup installer (no desktop shortcuts, no launch prompt)
- `installer/ObtainHub.msi` — Python msilib MSI installer

## GitHub Actions

Automated builds on tag push (e.g., `git tag v0.1.0 && git push origin v0.1.0`):

- Builds on `windows-latest`
- Creates `ohub.exe`, `ObtainHub-Setup.exe`, and `ObtainHub.msi`
- Publishes to GitHub Releases as prerelease or stable

Workflow: `.github/workflows/release.yml`

**Note:** Release tag `v0.1.0-beta.2` is used for pre-releases. Assets are updated on this tag directly.

## Requirements

- Windows 10/11 x64
- Python 3.11+ (for development)
- GitHub API access (token optional, but recommended for higher rate limits)

## License

MIT License — see LICENSE file.

## Author

Davoud Teimouri — https://github.com/DavoudTeimouri