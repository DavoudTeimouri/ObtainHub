# ObtainHub

A cross-platform, open-source CLI tool for managing and updating GitHub-based applications on Windows with support for EXE, MSI, and ZIP installers, self-update mechanism, and custom manifest sources.

## Features

- **GitHub Release Management**: Search, install, update, and manage applications from GitHub releases
- **Multiple Installer Types**: MSI, EXE, NSIS, InstallShield, ZIP, and portable apps
- **Scheduled Checks**: Automated background update checks with configurable schedule
- **Self-Update**: ObtainHub can update itself from GitHub releases
- **Cross-Platform Architecture**: Supports x64, ARM64, and x86 architectures
- **Terminal UI (TUI)**: Interactive terminal interface for managing apps
- **Hooks System**: Custom scripts before/after install/uninstall (`pre_install`, `post_install`, `pre_uninstall`, `post_uninstall`)
- **State Export/Import**: Backup and restore ObtainHub state anywhere
- **Plugin System**: Extensible plugin architecture (`obtainhub/plugins`)
- **Desktop Notifications**: Optional notifications via `plyer`
- **State Import/Export**: `ohub state export` and `ohub state import`
- **Package Manager Fallback**: Winget, Scoop, Chocolatey via `ohub install --fallback`
- **GitHub API Caching**: ETag/Last-Modified caching to reduce API calls
- **Batch Operations**: `--all` flag for bulk operations
- **Automatic Updates**: Scheduled background checks and updates

## Quick Start

### Install via GitHub Releases (recommended)

```powershell
# Download and run the installer
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
ohub config path
ohub config move "C:\new\config\dir"
ohub config repair
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

- `github_token`: GitHub API token (optional, stored in system keyring)
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

## Troubleshooting

| Issue | Solution |
|-------|----------|
| App not found | Verify repo name and that ObtainHub has access |
| Rate limited (403) | Set `github_token` in config or wait for rate limit reset (60 req/hr unauth, 5000 auth) |
| Architecture mismatch | Use `--arch x64|arm64|x86|auto` |
| TUI not rendering | Ensure terminal supports ANSI and `textual` is installed |
| Shim not in PATH | Add `%USERPROFILE%\bin\obtainhub` to PATH |

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
4. GitHub Actions builds and publishes release (MSI, EXE, ZIP)

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT © [ObtainHub Contributors](LICENSE)
