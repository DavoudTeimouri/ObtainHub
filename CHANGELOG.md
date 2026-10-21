# Changelog

All notable changes to this project will be documented in this file.

## [v3.0.65-rc1] - 2026-10-21
Caches the GitHub candidate search.

### Added
- `ohub check --candidates` searches GitHub up to four times per installed app, on every run. The result is now cached for a day (`%APPDATA%\obtainhub\candidate-cache.json`), so a second run costs no API calls and does not eat the rate limit.

## [v3.0.64-rc1] - 2026-10-21
The three plan items that were declared but never acted on: dependencies, the bandwidth limit, and the checksum for other registries.

### Fixed
- `ohub install --dependencies a/b,c/d` recorded the dependencies in the state but never installed them. They are installed first now, and marked in the state so `ohub uninstall` will not remove a dependency on its own. One level deep on purpose: a dependency's own dependencies are not known until it is installed, and a cycle would recurse forever.
- `download_bandwidth_limit` was a config field that nothing read. The download is really paced now: the file is fetched in chunks, one chunk per second, as many bytes as the limit allows in that second. `minreq` buffers the whole body, so a single request cannot be slowed down - the server has to support Range requests.
- Checksum verification for non-GitHub registries was a TODO. crates.io publishes the sha256 of the `.crate` file, and it is verified now.
- `ohub config set download_bandwidth_limit 512` is a real setting now (KB per second; `none` clears it).

### Added
- The release workflow can be dispatched from the Actions tab with a tag: it creates the tag, and the tag push starts a fresh run that builds, checks and publishes the release.

## [v3.0.63-rc1] - 2026-10-21
The GitHub token leaves the config file and goes into the OS credential store.

### Fixed
- The GitHub token was stored in plain text in `config.toml`. It now goes into the Windows Credential Manager, and the plain text copy is removed from the config file. A token left behind by an older version moves into the credential store on the first run.
- `ohub config set github_token <token>` echoed the token to the terminal and to the log file. It prints `[stored]` now.
- `ohub config show` printed the token. It is masked now.
- `ohub self-uninstall` printed "GitHub token removal from keyring not implemented in this version" and left the credential behind. It removes the credential now.
- `ohub reset` cleared the config but not the credential store. Both are cleared now, and `--keep-token` puts the token back.

### Changed
- `ohub config auth` reports where the token actually lives: "credential store", "config file" or "not set".
- A machine with no credential store keeps the token in the config file and says so.

### Security
- The token no longer lands in a config backup (`ohub config backup`, `ohub reset --backup`) or in a restored config file.

## [v3.0.62-rc1] - 2026-10-21
Wires up three more flags that were accepted but did nothing, and fixes an
architecture bug in the asset selection.

### Fixed
- `--arch` was ignored by `install`, `update` and `rollback`: the asset was picked by the machine's architecture, not the one you asked for. It is honoured now, and `rollback` gained the flag it was missing. The old matcher also accepted an arm64 asset on an x64 machine - that cannot happen any more.
- `ohub check --timeout N` was accepted and did nothing. The timeout is now one setting for the whole run: every GitHub call uses it, and the value is validated (10-300 seconds).
- `ohub add --add-type zip` printed "not yet implemented". It extracts the archive into the managed tree and tracks it.
- `ohub add --as-source` printed that it "would need config manager mutable access". The source is registered now.

### Added
- `--timeout` on `install` and `update` (the `check` flag existed and did nothing).
- `--arch` on `rollback`.

## [v3.0.61-rc1] - 2026-10-21
Wires up the flags that were accepted but did nothing, and makes the backup
restore do its job.

### Fixed
- `ohub check --notes` and `ohub update --notes` were accepted and did nothing - `fetch_release_notes` lived in the TUI, so the CLI path had nothing to call. The helper moved to `core::registries` and is now shared: `check --notes` prints the release notes of every outdated repo, `update --notes` prints them for every repo that was updated.
- `ohub restore --config` printed "Config restore not yet implemented (requires ConfigManager save)". `ConfigManager::save()` has existed all along - the saved config is now written back.

### Changed
- README: `--notes` and the `backup` / `restore` commands are documented.
- PROJECT.md: three stale claims corrected - `update.rs` does verify the published SHA256, and `ohub rollback` is implemented.

## [v3.0.60-rc1] - 2026-10-21
Finishes the three half-built commands. Same content as the withdrawn
v3.0.59-rc1, which failed the clippy gate on a collapsed-if lint and was
never published.

### Added
- `ohub group install|update|check|uninstall` now run the real command for every member of the group, one at a time, instead of printing "Bulk X integration pending". The group config model was already there - only the loop was missing.
- `ohub schedule enable` registers a real Windows Task Scheduler task (`ObtainHubScheduledCheck`) that runs `ohub check --quiet --log` on the configured interval. `disable` removes it, `status` shows the task's next run time, and `run` does the check now and writes the same report the scheduled task would. The task name is the one `ohub cleanup tasks` already looks for.
- `ohub check --log <PATH>` appends a run report (outdated apps, errors, summary) to a file. The report is written even when the console output is suppressed, so a scheduled run leaves a record.

### Fixed
- The clippy gate (`-D warnings`) fired on a nested `if` in the check summary, which blocked the whole release. The `if` is collapsed and the `--force` branch in `update` is flattened the same way.
- `ohub update --force` was passed down to the installer and then ignored, so it did nothing. It now reinstalls the app even when it is already on the latest version, and says so (`Force reinstalling 3.9`).
- The dead `force` parameter of `install_release` was removed rather than left as a no-op.

### Changed
- `ohub group` and `ohub schedule` take a mutable state manager, so the bulk actions can install, update and uninstall for real.
- README: the group and schedule commands are documented, and the wrong `ohub group create` example is now `ohub group add`.

