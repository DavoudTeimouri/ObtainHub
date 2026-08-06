# Changelog

All notable changes to ObtainHub are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.1.0-beta.1] - 2026-08-03

### Added
- **Windows x64 Native Installer Support**
  - Inno Setup based `ObtainHub-Setup.exe` installer (pure CLI - no desktop shortcuts, no launch prompts)
  - Python `msilib` based `ObtainHub.msi` installer (stdlib, no WiX dependency)
  - Both installers support silent installation (`/VERYSILENT` for EXE, `/qn` for MSI)
- **CLI Command Suite**
  - `ohub search <query>` - Search GitHub repositories via GitHub Search API (`/search/repositories`)
  - `ohub install <owner/repo>` - Install apps from GitHub Releases with asset matching
  - `ohub update [owner/repo]` - Update installed apps sequentially
  - `ohub check [owner/repo]` - Check for updates without installing (table/JSON output)
  - `ohub list` - Display installed apps in terminal table or JSON
  - `ohub uninstall <owner/repo>` - Uninstall apps with optional data retention
  - `ohub self-update` - Self-update ObtainHub itself
  - `ohub config` - Manage configuration
  - `ohub source` - Manage custom GitHub/manifest sources
- **Asset Matching & Selection**
  - Architecture priority: x64 > ARM64 > x86 (ARM64/x86 only if explicitly allowed)
  - Installer priority: MSI > Setup.exe > ZIP
  - Exclusion filters for checksums, signatures, non-Windows packages
  - Download-only fallback for portable `.zip` releases
- **Prerelease Handling**
  - Mandatory user confirmation prompts for prerelease versions
  - `--prerelease` flag to opt-in
  - `--yes` flag to auto-confirm prompts
- **State Management**
  - Tracks installed apps in `state.json` with version, installer type, paths, timestamps
  - Records download history and update checks
  - Manual uninstall detection fallback

### Changed
- Removed desktop shortcut generation from Inno Setup installer
- Removed "Launch Application" checkbox from setup wizard final screen
- Updated build pipeline to produce both `ObtainHub-Setup.exe` and `ObtainHub.msi`
- Moved from WiX-based MSI to Python stdlib `msilib` for MSI generation
- Updated GitHub Actions workflow to build and upload all three artifacts

### Fixed
- PyInstaller spec file path handling for cross-platform compatibility
- Asset matcher architecture detection (ARM64 before X64, word boundaries for "64")
- State manager API consistency (`add_installed_app`, `get_installed_app`, `get_all_apps`, `get_app`)
- Self-updater `check_and_update` parameter handling and constructor signature
- **Method signature mismatches resolved**: `AssetMatcher.__init__` now accepts `require_installer`, `SelfUpdater.__init__` accepts `config_manager`, `state_manager`, `current_version`
- **CLI search enhancements**: Added `--min-stars` flag and case-insensitive search by default, results sorted by stars descending
- All 121 unit tests passing

### Security
- GitHub token stored in config file (not in code)
- Optional token via `GITHUB_TOKEN` environment variable
- Rate limit handling with automatic backoff

### Known Limitations
- Windows x64 only (no cross-platform support)
- No ARM64 native builds (explicitly rejected by default)
- Manual uninstall required for apps installed outside ObtainHub
- ZIP assets are download-only (no auto-install)

---

## [Unreleased]

### Planned
- Manifest-based custom sources
- Auto-uninstall attempt for manual uninstall cases
- Progress bar for downloads
- Parallel update checks for multiple apps
- Shell completion scripts (PowerShell, Bash)