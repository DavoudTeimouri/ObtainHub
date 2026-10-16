# Changelog

All notable changes to this project will be documented in this file.

## [v3.0.25-rc1] - 2026-10-13
### Added
- `ohub search` now shows interactive selection - select repos from search results, then add to managed list or install immediately
- `ohub install` falls back to GitHub search when exact repo not found, offers interactive selection of candidates
- `ohub update` auto-detects unmanaged apps on the system and offers to add them as managed repositories before updating
- `ohub check --all` shows sorted list of unmanaged apps, then after confirming selections offers candidate repositories for each

### Fixed
- `ohub install` no longer fails with "missing field tag_name" when registry API omits tag_name - now defaults to "unknown"
- `ohub self-update` lists available assets with manual download URL when no platform-specific zip found

## [v3.0.24-rc1] - 2026-10-13
### Fixed
- `ohub self-update` no longer bails with "No suitable release asset found" when no platform-specific zip exists - now lists available assets and provides manual download URL
- `ohub self-update` falls back to any asset when no platform-specific zip found

## [v3.0.23-rc1] - 2026-10-13
### Fixed
- `ohub check --candidates` now shows ALL unmanaged apps with candidate repositories found via GitHub search
- `ohub check --candidates` cleans app names (strips version numbers like " V3 3.8.6") for better GitHub search results
- `ohub check --candidates` allows manual `owner/repo` entry when no candidates found
- `ohub check --candidates` falls through to show check results for newly added repos

## [v3.0.22-rc1] - 2026-10-13
### Fixed
- `ohub check --all` 404 - `fetch_latest_release` returns `Option<GitHubRelease>`, skips repos without releases gracefully
- `ohub check --candidates` no longer returns early - falls through to show check results for newly added repos
- `ohub update` 404 - same `Option<GitHubRelease>` handling with retry logic
- `ohub tui` now fetches latest versions from GitHub, shows Current/Update/Unknown/Unmanaged status
- `ohub tui` 'r' key actually refreshes app list from GitHub

### Added
- Retry logic for `ohub update` (configurable via http_retries, http_retry_delay_ms, http_retry_backoff)

## [v3.0.21-rc1] - 2026-10-13
### Added
- `ohub add --type folder` - manage portable applications from local folders
- Folder mode scans for executables (.exe on Windows, executable permission on Unix)
- `--recursive` flag for subdirectory scanning
- `--repo-arg` to link folder app to a GitHub repo for updates
- Creates shims in shim_dir for each executable found
- Adds each executable to state.json for tracking
- Shows PATH instructions for using apps from anywhere

## [v3.0.20-rc1] - 2026-10-13
### Added
- `ohub add --type folder` - manage portable applications from local folders
- Folder mode scans for executables (.exe on Windows, executable permission on Unix)
- `--recursive` flag for subdirectory scanning
- `--repo-arg` to link folder app to a GitHub repo for updates
- Creates shims in shim_dir for each executable found
- Adds each executable to state.json for tracking
- Shows PATH instructions for using apps from anywhere

## [v3.0.19-rc1] - 2026-10-13
### Fixed
- Self-update 404 - falls back to releases list, then tags when no releases published
- Check command: `fetch_latest_release` returns `Option<GitHubRelease>` - no longer errors on 404, skips repos without releases gracefully
- Check command: `--candidates` shows ALL unmanaged apps (not just those with candidates), lets user choose both software AND candidate repository
- Add command: verifies GitHub repository exists before adding to management

### Added
- Retry logic for `ohub add` repository availability check
- Configurable retry via `http_retries`, `http_retry_delay_ms`, `http_retry_backoff` in config

## [v3.0.18-rc1] - 2026-10-13
### Added
- CLI message templates module for consistent output formatting
- Version templates with build metadata (timestamp, rustc version, git info)
- Build script emits vergen-compatible constants without external dependency
- Error/Warning/Info/Success message templates
- Progress/Status templates for long-running operations
- Repository info, install result, update availability templates
- Search result, list item, uninstall confirmation templates
- Rollback info, config, dry run templates

### Fixed
- Version output uses standardized template
- Build constants generated without vergen dependency (Rust 1.85 compatible)

## [v3.0.17-rc1] - 2026-10-13
### Fixed
- Self-update 404 - fixed GitHub API endpoint (ObtainHub repo name case)
- Check command: `--all` no longer 404s on ObtainHub's own repo (skipped during check)
- NSIS installer detects installed version and offers upgrade/uninstall options
- Colors: Only green removed - uses terminal default colors everywhere

