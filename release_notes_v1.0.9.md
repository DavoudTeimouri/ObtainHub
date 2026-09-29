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