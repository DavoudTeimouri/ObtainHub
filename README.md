# ObtainHub

**Windows x64 app manager via GitHub Releases — and custom sources**

ObtainHub (`ohub`) is a CLI tool for installing, updating, and tracking Windows x64 applications distributed via **GitHub Releases** or **custom sources** (any GitHub repo, or a JSON manifest hosted anywhere — including non-GitHub hosts). It handles downloading, silent installation, updates, and state tracking — all from the command line.

## Features

- **Windows x64 only** — optimized for `.msi`, `.exe` (Inno/NSIS/InstallShield), `.zip` installer, and portable archives
- **Silent installation** — `msiexec /qn` for MSI, auto-detected flags for EXE
- **Smart asset selection** — prefers x64 > ARM64 > x86, EXE_SETUP (Inno) > MSI > ZIP_INSTALLER; portable archives are extracted and tracked
- **GitHub repo management** — track a repo by exact `owner/repo` and keep it updated
- **Older-version install** — `ohub install owner/repo --version 1.2.3`, or pick from the 3 most recent releases interactively
- **Archive (zip) repos** — for repos (incl. archived) that only ship ZIP/portable assets: download, extract to a folder, and track for updates
- **Local folder management** — `ohub add --type folder --name MyApp --repo owner/repo` tracks a folder app linked to a GitHub repo for updates
- **Custom sources (non-GitHub)** — `ohub source add` registers a GitHub repo or a JSON manifest; `install`/`update`/`check` fall back to these sources when an `owner/repo` is not on GitHub. Manifest format supports `exe_setup`/`msi`/`zip`/`exe_standalone` assets on any host.
- **Download reuse** — reuses an existing installer in the download folder when the size matches, and asks before re-downloading
- **Source validation** — `ohub source add` verifies the URL serves installable content before accepting it
- **Exact-match check** — `ohub check` links unmanaged apps only to an EXACT GitHub repo (or custom-source) match; `--candidates` offers a list when no exact match
- **Candidate asset selection** — when no standard installer exists, lists available assets and lets you pick one; the chosen pattern is saved for future updates
- **Archived / inactive warnings** — flagged during check, install, update, and add
- **Self-update (manual)** — `ohub self-update` upgrades ohub itself on demand (no longer runs automatically on every command)
- **State tracking** — records installed apps, versions, type, installer paths, and source in `state.json`
- **Prerelease support** — opt-in with `--prerelease` flag
- **Download-only mode** — fetch installers without executing them
- **System app detection** — scan Windows Registry for installed applications (with `ohub list --all` / `ohub check --all`)
- **GitHub token support** — higher rate limits with `ohub config set github_token`
- **Global + per-user config** — machine-wide settings apply to all users; each user's token and explicit overrides win
- **Single-source versioning** — `obtainhub/__init__.py` is the one version of truth; the installer/manifest files are synced automatically at build time

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
ohub install owner/repo --version 1.2.3     # or pick from recent releases

# Install / update from a custom (non-GitHub) source
ohub source add myapp https://github.com/owner/repo
ohub source add mymanifest https://example.com/manifest.json --type manifest
ohub install owner/repo                    # falls back to sources when not on GitHub

# Add a repo / archive / local folder for management
ohub add owner/repo
ohub add owner/repo --type zip            # repo ships archives: download, extract, track
ohub add "D:\My Folder" --type folder --name MyApp --repo owner/repo     # track folder app (name + repo required)

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
Install an application from GitHub Releases. The app can be given by exact id (`owner/repo`) or by display name.

```cmd
ohub install owner/repo                    # Latest stable release
ohub install owner/repo --tag v1.2.3       # Specific tag
ohub install owner/repo --version 1.2.3    # Install a specific (older) version
ohub install owner/repo --prerelease       # Include prereleases
ohub install owner/repo --download-only    # Download only, don't install
ohub install owner/repo --force            # Force reinstall
ohub install owner/repo --yes              # Auto-confirm prompts
```

Installing also registers the repo as a manifest source. If the app is already managed by ohub and up to date, install is skipped; if a newer version exists, it installs as an update. For portable/archive installs, ohub prompts before overwriting an existing folder (back up your config first).

### `ohub update [owner/repo]`
Update installed applications. The target can be an exact id or a display name. Folder-managed apps are skipped unless linked to a GitHub repo via `ohub add --repo`.

