# ObtainHub

A cross-platform, open-source CLI tool for managing and updating GitHub-based applications on Windows with support for EXE, MSI, and ZIP installers, self-update mechanism, and custom manifest sources.

## Features

- **GitHub Release Management**: Search, install, update, and manage applications from GitHub releases
- **Multiple Installer Types**: MSI, EXE, NSIS, InstallShield, ZIP, and portable apps
- **Scheduled Checks**: Automated background update checks with configurable schedule
- **Self-Update**: ObtainHub can update itself from GitHub releases (detached installer)
- **Self-Protection**: Prevents accidental removal of ObtainHub itself
- **Self-Uninstaller**: Complete removal with optional backup/restore to zip
- **Cross-Platform Architecture**: Supports x64, ARM64, and x86 architectures
- **Terminal UI (TUI)**: Interactive terminal interface for managing apps
- **Hooks System**: Custom scripts before/after install/uninstall (`pre_install`, `post_install`, `pre_uninstall`, `post_uninstall`)
- **State Export/Import**: Backup and restore ObtainHub state anywhere
- **Plugin System**: Extensible plugin architecture (`obtainhub/plugins`)
- **Desktop Notifications**: Optional notifications via `plyer`
- **Config Backup/Restore**: Backup and restore config/state to zip files
- **Apps Backup/Restore**: Backup and restore application folders
- **Cleanup Command**: Clean up orphaned tasks, incomplete downloads, and old cache
- **Package Manager Fallback**: Winget, Scoop, Chocolatey via `ohub install --fallback`
- **GitHub API Caching**: ETag/Last-Modified caching to reduce API calls
- **Batch Operations**: `--all` flag for bulk operations
- **Automatic Updates**: Scheduled background checks and updates
- **Backup Rotation**: Configurable retention for all backup operations

## Quick Start

### Install via GitHub Releases (recommended)

```powershell
# Download and run the installer from https://github.com/DavoudTeimouri/ObtainHub/releases
# Or install via package manager:
ohub install owner/repo
```

### TUI:

```powershell
ohub tui
```

### GitHub Search and Install:

```powershell
ohub search "vscode" --limit 5
ohub install Microsoft/vscode
ohub update Microsoft/vscode
ohub list
ohub uninstall Microsoft/vscode
```

### Config Management:

```powershell
ohub config show
ohub config --json
ohub config get download_dir
ohub config set backup_retention_count 5
ohub config path
ohub config move "C:\new\config\dir"
ohub config repair
ohub config auth
ohub config auth --token-source env
ohub config backup backup.zip
ohub config backup backup.zip --include-downloads
ohub config restore backup.zip
ohub config restore backup.zip --target-config "C:\new\config" --no-token
```

### GitHub Token Storage:

```powershell
ohub config auth
```

Reports which credential store holds the GitHub token and whether it is protected at rest. Use
`--token-source` to inspect a specific store: `auto` (default), `keyring`, `env`, `file`, or
`plaintext-keyring`.

```powershell
ohub config set github_token ghp_yourtoken
```

The token is written to the OS credential store (Windows Credential Manager, macOS Keychain), not to
`config.json`. On a machine with no credential store, ohub refuses to store the token in plaintext
and tells you to export `GITHUB_TOKEN` instead. `ohub config show`, `ohub config get github_token`
and `ohub config set github_token` never print the secret, and backup archives omit it.

### Apps Backup/Restore:

```powershell
ohub apps backup apps_backup.zip
ohub apps backup apps_backup.zip --app owner/repo1,owner/repo2
ohub apps restore apps_backup.zip
ohub apps restore apps_backup.zip --target-dir "C:\new\apps" --dry-run
ohub apps restore apps_backup.zip --app owner/repo
```

### Cleanup:

```powershell
ohub cleanup all
ohub cleanup tasks      # Remove orphaned scheduled tasks
ohub cleanup downloads  # Remove incomplete downloads (.part files)
ohub cleanup cache      # Clean old manifest cache entries (30+ days)
```

### Groups:

```powershell
ohub group add devtools "git-for-windows/git,vscode/vscode"
ohub group list
ohub group install devtools
ohub group update devtools
```

### Plugin Development:

Place plugins in `obtainhub/plugins/`. Each plugin must implement `obtainhub.plugins.base.Plugin` and its methods.

Example (`obtainhub/plugins/example.py`):

```python
from obtainhub.plugins.base import Plugin

class ExamplePlugin(Plugin):
    def on_load(self):
        print(f"Plugin {self.name} loaded")

    def on_install(self, app_id: str, latest_version: str):
        print(f"Installing {app_id}: {latest_version}")

    def on_update(self, app_id: str, latest_version: str):
        print(f"Updating {app_id}: {latest_version}")

    def on_uninstall(self, app_id: str):
        print(f"Uninstalling {app_id}")
```

