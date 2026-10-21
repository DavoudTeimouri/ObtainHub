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
| `tui` | Launch the interactive app table |
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
ohub group add dev BurntSushi/ripgrep BurntSushi/fd
ohub group list
ohub group update dev           # update every app in the group
ohub group check dev            # check every app in the group
ohub group uninstall dev --force

# Scheduled checks (Windows Task Scheduler)
ohub schedule enable            # register the scheduled task
ohub schedule status            # config + the task's next run time
ohub schedule run               # do the check now, write the report
ohub schedule disable

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

### TUI keys

| Key | Action |
|-----|--------|
| `j` / `k` or `↓` / `↑` | Move the selection |
| `Space` | Mark the app for a bulk update |
| `U` | Update every marked app |
| `A` | Update every outdated app |
| `u` | Update the selected app |
| `x` | Stop managing the selected app (its files stay on disk) |
| `s` | Cycle the status filter: all / outdated / current / unknown |
| `R` | Refresh the selected app only (one GitHub call) |
| `r` | Refresh every app (one GitHub call each) |
| `n` | Show the release notes of the selected app |
| `y` | Copy the install path to the clipboard |
| `a` | Search GitHub, then add or install a repository |
| `/` | Filter by name / repo / status |
| `c` | Clear the filter |
| `Enter` | App details, or apply the filter |
| `?` / `h` / `F1` | Help |
| `q` / `Esc` | Quit |

Update and remove ask for confirmation first: the status line shows what will
happen, `Enter` confirms, `Esc` or any other key cancels.

## Configuration

Config file: `%APPDATA%\ObtainHub\config.toml` (Windows) or `$XDG_CONFIG_HOME/ObtainHub/config.toml` (Unix)
State file: `%APPDATA%\ObtainHub\state.json`

```bash
ohub config list          # Show all config
ohub config get key       # Get value
ohub config set key value # Set value
ohub config auth          # Where the GitHub token lives
ohub config set download_bandwidth_limit 512   # KB per second (none to clear)
```

The GitHub token is stored in the **OS credential store** (Windows Credential
Manager), not in `config.toml`. `ohub config set github_token <token>` writes
it there and removes the plain text copy from the config file; `ohub config
auth` reports where the token actually is. A machine with no credential store
keeps it in the config file instead.

## Command reference

