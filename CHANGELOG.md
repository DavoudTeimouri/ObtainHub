# Changelog

All notable changes to ObtainHub will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.2] - 2026-10-03

### Fixed

- The EXE and MSI installers could be installed over each other, leaving two
  entries in Apps & Features and two half-working uninstallers for the same
  folder. Each installer now detects the other and refuses to run when it is
  already installed, so install one or the other, never both.
- The MSI used `Product Id="*"`, which made Windows Installer generate a new
  ProductCode on every build. Upgrades and repair could not match the installed
  product, so `MajorUpgrade` was unreliable. The ProductCode is now pinned to
  the UpgradeCode GUID.
- `PATH` entries are now compared as whole entries. A folder merely ending in
  `ObtainHub` (for example `C:\Tools\ObtainHubBackup`) no longer suppresses the
  real entry, and uninstalling removes the entry it added.

### Changed

- `README.md` install section now states the installers are machine-wide and
  install to `C:\Program Files\ObtainHub`. Earlier wording wrongly described a
  per-user install under `%LOCALAPPDATA%`.

## [2.1.1] - 2026-10-03

### Changed
- **No Start-menu or desktop shortcut.** `ohub` is a console tool: launched with no arguments it
  prints its help and exits, so a shortcut only flashed a console window and closed it. Both
  installers now create no shortcuts at all. The install folder is still added to `PATH`; the
  README documents running `ohub` from a terminal and by full path.
- README gained an Install section (both release assets, install location, the `PATH` caveat) and a
  Run and use section covering search/install, global flags, self-update, backup and restore,
  sources, cleanup and reset.

## [2.1.0] - 2026-10-03

### Fixed
- **Zip Slip in archive extraction (security).** A release ZIP with a member like
  `wrapper/../../evil.exe` escaped the extraction folder and wrote wherever the path pointed.
  This ran on every downloaded release archive, so the archive was attacker-controlled. Every
  member is now validated to resolve inside the destination before anything is written, and a
  hostile archive is rejected with a clear error instead of landing files somewhere unexpected.
- **Remote manifests could run commands on your machine (security).** A manifest source's
  `hooks` field was copied straight into the app entry, so any JSON manifest you added could set
  a `pre_install` hook and have it execute with your privileges. Hooks are now read only from your
  own source configuration, never from fetched content.
- **Log files now scrub GitHub tokens.** A `SecretRedactionFilter` sits on the root logger and
  redacts token-shaped values (`ghp_`, `github_pat_`, `token ...`, `Bearer ...`) from log messages
  and their arguments, so a credential cannot be persisted to disk even if a future call site
  logs a request header.
- **`ohub config restore` no longer crashes.** It passed the wrong keyword argument names to
  `SelfUninstaller.restore_from_zip()`, which raised `TypeError` on every invocation — disaster
  recovery was completely unusable. The correct `target_config_dir` / `target_state_dir` /
  `target_download_dir` arguments are now passed and a restore completes.
- **`ohub tui` no longer crashes on startup.** The dashboard refresh called three APIs that do
  not exist (`AssetMatcher.find_best_asset`, `Config.include_prerelease`, `Config.architecture`),
  passed a single combined string to a three-argument `get_latest_release()`, and read
  attributes off plain dictionaries. It now splits `owner/repo`, uses the real
  `get_best_match` entry point, and reads the release payload as a dict. The dashboard renders.
- **Installed-app inventory is no longer at risk of being erased.** `state.json` was written by
  truncating the live file first, so an interrupt during the write left a truncated file that the
  loader silently read as "nothing is installed". Saves are now atomic (temp file + rename, with
  temp cleanup on failure), matching how `config.json` has always been written.
- **`ohub uninstall` self-protection actually works.** The guard that stops `ohub` from
  uninstalling itself was handed the state manager instead of the app, so every attribute lookup
  returned empty and the check silently passed everything through. It now receives the resolved app.
- **GitHub API calls no longer hang indefinitely.** Four requests were missing a timeout while
  their siblings had one. All six session calls now use a finite timeout, so a stalled connection
  surfaces an error instead of blocking the command forever.
- **A malformed `Content-Length` header no longer kills a download.** The header was converted
  with a bare `int()`; a proxy or hostile server returning anything non-numeric raised `ValueError`
  and failed the transfer permanently. Sizes are now parsed defensively and an unusable value is
  treated as unknown rather than fatal.
- **Start-menu shortcut pointed at the wrong path.** The WiX shortcut target was
  `[INSTALLFOLDER]ohub.exe` with no directory separator, so the Start-menu entry could not launch
  the app.
- **Build provenance was skipped while reporting success.** The provenance job downloaded its
  artifacts to the repository root and then guarded on `dist/` paths, which never exist after a
  download, so all three attestation steps were skipped and the job still went green. It now
  downloads the installer and SBOM artifacts to `artifacts/` and guards on those real paths.

### Known issues
- **The Inno Setup (EXE) installer still matches `PATH` by substring.** An unrelated folder such as
  `C:\Tools\ObtainHubBackup` can suppress the installer's own `PATH` entry, and uninstalling leaves
  that entry behind. A fix was attempted and reverted: the ISCC build step failed and the
  available credentials could not read the build log to diagnose it, so the change was rolled back
  rather than shipped unverified. `installer/setup.iss` is byte-identical to the version that
  shipped in 2.0.0. The MSI installer is unaffected.