```cmd
ohub update                          # Update all apps
ohub update owner/repo               # Update specific app
ohub update qbittorrent                # Update by display name
ohub update --prerelease             # Include prereleases
ohub update --dry-run                # Show what would be updated
ohub update --reset                  # Forget saved choices so prompts re-appear
ohub update --yes                    # Auto-confirm prompts
```

When no standard installer is found in a release, `ohub update` lists the available candidate assets and installs/extracts the chosen one (the choice is remembered for future updates).

### `ohub check [owner/repo]`
Check for available updates without installing. The target can be an exact id or a display name.

```cmd
ohub check                           # Check managed apps
ohub check owner/repo                # Check specific app
ohub check --prerelease              # Include prereleases
ohub check --all                     # Also scan system-installed (unmanaged) apps
ohub check --candidates              # For unmanaged apps w/o exact match, offer candidate repos to link ([0] skips)
ohub check --timeout 30              # Per-repo search timeout (10-60s; default 20, retries 3)
ohub check --reset                   # Forget saved choices so prompts re-appear
ohub check --json                    # Output as JSON
```
Running `ohub check` with no app on an interactive terminal shows a numbered list of managed apps so you can check one or all. Apps that were manually uninstalled are detected and dropped from ohub automatically.

- Managed apps are always checked for updates.
- Unmanaged system apps are scanned only with `--all`; an unmanaged app is linked only to an **exact** GitHub repo name match, unless `--candidates` is given (then a list of candidate repos by name is offered).
- When an app has no standard installer, `ohub check` lists the available assets and (interactively) lets you pick one; the chosen asset is downloaded/extracted if an update is available, and the pattern is saved for future updates.
- Archived or inactive repositories print a warning.
- Every interactive choice (asset, repo link) is remembered in state. Use `--reset` (or `ohub remove`) to clear them and be re-prompted.

### `ohub add <owner/repo>`
Add a repository, archive, or local folder for management.

```cmd
ohub add owner/repo                       # Track a GitHub repo (exact match)
ohub add owner/repo --type zip             # Repo ships archives: download, extract, track
ohub add owner/repo --type zip --location D:\Apps\MyApp
ohub add "D:\MyFolder" --type folder --name MyApp --repo owner/MyApp   # Track a folder app (--name AND --repo required)
ohub add owner/repo --as-source            # Also register as a manifest source
```

- `--type github` (default): track a GitHub repository by exact `owner/repo`.
- `--type zip`: for repositories (including archived ones) that only ship ZIP/portable assets — the archive is downloaded, extracted to a folder, and tracked; updates re-use the saved asset pattern.
- `--type folder`: track a single local-folder app. **Both `--name` (the real application name) and `--repo owner/repo` are required.** The folder is NOT scanned for executables - the name and repo are the only source of truth, used to find updates. Drive roots such as `C:\` are refused. Quote the path if it contains spaces, e.g. `ohub add "D:\My Folder" --type folder --name MyApp --repo owner/MyApp`.
- During check/install/update/add, archived or inactive repositories print a warning.

### `ohub list`
List all installed applications.

```cmd
ohub list                            # Tabular output (ohub-managed apps)
ohub list --json                     # JSON output
ohub list --all                      # Include system-installed apps from Windows Registry
```

**Output format:**
```
Name                      Version          Type                  Source
--------------------------------------------------------------------------------
MyApp                     1.2.3            github                ohub
AnotherApp                2.0.0-beta       zip @ C:\Apps\Another  ohub
PortableTool             -               folder @ D:\Tools      ohub
```
The `Type` column shows `github`, `zip`, or `folder`, and (for zip/folder) the install location.

### `ohub uninstall <owner/repo>`
Uninstall an application from the system and remove it from ohub (state + any registered manifest source). For MSI/EXE installs the real uninstaller is invoked; for portable/zip apps the extracted folder is removed. Permission failures suggest running as administrator.

```cmd
ohub uninstall owner/repo              # Uninstall with confirmation
ohub uninstall owner/repo --yes        # Auto-confirm
ohub uninstall owner/repo --keep-data  # Keep downloaded installer files
```

### `ohub remove <id|name>`
Remove an app or folder from ohub management **without** uninstalling it (untrack only).

```cmd
ohub remove owner/repo                 # Remove from management (confirm)
ohub remove qbittorrent                 # Remove by display name
ohub remove folder:MyApp               # Remove a folder-managed app
ohub remove owner/repo --yes           # Auto-confirm
```

### `ohub source`
Manage custom sources (GitHub repos or manifest URLs). Sources let you install and update apps that are **not** on the default GitHub repo, including non-GitHub hosts.

```cmd
ohub source list                       # List configured sources
ohub source add my-source https://github.com/owner/repo
ohub source add my-repo-api https://api.github.com/repos/owner/repo/releases
ohub source add my-manifest https://example.com/manifest.json --type manifest
ohub source remove my-source
```

`ohub source add` validates the URL before accepting it (a GitHub source must expose releases/assets; a manifest source must be a JSON list). Once added, `ohub install <name>` and `ohub update` fall back to these sources when an `owner/repo` is not found on GitHub. Apps installed from a source are tracked by source name; `ohub update` checks them for newer versions, and `ohub uninstall`/`ohub remove` drops them from ohub (the shared source stays).

A manifest is a JSON list of apps:
```json
[
  {"name": "AppName", "version": "1.2.3", "url": "https://host/AppName-1.2.3-setup.exe", "installer_type": "exe_setup", "sha256": "", "size": 0}
]
```
`installer_type` is one of `exe_setup`, `msi`, `zip`, `exe_standalone` (auto-detected from the URL when omitted).

**How to add a custom source and use it**

```cmd
# 1) Add a GitHub repo as a source (validated: must expose releases/assets)
ohub source add myapp https://github.com/owner/repo

