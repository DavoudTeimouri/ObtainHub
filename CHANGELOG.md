# Changelog

All notable changes to this project will be documented in this file.

## [v3.0.3] - 2026-10-09
### Fixed
- Mutual refusal was dead code in both directions.
  - NSIS looked for the MSI under `Uninstall\{UpgradeCode}`, but Windows Installer
    registers under the ProductCode and `setup.wxs` uses `Id="*"`, so that key
    holds a different GUID on every build. NSIS now detects the MSI through its
    stable marker `HKLM\Software\ObtainHub\PathInstalled`, and clears that
    marker on uninstall.
  - The MSI searched `Uninstall\{...}_is1`, but NSIS only appends `_is1` when the
    app id is not already a GUID. The key never existed, so the search could not
    match. Fixed the key and restored the launch Condition.
- `check --all` sent every installed Windows program's `DisplayName` to the GitHub
  releases API. `NVIDIA Corporation` is not `owner/repo`, so every lookup 404'd
  and the request volume exhausted the unauthenticated rate limit. Only programs
  tracked in `state.json` are now queried; the rest are reported as skipped.
- Silent-install conflict handling never compiled: `StrCmp $Silent 1` was rejected
  as an unknown variable, so the auto-uninstall-MSI and upgrade-in-place branches
  were silently dropped. Replaced with the `IfSilent` instruction.

### Changed
- NSIS installer now builds with zero warnings (was 2).

## [v3.0.1] - 2026-10-09
### Fixed
- MSI build: `installer/setup.wxs` was missing `Platform="x64"`, so ICE80 rejected
  the package (LGHT0204) because `PathEnvironment` and `MainExecutable` are both
  `Win64="yes"`. Removed the 32-bit `RegistrySearch` too — a 64-bit package cannot
  carry a 32-bit Locator (LGHT1076).
- Zip-slip: `install.rs` joined attacker-controlled zip entry names onto the
  install directory without validation, so an entry named `../../evil.exe` wrote
  outside it. Reachable via `install` and `install --url`, which fetch archives
  from the internet. `update.rs` had the same hole through `archive.extract()`.
  Both now normalize the path through `Path::components()` before the containment
  check, with three tests covering parent traversal, absolute paths, and normal
  entries.
- `uninstall --purge` now drops the repository's state metadata and its membership
  in any group, instead of printing "not yet fully implemented".
- `update` installs to `config.install_dir` instead of a hardcoded
  `ObtainHub/repos` path, so a custom install directory is respected.
- `ohub completion` no longer panics on a broken pipe (`ohub completion fish | head`).
- Config values that would hang or divide by zero (`parallel_downloads`,
  `timeout_seconds`, `update_check_interval_hours`, `schedule.interval_hours`)
  are reset to defaults on load and on save.

### Added
- `PROJECT.md`: living reference for installer invariants, GUID requirements,
  filesystem layout, config contract, and security posture.
- `CONTRIBUTING.md`: build, test, installer, and release procedure.
- README: examples for every major command; corrected config path.

## [v3.0.0] - 2026-10-08
### Added
- Complete rewrite from Python to Rust (ObtainHub-rs merged into main)
- Rust 1.85+ binary with zero-cost abstractions and memory safety
- 25 commands: search, install, update, check, list, uninstall, doctor, info, readme, license, releases, workflows, issues, topics, stats, config, auth, completion, version, help, self-update, state, backup, restore, apps, cleanup, tui, group, shim, schedule
- GitHub-native features: stars, topics, releases, readme, license, issues, workflows
- Windows installers: MSI (WiX v3) and NSIS EXE (NSIS 3.13), both machine-wide, admin-only
- Unified icon (installer/icon.ico) used for MSI, NSIS EXE, and embedded in ohub.exe
- Installer UX: NSIS detects existing MSI/EXE and prompts Uninstall/Upgrade/Cancel; silent mode auto-handles
- Mutual refusal: MSI blocks EXE install, EXE blocks MSI install via shared GUID
- PATH management: exact add/remove semantics for user scope
- `ohub check --all` enumerates all installed software from Windows registry and skips ObtainHub itself
- No standalone binary: only MSI and NSIS EXE published to releases
- Self-contained: no .NET, VC++ redist, or Python required
- Configuration: `%APPDATA%\\ObtainHub\\state.json`
- Changelog per release (this file)

### Fixed
- NSIS installer corruption: replaced `/SOLID LZMA` with per-file LZMA/zlib and CRCCheck on to avoid CRC bug
- MSI build: removed unsupported `Platform` and `Schedule` attributes from WiX XML
- Missing imports in TUI modules: `anyhow::Result` in `src/tui/mod.rs`; `ratatui::Frame`, `ratatui::Terminal`, `ratatui::backend::CrosstermBackend` in `src/commands/tui.rs`; `tracing::subscriber::registry` in `src/core/logger.rs`
- Dependency compilation hang: removed `build.rs` workaround, cleaned Cargo.toml, used offline builds with proper target directory
- Silent mutual refusal: EXE and MSI both respect `/S` flag for silent uninstall during conflict resolution

### Changed
- ObtainHub-rs repository deleted after migration (code now in main repo)
- Build process: uses `cargo build --release --target x86_64-pc-windows-gnu` for Windows binaries
- Installer scripts: NSIS uses zlib compression with CRC; WiX uses standard heat/candle/light
- Version: bumped to 3.0.0 for major rewrite

### Removed
- Standalone ohub.exe from releases (only installers)
- Python implementation and related scripts
- ObtainHub-rs submodule/repository

