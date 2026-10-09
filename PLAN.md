# ObtainHub Improvement Plan

## High Priority Bug Fixes

### 1. Update command ignores custom install directory
- **File**: `src/commands/update.rs`
- **Issue**: The `install_release` function uses a hardcoded path (`ObtainHub/repos`) instead of reading the install directory from config.
- **Impact**: Users who set a custom install directory via config will see updates fail or install to the wrong location.
- **Fix**: Use `config.get().install_dir.join(&repo)` similar to the install command.
- **Effort**: Low

### 2. Missing checksum verification in update command
- **File**: `src/commands/update.rs`
- **Issue**: TODO comment at line 154 indicates checksum verification is not implemented. The `install_release` function sets checksum to None.
- **Impact**: No verification of downloaded assets during updates, posing a security risk.
- **Fix**: Implement checksum verification similar to the install command (download asset to temp file, verify, then extract).
- **Effort**: Medium

### 3. Uninstall --purge does not remove config/data
- **File**: `src/commands/uninstall.rs`
- **Issue**: TODO comment at line 47 indicates the --purge flag does not remove associated config/data.
- **Impact**: Incomplete cleanup when purging a repository.
- **Fix**: Implement removal of config and data files associated with the repository when --purge is used.
- **Effort**: Low

## Medium Priority Improvements

### 4. Refactor shared download/extract logic
- **Files**: `src/commands/install.rs`, `src/commands/update.rs`, potentially others
- **Issue**: Duplication of download progress, extraction, and checksum verification code between install and update commands.
- **Impact**: Code maintenance burden, inconsistent behavior.
- **Fix**: Create a utility module (e.g., `src/core/assets.rs`) with functions for downloading, verifying, and extracting assets.
- **Effort**: Medium

### 5. Improve error handling and user feedback
- **Files**: Various command files
- **Issue**: Some error messages are generic; could be more specific to help users troubleshoot.
- **Impact**: Better user experience.
- **Fix**: Enhance error messages with context (e.g., include URL, file path, or operation that failed).
- **Effort**: Low

### 6. Add timeout configuration for GitHub API requests
- **Files**: `src/core/config.rs`, `src/commands/install.rs`, `src/commands/update.rs`
- **Issue**: HTTP requests to GitHub use a hardcoded timeout (30 seconds) from config, but there's no way to configure it per command or via CLI.
- **Impact**: Users on slow networks may experience failures; no way to adjust.
- **Fix**: Add a CLI argument or config option to override request timeout.
- **Effort**: Low

### 7. Ensure consistent architecture selection across commands
- **Files**: `src/cli.rs` (Args structs), `src/commands/install.rs`, `src/commands/update.rs`, `src/commands/check.rs`
- **Issue**: The install command uses an `Arch` enum with Auto/X64/Arm64/X86, but update and check commands may not use it consistently.
- **Impact**: Inconsistent behavior when specifying architecture.
- **Fix**: Ensure all relevant commands accept and use the architecture argument uniformly.
- **Effort**: Low

### 8. Add validation for config values
- **File**: `src/core/config.rs`
- **Issue**: Config values like `parallel_downloads`, `timeout_seconds` are not validated (e.g., could be zero or negative).
- **Impact**: Potential runtime panics or misconfiguration.
- **Fix**: Add validation in `ConfigManager::new()` or when setting values via CLI.
- **Effort**: Low

## Low Priority Enhancements

### 9. Improve TUI discoverability
- **File**: `src/tui.rs` (or `src/commands/tui.rs`)
- **Issue**: The TUI command exists but may lack documentation or key bindings help.
- **Impact**: Users may not know how to use the TUI effectively.
- **Fix**: Add in-app help screen and improve documentation in README.
- **Effort**: Low

### 10. Add support for GitHub API pagination in search
- **File**: `src/commands/search.rs`
- **Issue**: Search results are limited to the first page (default 20). Users may miss results.
- **Impact**: Incomplete search results.
- **Fix**: Implement pagination to fetch more results when needed (respecting rate limits).
- **Effort**: Medium

### 11. Add self-update signature verification
- **File**: `src/commands/self_update.rs`
- **Issue**: Self-update downloads and executes binaries without verifying authenticity.
- **Impact**: Security risk if update mechanism is compromised.
- **Fix**: Implement signature verification using GitHub releases' GPG signatures or checksums from a trusted source.
- **Effort**: High

### 12. Add completion for power shells (e.g., fish)
- **File**: `src/commands/completion.rs`
- **Issue**: Currently supports bash, zsh, powershell, elvish. Missing fish and others.
- **Impact**: Incomplete shell support.
- **Fix**: Add fish shell completion generator.
- **Effort**: Low

## New Features

### 13. Add dependency tracking for installed apps
- **Files**: `src/core/state.rs`, `src/commands/install.rs`, `src/commands/update.rs`
- **Issue**: ObtainHub does not track dependencies between repositories; updating one might break another if they share dependencies.
- **Impact**: Users cannot manage complex dependency chains.
- **Fix**: Allow specifying dependencies in config/state and check/install them automatically.
- **Effort**: High

### 14. Add ability to install from GitHub Packages or other registries
- **File**: `src/commands/install.rs`
- **Issue**: Currently only supports GitHub releases assets.
- **Impact**: Limited to public GitHub repositories.
- **Fix**: Extend install command to support other package registries (e.g., GitHub Packages, crates.io, etc.) via configuration.
- **Effort**: High

### 15. Add rollback functionality for updates
- **File**: `src/core/state.rs`, `src/commands/update.rs`
- **Issue**: No easy way to revert an update if the new version is problematic.
- **Impact**: Users stuck with broken updates.
- **Fix**: Keep previous version's asset or state and allow rolling back to it.
- **Effort**: Medium

### 16. Add network bandwidth throttling for downloads
- **File**: `src/core/config.rs`, download utilities
- **Issue**: Downloads consume full bandwidth, affecting other network activities.
- **Impact**: Poor user experience on shared networks.
- **Fix**: Add config option to limit download speed.
- **Effort**: Medium

## Chore / Documentation

### 17. Update README with examples for all major commands
- **File**: `README.md`
- **Issue**: README lacks comprehensive examples.
- **Impact**: Steeper learning curve.
- **Fix**: Add examples for search, install, update, TUI, config, etc.
- **Effort**: Low

### 18. Add contributing guidelines and development setup instructions
- **File**: `CONTRIBUTING.md`
- **Issue**: Missing contributing guide.
- **Impact**: Hard for new contributors to start.
- **Fix**: Add guide on building, testing, and submitting patches.
- **Effort**: Low

### 19. Set up CI/CD for automatic releases
- **Files**: `.github/workflows/`
- **Issue**: Manual release process.
- **Impact**: Delayed releases.
- **Fix**: Automate building, testing, and publishing releases via GitHub Actions.
- **Effort**: Medium
