# Changelog

All notable changes to ObtainHub will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.4.3] - 2026-08-13

### Fixed
- **`ohub check --all` no longer lists ohub itself.** The unmanaged-app filter now excludes any registry entry whose name starts with a managed app's name (so "ObtainHub 0.7.4.3" is hidden even though the managed name is "ObtainHub").
- **Apps with messy names are now found.** `ohub check` cleans the registry name before searching GitHub — stripping all version-like tokens (e.g. "OnionHop V3 version 3.7.10" -> "OnionHop") — and falls back through progressively shorter queries, then the raw name, until a repository is found. Names that mix letters and digits (e.g. "v2rayN") are kept.

## [0.7.4.2] - 2026-08-13

### Fixed
- **`ohub check --all --candidates` now works.** The candidate list is always shown when repositories are found (the exact-match fast path no longer skipped it). The exact match is marked with `<=` in the list.
- **Version numbers in app names no longer block matching.** The exact-match comparison now uses the version-stripped name (e.g. "v2rayN 6.0" matches repo `v2rayN`). A fallback search with the raw name runs when the stripped query finds nothing.

## [0.7.4.1] - 2026-08-13

### Fixed
- **`ohub check` crash** (`NameError: name 'a' is not defined`) — the unmanaged-app filter built its install-location set as a literal referencing an undefined comprehension variable. Now computed via proper comprehensions over the managed apps.

## [0.7.4.0] - 2026-08-13

### Fixed
- **Ohub now appears in the managed list.** Its own repo (`DavoudTeimouri/ObtainHub`) is registered as a managed app on startup, so `ohub list` / `ohub check` / `ohub update` include it and self-update stays consistent.
- **`ohub check` crash** ("cannot access local variable 'app'") fixed — renamed the leaked comprehension variable that shadowed the managed-app loop variable.
- **Cancel now aborts.** In `ohub update` and `ohub install`, selecting cancel (0) at the installer-choice prompt stops that app instead of continuing with a default.
- **`ohub add --type folder` requires a finished install.** It now refuses to track a folder that contains no runnable app (no `.exe`), telling the user to finish installing first.
- **`ohub self-update` 403** is no longer logged as an error when running without a token — it's treated as a skipped/rate-limited check (set a token for self-update to work unauthenticated-limited).

## [0.7.3.0] - 2026-08-13

### Fixed
- **Self-managed apps no longer re-detected as unmanaged.** In `ohub check --all`, apps ohub already manages (by name or install location) are excluded from the system scan.
- **`Found N unmanaged` header** prints once, and when you pick a single unmanaged app it no longer shows the full count / scans all 68.
- **`ohub check` now handles folder/portable apps** like `ohub update` does — it searches GitHub by the app's name when no `owner/repo` is linked, instead of reporting "cannot resolve remote".
- **`ohub check` candidate fallback:** search query now strips version numbers (e.g. "App 1.2.3" → "App"). Without `--candidates`, the best-starred repo is offered as the match; with `--candidates` a numbered list is shown.
- **Background `[*]` progress** now prints immediately (flushed) for `check`, `install`, and `update`.
- README: added a worked example for keeping an app from a non-manifest (plain GitHub) source.

## [0.7.2.0] - 2026-08-13

### Fixed
- Extraction `PermissionError` now tells the user to **close the running app** and retry (or run as admin / pick an owned folder).
- `ohub check` no longer crashes on folder-managed apps whose id has no `owner/repo` (`not enough values to unpack`).
- `ohub check --all` no longer re-checks every app after you select a single unmanaged app.
- Custom sources in the legacy top-level `sources` key are now migrated into `manifest_sources` (they were previously ignored). The bogus built-in `default` manifest source was removed.
- `ohub source add --type` is now stored; sources without installable content (no releases/assets, or non-JSON) are rejected.
- Global config directory (`%ProgramData%\ObtainHub`) is created automatically if missing.

### Changed
- Every interactive selection now offers a numbered **Cancel/Skip** option.
- Commands print a `[*]` progress line so background runs stay informative.
- README: config table added, custom-source how-to expanded, non-Windows samples removed (Windows x64 only).

## [0.7.1.0] - 2026-08-13

### Added
- `ohub check` now also discovers unmanaged system apps in **custom sources** (non-GitHub). When a registry app's name matches a source entry, ohub offers to install/update it from that source; the match is recorded so future checks skip it.

## [0.7.0.0] - 2026-08-13