| Command | Purpose |
|---------|---------|
| `ohub search <query>` | Search GitHub repositories by keyword, language, stars. Results offer to add or install. |
| `ohub install <owner/repo>` | Install an app from a GitHub release. Supports `--version`, `--arch`, `--file` (local archive), `--url` (direct download), `--dry-run`, `--timeout` (request timeout in seconds, 10-300), `--dependencies` (install these repos first, comma separated). |
| `ohub check` | Check all managed repositories for updates. Compares installed version (from state.json) against latest GitHub release tag. `--notes` prints the release notes of every outdated repo. `--timeout` sets the request timeout in seconds (10-300). `--log <PATH>` appends a run report to a file (used by the scheduled task). |
| `ohub check --all` | **Discovery mode.** Scans ALL installed Windows programs (registry `Uninstall` keys), separates managed vs unmanaged, offers to add unmanaged ones with GitHub candidate repos, then checks all managed repos for updates. Existing `state.json` versions are synced with actual registry `DisplayVersion` values. |
| `ohub check --candidates` | **Candidate mode.** Shows unmanaged installed apps sorted by name. First presents a vendor exclusion list (Microsoft, Adobe, Oracle, etc. pre-selected) so GitHub search stays efficient. Then searches GitHub for candidate repos for each remaining app, lets you select which to manage, and offers manual `owner/repo` entry if no candidates found. |
| `ohub update <owner/repo>` | Update a managed repository to its latest version. Without args, updates all managed repos. `--force` reinstalls even when the app is already on the latest version. `--notes` prints the release notes of every repo that was updated. `--arch` picks the architecture of the installer asset. `--timeout` sets the request timeout in seconds (10-300). Supports `--dry-run`. `--quiet` suppresses progress output, `--log <PATH>` appends a run report to a file. |
| `ohub backup` / `ohub restore <file>` | Back up the config and the installed-repo list into one zip, plus the app folders with `--include-repos`; restore them again with `ohub restore <file>`. `restore --config` puts the saved config back, `--state` the installed-repo list, `--repos` the app folders (each verified against its SHA256). |
| `ohub rollback <owner/repo>` | Reinstall the previously installed version of a managed app from its GitHub release tag. Supports `--yes` (skip confirmation), `--quiet`. |
| `ohub list` | Show installed repositories with version, install path, and install date. The path is the app's **real install folder** on disk, resolved from the Windows uninstall registry: `InstallLocation` first, then `DisplayIcon` (the program's own exe path), then the folder holding the uninstaller. The resolved path is written back to `state.json`, so it stays correct for the TUI and `ohub uninstall` too. |
| `ohub uninstall <owner/repo>` | Uninstall an app. Runs the app's own registered uninstaller (from the Windows uninstall registry) with elevation, then removes leftovers. Use `--yes` to skip confirmation, `--purge` to also remove metadata. |
| `ohub remove <owner/repo>` | Stop tracking an app in ObtainHub (keep files on disk). |
| `ohub add <owner/repo>` | Add an existing install to management without re-installing. |
| `ohub self-update` | Check for and install a new ohub release. Renames running `ohub.exe` before launching installer so the file can be replaced. Launches MSI/EXE installers elevated via PowerShell `Start-Process -Verb RunAs`. Use `--skip-signature` to bypass signature check, `--prerelease` for release candidates. |
| `ohub config` | Get/set configuration keys (github_token, install_dir, etc.). |
| `ohub doctor` | Diagnose installation issues: directory existence/writability, proxy, GitHub token and rate limit, PATH. `--fix` repairs what it can, `--strict` exits non-zero when issues remain. |
| `ohub tui` | Interactive table of the managed apps - one row per app with Installed / Latest / Status columns, and `^` marking the apps that need an update. Press `?` for the full key list. |
| `ohub group <add\|list\|remove\|delete\|install\|update\|check\|uninstall>` | Manage groups of repos. A group is a named list of `owner/repo` entries; the bulk actions run the real install / update / check / uninstall command for every member, one at a time. |
| `ohub schedule <enable\|disable\|status\|run>` | Schedule automatic update checks. `enable` registers a Windows Task Scheduler task (`ObtainHubScheduledCheck`) that runs `ohub check --quiet --log` on the configured interval; `status` shows the config plus the task's next run time; `run` does the check now and writes the same report the scheduled task would. |

### Version comparison
Version strings are normalized before comparison: the `v`/`V` prefix is stripped, so `v3.0.32` matches `3.0.32`.

### `ohub check --all` flow
`ohub check --all` is a **full system scan**, not a second update check. In short:
it finds every program installed on this PC, sorts them into "already managed
by ObtainHub" and "not managed yet", lets you adopt the ones you want, and
then checks the managed ones for updates.

1. Scan the Windows uninstall registry for every installed program
2. Skip ObtainHub itself
3. Partition into managed (in state.json) vs unmanaged
4. Sync `state.json` versions with actual registry `DisplayVersion` (fixes stale versions from previous runs)
5. List the unmanaged apps so you can add them
6. Check all managed repos for updates against GitHub latest release
7. Print a summary: managed / unmanaged / outdated / up to date

`ohub check` on its own only checks the repos ObtainHub already manages. `--all` adds the registry scan on top.

### `ohub check --candidates` flow
1. Scan Windows registry for all installed programs
2. Partition into managed vs unmanaged
3. Show vendor exclusion MultiSelect (common non-GitHub vendors pre-checked: Microsoft, Adobe, Oracle, Apple, Intel, NVIDIA, AMD)
4. Filter out apps from excluded vendors
5. Search GitHub for candidate repos for each remaining app
6. MultiSelect: pick apps to manage
7. For each selected app: Select candidate repo, or enter `owner/repo` manually
8. Newly added repos get correct installed version from registry scan

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
