# Changelog

All notable changes to ObtainHub will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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