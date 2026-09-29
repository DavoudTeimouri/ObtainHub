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