### Changed
- Release assets are exactly `ObtainHub.msi` and `ObtainHub-Setup.exe`. The generated
  `ObtainHub-sbom.json` is still produced and attested internally as a CI artifact and provenance
  subject, but is no longer published as a user download, matching every prior release.

## [2.0.0] - 2026-09-30

### Added
- **Plugin sandbox with capability grants.** `obtainhub/plugins/sandbox.py` enforces declared
  filesystem, network, subprocess, config and state capabilities and fails closed outside them.
  `sandbox_runner.py` executes plugin commands in an isolated child process, `manifest.py` verifies
  SHA256-signed manifests against a local trusted-key store, and `registry.py` adds
  `PluginRegistry` / `LocalPluginManager`. Third-party discovery hook is
  `[project.entry-points."obtainhub.plugins"]` in `pyproject.toml`. A worked manifest ships at
  `obtainhub/plugins/example.yaml`.
- **`ohub config auth [--token-source auto|keyring|env|file|plaintext-keyring]`.** Reports which
  credential store holds the GitHub token and whether it is protected at rest. Emits JSON when piped
  and a readable table on a TTY, with an explicit warning when the backend stores secrets in
  plaintext.
- **Hexagonal ports and adapters.** `obtainhub/ports/` declares the ABC contracts
  (`RepositorySource`, `StateStore`, `Downloader`, `Installer`, `SystemScanner`,
  `AssetMatcherPort`, `EventBus`) and DTOs; `obtainhub/adapters/` holds `GitHubAdapter`,
  `JsonStateStore` and an in-memory `core/event_bus.py`. Dependencies point inward only.
- **Scriptable CLI.** Global `--json` and `--quiet` plus per-command `--dry-run` and `--force`
  across the argparse tree, so every subcommand can run unattended without parsing human output.
- **Shell completion** for `scripts/ohub.bash-completion`, including `config auth` completion
  and the full config key list for `config set`/`get`.
- **Build and supply-chain hardening.** `ObtainHub.spec` builds an `--onedir` distribution with
  high-entropy ASLR, DEP, NXCOMPAT and CFG; UPX is gated behind `OBTAINHUB_SIGNED_BUILD=1`
  because it rewrites sections that code-signing rejects. Both installers now package
  `dist/ohub/` recursively.
- **CI/CD maturity.** The release pipeline is split into `typecheck` (mypy), `security-audit`
  (pip-audit, JSON report retained 30 days), `build` (PyInstaller to WiX MSI with an ICE60 check to
  Inno Setup EXE to CycloneDX SBOM), `smoke-test`, `provenance` and `release`. Gates run with
  `continue-on-error` so a new warning never blocks a tagged release.

### Changed
- **Building on a plaintext credential backend is now an error, not a silent write.** `keyring`
  falls back to `keyrings.alt.file.PlaintextKeyring` on any machine without an OS credential store
  and the old code reported success while writing the token unencrypted to disk. `ConfigManager.save()`
  now refuses and names the remedy; export `GITHUB_TOKEN` to keep the secret out of any file.
- **`ohub config show` and `ohub config get github_token` redact the token** to
  `<set, N chars, hidden>` instead of printing it, and `ohub config set github_token` no longer
  echoes the value. This removes the secret from terminals, CI logs and shell history.
- **Backups no longer carry the token.** `ohub config backup` and the self-uninstaller previously
  wrote the live token into `metadata.json` inside the zip; backup archives are copied around and
  often land in cloud storage. `ohub config restore` re-reads the token from the credential store.

### Fixed
- **`ohub config backup`, `ohub config restore` and `ohub self-uninstall` failed outright** with an
  `IndentationError` in `core/self_uninstall.py`, which made the module unimportable.
- **`ohub config backup` raised `UnboundLocalError` on `shutil`**, shadowed by a local import in the
  same function.
- **`ohub config backup` raised `NameError: __version__`**, which was never imported in `main.py`.
- `self_uninstall.create_backup_zip` had the same unindentation and the same plaintext token leak in
  its `metadata.json`, so a self-uninstall backup carried the secret even after the config-backup path
  was fixed.

## [1.0.12] - 2026-09-30

### Changed
- `ohub update` now delegates self-updates to the SelfUpdater mechanism when detecting ObtainHub itself
  - Uses detached silent installer (Inno EXE or MSI) with `/VERYSILENT` / `/quiet` flags
  - Auto-exits ohub so the installer can replace the running executable
  - Consistent behavior with `ohub self-update` command

## [1.0.11] - 2026-09-30

### Fixed
- `arch_preference` not defined error when updating folder/zip apps without explicit CLI `--arch` flag
  - `_apply_match` now properly reads `arch_preference` from app state when CLI arch is "auto" (default)

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

## [1.0.8] - 2026-09-29

### Fixed
- shutil import issue in `ohub config repair` command causing "cannot access local variable 'shutil'" error
- `ohub config` (no subcommand) now shows configuration validity/status instead of empty output
- Release assets now include only ObtainHub-Setup.exe and ObtainHub.msi (standalone ohub.exe removed)

## [1.0.7] - 2026-09-20

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
