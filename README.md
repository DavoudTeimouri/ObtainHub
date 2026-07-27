# ObtainHub

**GitHub-based Package Updater and Manager for Windows x64**

ObtainHub (`ohub`) is a command-line tool for managing and updating Windows applications distributed via GitHub Releases. It downloads and executes `.msi` and `-Setup.exe` installers compiled for x64 architecture.

## Features

- **Windows x64 Only**: Strictly targets 64-bit Windows (x64/AMD64)
- **Native Installers**: Only downloads and executes `.msi` and `-Setup.exe` files
- **Self-Update**: Checks for and installs its own updates on every run
- **Prerelease Support**: Optional `--prerelease` flag with explicit confirmation prompts
- **ZIP Fallback**: Portable `.zip` archives are downloaded only (no auto-install)
- **Manual Uninstall Detection**: Prompts for manual uninstall when required
- **GitHub Token Support**: Higher API rate limits with personal access token
- **Structured Logging**: JSON and console output with rotation

## Installation

### Option 1: Download Installer (Recommended)

Download the latest **`.msi`** or **`-Setup.exe`** from the [Releases](https://github.com/ObtainHub/ObtainHub/releases) page.

> **Note**: Only Windows x64 installers are provided. No Linux, macOS, or ARM64 builds.

### Option 2: Build from Source

```cmd
git clone https://github.com/ObtainHub/ObtainHub.git
cd ObtainHub
python -m pip install -e .
```

Requires Python 3.10+ on Windows x64.

## Quick Start

```cmd
# Install an application from GitHub releases
ohub install microsoft/vscode

# Check for updates
ohub check

# Update all installed applications
ohub update

# Add a custom manifest source
ohub source add my-source https://example.com/manifest.json

# View configuration
ohub config --list
```

## Commands

| Command | Description |
|---------|-------------|
| `install <owner/repo>` | Install an application from GitHub releases |
| `update` | Update all installed applications |
| `check` | Check for available updates |
| `source` | Manage manifest sources (add/remove/list/enable/disable) |
| `config` | View or modify configuration |

### Global Options

| Option | Description |
|--------|-------------|
| `--skip-self-update` | Skip ObtainHub self-update check on startup |
| `--prerelease`, `-p` | Include prerelease versions (requires confirmation) |
| `--verbose`, `-v` | Enable verbose output |
| `--config-dir PATH` | Use custom configuration directory |

## Self-Update Behavior

ObtainHub checks for its own updates **on every command execution** (except `config`).

1. Fetches latest release from GitHub
2. Filters for Windows x64 `.msi` or `-Setup.exe` assets
3. If newer version found:
   - Downloads installer
   - **Prerelease**: Prompts `"Warning: Version X.Y.Z is a Prerelease. Are you sure you want to proceed? [y/N]"`
   - Launches installer detached (allows file replacement)
   - Exits current instance

Use `--skip-self-update` or set `skip_self_update: true` in config to disable.

## Prerelease Handling

By default, only **Stable** releases are considered.

```cmd
# Include prereleases (will prompt for confirmation)
ohub install owner/repo --prerelease
ohub update --prerelease
```

**Confirmation prompt:**
```
Warning: Version 2.0.0-beta.1 is a Prerelease.
Are you sure you want to proceed? [y/N]
```

Use `--auto-confirm-prerelease` config option for CI/CD (not recommended for interactive use).

## ZIP Archive Handling

If a release only provides `.zip` (portable/archive), ObtainHub **downloads only**:

```
No Windows x64 installer (.msi/.exe) found.
Downloading portable archive: App-portable.zip
```

The file is saved to your downloads folder (`~/Downloads/ObtainHub` by default). No automatic extraction or installation is attempted.

## Manual Uninstall Detection

Some applications require manual uninstallation before upgrading.

When detected:
```
Notice: AppName requires manual uninstallation of the previous version.
Installer downloaded. Do you want ohub to attempt auto-uninstalling the previous version, or will you perform it manually?
[1: Attempt Auto-Uninstall / 2: Manual / Abort]
```

- **1**: ObtainHub attempts silent uninstall via MSI/EXE
- **2**: You manually uninstall, then re-run install
- **Abort**: Cancel the operation

## Configuration

Config file: `%USERPROFILE%\.config\obtainhub\config.json`

```json
{
  "github_token": "",
  "install_dir": "C:\\Users\\<user>\\Applications\\ObtainHub",
  "download_dir": "C:\\Users\\<user>\\Downloads\\ObtainHub",
  "update_interval_hours": 24,
  "proxy": "",
  "auto_update": true,
  "log_level": "INFO",
  "max_parallel_downloads": 3,
  "manifest_sources": [
    {
      "name": "default",
      "url": "https://raw.githubusercontent.com/ObtainHub/manifests/main/manifest.json",
      "enabled": true
    }
  ],
  "preferred_arch": "x64",
  "allow_prerelease": false,
  "skip_self_update": false,
  "auto_confirm_prerelease": false
}
```

### Key Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `github_token` | GitHub Personal Access Token (classic) for higher rate limits | (empty) |
| `install_dir` | Where applications are installed | `~/Applications/ObtainHub` |
| `download_dir` | Where installers are downloaded | `~/Downloads/ObtainHub` |
| `auto_update` | Enable self-update checks | `true` |
| `preferred_arch` | Target architecture | `x64` |
| `allow_prerelease` | Include prereleases by default | `false` |
| `skip_self_update` | Disable self-update on startup | `false` |

## Manifest Sources

Manifest sources define where to find application metadata. The default source points to the ObtainHub community manifests.

```cmd
# Add custom source
ohub source add my-source https://my-server/manifest.json

# List sources
ohub source list

# Remove source
ohub source remove my-source
```

Manifest format (JSON):
```json
{
  "applications": [
    {
      "owner": "microsoft",
      "repo": "vscode",
      "name": "Visual Studio Code",
      "description": "Code editor",
      "requires_manual_uninstall": false
    }
  ]
}
```

## Logging

Logs are written to `%LOCALAPPDATA%\obtainhub\logs\`:
- `obtainhub.log` - Human-readable
- `obtainhub.json` - Structured JSON (rotating, 5MB max, 3 backups)

## Building the Installer

```cmd
# Build MSI installer
python -m pip install cx_Freeze
python setup.py bdist_msi

# Build NSIS installer (Setup.exe)
makensis installer.nsi
```

Only Windows x64 builds are supported.

## Requirements

- Windows 10/11 x64 (64-bit)
- Python 3.10+ (if running from source)
- Internet access for GitHub API

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes (Windows x64 focus only)
4. Submit a Pull Request

---

**ObtainHub** - Simple, native Windows application management via GitHub Releases.