## [v3.0.58-rc1] - 2026-10-21
TUI feature batch.

### Added
- TUI: mark apps with `Space` and update them together with `U`, or update every outdated app with `A`. Marked rows show `[x]`, the panel title counts them.
- TUI: `s` cycles the status filter - all / outdated / current / unknown - and the panel title says which one is active.
- TUI: `R` refreshes only the selected app. `r` still refreshes every app, which is one GitHub call per app.
- TUI: `n` shows the release notes of the selected app in the details panel.
- TUI: `y` copies the selected app's install path to the Windows clipboard.
- Update and remove now ask for confirmation: the status line shows what will happen (`Update OnionHop 3.8.6 -> 3.9?`), `Enter` confirms, `Esc` or any other key cancels.
- README: a table of the TUI keys.

### Changed
- The version comparison that decides the Status column lives in one place (`status_for`), so the TUI list, the `^` marker, the update counters and the status filter can no longer disagree about what needs an update.

## [v3.0.57-rc1] - 2026-10-21
Clean CI on the tag. The binary is behaviour-identical to v3.0.56-rc1 - the
only changes are two clippy fixes and the TUI regression tests.

### Fixed
- Two clippy findings in the new path lookup: `manual_strip` in `core/winreg.rs` (`strip_prefix` instead of `starts_with` + slice) and `type_complexity` in `commands/list.rs` (the row type is now named). Both are behaviour-neutral, so the v3.0.56-rc1 binary is unaffected.

### Added
- TUI layout regression tests. The TUI is rendered into a `ratatui` `TestBackend` and asserted: every app gets its own row, the table fills the main area (the list used to be squeezed into a 3-row strip where only one app was visible), apps needing an update carry the `^` marker and are counted in the title, and the filter narrows the table.

## [v3.0.56-rc1] - 2026-10-21
Deeper fixes on top of v3.0.54-rc1 / v3.0.55-rc1, which addressed the same five
reports but only part of the way.

### Fixed
- `ohub list` still showed the wrong folder for some apps. The install path is now resolved through a cascade: `InstallLocation` (only when the folder really exists on disk), then `DisplayIcon` - the program's own exe path, which is the only answer for the many apps that leave `InstallLocation` empty - then the folder holding the uninstaller. Uninstaller paths in a `bin` subfolder resolve to the app folder, and quoted paths that contain spaces (`C:\Program Files\...`) are no longer truncated.
- `ohub list` now writes the resolved path back to `state.json`, so the TUI, `ohub uninstall` and every later run agree on where the app lives instead of each re-deriving it.
- The registry lookup is version-aware: when an old install is left behind next to a new one, the entry matching the recorded version wins.
- TUI: the app list is a table - one row per app with aligned Installed / Latest / Status columns - so the whole list is visible at a glance instead of one long line per app. The header and footer are one line each, giving the table the rest of the screen.
- TUI: `^` marks the apps that need an update, the Status column is red and bold for them, and the panel title says how many need one.
- TUI: `remove` and `add` corrupted the screen because the command printed into the alternate screen while the TUI was still in raw mode. The TUI now leaves the alternate screen for the duration of the command and comes back afterwards.
- TUI: while a filter is active, every printable key was swallowed by the command shortcuts, so `q`, `a`, `r`, `u`, `x` and `c` could not be typed into the filter. The command keys are now guarded off while filtering, and only Esc, Enter, Backspace and the arrow keys stay live.
- `ohub check --all` and `--candidates` explain their purpose in plain words, with an example, and end with a summary line: managed / unmanaged / outdated / up to date.

## [v3.0.55-rc1] - 2026-10-21
Same fixes as v3.0.54-rc1 (real install paths, TUI list layout, TUI screen corruption, TUI version comparison, `ohub check --all` explanation, rollback tag lookup). The only difference is the CI clippy gate:

### Fixed
- `ohub list` passed `&repo` where `repo` was already a reference, which clippy rejected (`needless_borrow`). The binary in v3.0.54-rc1 was unaffected - only the CI lint gate was red.

## [v3.0.54-rc1] - 2026-10-21
### Fixed
- `ohub list` showed ObtainHub's own download folder instead of where the app actually lives. The path is now read from the Windows uninstall registry (`C:\Users\x\AppData\Local\Programs\OnionHop V3\`), falling back to the stored path when Windows does not know the app.
- `ohub add` now records the app's real install folder instead of `repos\<owner>\<repo>\`. The "path already exists" prompt only fires for folders inside ObtainHub's own tree.
- TUI: the app list was rendered into a 3-row strip when no filter was active, so only one app was visible at a time. The list now gets the whole main area and the filter bar row collapses when not filtering.
- TUI: install/remove printed to stdout, which landed inside the alternate screen and left the command output mixed into the UI. The screen is now wiped and repainted after those actions.
- TUI: up-to-date apps were shown as "Update" because the GitHub tag (`v3.9`) and the installed version (`3.9`) were compared as raw strings. Versions are now normalized before comparing.
- `ohub update` stored the raw tag (`v3.9`) as the installed version, which then differed from the registry version. The stored version is now normalized.
- `ohub rollback` looked up the release tag as `3.8.6` when the tag on GitHub is `v3.8.6`. It now tries both forms.

### Changed
- `ohub check --all` and `ohub check --candidates` now print what they are about to do before doing it, so the purpose of a full registry scan is obvious.
- `normalize_version()` moved to `core::state` and is shared by check, update and tui instead of being copied three times.

## [v3.0.53-rc1] - 2026-10-21
### Changed
- CI uploads `check.log` / `test.log` / `clippy.log` / `build.log` as workflow artifacts when a job fails. Job logs are admin-only in the public API, so before this a failed Windows build could not be diagnosed without repo access.
- Clippy is a hard gate again (`-D warnings`) now that the lint backlog is cleared.