### Added
- **Install/update from custom sources (non-GitHub).** `ohub source add <name> <url> --type github|manifest` registers a source; `ohub install` / `ohub update` now fall back to these sources when a `owner/repo` is not found on GitHub.
  - `--type github` sources read releases/assets from any GitHub repo URL or `.../releases` API.
  - `--type manifest` sources read a JSON list of apps (`[{"name","version","url","installer_type","sha256?","size?"}]`) served over HTTP.
- Apps installed from a source are recorded with their `source` name; `ohub update` checks them against the source for newer versions. `ohub uninstall`/`ohub remove` drops them from ohub (the shared source stays).

### Changed
- `ohub source add` now stores the source `type` and validates reachability/contents before accepting it.

## [0.6.0.0] - 2026-08-13

### Added
- **Install older versions**: `ohub install owner/repo --version 1.2.3` installs a specific version; without `--version`/`--tag` an interactive menu offers the 3 most recent versions (older versions warn they may be unstable). Versions older than the offered 3 fall back to a download you install manually.
- **Download reuse**: if the installer already exists in the download folder with a matching size, ohub reuses it and asks before re-downloading.
- **`ohub source add` validates the URL**: GitHub repo URLs are checked for releases/assets; manifest URLs must be a JSON list. Invalid sources are rejected.
- **Global + per-user config**: machine-wide settings (in `%ProgramData%\ObtainHub\config.json` on Windows or `/etc/obtainhub/config.json`) apply to all users; each user's `github_token` and any explicit override win. Set `OBTAINHUB_GLOBAL_CONFIG` to point elsewhere.

### Fixed
- `ohub install` ZIP/archive path hardened so a non-suitable installer no longer crashes with an attribute error.
- Archive extraction now asks for a **destination folder** when none exists, and a **permission-denied** extraction prints a clear fix (run as administrator or pick a folder you own).
- Download retries now also recover from dropped connections (`RemoteDisconnected`/connection resets) instead of failing.

## [0.5.0.0] - 2026-08-13

### Changed
- **Self-update removed from all commands.** `ohub` no longer phones home on every command. Run `ohub self-update` manually when you want to upgrade. The `--skip-self-update` flag was removed.

### Fixed
- `ohub uninstall` no longer fails with "No uninstall method available" for apps that were added (not installed) or tracked as portable EXEs - they are now cleanly removed from ohub management. Real MSI/EXE installs still invoke the system uninstaller, and permission errors suggest running as administrator.
- Setup EXEs that don't end in exactly `Setup.exe` (e.g. `OnionHop-Setup-v3.exe`) are now correctly detected as installers and actually installed, then tracked as a managed app.
- `ohub check` now always prints a result for a selected managed app (previously "up to date" apps with a normal installer printed nothing).
- `ohub add --type folder` no longer scans the folder for EXEs. It tracks a single app from the mandatory `--name` and the mandatory `--repo owner/repo`; the name + repo are the only source of truth. Folder apps resolve updates via their linked repo.
- `ohub source` with no subcommand now prints its usage/flags instead of silently doing nothing.
- `ohub check --all` now offers a selectable list that includes both managed and system (unmanaged) apps; choosing one unmanaged app checks just that app.

## [0.4.0.0] - 2026-08-13

### Fixed
- `ohub uninstall` now handles portable / zip / exe_standalone apps (deletes the extracted folder or installer dir) instead of failing with "No uninstall method available". Permission failures now suggest running as administrator. On success the app is fully removed from ohub state **and** any manifest source registered for it.
- `ohub update` / `ohub check` version comparison is now semantic (`1.10` > `1.2`), so apps are no longer wrongly reported "up to date".
- `ohub check --candidates` now offers `[0] Skip` to decline linking, and the search is timeout-bounded (see below) so a slow lookup cannot hang the whole scan.
- Self-update 403 / rate-limit errors are now logged at debug level (no scary ERROR) when no token is set.
- Repo links with wrong casing (e.g. `2dust/v2rayn` vs `v2rayN`) are auto-corrected via search, so folder apps linked with a typo can now find their release.
- Managed apps whose install location / uninstaller has been manually removed are now detected and dropped from ohub automatically (with a notice) during `check` and `update`.

### Added
- `ohub install` now also registers the repo as a manifest source, and refuses to reinstall an app already managed by ohub (acts as an update only when a newer version exists).
- Zip/archive install prompts before overwriting an existing folder, reminding the user to back up config first.
- `ohub check` timeout control: `--timeout SECONDS` (clamped 10-60, default 20) plus `check_timeout_seconds` and `check_timeout_retries` (default 3) in config. A per-repo search that exceeds the timeout is skipped and the next app is processed.
- Interactive app selection: running `ohub check` with no app on a TTY shows a numbered list of managed apps to check one or all.

