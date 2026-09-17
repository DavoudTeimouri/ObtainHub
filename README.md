# ObtainHub

A cross-platform, open-source package manager for Windows that simplifies installing and updating applications from GitHub releases.

## Features

- **GitHub Integration**: Install and update apps directly from GitHub releases.
- **Cross-Platform**: Primarily Windows x64, with support for other architectures via configuration.
- **Multiple Installer Types**: Supports MSI, EXE (Inno Setup, NSIS, Wise, InstallShield, generic silent), ZIP, and portable folder apps.
- **Scheduled Checks**: Automatically check for updates on a schedule.
- **Self‑Update**: ObtainHub can update itself.
- **Shims**: Create portable shims (`ohub shim <app>`) to run apps from anywhere.
- **TUI Dashboard**: Interactive terminal UI (`ohub tui`) to browse, install, update, and remove apps.
- **Hooks**: Run custom scripts before/after install/uninstall (`pre_install`, `post_install`, `pre_uninstall`, `post_uninstall`).
- **Groups**: Organize apps into groups for bulk operations.
- **Architecture Preferences**: Prefer x64, allow x86 fallback, or force ARM64.
- **Plugin System**: Extend functionality with plugins (see `obtainhub/plugins`).
- **Notifier Plugin**: Desktop notifications on update (requires `plyer`).
- **State Export/Import**: Backup and restore full app state via `ohub state export` and `ohub state import`.
- **Package Manager Fallback**: When GitHub release lacks a suitable asset, fall back to Winget, Scoop, or Chocolatey.
- **Asset Caching**: Reduce GitHub API calls with ETag/Last-Modified caching.
- **Parallel Checks**: Speed up `--all` checks with concurrent processing.
- **Incremental State**: Efficient state file updates.
- **Structured Logging**: Optional JSON log output.

## Installation