### State Export/Import:

```powershell
ohub state export C:\backup\ohub_state.json
ohub state import C:\backup\ohub_state.json
```

### Schedule:

```powershell
ohub schedule enable
ohub schedule disable
ohub schedule status
ohub schedule run --prerelease
```

### Architecture Preferences:

```powershell
ohub config set arch_preference "x64"
# or per-app:
ohub install owner/repo --arch x64
```

### Package Manager Fallback:

```powershell
ohub install owner/repo --fallback
```

### Self-Update & Self-Protection:

```powershell
ohub self-update --prerelease --force
ohub check
ohub list
ohub update
# ohub uninstall DavoudTeimouri/ObtainHub  # BLOCKED - self-protection
# ohub remove DavoudTeimouri/ObtainHub     # BLOCKED - self-protection
```

### Self-Uninstaller:

```powershell
ohub self-uninstall --backup backup.zip
ohub self-uninstall --backup backup.zip --include-downloads --force
ohub self-uninstall --restore backup.zip
ohub self-uninstall --restore backup.zip --target-config "C:\config" --no-token
```

### Caching:

Reduce GitHub API calls with ETag and Last-Modified headers. Cache stored in `%USERPROFILE%\.cache\obhub\`. No auth required.

### Parallel Checks:

Speed up batch operations with `--all` and `--workers` (default: CPU count).

```powershell
ohub check --all --workers 8
```

### State Management:

State tracks installed apps, versions, and metadata. Read-only access, no encryption required; optimization only.

### Logging:

Enable JSON-formatted logging for CI/CD and log aggregation tools.

```powershell
ohub config set log_file "C:\logs\obtainhub.json"
ohub config set log_format JSON
```

Setting `log_format` to `JSON` outputs structured logs; human-readable unless `JSON` specified. `log_file` and `log_format` work together (both set).

### Dry Run:

Preview operations without executing.

```powershell
ohub install owner/repo --dry-run
ohub update owner/repo --dry-run
```

### Release Notes:

```powershell
ohub install owner/repo --notes
```

## Configuration

Config file: `%USERPROFILE%\.config\obtainhub\config.json`. Key settings:

- `github_token`: GitHub API token (optional; stored in the OS credential store, never in this file)
- `install_dir`: Default install directory (`%USERPROFILE%\Applications\ObtainHub`)
- `download_dir`: Download location (`%USERPROFILE%\Downloads\ObtainHub`)
- `bin_dir`: Shim directory (`%USERPROFILE%\bin\obtainhub`)
- `log_level`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`, or `JSON` logging
- `log_file`: Path to log file (optional)
- `log_format`: `text` or `JSON`
- `fallback_managers`: List of fallback package managers (GitHub, Chocolatey)
- `check_interval_hours`: Background check interval
- `prefer_x64`: Prefer x64 assets when available
- `allow_prerelease`: Allow prereleases in updates
- `prefer_native`: Prefer native GitHub releases over package managers
- `backup_retention_count`: Number of backups to keep (1-10, default: 2)
- `schedule_enabled`: Enable scheduled checks
- `schedule_interval_hours`: Schedule interval in hours
- `schedule_notify_on_update`: Notify on update available
- `schedule_run_on_startup`: Run scheduled check on startup

## Commands Reference

| Command | Description |
|---------|-------------|
| `ohub search <query>` | Search GitHub for apps |
| `ohub install <owner/repo>` | Install an app |
| `ohub update [app]` | Update installed apps |
| `ohub check [app]` | Check for updates |
| `ohub list` | List installed apps |
| `ohub uninstall <app>` | Uninstall an app |
| `ohub remove <app>` | Remove app from tracking |
| `ohub config [show|get|set|edit|auth|path|move|repair|backup|restore]` | Manage configuration |
| `ohub apps [backup|restore]` | Backup/restore application folders |
| `ohub cleanup [all|tasks|downloads|cache]` | Clean up leftover files and tasks |
| `ohub self-update` | Update ohub itself |
| `ohub self-uninstall` | Completely remove ohub with optional backup |
| `ohub state [export|import]` | Export/import state |
| `ohub schedule [enable|disable|status|run]` | Manage scheduled checks |
| `ohub group [list|add|remove|delete|install|update|check]` | Manage app groups |
| `ohub shim [list|add|remove|path]` | Manage portable shims |
| `ohub reset` | Reset ohub state and configuration |
| `ohub tui` | Launch terminal UI dashboard |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| App not found | Verify repo name and that ObtainHub has access |
| Rate limited (403) | Set `github_token` in config or wait for rate limit reset (60 req/hr unauth, 5000 auth) |
| Architecture mismatch | Use `--arch x64|arm64|x86|auto` |
| TUI not rendering | Ensure terminal supports ANSI and `textual` is installed |
| Shim not in PATH | Add `%USERPROFILE%\bin\obtainhub` to PATH |
| Config corrupted | Run `ohub config repair` |
| Self-update fails | Run `ohub self-update --force` |
| Cannot uninstall ohub | Use `ohub self-uninstall` instead |