## [0.3.0.0] - 2026-08-13

### Fixed
- `ohub update` now actually updates: it fetches the repo release, and when no standard installer is found it **always** lists candidate assets for you to select, then installs/extracts the chosen one. Previously it silently did nothing for apps without a strict installer.
- Folder/zip apps are now checked and updated by resolving a GitHub repository from the app's **name** (auto-search on first update) instead of being marked "no remote check". If no repository is found, ohub tells you to `ohub remove` and re-`add` with `--name`/`--repo`.
- `ohub check` candidate selection now **persists** the chosen asset (and links folder apps to the selected GitHub release), so subsequent `update` works without re-prompting.
- `ohub uninstall` now resolves apps by display name (was failing with "App not found in state").
- `ohub install` no longer reinstalls an app already managed by ohub; it only proceeds (acting as an update) when a newer version is available.

### Changed
- `ohub add --type folder` now requires `--name` (the real application name), used to find the matching GitHub repository for updates.
- `_apply_match` records `github_repo` on the app so folder/zip apps chosen from a GitHub release stay linked.

## [0.2.0.0] - 2026-08-13

### Added
- `ohub update` now checks candidate assets the same way `ohub check` does — when no standard installer is found it lists available assets and installs/extracts the chosen one (portable archives are downloaded and extracted).
- `ohub check` candidate-asset selection now actually installs/extracts the chosen asset when an update is available (not just saves the pattern).
- `ohub check --candidates`: for unmanaged apps with no exact repo match, offer a list of candidate GitHub repositories by name and link the chosen one.
- `ohub remove <id|name>`: remove an app or folder from ohub management without uninstalling it (distinct from `ohub uninstall`).
- `ohub add --type folder --recursive`: scan one level into subfolders for applications.
- `ohub add --type folder --repo owner/repo`: link a folder app to a GitHub repository so it can be checked/updated like a managed app.
- Choice memory + reset switch: selections (asset patterns, repo links, unmanaged linking) are remembered in state; `--reset` (on `check`/`update`/`install`) or `ohub remove` forgets them so prompts re-appear.
- `--reset` on `check`/`update`/`install` clears saved choices for re-prompting.

### Fixed
- `ohub update` for apps with only portable/archive assets now offers candidates instead of silently doing nothing.
- Folder apps linked to a GitHub repo (`--repo`) are now checked/updated against that repo.

### Changed
- `InstalledApp` gains a `github_repo` field used to link folder apps to a source repository.

## [0.1.0.14] - 2026-08-13