### Added
- More informative output - detailed progress/info messages for all operations
- Check command: Shows "Checking ObtainHub self-update..." before self-update check
- Check command: Shows "Checking N managed repositories for updates..."
- Check command: Shows "Scanning Windows registry for installed programs..."
- NSIS installer: Displays installed version vs new version in conflict dialogs
- Uses terminal default colors - no custom color overrides

## [v3.0.16-rc1] - 2026-10-13
### Fixed
- Self-update check 404 - fixed GitHub API endpoint and added retry logic
- Check command: `--candidates` now shows all unmanaged apps with their candidate repositories
- Check command: `--all` now shows all unmanaged apps with interactive selection
- Colors: Only green for selection checkboxes/ticks, default color for all other text
- Added retry logic for all HTTP requests, configurable via config (http_retries, http_retry_delay_ms, http_retry_backoff)
- More informative output - progress bars for scanning and candidate searching with detailed messages
- Self-update check now uses retry config and proper error handling

### Added
- Progress bars for scanning installed programs and finding candidates
- Green tick marks and gray checkboxes in interactive MultiSelect
- Interactive `--all` offers selectable list for unmanaged apps
- Interactive `--candidates` offers selectable list to add apps to management
- After selecting app, immediately checks candidates and offers repository selection
- Added `dialoguer`, `console`, `indicatif` dependencies for interactive prompts and progress bars
- Retry configuration in config.json (http_retries=3, http_retry_delay_ms=1000, http_retry_backoff=2.0)

## [v3.0.15-rc1] - 2026-10-13
### Added
- Check command: Removed timestamp from command output (clean output)
- Check command: Progress bars for scanning and candidate searching
- Check command: Green tick marks and gray checkboxes in interactive selection (MultiSelect)
- Check command: Interactive `--all` offers selectable list for unmanaged apps
- Check command: Interactive `--candidates` offers selectable list to add apps to management
- Check command: After selecting app, immediately checks candidates and offers repository selection
- Added `dialoguer`, `console`, `indicatif` dependencies for interactive prompts and progress bars

### Fixed
- Check command: `--candidates` works independently of `--all`
- Check command: Shows candidate repositories for unmanaged apps with GitHub search
- Check command: Self-update check when no specific repo specified
- Check command: `--quiet` flag to suppress non-error output
- NSIS "Installer corrupted: invalid opcode" - pinned NSIS 3.11 with SourceForge fallback
- NSIS PathHasEntry Exch → Push fix for NSIS 3.13 stack-exchange bug

## [v3.0.14-rc1] - 2026-10-13
### Added
- Check command: `--all` now offers interactive selectable list for unmanaged apps
- Check command: `--candidates` now offers interactive selection to add apps to management
- Check command: After selecting app, immediately checks candidates and offers repository selection
- Added `dialoguer` and `console` dependencies for interactive prompts

### Fixed
- Check command: `--candidates` works independently of `--all`
- Check command: shows candidate repositories for unmanaged apps with GitHub search
- Check command: self-update check when no specific repo specified
- Check command: `--quiet` flag to suppress non-error output

## [v3.0.13-rc1] - 2026-10-13
### Fixed
- Check command: `--all` now checks unmanaged apps by finding GitHub repos by name
- Check command: `--candidates` now works independently of `--all`
- Check command: shows candidate repositories for unmanaged apps with GitHub search

## [v3.0.12-rc1] - 2026-10-12
### Fixed
- Check command: added self-update check when no specific repo specified
- Check command: added `--candidates` flag to find GitHub repos for unmanaged apps
- Check command: added `--quiet` flag to suppress non-error output

## [v3.0.11-rc1] - 2026-10-12
### Fixed
- NSIS "Installer corrupted: invalid opcode" — replaced `Exch $R0` with `Push $R0` in `PathHasEntry` / `un.PathHasEntry` to avoid NSIS 3.13 stack-exchange bug triggered by compiler optimization `+2`

## [v3.0.10-rc1] - 2026-10-12
### Fixed
- NSIS "Installer corrupted: invalid opcode" — replaced `Exch $R0` with `Push $R0` in `PathHasEntry` / `un.PathHasEntry` to avoid NSIS 3.13 stack-exchange bug triggered by compiler optimization `+2`

## [v3.0.9-rc1] - 2026-10-12
### Added
- RC build for v3.0.9 with all v3.0.8 features
### Fixed
- NSIS pinned to 3.11 with SourceForge fallback (fixes "Installer corrupted: invalid opcode")

## [v3.0.8-rc1] - 2026-10-12
### Added
- RC build for v3.0.8 with all v3.0.7 features
### Changed
- NSIS pinned to 3.11 with SourceForge fallback
- Updated CHANGELOG for RC release

