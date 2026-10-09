# ObtainHub

GitHub-based package updater & manager for Windows x64. Install, update, and track apps from GitHub or custom manifest sources (non-GitHub). Handles MSI/EXE/portable-ZIP installs, folder-managed apps, older-version installs, and per-machine + per-user config.

## Installation

### Windows (MSI)
Download the latest `.msi` from [Releases](https://github.com/DavoudTeimouri/ObtainHub/releases).

### Windows (NSIS Installer)
Download `ObtainHub-Setup.exe` from [Releases](https://github.com/DavoudTeimouri/ObtainHub/releases).

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
ohub search rust --language Rust --sort-stars --limit 10

# Install from GitHub
ohub install BurntSushi/ripgrep
ohub install BurntSushi/ripgrep --dry-run

# Install from local archive
ohub install --file ./myapp.zip

# Install from direct URL
ohub install --url https://example.com/app.tar.gz

# Check for updates
ohub check
ohub check --all                  # every installed Windows program, skips ohub itself
ohub check --outdated-only

# Update
ohub update                        # all installed repos
ohub update BurntSushi/ripgrep     # one repo
ohub update --dry-run              # show what would change

# Manage installed repos
ohub list
ohub list --format json
ohub uninstall BurntSushi/ripgrep --yes
ohub uninstall BurntSushi/ripgrep --purge --yes   # also drop metadata + group entries
ohub remove BurntSushi/ripgrep --yes             # untrack, keep files

# Groups
ohub group create dev
ohub group add dev BurntSushi/ripgrep

# Shell completions
ohub completion fish > ~/.config/fish/completions/ohub.fish
ohub completion powershell | Out-String | Invoke-Expression

# Diagnostics
ohub doctor
ohub info BurntSushi/ripgrep

# TUI
ohub tui
```

## Configuration

Config file: `%APPDATA%\ObtainHub\config.toml` (Windows) or `$XDG_CONFIG_HOME/ObtainHub/config.toml` (Unix)
State file: `%APPDATA%\ObtainHub\state.json`

```bash
ohub config list          # Show all config
ohub config get key       # Get value
ohub config set key value # Set value
```

Zero-valued `parallel_downloads`, `timeout_seconds`, and
`update_check_interval_hours` are reset to their defaults on load — a hand-edited
config can never set them to 0.

## License

MIT