# 2) Or add a JSON manifest hosted anywhere (non-GitHub)
ohub source add mylist https://example.com/manifest.json --type manifest

# 3) List / remove sources
ohub source list
ohub source remove myapp

# 4) Install from a source: same command as GitHub; ohub falls back to sources
ohub install owner/repo            # resolves via the source when not on github.com

# 5) Update apps installed from sources
ohub update                        # checks each source for a newer version

# 6) Discover unmanaged system apps that live in a source
ohub check --all                  # matches registry apps to source entries
```

A source with no manifest (a plain GitHub repo URL) still works — ohub reads its releases directly. You do **not** need a separate manifest file; `--type github` sources use the repo's own releases. Use `--type manifest` only when you host your own JSON list on a non-GitHub host.

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
Update ObtainHub itself. **Self-update is manual** - ohub no longer checks for updates automatically on every command. Run this when you want to upgrade.

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

## Configuration

Config file: `%USERPROFILE%\.config\obtainhub\config.json`

```json
{
  "github_token": "",
  "self_update_enabled": true,
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
  "manifest_sources": []
}
```

### Global vs per-user settings
On a multi-user Windows machine, a config in `%ProgramData%\ObtainHub\config.json` applies to **all** users. Each user's own `%USERPROFILE%\.config\obtainhub\config.json` is overlaid on top, so a user can override any value — most importantly their own `github_token` (always per-user, never read from the global file). The global directory is created automatically on first run if missing. Set `OBTAINHUB_GLOBAL_CONFIG` to point at a custom shared-config path.

### Configuration items

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `github_token` | str | `""` | GitHub PAT; raises API limit 60→5000/hr. Always per-user. |
| `self_update_enabled` | bool | `true` | Allow `ohub self-update`. |
| `install_dir` | str | `...\Applications\ObtainHub` | Root for installed/portable apps. |
| `download_dir` | str | `...\Downloads\ObtainHub` | Where installers are downloaded (reuse prompt applies). |
| `config_dir` | str | `%USERPROFILE%\.config\obtainhub` | Config file location. |
| `state_dir` | str | `%USERPROFILE%\.local\share\obtainhub` | `state.json` location. |
| `update_interval_hours` | int | `24` | Reserved for scheduler cadence. |
| `auto_update` | bool | `true` | Reserved. |
| `allow_prerelease` | bool | `false` | Include prereleases in install/update. |
| `prefer_x64` | bool | `true` | Prefer x64 assets. |
| `allow_x86_fallback` | bool | `false` | Fall back to x86 if no x64 asset. |
| `auto_attempt_uninstall` | bool | `false` | Try to run the uninstaller on remove. |
| `manifest_sources` | list | `[]` | Custom sources (see below). Each: `{"name","url","enabled","type":"github"\|"manifest"}`. |
| `proxy` | str | `""` | HTTP(S) proxy URL. |
| `timeout_seconds` | int | `30` | Network timeout. |
| `check_timeout_seconds` | int | `20` | Per-app check timeout (10–60). |
| `check_timeout_retries` | int | `3` | Check retries (1–5). |
| `max_parallel_downloads` | int | `3` | Reserved. |
| `log_level` | str | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`. |
| `log_file` | str | `""` | Log destination (empty = stderr). |

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
[!] Error: GitHub API rate limit exceeded.
[!] Set the GITHUB_TOKEN environment variable (e.g. `$env:GITHUB_TOKEN='your_token'`) to increase limit from 60 to 5000 req/hr.
```

## State Tracking

Installed apps are tracked in `%APPDATA%\ObtainHub\state.json` (Windows) or `~/.obtainhub/state.json` (other platforms):

```json
{
  "installed": {
    "owner/repo": {
      "id": "owner/repo",
      "name": "repo",
      "version": "1.2.3",
      "installer_type": "msi",
      "installer_path": "C:\\Users\\<user>\\Downloads\\ObtainHub\\app.msi",
      "source_url": "https://github.com/owner/repo/releases/tag/v1.2.3",
      "tag": "v1.2.3",
      "app_type": "github",
      "install_location": "",
      "asset_pattern": "",
      "preferred_asset": "",
      "installed_at": 1700000000,
      "updated_at": 1700000000,
      "requires_manual_uninstall": false
    },
    "folder:qimgv": {
      "id": "folder:qimgv",
      "name": "qimgv",
      "version": "",
      "installer_type": "folder",
      "installer_path": "D:\\Tools\\qimgv",
      "source_url": "",
      "tag": "",
      "app_type": "folder",
      "install_location": "D:\\Tools\\qimgv",
      "asset_pattern": "",
      "preferred_asset": ""
    }
  },
  "check_history": {}
}
```

`app_type` is one of `github`, `zip`, or `folder`. `zip`/`folder` apps record `install_location`; `zip` apps also record `asset_pattern` (saved candidate pattern) and `preferred_asset`.

## System Application Detection

`ohub list --all` scans the Windows Registry for installed applications:

- `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall`
- `HKLM\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall`
- `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall`

This enables `ohub check` to match system-installed apps against GitHub repositories for update detection.

## Asset Selection Logic

When multiple assets exist in a release, ObtainHub selects the best match:

1. **Architecture priority**: x64 > ARM64 > x86 (ARM64/x86 only if explicitly allowed)
2. **Installer priority**: EXE_SETUP (Inno Setup) > MSI > ZIP_INSTALLER
3. **Portable archives**: a bare `.zip`/`.exe` standalone asset is downloaded and, for `zip` apps, extracted to a folder and tracked (not executed)
4. **Exclusions**: Checksums (`.sha256`, `.asc`), signatures, non-Windows packages (`.deb`, `.rpm`, `.dmg`, `.tar.gz`), source archives
5. **Candidate selection**: if no strict installer is found, `ohub install`/`update`/`check` list the available assets and let you pick one; the choice is saved as an asset pattern for future updates

## Candidate Assets & Patterns

For repositories that ship only portable archives (common with archived projects), ObtainHub records the chosen asset's pattern (e.g. `*x64*.zip`). On the next `update`, it re-matches the newest release against that pattern automatically — so you only pick once.

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

Automated builds on tag push (e.g., `git tag v0.1.0.14 && git push origin v0.1.0.14`):

- Builds on `windows-latest`
- Runs `tools/sync_versions.py` so the Inno Setup, WiX MSI, and PyPI metadata all carry the version from `obtainhub/__init__.py` (no more desynced installers)
- Creates `ohub.exe`, `ObtainHub-Setup.exe`, and `ObtainHub.msi`
- Syncs `CHANGELOG.md` into the release notes automatically

Workflows: `.github/workflows/release.yml`, `.github/workflows/sync-release-notes.yml`

**Note:** Release tags with `beta` or `alpha` are published as pre-releases. Assets are generated for each tag pushed.

## Requirements

- Windows 10/11 x64
- Python 3.11+ (for development)
- GitHub API access (token optional, but recommended for higher rate limits)

## License

MIT License — see LICENSE file.

## Author

Davoud Teimouri — https://github.com/DavoudTeimouri