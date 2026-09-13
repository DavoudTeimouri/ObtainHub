# ObtainHub Feature Plan

## 1. Scheduled background checks + notifications
- Add `ohub schedule` subcommand: enable/disable/status Windows Task Scheduler job
- Store last_check timestamp in state
- Toast notifications via win10toast / plyer (Windows) or notify-send (Linux)
- Config: check_interval_hours, notify_on_update

## 2. Multi-arch asset tracking
- Add --arch flag to install/update/check (x64/arm64/x86/auto)
- Per-app arch_preference in InstalledApp
- AssetMatcher already supports allow_arm64/allow_x86_fallback

## 3. SHA256 verification from release notes
- Parse release.body for SHA256 patterns (checksums.txt, .sha256 files, inline)
- Auto-match asset name to checksum
- Fail download on mismatch, warn on missing

## 4. App groups / profiles
- New subcommand: `ohub group <add|remove|list|install|update> <name>`
- Groups stored in config.json (manifest_sources style)
- Install/update all apps in group

## 5. Winget/Scoop/Chocolatey fallback source
- New source type: "winget", "scoop", "chocolatey"
- Query via CLI (winget search, scoop search, choco search)
- Normalize to SourceAppEntry

## 6. Pre/post install scripts
- ManifestSource supports hooks: {pre_install, post_install, pre_uninstall, post_uninstall}
- Commands run in app install_location with env vars (OHUB_APP_ID, OHUB_VERSION, etc.)

## 7. Portable app shims
- New subcommand: `ohub shim <app>` creates .exe shim in ~/bin or config.shim_dir
- Shim launches actual exe with same args
- `ohub shim --list`, `ohub shim --remove`

## 8. Release notes preview
- `ohub check --notes` shows release.body diff since current version
- Truncate long bodies, link to full release

## 9. Bulk state export/import
- `ohub state export [file]` → JSON of all apps
- `ohub state import [file]` → add/update apps, dry-run flag

## 10. TUI dashboard
- New dependency: textual
- `ohub tui` launches interactive app
- Panels: app list (managed/unmanaged), details, log
- Keys: j/k navigate, Enter check, u update, i install, q quit

---
Start with 1, 2, 3, 7, 8, 9 (lower effort, high value)