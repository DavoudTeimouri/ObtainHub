# Changelog

All notable changes to ObtainHub will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.10] - 2026-09-29

### Added
- Config backup/restore commands (`ohub config backup`, `ohub config restore`)
  - Backup config and state to zip file with optional downloads folder
  - Restore from zip with custom target directories
  - Option to exclude GitHub token from restore (`--no-token`)
- Apps backup/restore commands (`ohub apps backup`, `ohub apps restore`)
  - Backup application folders from download directory to zip
  - Selective backup/restore by app identifier
  - Dry-run mode to preview changes
  - Custom target directory for restore
- Cleanup command (`ohub cleanup`)
  - `all` — run all cleanup operations
  - `tasks` — remove orphaned scheduled tasks (Windows Task Scheduler / cron)
  - `downloads` — remove incomplete downloads (.part files)
  - `cache` — clean old manifest cache entries (older than 30 days)

## [1.0.9] - 2026-09-29

### Added
- Backup rotation system with configurable retention (`backup_retention_count`, default 2, range 1-10)
- Self-uninstaller command (`ohub self-uninstall`) with backup/restore to zip
  - `--backup PATH` — create backup zip before uninstalling
  - `--include-downloads` — include download folder in backup
  - `--force` / `-y` — skip confirmation prompt
  - `--restore PATH` — restore from backup zip
  - `--target-config/state/downloads DIR` — custom restore paths
  - `--no-token` — don't restore GitHub token to keyring
- Config backup/restore utilities in `obtainhub/utils/backup.py`

### Fixed
- `config repair` now preserves GitHub token from keyring
- `config move` correctly persists new config/state locations
- Removed duplicate `_is_self_app` function
- Config validation error message for `backup_retention_count`

### Changed
- `ohub config` (no subcommand) now shows full configuration with `--json` option
- Release assets: only ObtainHub-Setup.exe and ObtainHub.msi (standalone ohub.exe removed)

## [1.0.8]
### Fixed
- shutil import issue in `ohub config repair` command causing "cannot access local variable 'shutil'" error
- `ohub config` (no subcommand) now shows configuration validity/status instead of empty output
- Release assets now include only ObtainHub-Setup.exe and ObtainHub.msi (standalone ohub.exe removed)

## [1.0.7]
### Fixed
- Config import missing in reset function
- Stray backslashes in main.py
- Config.load returns defaults when file missing
- New config commands (path, move, repair)

## [1.0.6] - 2026-09-20

### Added
- Secure GitHub token storage using system keyring (service=`obtainhub`, username=`github_token`). Plain text token in config is migrated to keyring on first load.
- New `ohub reset` command to backup state and config, then reset to defaults. Flags: --backup <path>, --keep-token, --move-token <path>.

### Changed
- Updated changelog template to match the style of v0.7.6 entries (clear sections, consistent styling).
- Improved reset command to handle token in keyring appropriately.

### Fixed
- Duplicate prerelease warning block in `cmd_install()` (main.py) that caused redundant user prompts.
- Version consistency across all files (now 1.0.6).

## [1.0.5] - 2026-09-20
### Changed
- Updated changelog template to match the style of v0.7.6 entries (clear sections, consistent styling).

## [1.0.4] - 2026-09-20
### Fixed
- Removed duplicate prerelease warning block in `cmd_install()` function (main.py) that caused redundant user prompts.

## [1.0.3] - 2026-09-17
### Added
- Notifier plugin for desktop notifications (plyer)
- State export/import commands
- Package manager fallback (Winget, Scoop, Chocolatey)
- Hooks system for plugins
- Groups feature for organizing applications
- Plugin system with marketplace and dependency resolution
- Architecture preferences per application
### Changed
- Enhanced self-update mechanism with cross-platform support
- Improved CLI with dry-run flag for more commands
- Better asset matching with user-definable preferences
- Diagnostic tools (`ohub doctor`)
- Security improvements (GPG signature verification, sandboxed plugins)
- User experience enhancements (progress bars, better error messages)
### Fixed
- Version tag mismatch across files
- Inno Setup conflict resolution
- TUI dependency bundling in installers
- CHANGELOG format consistency

## [1.0.2] - 2026-09-12
### Added
- Scheduled background checks (`schedule` command)
- Plugin system scaffold
- Async update placeholder
- Notifier plugin
- CI workflow with GPG signing and TUI verification
### Changed
- Version bumped to 1.0.2
- README rewritten with all features
- Changelog automation script
- Constants extraction and type hints
- Help text updated to show all commands
### Fixed
- Test failures in `test_github_client.py`
- Indentation errors in test fixtures
- Main.py corruption during async update edit
- Git push resolution (separate tag push)
- CHANGELOG v1.0.2 entry detail

## [1.0.1] - 2026-09-05
### Added
- Multi-arch support (`--arch` flag)
- State export/import
- Package manager fallback
- Hooks system
- Groups feature
### Changed
- Version bumped to 1.0.1 across all files
- Embedded TUI dependencies in PyInstaller
- CHANGELOG format following Keep a Changelog
- Inno Setup conflict resolution (`CloseApplications=yes`, etc.)
- Help text updated for new commands
### Fixed
- Version tag mismatch (1.0.0 → 1.0.1)

## [1.0.0] - 2026-09-01
### Added
- Initial release of ObtainHub CLI
- GitHub app search and installation
- Update checking and self-update
- Portable app support (ZIP)
- Basic state management