### Fixed
- 75 clippy findings cleared across 16 files: needless borrows, redundant field names, no-op `..Default::default()` struct updates, `sort_by` → `sort_by_key`, `iter().any()` → `contains()`, `iter().cloned().collect()` → `to_vec()`, `Iterator::last` → `next_back`, collapsible `if` blocks and match arms, unnecessary casts, a dead `GitHubRepoInfo` struct, and an unused type parameter on the TUI draw function.

## [v3.0.52-rc1] - 2026-10-21
### Fixed
- Windows build broke in two places, both hidden from Linux because the code sits behind `#[cfg(windows)]`:
  - `src/core/elevate.rs` called `Result::context()` — a trait method — but only imported `anyhow::Result` (E0599). `anyhow::Context` is now imported under `#[cfg(windows)]`.
  - `src/commands/check.rs` moved `entry.display_name` out of the registry entry and then borrowed the whole entry again for `entry.install_dir()` (E0382: borrow of partially moved value). The install path and uninstaller are now read before the move.
- The v3.0.50-rc1 and v3.0.51-rc1 releases never published an installer: the Windows CI build failed on the same errors, so no MSI or NSIS EXE was attached. Use v3.0.52-rc1 instead.

## [v3.0.51-rc1] - 2026-10-13
### Added
- `ohub update --quiet` suppresses progress output; `--log <PATH>` appends a run report to a file. Scheduled runs now leave a record behind.
- `ohub rollback` re-downloads and reinstalls the recorded `previous_version` from its GitHub release tag instead of copying files around. Supports `--yes` (skip confirmation) and `--quiet`.
- `ohub doctor` rewritten: checks Install / Download / Shim directories for existence **and** writability, reports proxy, GitHub token state plus remaining rate limit, and verifies the install and shim directories are on `PATH`. New `--strict` flag exits non-zero when issues are found.
- `ohub check` offers to update outdated apps in one go (skipped under `--quiet` / `--outdated_only`, auto-confirmed with `--yes`).
- New `src/core/elevate.rs`: one shared elevated-launch helper for installers and uninstallers (PowerShell `Start-Process -Verb RunAs -Wait`).
- CI: separate `check` job on pull requests — `cargo check --all-targets`, `cargo test`, `cargo clippy --all-targets -- -D warnings`.

### Fixed
- `ohub check` ran its self-update check against a throwaway `ConfigManager`/`StateManager`, so the user's GitHub token was ignored and every self-update check hit the anonymous 60 req/hr limit. It now uses the real config and state.
- `ohub update` reported success when an installer failed because the app was still running. The Windows uninstall registry is now snapshotted before and after the installer runs, and the result is verified against it.
- `ohub update` prints a progress bar while downloading and shows the download directory it actually uses.

### Changed
- Compiler warnings: **91 → 0**. Unused parameters renamed to `_`, dead serde fields marked `#[allow(dead_code)]`, `partition_gitHub_managed` renamed to `partition_git_hub_managed` (clippy `snake_case`).
- Dead code deleted instead of maintained: `src/cli/templates.rs`, `src/tui/mod.rs`, `assets.rs::{download_with_progress, verify_checksum, download_verify_extract}`, `logger.rs::init_with_level`, `registries.rs::Registry::registry_type`, `install.rs::{fetch_repo_info, fetch_latest_release, fetch_release_by_tag}`, `update.rs::{enumerate_all_installed_software, find_candidate_repos, clean_app_name}`.

## [v3.0.50-rc1] - 2026-10-13
### Added
- Track real install location + uninstaller for third-party installers. `ohub update` snapshots the Windows uninstall registry before and after running an installer, then records where the app landed and how to remove it.
- `ohub uninstall` now runs the app's own registered uninstaller (elevated) instead of only deleting ObtainHub's download folder. Handles NSIS (`unins000.exe`), MSI (`MsiExec /X{GUID}`) and Burn bundles (`/I` → `/X`).
- New `src/core/winreg.rs`: uninstall-registry scanning and change detection (new entry or version bump), with 4 unit tests.
- New `src/core/elevate.rs`: shared elevated-launch helper for installers and uninstallers (PowerShell `Start-Process -Verb RunAs -Wait`).
- `state.json`: new `uninstaller` field on each managed app (optional; old state files still load).

### Changed
- `ohub list` Path column now shows the app's real install folder (e.g. `C:\Users\x\AppData\Local\Programs\OnionHop V3\`) instead of ObtainHub's download folder.
- `ohub check --all` / `--candidates` capture each app's uninstaller from the registry, so `ohub uninstall` works for apps tracked without an update.
- `check.rs` registry scan now delegates to `core::winreg` (removed ~40 lines of duplicated code).

## [v3.0.49-rc1] - 2026-10-13
### Added
- TUI: Interactive update (`u`) - updates selected app with update available
- TUI: Remove from management (`x`) - removes selected app from tracked list
- TUI: Filter apps (`/`) - filter by name, repo, or status with live filtering
- TUI: Clear filter (`c`) - clears active filter
- TUI: App details (`Enter`) - shows full app info including install path
- TUI: Shows available version arrow (→ v3.9) next to outdated apps
- TUI: Filter bar shows active filter text
- TUI: Updated key bindings in help screen