Download the latest release from the [Releases page](https://github.com/DavoudTeimouri/ObtainHub/releases) and run the installer, or use the ZIP portable version.

### Quick Start (Windows)

```powershell
# Install ObtainHub (run as Administrator)
ohub install owner/repo
```

### First‑time Setup

After installation, you may want to:

1. Set your GitHub token for higher rate limits:
   ```powershell
   ohub config set github_token <your_personal_token>
   ```
2. Enable scheduled checks:
   ```powershell
   ohub config set schedule_enabled true
   ohub config set schedule_interval_hours 12
   ```
3. Try the TUI:
   ```powershell
   ohub tui
   ```

## Usage

### Core Commands

| Command | Description |
|---------|-------------|
| `ohub add <repo> [options]` | Add a GitHub repo for management. |
| `ohub install <app> [options]` | Install or update an app. |
| `ohub check [options]` | Check for updates without installing. |
| `ohub update <app> [options]` | Update specific app(s). |
| `ohub remove <app>` | Remove app from management (does not uninstall). |
| `ohub shim <app>` | Create a shim executable for portable apps. |
| `ohub tui` | Launch the terminal user interface. |
| `ohub config <action>` | View or modify configuration. |
| `ohub schedule <action>` | Enable/disable/view scheduled checks. |

### Advanced Features

#### Hooks

Define scripts in your config or via manifest sources:

```json
{
  "hooks": {
    "pre_install": "echo \"Installing $APP_ID\"",
    "post_install": "echo \"Done installing $APP_ID\"",
    "pre_uninstall": "echo \"Preparing to uninstall $APP_ID\"",
    "post_uninstall": "echo \"Uninstalled $APP_ID\""
  }
}
```

#### Groups

```powershell
ohub config set groups.devtools=\"git-for-windows/vscode,PowerShell/PowerShell\"
ohub install devtools  # installs all apps in the devtools group
```

#### Plugin System

Place Python plugins in `obtainhub/plugins/`. They must subclass `obtainhub.plugins.base.Plugin` and implement the lifecycle methods.

Example plugin (`obtainhub/plugins/example.py`):

```python
from obtainhub.plugins.base import Plugin

class ExamplePlugin(Plugin):
    def on_load(self):
        print(f"[Plugin] {self.name} loaded")

    def on_update(self, app_id: str, current_version: str, latest_version: str):
        print(f"[Plugin] {self.name}: {app_id} updated {current_version} -> {latest_version}")

    # ... other methods
```

#### Notifier Plugin

Show desktop notifications when updates are available. Requires `plyer` (`pip install plyer`).

Enable via config:

```powershell
ohub config set notifier_enabled true
# Optional: custom command
ohub config set notifier_cmd "powershell -Command \"[reflection.assembly]::LoadWithPartialName('System.Windows.Forms');[System.Windows.Forms.MessageBox]::Show('Update available for $APP_ID')\""
```

#### State Export/Import

Backup or migrate your managed apps list:

```powershell
ohub state export C:\backup\ohub_state.json
ohub state import C:\backup\ohub_state.json
```

Use `ohub state import --dry-run` to preview changes.

#### Package Manager Fallback

When a GitHub release has no suitable installer, ObtainHub can try Winget, Scoop, or Chocolatey:

```powershell
ohub config set enable_winget true
ohub config set enable_scoop true
ohub config set enable_choco true
ohub config set prefer_native false  # try package managers first
```

#### Architecture Preferences

```powershell
ohub config set prefer_x64 false
ohub config set allow_x86_fallback true
ohub install owner/repo --arch x86
```

#### Self‑Update

```powershell
ohub self-update
```

#### Dry‑Run

```powershell
ohub install owner/repo --dry-run
```

#### Release Notes

```powershell
ohub update owner/repo --notes
```

## Configuration

Configuration is stored in `%USERPROFILE%\.config\obtainhub\config.json`. All options can be viewed with:

```powershell
ohub config show
```

### Key Settings

- `github_token`: Personal access token for higher API rate limits.
- `self_update_enabled`: Toggle self‑update capability.
- `install_dir`: Where apps are installed (default: `%USERPROFILE%\Applications\ObtainHub`).
- `download_dir`: Where installers are downloaded (default: `%USERPROFILE%\Downloads\ObtainHub`).
- `schedule_enabled`: Enable automatic background checks.
- `schedule_interval_hours`: How often to run checks (in hours).
- `log_level`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
- `log_file`: Path to a log file (optional).
- `groups`: Define app groups for bulk operations.
- `manifest_sources`: Add custom manifest sources (GitHub, Winget, Scoop, Chocolatey).
- `notifier_enabled`: Enable desktop notifications on update.
- `notifier_cmd`: Custom command to run on notification (optional).
- `prefer_x64`: Prefer x64 assets when available.
- `allow_x86_fallback`: Allow x86 if x64 not found.
- `allow_arm64`: Allow ARM64 assets.
- `enable_winget`: Enable Winget as fallback source.
- `enable_scoop`: Enable Scoop as fallback source.
- `enable_choco`: Enable Chocolatey as fallback source.
- `prefer_native`: Try GitHub assets first before package managers.

## Troubleshooting

| Symptom | Solution |
|---------|----------|
| **"App not detected after installation"** | Some installers spawn child processes and exit early. ObtainHub verifies installation by checking the Windows Registry and install location. If verification fails, run `ohub check` to see if the app installed despite the error. |
| **Rate limit errors (403)** | Set a GitHub token via `ohub config set github_token <token>` to increase limits from 60 to 5000 requests per hour. |
| **"No suitable asset found"** | Ensure the release contains an asset matching your architecture preferences (`--arch`) and installer type. Use `--yes` to auto‑pick the first compatible asset, or interactively choose. |
| **Shim not working** | Remember to add the shim directory (`%USERPROFILE%\bin\obtainhub` by default) to your `PATH` environment variable. |
| **TUI fails to start** | The TUI requires the `textual` and `rich` Python packages. They are bundled in the installer but may be missing in development environments. Install with `pip install textual rich`. |
| **Plugin not loading** | Check the console for `[Plugin] Failed to load ...` messages. Ensure the plugin class inherits from `obtainhub.plugins.base.Plugin` and implements all abstract methods. |
| **Notifier not working** | Ensure `plyer` is installed (`pip install plyer`) and `notifier_enabled` is true. |

## Building from Source

### Prerequisites

- Python 3.9+
- GitHub account (for token)
- (Optional) `pyinstaller` for building executables

### Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/DavoudTeimouri/ObtainHub.git
   cd ObtainHub
   ```
2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -e .
   ```
4. Run:
   ```bash
   python -m obtainhub
   ```

### Creating a Release

1. Update the version in `obtainhub/__init__.py` and `obtainhub/main.py`.
2. Add a changelog entry under `## [X.Y.Z] - YYYY-MM-DD` in `CHANGELOG.md`.
3. Commit and tag:
   ```bash
   git add .
   git commit -m "Release vX.Y.Z"
   git tag vX.Y.Z
   git push origin main --tags
   ```
4. GitHub Actions will build the distributables (MSI, EXE, ZIP) and publish the release.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.