## [v3.0.7-rc2] - 2026-10-11
### Fixed
- The NSIS installer failed on Windows with "Installer corrupted: invalid
  opcode" before showing any dialog. v3.0.4 and v3.0.5 were both built with
  NSIS 3.13, which winget installs by default. The published file was not
  corrupt in transit: its SHA-256 matched the published `SHA256SUMS`, the MZ
  header was intact, the `NullsoftInst` magic sat at the expected offset, and
  the sizes matched what CI built. The fault was in how 3.13 emitted this
  script.
- The build toolchain was unpinned. `winget install NSIS.NSIS` resolves to
  whatever "latest" is, so the NSIS version could change between runs with no
  diff to review. NSIS is now pinned to 3.11, the installer download is
  verified by SHA-256 before use, and the build asserts `makensis -VERSION`
  reports 3.11 before running.

### Changed
- The release job now checks out the repository. It previously ran the
  changelog extraction against an empty workspace, so
  `awk: cannot open file 'CHANGELOG.md'` failed every release.

### Notes
- This is a release candidate. Install `ObtainHub-Setup.exe` and confirm it
  completes before v3.0.6 is cut.

## [v3.0.5] - 2026-10-09
### No changes — this tag exists to verify the automated changelog extraction.

## [v3.0.4] - 2026-10-09
### Fixed
- Checksum verification never verified anything. `verify_checksum` looked for a
  `<archive>.sha256` file inside the newly created install directory, where
  nothing ever writes one, so every install warned and returned `Ok`. `install`
  now reads a digest published with the release (`<name>.sha256`, `SHA256SUMS`,
  `checksums.txt`) and compares against it; `install --file` and `--url` read a
  sidecar next to the archive. Mismatches abort the install.
- `self-update` downloaded a release asset and overwrote the running binary with
  nothing verified. It now requires a published digest and refuses to run when
  none exists, failing closed.
- `config get github_token` printed the token verbatim, leaking it into shell
  history and CI logs. It now returns `[stored]`.
- `backup` and `reset --backup` embedded the plaintext GitHub token in the archive.
  Both strip it and report that they did.
- `reset --move-token` and `--keep-token` were stubs that printed "not implemented".
  The token is now captured before the reset: `--keep-token` restores it,
  `--move-token` writes it to the given path with 0600 on Unix.

### Added
- Releases now publish `SHA256SUMS` alongside both installers, which is what makes
  self-update's verification satisfiable.
- Tests for the digest parsers and the manifest filename match: 13 total.

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

## [v3.0.2] - 2026-10-09
### Fixed
- Silent-install conflict handling never compiled. `StrCmp $Silent 1` was rejected
  by makensis as an unknown variable, and the compiler silently ignored both
  occurrences, so the auto-uninstall-MSI and upgrade-in-place branches were dropped
  from the binary. Replaced with the `IfSilent` instruction.
- Version numbers had drifted: the v3.0.1 tag was cut while `Cargo.toml`,
  `installer/ObtainHub.nsi`, and `installer/setup.wxs` all still said 3.0.0, so the
  published installers reported the wrong version. All four sites are now bumped
  together and `PROJECT.md` §2 records the rule.

### Changed
- The NSIS installer builds with zero warnings (was 2).

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
## [v3.0.7-rc2] - 2026-10-11
### Fixed
- NSIS installer binary path now uses relative 'ohub.exe' to ensure the binary is correctly picked up from installer/ directory
- Checksum verification now works in `update` command by fetching published SHA256SUMS/checksums.txt from release assets
- Search command now supports pagination (`--page`, `--per-page`) and per-repo timeout configuration
- Architecture selection now consistent across install/update commands (Plan #7)

### Added
- Public `fetch_published_checksum` and `calculate_sha256` functions in install module for cross-command reuse
- GitHub API pagination support in search command (respects GitHub's 100 results/page limit)
- Config-driven install directory now properly used in update command
- Shared download/verify/extract utilities in `src/core/assets.rs` (Plan #4)
- Config validation with upper bounds and absolute path normalization (Plan #8)
- Tests for config validation (15 tests total now)
- Error handling improvements with better context (Plan #5)
- TUI in-app help screen with key bindings (Plan #9)
- Rollback support: `previous_version` and `previous_install_path` stored in state (Plan #15)
- Network bandwidth throttling for downloads via `download_bandwidth_limit` config (Plan #16)
- New `ohub rollback <repo>` command to revert to previous version (Plan #15)
- Self-update signature verification with Ed25519 (Plan #11)
- `--skip-signature` flag for self-update (emergency bypass)
- Dependency tracking for installed apps (Plan #13)
  - `dependencies` field in state for declaring repo dependencies
  - Auto-update of dependencies during `ohub update` (with `--skip-deps` to opt out)
  - Uninstall protects dependencies with `--force` override
  - `--dependencies` flag for `ohub install` to declare deps at install time
