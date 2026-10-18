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
| `search` | Search GitHub repositories; select results to add or install |
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
ohub search cli --page 1 --per-page 30

# Search results offer to add/install
# After the table, you can select repos to add to managed list,
# then choose whether to install them right away.

# Install from GitHub
ohub install BurntSushi/ripgrep
ohub install BurntSushi/ripgrep --dry-run
ohub install BurntSushi/ripgrep --version 14.1.0 --arch x64
ohub install unknown/repo   # falls back to GitHub search candidates if exact repo not found

# Install from local archive
ohub install --file ./myapp.zip

# Install from direct URL
ohub install --url https://example.com/app.tar.gz

# Check for updates
ohub check                                # managed repositories only
ohub check --all                          # scan ALL installed Windows programs; select unmanaged ones to add; offers candidate GitHub repos for each; then checks for updates
ohub check --candidates                   # unmanaged apps with candidate repos; select to manage
ohub check --outdated-only
ohub check --force                        # bypass recent check cache

# Version comparison strips v/V prefix (v3.0.32 == 3.0.32)

# Update
ohub update                               # all managed repositories
ohub update BurntSushi/ripgrep            # one repo
ohub update --dry-run                     # show what would change
ohub update --force                       # reinstall even if current

# Rollback
ohub rollback BurntSushi/ripgrep   # revert to previous version
ohub rollback BurntSushi/ripgrep --yes  # skip confirmation

# Self-update
ohub self-update                 # check + install latest release
ohub self-update --prerelease    # include prerelease releases
ohub self-update --skip-signature   # bypass signature check
ohub self-update --check-only    # just report available version

# Manage installed repos
ohub list
ohub list --format json
ohub uninstall BurntSushi/ripgrep --yes
ohub uninstall BurntSushi/ripgrep --purge --yes   # also drop metadata + group entries
ohub remove BurntSushi/ripgrep --yes             # untrack, keep files

# Groups
ohub group create dev
ohub group add dev BurntSushi/ripgrep
ohub group list
ohub group install dev           # install all apps in group

# Shell completions
ohub completion fish > ~/.config/fish/completions/ohub.fish
ohub completion powershell | Out-String | Invoke-Expression
ohub completion bash > /usr/local/etc/bash_completion.d/ohub

# Configuration
ohub config list                 # Show all config
ohub config get install_dir      # Get install directory
ohub config set download_bandwidth_limit 1048576  # Limit to 1 MB/s

# Diagnostics
ohub doctor
ohub info BurntSushi/ripgrep

# TUI
ohub tui                         # Press '?' for help, 'j/k' to navigate
```

## Configuration

Config file: `%APPDATA%\ObtainHub\config.toml` (Windows) or `$XDG_CONFIG_HOME/ObtainHub/config.toml` (Unix)
State file: `%APPDATA%\ObtainHub\state.json`

```bash
ohub config list          # Show all config
ohub config get key       # Get value
ohub config set key value # Set value
```

### Config parameters

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `github_token` | `string` | *(none)* | GitHub personal access token for authenticated API requests |
| `install_dir` | `path` | `%APPDATA%\ObtainHub\repos` | Where installed repositories live |
| `download_dir` | `path` | `%APPDATA%\ObtainHub\downloads` | Where downloads are cached |
| `shim_dir` | `path` | `%USERPROFILE%\bin\obtainhub` | Where portable shims are created |
| `parallel_downloads` | `u32` | 4 | Max concurrent downloads (1–32) |
| `timeout_seconds` | `u64` | 30 | GitHub API request timeout in seconds (1–3600) |
| `update_check_interval_hours` | `u64` | 24 | Scheduled background check interval in hours (1–8760) |
| `download_bandwidth_limit` | `u64?` | *(none)* | Bandwidth limit in bytes/sec; unset = unlimited |
| `verify_checksums` | `bool` | true | Verify SHA256 checksums on install |
| `auto_cleanup` | `bool` | true | Auto-cleanup temp files after install/update |
| `proxy` | `string?` | *(none)* | HTTP proxy URL for outbound requests |
| `http_retries` | `u32` | 3 | Number of HTTP retry attempts on failure |
| `http_retry_delay_ms` | `u64` | 1000 | Initial retry delay in milliseconds |
| `http_retry_backoff` | `f64` | 2.0 | Exponential backoff multiplier for retries |

#### Schedule config (nested under `[schedule]`)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | `bool` | false | Run scheduled background checks |
| `interval_hours` | `u64` | 24 | Interval between scheduled checks |
| `notify_on_update` | `bool` | true | Notify when an update is found |
| `run_on_startup` | `bool` | false | Run a check on startup |

Zero-valued `parallel_downloads`, `timeout_seconds`, `update_check_interval_hours`, and `schedule.interval_hours` are reset to their defaults on load — a hand-edited config can never set them to 0.

`github_token` is stored in plain text in `config.toml`. `ohub config get github_token` returns `[stored]`, never the value, to avoid leaking it into shell history or logs.

## Self-update assets

ObtainHub ships MSI + NSIS EXE installers only (no standalone `ohub.exe` asset).
`ohub self-update` will:
1. Download the matching release asset (`.exe`/`.msi` installer, or `.zip` portable).
2. Verify checksum against the release's `SHA256SUMS`.
3. Verify Ed25519 signature if present (use `--skip-signature` to bypass).
4. Run MSI silently (`msiexec /i /qn /norestart`) or EXE silently (`/S`), or extract `.zip` and replace the running binary.

## Release process

Each release tag (`vX.Y.Z-rc1`) must have its own `## [vX.Y.Z]` section in `CHANGELOG.md`. Only `ObtainHub.msi`, `ObtainHub-Setup.exe`, and `SHA256SUMS` are published as assets. See `CONTRIBUTING.md` for build and release steps.

## License

MIT