### Fixed
- `ohub update` crashed on folder-managed apps (`not enough values to unpack`), which aborted the whole update loop before checking anything. Folder apps are now skipped with a clear message.
- `ohub update` / `ohub install` now resolve an app by display name, not just exact id (e.g. `ohub update v2rayN` works).
- `ohub install` download failed with `WinError 183` when the target file already existed. Downloads now overwrite via `os.replace`.
- `ohub check` no longer re-scans all unmanaged system apps every run — only with `--all`. Managed apps are still checked (that's the point of check). Folder apps are skipped cleanly.
- `ohub check` now waits for you to pick a candidate asset when no strict installer is found (interactive; saves the chosen pattern for future updates).
- `ohub add` strips surrounding quotes so folder paths with spaces work (`ohub add "C:\My Apps" --type folder`).
- Self-update check no longer logs a scary `403 Forbidden` error when run without a GitHub token (unauthenticated rate limiting is expected).

## [0.1.0.13] - 2026-08-13

### Fixed
- Version desync: installer (Inno/MWiX) and PyPI metadata now derive from `obtainhub/__init__.py` via `tools/sync_versions.py`, run automatically in the release build. The MSI `ProductVersion` was stuck at `0.1.0.3`, which made `MajorUpgrade` block upgrading from any `0.1.0.x` install ("newer version already installed"). All version surfaces now report the correct release.

## [0.1.0.12] - 2026-08-13

### Added
- `ohub add --type zip <owner/repo>`: manage repositories that only ship archive assets (e.g. archived repos) — the ZIP is downloaded, extracted to a folder, and tracked for updates
- `ohub add --type folder <path>`: track applications inside a local folder (only the folder root is scanned, no recursion)
- `ohub check` / `install` / `update` now list candidate assets when no standard installer is found, and remember the chosen asset pattern for future updates
- Archived / inactive repositories are flagged with a warning during check, install, update, and add

### Changed
- `ohub check` no longer suggests candidate GitHub repositories for unmanaged apps — it only links an EXACT repository name match
- Installer priority is EXE_SETUP (Inno Setup) > MSI > ZIP_INSTALLER; portable archives are now extracted and managed instead of being download-only
- `ohub list` shows app type (github/zip/folder) and install location

### Fixed
- `ohub check` respects managed apps and reports updates/available assets without re-scanning everything every run
- State schema extended with `app_type`, `install_location`, `asset_pattern`, `preferred_asset` (backward compatible)

## [0.1.0.11] - 2026-08-13

### Fixed
- `ohub check`: managed apps now only print when they have an update or available assets; up-to-date apps are silent unless `--all` or `--json` is used
- `ohub check`: unmanaged apps with no exact GitHub match now list candidate repositories for the user to pick from, instead of silently giving up
- `ohub check`: managed apps with no strict installer still list available assets to choose from
- `ohub check`: `--all` re-checks unmanaged apps (ignored/managed/error history respected by default)

## [0.1.0.10] - 2026-08-13

### Added
- CHANGELOG.md for release documentation
- User selection menu when multiple installer assets are available (install/update/check)
- Strict installer priority: EXE_SETUP (Inno Setup) > MSI (WiX) > ZIP_INSTALLER only (ZIP/EXE_STANDALONE no longer auto-selected)

### Changed
- `ohub check` now respects history by default (skips managed/ignored apps, shows from history)
- Asset matcher: `get_best_match` only returns installer types, returns None for ZIP/standalone EXE
- `ohub install/update` now prompts user to select when no strict match but installer options exist

### Fixed
- ZIP files no longer incorrectly selected as installers
- Asset detection: ZIP_INSTALLER requires explicit "setup" or "install" keywords

## [0.1.0.9] - 2026-08-13

### Added
- Detailed `--version` output with homepage and license information
- `--all` flag for `ohub check` to re-check all unmanaged applications
- Asset selection menu when multiple installer assets are available (EXE_SETUP, MSI, ZIP_INSTALLER)
- PATH management during installation (adds to user PATH, HKCU)

### Changed
- Rate limit message now points to `ohub config set github_token <token>`
- `ohub check` now respects previous user choices (managed/ignored) by default
- Installer priority: EXE_SETUP (Inno Setup) > MSI (WiX) > ZIP_INSTALLER > ZIP > EXE_STANDALONE
- ZIP_INSTALLER detection now requires explicit "setup" or "install" keywords

### Fixed
- Inno Setup 6.7 compatibility (removed CurUninstallStepChanged)
- GitHub API rate limit handling and messaging

## [0.1.0.8] - 2026-08-12

### Added
- Inno Setup installer with PATH management
- WiX MSI installer support
- Uninstall data prompt (kept/removed config files)
- Check history persistence in state.json

### Changed
- Version bump to 0.1.0.9 (stable, removed beta)

## [0.1.0-beta.8] - 2026-08-11

### Added
- Check history for unmanaged applications
- Installer selection when multiple assets available
- Enhanced asset matching with ZIP_INSTALLER type

### Changed
- Asset priority: EXE_SETUP > MSI > ZIP_INSTALLER > ZIP > EXE_STANDALONE

## [0.1.0-beta.7] - 2026-08-10

### Added
- GitHub API rate limit handling
- Custom config sources support
- Prerelease support for check/install/update

### Fixed
- Search case-insensitive matching
- Active-only repository filtering

## [0.1.0-beta.6] - 2026-08-09

### Added
- `ohub search` command with filters (--min-stars, --active-only)
- `ohub list --all` to show system-installed apps
- `ohub self-update` command

## [0.1.0-beta.5] - 2026-08-08

### Added
- Silent installer support (Inno Setup, MSI, NSIS, WiX)
- Download with SHA256 verification
- State management with update history

## [0.1.0-beta.4] - 2026-08-07

### Added
- `ohub check` for update checking without installing
- Unmanaged system app detection
- GitHub repository search and auto-add

## [0.1.0-beta.3] - 2026-08-06

### Added
- `ohub install` and `ohub update` commands
- Asset matching for Windows x64 installers
- Configuration management (GitHub token, sources)

## [0.1.0-beta.2] - 2026-08-05

### Added
- Initial CLI structure
- GitHub client with token authentication
- Release fetching and asset matching

