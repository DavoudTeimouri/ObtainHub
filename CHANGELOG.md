# Changelog

All notable changes to ObtainHub will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
### Changed
### Fixed
### Removed

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