## Install

Download one of the two assets from the
[releases page](https://github.com/DavoudTeimouri/ObtainHub/releases):

| Asset | Notes |
| --- | --- |
| `ObtainHub-Setup.exe` | Inno Setup installer. |
| `ObtainHub.msi` | Windows Installer package, useful for scripted/GPO deployment. |

Both are machine-wide (`perMachine`) and install `ohub.exe` to `C:\Program Files\ObtainHub`, adding
that folder to the user `PATH`. **Install one, not both** — they write to the same folder, and each
now detects the other and refuses to run if it is already installed. Uninstall whichever one you used
before switching.

No Start-menu or desktop shortcut is created — `ohub` is a console tool, so launch it from a
terminal. Open a new terminal after installing so the updated `PATH` is picked up.

If you cannot run an elevated installer, invoke the binary by full path instead:

```powershell
& "C:\Program Files\ObtainHub\ohub.exe" --version
```

## Run and use

`ohub` with no arguments prints its help and exits, so always pass a command:

```powershell
ohub --version          # installed version
ohub --help             # full command list
ohub tui                # terminal UI
```

### Find and install apps

```powershell
ohub search vscode --limit 10              # search GitHub, newest/upvoted first
ohub search vscode --min-stars 500         # raise the quality floor
ohub search vscode --active-only           # skip archived repositories
ohub install DavoudTeimouri/ObtainHub      # install owner/repo
```

`install` accepts a `owner/repo` reference or a local folder or `.zip` archive:

```powershell
ohub install .\downloads\myapp.zip         # extract and install from a zip
ohub check                                # report installed apps and their state
ohub list                                 # installed inventory
ohub uninstall owner/repo                 # remove, keeping data
ohub uninstall owner/repo --keep-data=false
```

### Global flags

| Flag | Effect |
| --- | --- |
| `--json` | Machine-readable output, for scripting. |
| `--quiet` | Suppress non-error output. |
| `--dry-run` | Show what would happen; change nothing. |
| `--force` | Skip confirmation prompts. Never use unattended. |
| `-v, --verbose` | Verbose logging. |

Put `--dry-run` first in front of any command you have not run before.

### Keep it updated

```powershell
ohub self-update                           # replace the installed binary
ohub self-uninstall                        # remove ObtainHub itself
```

`self-update` verifies the downloaded asset before replacing anything; a failed or partial
verification leaves your current binary untouched.

### Backup and restore

```powershell
ohub config backup backup.zip                       # config + state
ohub config backup backup.zip --include-downloads   # add the download folder
ohub config restore backup.zip                      # restore settings
ohub config restore backup.zip --no-token           # do not restore the token to keyring
```

A backup never copies the keyring, so your GitHub token is not in the archive. `--no-token` controls
the *restore* direction: by default a restore puts the backup's token back into the keyring. Tokens
are redacted from logs.

### Manage sources and scheduled tasks

```powershell
ohub source add https://example.com/apps.json      # a local manifest
ohub source list
ohub schedule list
ohub cleanup                                        # remove stale downloads and caches
ohub reset                                          # clear local state, keep config
```

Remote manifests are treated as untrusted data: only hooks defined in your own local source
configuration run. Manifests cannot execute commands on your behalf.

## Development

```powershell
git clone https://github.com/DavoudTeimouri/ObtainHub.git
cd ObtainHub
python -m pip install -e .[dev]
python -m pytest tests/
```

Version managed in `obtainhub/__init__.py` and `obtainhub/main.py`.

Release process:
1. Update version in `obtainhub/__init__.py` and `obtainhub/main.py`
2. Update `CHANGELOG.md` with `YYYY-MM-DD` date
3. Commit and tag:
   ```bash
   git commit -m "Release vX.Y.Z"
   git tag vX.Y.Z
   git push origin main --tags
   ```
4. GitHub Actions builds and publishes release (MSI, EXE)

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT © [ObtainHub Contributors](LICENSE)
