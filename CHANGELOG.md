# Changelog

All notable changes to ObtainHub will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

