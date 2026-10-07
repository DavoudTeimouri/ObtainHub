# ObtainHub

GitHub-based package updater & manager for Windows x64. Install, update, and track apps from GitHub or custom manifest sources (non-GitHub). Handles MSI/EXE/portable-ZIP installs, folder-managed apps, older-version installs, and per-machine + per-user config.

## Installation

### Windows (MSI)
Download the latest `.msi` from [Releases](https://github.com/DavoudTeimouri/ObtainHub/releases).

### Windows (NSIS Installer)
Download `ObtainHub-Setup.exe` from [Releases](https://github.com/DavoudTeimouri/ObtainHub/releases).

### Portable Binary
Download `ohub.exe` from [Releases](https://github.com/DavoudTeimouri/ObtainHub/releases) and place in your PATH.

### From Source
```bash
cargo build --release
# Binary at target/release/ohub.exe
```

## Usage

```
ohub <COMMAND>
```

### Commands
| Command | Description |
|---------|-------------|
| `search` | Search GitHub repositories |
| `install` | Install a repository (supports `--file` for local archives, `--url` for direct downloads) |
| `check` | Check for updates to installed repositories |
| `list` | List installed repositories |
| `update` | Update installed repositories |
| `uninstall` | Uninstall a repository |
| `remove` | Remove from management (keep files) |
| `add` | Add to management without installing |
| `source` | Manage custom manifest sources |
| `schedule` | Manage scheduled background checks |
| `group` | Manage app groups/profiles |
| `shim` | Manage portable shims |
| `state` | Export/import state |
| `apps` | Backup/restore application folders |
| `cleanup` | Clean up leftover files |
| `tui` | Launch Textual User Interface |
| `config` | Manage configuration |
| `backup` | Backup installed repositories and config |
| `restore` | Restore from backup |
| `self-update` | Update ohub itself |
| `completion` | Generate shell completions |
| `doctor` | Diagnose installation issues |
| `self-uninstall` | Completely remove ohub |

### Examples
```bash
# Search for repositories
ohub search ripgrep --min-stars 100

# Install from GitHub
ohub install BurntSushi/ripgrep

# Install from local archive
ohub install --file ./myapp.zip

# Install from direct URL
ohub install --url https://example.com/app.tar.gz

# Check for updates
ohub check

# Update all
ohub update

# Launch TUI
ohub tui
```

## Configuration

Config file: `%APPDATA%\ObtainHub\config.json` (Windows) or `~/.config/obtainhub/config.json` (Unix)

```bash
ohub config list          # Show all config
ohub config get key       # Get value
ohub config set key value # Set value
```

## License

MIT