## [v3.0.48-rc1] - 2026-10-13
### Fixed
- `ohub update` sets `install_path` to install directory (`repos\owner\repo\`) instead of downloaded setup file (`repos\owner\repo\OnionHop-Setup-v3.exe`). `ohub list` Path column now shows the install folder, not the downloaded .exe/.msi file.

## [v3.0.47-rc1] - 2026-10-13
### Fixed
- Consistent 403 error message across ALL commands: "GitHub API rate limited or access denied (403). Set a token: ohub config set github_token <token>"
  - check (check.rs, find_candidate_repos)
  - update (update.rs, find_candidate_repos)
  - self_update (self_update.rs - releases/latest, releases list, tags)
  - install (install.rs - fetch_repo_info, fetch_latest_release, fetch_release_by_tag, search_github_repos)
  - info (info.rs)
  - source (source.rs)
  - tui (tui.rs)
  - add (add.rs)
  - search (search.rs)

## [v3.0.46-rc1] - 2026-10-13
### Added
- `ohub update` skip download if file already exists with matching size + SHA256 checksum (prevents redownload)
- `ohub update` removes old file with same name before writing new one
- `ohub update` shows both Install directory and Download directory at start
- `ohub update` download folder cleanup: keeps only latest versioned file per base name, removes older duplicates

### Fixed
- `ohub update` showed wrong directory (download_dir instead of install_dir where files are actually stored)

## [v3.0.45-rc1] - 2026-10-13
### Fixed
- CI compile error E0716: `format!()` temporary dropped before `Command::args()` used it in `run_installer` (update.rs) and self-update elevation (self_update.rs). Now binds `format!()` result to a named variable before passing its reference to `.args()`.

## [v3.0.44-rc1] - 2026-10-13
### Added
- `ohub update` progress bar on download (indicatif)
- `ohub update` shows download directory at start
- `ohub update` verifies installation succeeded (file exists, non-zero, correct size)
- `ohub update` runs .exe/.msi installer after download with elevation

### Fixed
- `ohub update` 403 error now says "rate limited or access denied" with token hint
- `ohub update` runs installer for .exe/.msi assets (was only saving to disk)

## [v3.0.43-rc1] - 2026-10-13
### Fixed
- CI: NSIS install uses winget → Chocolatey → GitHub releases (SourceForge returned HTML error pages instead of binaries). Size validation raised to 2MB. Accepts NSIS 3.10.1 or 3.11.

## [v3.0.42-rc1] - 2026-10-13
### Fixed
- CI: NSIS install robustness — multiple SourceForge mirrors, `-UseBasicParsing`, file size validation; accepts NSIS 3.10.1 or 3.11 (prevents corrupted-download build failures)

## [v3.0.41-rc1] - 2026-10-13
### Fixed
- `ohub update` asset detection: if no arch-specific installer (.exe/.msi matching `x64`, `win64`, `windows`, etc.) is found, falls back to ALL `.exe`/`.msi` assets. Asset naming varies across repos — some use `Setup.exe` with no arch token — fallback ensures installers are never missed.

## [v3.0.40-rc1] - 2026-10-13
### Fixed
- `ohub update` arch detection now matches `x64`, `64-bit`, `64bit` tokens in addition to `x86_64`, `amd64`, `aarch64`, `arm64` — Windows assets named `Setup-x64.exe` / `Setup-64bit.msi` are now detected
- Same arch tokens added to `install.rs` `select_asset` for consistency

## [v3.0.39-rc1] - 2026-10-13
### Added
- `ohub update` interactive asset selection: Select dialog lists only `.exe` (setup) and `.msi` installer assets matching current architecture. `.msi` preferred over `.exe` (sorted first, default selection). Other file types (.zip, .tar.gz, etc.) hidden.
- `GitHubAsset` in update.rs now derives `Clone`

### Fixed
- `ohub update` dependency update call passes new `selected_asset` parameter
- `fetch_published_checksum` call uses local `InstallGitHubRelease` conversion

## [v3.0.38-rc1] - 2026-10-13
### Added
- `ohub check --candidates` vendor exclusion: MultiSelect before GitHub search lets user exclude vendors (Microsoft, Adobe, Oracle, Apple, Intel, NVIDIA, AMD pre-selected) to keep candidate search efficient
- README command reference: detailed descriptions for every command, `--all`/`--candidates` flows, version comparison rules

### Fixed
- `src/commands/check.rs`: removed duplicate managed-repo checking code that was accidentally inside `--candidates` block
- `src/commands/check.rs`: added `extract_vendor()` helper for vendor name detection from installed program names

## [v3.0.37-rc1] - 2026-10-13
### Fixed
- `ohub self-update` EXE/MSI installer now replaces running `ohub.exe` correctly. Renames running exe to `ohub.exe.old` before launching installer, restores on failure, deletes on success. Fixes "ohub.exe not replaced — Control Panel shows new version but file is old".

## [v3.0.36-rc1] - 2026-10-13
### Fixed
- RC build for self-update test: verifies elevated EXE/MSI installer launch via `find_powershell()` path resolution

## [v3.0.35-rc1] - 2026-10-13
### Fixed
- `ohub self-update` EXE/MSI elevation: `powershell` not found → "program not found". Now resolves `powershell.exe` from explicit paths (`C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`, `C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe`) then falls back to PATH.

## [v3.0.34-rc1] - 2026-10-13
### Fixed
- `src/commands/check.rs`: added missing `use std::path::PathBuf;` import — CI compile error `E0433: cannot find type PathBuf in this scope`

## [v3.0.33-rc1] - 2026-10-13
### Fixed
- `ohub list` Path column now shows install folder (from Windows `InstallLocation` or `UninstallString` directory), not `uninstall.exe` path
- `ohub check --all` documented: scans ALL installed Windows programs, lets user select unmanaged ones to add, offers candidate GitHub repos for each, then checks for updates

## [v3.0.32-rc1] - 2026-10-13
### Fixed
- `ohub check --all` now reads installed version from Windows registry scan (`DisplayVersion`) instead of stale `state.json` version from previous runs — `ohub list` shows correct installed version
- `ohub check --all` syncs corrected versions back to `state.json` when registry scan differs from stored version
- `ohub update` dependency version comparison now uses `normalize_version` (strips `v`/`V` prefix)
- `ohub check` fall-through version comparison uses `normalize_version` so `v3.9` vs `3.9` matches correctly

## [v3.0.31-rc1] - 2026-10-13
### Fixed
- `ohub check --candidates` / `ohub check --all` no longer overwrites installed `version` with GitHub's latest tag when adding repos - `ohub list` now shows correct installed version and `ohub update` correctly detects outdated repos
- Version comparison in `--candidates`/`--all` fall-through now strips `v`/`V` prefix (`normalize_version`) so `v3.9` vs `3.9` matches correctly

## [v3.0.30-rc1] - 2026-10-13
### Fixed
- `ohub check --candidates` / `ohub check --all` no longer lists duplicate managed repos (dedup via `already_checked` set)
- Added repos keep their real `install_path` and `version` from Windows registry scan instead of `unknown` / empty PathBuf
- `ohub list` now shows correct installed version and path (populated from registry scan at add time)
- `ohub update` correctly detects outdated repos (version normalization strips `v`/`V` prefix; installed version no longer overwritten by GitHub tag)
- `ohub self-update` / `ohub check` / `ohub update` no longer crash with "unexpected end of file" on empty GitHub API responses — validates body before JSON parsing
- `ohub self-update` launches MSI/EXE installers elevated via PowerShell `Start-Process -Verb RunAs` — fixes "The requested operation requires elevation" (os error 740)
- `ohub check`/`ohub self-update` give clear 403 error: "Rate limited or access denied. Set GitHub token with 'ohub config set github_token <token>'"

## [v3.0.29-rc1] - 2026-10-13
### Fixed
- `ohub self-update` now launches MSI/EXE installers elevated via PowerShell `Start-Process -Verb RunAs` — fixes "The requested operation requires elevation" (os error 740) on Windows

## [v3.0.28-rc1] - 2026-10-13
### Fixed
- `ohub self-update` no longer crashes with "unexpected end of file" when GitHub API returns empty body - now checks status code and body length before parsing JSON
- `ohub check --candidates` and `ohub update` no longer crash with "unexpected end of file" on GitHub API errors or empty responses - non-2xx status codes return empty candidate list instead of erroring
- All GitHub API JSON parsing now reads raw bytes first and validates non-empty body before deserializing

## [v3.0.27-rc1] - 2026-10-13
### Fixed
- `ohub check --candidates` and `ohub update` now strip noise words (`version`, `edition`, `x64`, `x86`, `64-bit`, `32-bit`, etc.) from app names so "OnionHop V3 version 3.8.6" cleans to "OnionHop"
- `find_candidate_repos` tries multiple search term variations: cleaned name, first word of cleaned name, original with digits/dots stripped, then original name — maximizing hit rate for apps with public GitHub repos

## [v3.0.26-rc1] - 2026-10-13
### Fixed
- `ohub self-update` no longer tries to extract `.exe`/`.msi` installer assets as zip - now runs MSI (`msiexec /i /qn /norestart`) and NSIS EXE (`/S`) installers silently instead
- `ohub update` defaults to checking only managed repositories (from state.json) - no longer scans all installed software by default
- Version comparison now strips `v`/`V` prefix (e.g. `v3.0.25` == `3.0.25`) so `ohub check`/`ohub update` correctly detects outdated repos

## [v3.0.25-rc1] - 2026-10-13
### Added
- `ohub search` now shows interactive selection - select repos from search results, then add to managed list or install immediately
- `ohub install` falls back to GitHub search when exact repo not found, offers interactive selection of candidates
- `ohub update` auto-detects unmanaged apps on the system and offers to add them as managed repositories before updating
- `ohub check --all` shows sorted list of unmanaged apps, then after confirming selections offers candidate repositories for each

### Fixed
- `ohub install` no longer fails with "missing field tag_name" when registry API omits tag_name - now defaults to "unknown"
- `ohub self-update` lists available assets with manual download URL when no platform-specific zip found

## [v3.0.24-rc1] - 2026-10-13
### Fixed
- `ohub self-update` no longer bails with "No suitable release asset found" when no platform-specific zip exists - now lists available assets and provides manual download URL
- `ohub self-update` falls back to any asset when no platform-specific zip found

## [v3.0.23-rc1] - 2026-10-13
### Fixed
- `ohub check --candidates` now shows ALL unmanaged apps with candidate repositories found via GitHub search
- `ohub check --candidates` cleans app names (strips version numbers like " V3 3.8.6") for better GitHub search results
- `ohub check --candidates` allows manual `owner/repo` entry when no candidates found
- `ohub check --candidates` falls through to show check results for newly added repos

## [v3.0.22-rc1] - 2026-10-13
### Fixed
- `ohub check --all` 404 - `fetch_latest_release` returns `Option<GitHubRelease>`, skips repos without releases gracefully
- `ohub check --candidates` no longer returns early - falls through to show check results for newly added repos
- `ohub update` 404 - same `Option<GitHubRelease>` handling with retry logic
- `ohub tui` now fetches latest versions from GitHub, shows Current/Update/Unknown/Unmanaged status
- `ohub tui` 'r' key actually refreshes app list from GitHub

### Added
- Retry logic for `ohub update` (configurable via http_retries, http_retry_delay_ms, http_retry_backoff)

## [v3.0.21-rc1] - 2026-10-13
### Added
- `ohub add --type folder` - manage portable applications from local folders
- Folder mode scans for executables (.exe on Windows, executable permission on Unix)
- `--recursive` flag for subdirectory scanning
- `--repo-arg` to link folder app to a GitHub repo for updates
- Creates shims in shim_dir for each executable found
- Adds each executable to state.json for tracking
- Shows PATH instructions for using apps from anywhere

## [v3.0.20-rc1] - 2026-10-13
### Added
- `ohub add --type folder` - manage portable applications from local folders
- Folder mode scans for executables (.exe on Windows, executable permission on Unix)
- `--recursive` flag for subdirectory scanning
- `--repo-arg` to link folder app to a GitHub repo for updates
- Creates shims in shim_dir for each executable found
- Adds each executable to state.json for tracking
- Shows PATH instructions for using apps from anywhere

## [v3.0.19-rc1] - 2026-10-13
### Fixed
- Self-update 404 - falls back to releases list, then tags when no releases published
- Check command: `fetch_latest_release` returns `Option<GitHubRelease>` - no longer errors on 404, skips repos without releases gracefully
- Check command: `--candidates` shows ALL unmanaged apps (not just those with candidates), lets user choose both software AND candidate repository
- Add command: verifies GitHub repository exists before adding to management

### Added
- Retry logic for `ohub add` repository availability check
- Configurable retry via `http_retries`, `http_retry_delay_ms`, `http_retry_backoff` in config

## [v3.0.18-rc1] - 2026-10-13
### Added
- CLI message templates module for consistent output formatting
- Version templates with build metadata (timestamp, rustc version, git info)
- Build script emits vergen-compatible constants without external dependency
- Error/Warning/Info/Success message templates
- Progress/Status templates for long-running operations
- Repository info, install result, update availability templates
- Search result, list item, uninstall confirmation templates
- Rollback info, config, dry run templates

### Fixed
- Version output uses standardized template
- Build constants generated without vergen dependency (Rust 1.85 compatible)

## [v3.0.17-rc1] - 2026-10-13
### Fixed
- Self-update 404 - fixed GitHub API endpoint (ObtainHub repo name case)
- Check command: `--all` no longer 404s on ObtainHub's own repo (skipped during check)
- NSIS installer detects installed version and offers upgrade/uninstall options
- Colors: Only green removed - uses terminal default colors everywhere

### Added
- More informative output - detailed progress/info messages for all operations
- Check command: Shows "Checking ObtainHub self-update..." before self-update check
- Check command: Shows "Checking N managed repositories for updates..."
- Check command: Shows "Scanning Windows registry for installed programs..."
- NSIS installer: Displays installed version vs new version in conflict dialogs
- Uses terminal default colors - no custom color overrides

## [v3.0.16-rc1] - 2026-10-13
### Fixed
- Self-update check 404 - fixed GitHub API endpoint and added retry logic
- Check command: `--candidates` now shows all unmanaged apps with their candidate repositories
- Check command: `--all` now shows all unmanaged apps with interactive selection
- Colors: Only green for selection checkboxes/ticks, default color for all other text
- Added retry logic for all HTTP requests, configurable via config (http_retries, http_retry_delay_ms, http_retry_backoff)
- More informative output - progress bars for scanning and candidate searching with detailed messages
- Self-update check now uses retry config and proper error handling

### Added
- Progress bars for scanning installed programs and finding candidates
- Green tick marks and gray checkboxes in interactive MultiSelect
- Interactive `--all` offers selectable list for unmanaged apps
- Interactive `--candidates` offers selectable list to add apps to management
- After selecting app, immediately checks candidates and offers repository selection
- Added `dialoguer`, `console`, `indicatif` dependencies for interactive prompts and progress bars
- Retry configuration in config.json (http_retries=3, http_retry_delay_ms=1000, http_retry_backoff=2.0)

## [v3.0.15-rc1] - 2026-10-13
### Added
- Check command: Removed timestamp from command output (clean output)
- Check command: Progress bars for scanning and candidate searching
- Check command: Green tick marks and gray checkboxes in interactive selection (MultiSelect)
- Check command: Interactive `--all` offers selectable list for unmanaged apps
- Check command: Interactive `--candidates` offers selectable list to add apps to management
- Check command: After selecting app, immediately checks candidates and offers repository selection
- Added `dialoguer`, `console`, `indicatif` dependencies for interactive prompts and progress bars

### Fixed
- Check command: `--candidates` works independently of `--all`
- Check command: Shows candidate repositories for unmanaged apps with GitHub search
- Check command: Self-update check when no specific repo specified
- Check command: `--quiet` flag to suppress non-error output
- NSIS "Installer corrupted: invalid opcode" - pinned NSIS 3.11 with SourceForge fallback
- NSIS PathHasEntry Exch → Push fix for NSIS 3.13 stack-exchange bug

## [v3.0.14-rc1] - 2026-10-13
### Added
- Check command: `--all` now offers interactive selectable list for unmanaged apps
- Check command: `--candidates` now offers interactive selection to add apps to management
- Check command: After selecting app, immediately checks candidates and offers repository selection
- Added `dialoguer` and `console` dependencies for interactive prompts

### Fixed
- Check command: `--candidates` works independently of `--all`
- Check command: shows candidate repositories for unmanaged apps with GitHub search
- Check command: self-update check when no specific repo specified
- Check command: `--quiet` flag to suppress non-error output

## [v3.0.13-rc1] - 2026-10-13
### Fixed
- Check command: `--all` now checks unmanaged apps by finding GitHub repos by name
- Check command: `--candidates` now works independently of `--all`
- Check command: shows candidate repositories for unmanaged apps with GitHub search

## [v3.0.12-rc1] - 2026-10-12
### Fixed
- Check command: added self-update check when no specific repo specified
- Check command: added `--candidates` flag to find GitHub repos for unmanaged apps
- Check command: added `--quiet` flag to suppress non-error output

## [v3.0.11-rc1] - 2026-10-12
### Fixed
- NSIS "Installer corrupted: invalid opcode" — replaced `Exch $R0` with `Push $R0` in `PathHasEntry` / `un.PathHasEntry` to avoid NSIS 3.13 stack-exchange bug triggered by compiler optimization `+2`

## [v3.0.10-rc1] - 2026-10-12
### Fixed
- NSIS "Installer corrupted: invalid opcode" — replaced `Exch $R0` with `Push $R0` in `PathHasEntry` / `un.PathHasEntry` to avoid NSIS 3.13 stack-exchange bug triggered by compiler optimization `+2`

## [v3.0.9-rc1] - 2026-10-12
### Added
- RC build for v3.0.9 with all v3.0.8 features
### Fixed
- NSIS pinned to 3.11 with SourceForge fallback (fixes "Installer corrupted: invalid opcode")

## [v3.0.8-rc1] - 2026-10-12
### Added
- RC build for v3.0.8 with all v3.0.7 features
### Changed
- NSIS pinned to 3.11 with SourceForge fallback
- Updated CHANGELOG for RC release

## [v3.0.7-rc2] - 2026-10-11
### Fixed
- The NSIS installer failed on Windows with "Installer corrupted: invalid
  opcode" before showing any dialog. v3.0.4 and v3.0.5 were both built with
  NSIS 3.13, which winget installs by default. The published file was not
  corrupt in transit: its SHA-256 matched the published `SHA256SUMS`, the MZ
  header was intact, the `NullsoftInst` magic sat at the expected offset, and
  the sizes matched what CI built. The fault was in how 3.13 emitted this
  script.
- The build toolchain was unpinned. `winget install NSIS.NSIS` resolves to
  whatever "latest" is, so the NSIS version could change between runs with no
  diff to review. NSIS is now pinned to 3.11, the installer download is
  verified by SHA-256 before use, and the build asserts `makensis -VERSION`
  reports 3.11 before running.

### Changed
- The release job now checks out the repository. It previously ran the
  changelog extraction against an empty workspace, so
  `awk: cannot open file 'CHANGELOG.md'` failed every release.

### Notes
- This is a release candidate. Install `ObtainHub-Setup.exe` and confirm it
  completes before v3.0.6 is cut.

## [v3.0.5] - 2026-10-09
### No changes — this tag exists to verify the automated changelog extraction.

## [v3.0.4] - 2026-10-09
### Fixed
- Checksum verification never verified anything. `verify_checksum` looked for a
  `<archive>.sha256` file inside the newly created install directory, where
  nothing ever writes one, so every install warned and returned `Ok`. `install`
  now reads a digest published with the release (`<name>.sha256`, `SHA256SUMS`,
  `checksums.txt`) and compares against it; `install --file` and `--url` read a
  sidecar next to the archive. Mismatches abort the install.
- `self-update` downloaded a release asset and overwrote the running binary with
  nothing verified. It now requires a published digest and refuses to run when
  none exists, failing closed.
- `config get github_token` printed the token verbatim, leaking it into shell
  history and CI logs. It now returns `[stored]`.
- `backup` and `reset --backup` embedded the plaintext GitHub token in the archive.
  Both strip it and report that they did.
- `reset --move-token` and `--keep-token` were stubs that printed "not implemented".
  The token is now captured before the reset: `--keep-token` restores it,
  `--move-token` writes it to the given path with 0600 on Unix.

### Added
- Releases now publish `SHA256SUMS` alongside both installers, which is what makes
  self-update's verification satisfiable.
- Tests for the digest parsers and the manifest filename match: 13 total.

## [v3.0.3] - 2026-10-09
### Fixed
- Mutual refusal was dead code in both directions.
  - NSIS looked for the MSI under `Uninstall\{UpgradeCode}`, but Windows Installer
    registers under the ProductCode and `setup.wxs` uses `Id="*"`, so that key
    holds a different GUID on every build. NSIS now detects the MSI through its
    stable marker `HKLM\Software\ObtainHub\PathInstalled`, and clears that
    marker on uninstall.
  - The MSI searched `Uninstall\{...}_is1`, but NSIS only appends `_is1` when the
    app id is not already a GUID. The key never existed, so the search could not
    match. Fixed the key and restored the launch Condition.
- `check --all` sent every installed Windows program's `DisplayName` to the GitHub
  releases API. `NVIDIA Corporation` is not `owner/repo`, so every lookup 404'd
  and the request volume exhausted the unauthenticated rate limit. Only programs
  tracked in `state.json` are now queried; the rest are reported as skipped.
- Silent-install conflict handling never compiled: `StrCmp $Silent 1` was rejected
  as an unknown variable, so the auto-uninstall-MSI and upgrade-in-place branches
  were silently dropped. Replaced with the `IfSilent` instruction.

### Changed
- NSIS installer now builds with zero warnings (was 2).

## [v3.0.2] - 2026-10-09
### Fixed
- Silent-install conflict handling never compiled. `StrCmp $Silent 1` was rejected
  by makensis as an unknown variable, and the compiler silently ignored both
  occurrences, so the auto-uninstall-MSI and upgrade-in-place branches were dropped
  from the binary. Replaced with the `IfSilent` instruction.
- Version numbers had drifted: the v3.0.1 tag was cut while `Cargo.toml`,
  `installer/ObtainHub.nsi`, and `installer/setup.wxs` all still said 3.0.0, so the
  published installers reported the wrong version. All four sites are now bumped
  together and `PROJECT.md` §2 records the rule.

### Changed
- The NSIS installer builds with zero warnings (was 2).

## [v3.0.1] - 2026-10-09
### Fixed
- MSI build: `installer/setup.wxs` was missing `Platform="x64"`, so ICE80 rejected
  the package (LGHT0204) because `PathEnvironment` and `MainExecutable` are both
  `Win64="yes"`. Removed the 32-bit `RegistrySearch` too — a 64-bit package cannot
  carry a 32-bit Locator (LGHT1076).
- Zip-slip: `install.rs` joined attacker-controlled zip entry names onto the
  install directory without validation, so an entry named `../../evil.exe` wrote
  outside it. Reachable via `install` and `install --url`, which fetch archives
  from the internet. `update.rs` had the same hole through `archive.extract()`.
  Both now normalize the path through `Path::components()` before the containment
  check, with three tests covering parent traversal, absolute paths, and normal
  entries.
- `uninstall --purge` now drops the repository's state metadata and its membership
  in any group, instead of printing "not yet fully implemented".
- `update` installs to `config.install_dir` instead of a hardcoded
  `ObtainHub/repos` path, so a custom install directory is respected.
- `ohub completion` no longer panics on a broken pipe (`ohub completion fish | head`).
- Config values that would hang or divide by zero (`parallel_downloads`,
  `timeout_seconds`, `update_check_interval_hours`, `schedule.interval_hours`)
  are reset to defaults on load and on save.

### Added
- `PROJECT.md`: living reference for installer invariants, GUID requirements,
  filesystem layout, config contract, and security posture.
- `CONTRIBUTING.md`: build, test, installer, and release procedure.
- README: examples for every major command; corrected config path.

## [v3.0.0] - 2026-10-08
### Added
- Complete rewrite from Python to Rust (ObtainHub-rs merged into main)
- Rust 1.85+ binary with zero-cost abstractions and memory safety
- 25 commands: search, install, update, check, list, uninstall, doctor, info, readme, license, releases, workflows, issues, topics, stats, config, auth, completion, version, help, self-update, state, backup, restore, apps, cleanup, tui, group, shim, schedule
- GitHub-native features: stars, topics, releases, readme, license, issues, workflows
- Windows installers: MSI (WiX v3) and NSIS EXE (NSIS 3.13), both machine-wide, admin-only
- Unified icon (installer/icon.ico) used for MSI, NSIS EXE, and embedded in ohub.exe
- Installer UX: NSIS detects existing MSI/EXE and prompts Uninstall/Upgrade/Cancel; silent mode auto-handles
- Mutual refusal: MSI blocks EXE install, EXE blocks MSI install via shared GUID
- PATH management: exact add/remove semantics for user scope
- `ohub check --all` enumerates all installed software from Windows registry and skips ObtainHub itself
- No standalone binary: only MSI and NSIS EXE published to releases
- Self-contained: no .NET, VC++ redist, or Python required
- Configuration: `%APPDATA%\\ObtainHub\\state.json`
- Changelog per release (this file)

### Fixed
- NSIS installer corruption: replaced `/SOLID LZMA` with per-file LZMA/zlib and CRCCheck on to avoid CRC bug
- MSI build: removed unsupported `Platform` and `Schedule` attributes from WiX XML
- Missing imports in TUI modules: `anyhow::Result` in `src/tui/mod.rs`; `ratatui::Frame`, `ratatui::Terminal`, `ratatui::backend::CrosstermBackend` in `src/commands/tui.rs`; `tracing::subscriber::registry` in `src/core/logger.rs`
- Dependency compilation hang: removed `build.rs` workaround, cleaned Cargo.toml, used offline builds with proper target directory
- Silent mutual refusal: EXE and MSI both respect `/S` flag for silent uninstall during conflict resolution

### Changed
- ObtainHub-rs repository deleted after migration (code now in main repo)
- Build process: uses `cargo build --release --target x86_64-pc-windows-gnu` for Windows binaries
- Installer scripts: NSIS uses zlib compression with CRC; WiX uses standard heat/candle/light
- Version: bumped to 3.0.0 for major rewrite

### Removed
- Standalone ohub.exe from releases (only installers)
- Python implementation and related scripts
- ObtainHub-rs submodule/repository
## [v3.0.7-rc2] - 2026-10-11
### Fixed
- NSIS installer binary path now uses relative 'ohub.exe' to ensure the binary is correctly picked up from installer/ directory
- Checksum verification now works in `update` command by fetching published SHA256SUMS/checksums.txt from release assets
- Search command now supports pagination (`--page`, `--per-page`) and per-repo timeout configuration
- Architecture selection now consistent across install/update commands (Plan #7)

### Added
- Public `fetch_published_checksum` and `calculate_sha256` functions in install module for cross-command reuse
- GitHub API pagination support in search command (respects GitHub's 100 results/page limit)
- Config-driven install directory now properly used in update command
- Shared download/verify/extract utilities in `src/core/assets.rs` (Plan #4)
- Config validation with upper bounds and absolute path normalization (Plan #8)
- Tests for config validation (15 tests total now)
- Error handling improvements with better context (Plan #5)
- TUI in-app help screen with key bindings (Plan #9)
- Rollback support: `previous_version` and `previous_install_path` stored in state (Plan #15)
- Network bandwidth throttling for downloads via `download_bandwidth_limit` config (Plan #16)
- New `ohub rollback <repo>` command to revert to previous version (Plan #15)
- Self-update signature verification with Ed25519 (Plan #11)
- `--skip-signature` flag for self-update (emergency bypass)
- Dependency tracking for installed apps (Plan #13)
  - `dependencies` field in state for declaring repo dependencies
  - Auto-update of dependencies during `ohub update` (with `--skip-deps` to opt out)
  - Uninstall protects dependencies with `--force` override
  - `--dependencies` flag for `ohub install` to declare deps at install time
