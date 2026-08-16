# Changelog

All notable changes to ObtainHub will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.6.6] - 2026-08-14

### Added
- **Code signing for release binaries.** The `release.yml` workflow now signs `ohub.exe`, `ObtainHub-Setup.exe`, and `ObtainHub.msi` using either Azure Trusted Signing (`AzureSignTool`) or a PFX certificate from GitHub secrets. Timestamped with DigiCert (SHA-256). Skips cleanly with a warning when no signing secrets are configured — no cert means unsigned build, not a failed build.

## [0.7.6.5] - 2026-08-13

### Fixed
- **Version comparison no longer ignores the 4th segment.** `parse_version` truncated versions to 3 parts (`0.7.6.3` and `0.7.6.4` both became `(0,7,6)`), so `ohub check` reported "Up to date" even when a newer patch release existed (e.g. current 0.7.6.3 vs latest 0.7.6.4). Now all segments are kept; short versions still pad (1.2 → (1,2,0)). Regression tests added.

## [0.7.6.4] - 2026-08-13

### Fixed
- **GitHub apps no longer falsely flagged as manually removed.** `ohub check` treated any managed app whose recorded `install_location` was missing on disk as removed. For setup-installed (GitHub) apps that path is often empty or stale, so valid installs were wrongly dropped. `install_location` is now only authoritative for folder/zip apps; GitHub apps are checked against the **system registry** (Programs & Features) instead — present there means keep it. Regression tests added.

## [0.7.6.3] - 2026-08-13

### Fixed
- **`ohub uninstall` no longer launches the install wizard.** Uninstall ran the cached *setup* exe, which re-opens the install/repair wizard instead of uninstalling. It now reads the real uninstaller from the Windows registry `UninstallString` (e.g. `unins000.exe`) and runs that — both interactively and silently. Falls back to the cached setup exe with uninstall flags only when no registry entry exists. Regression tests added.

## [0.7.6.2] - 2026-08-13

### Fixed
- **`ohub self-update --force` now works.** When already at the latest version, `check_for_update` raised "already latest" and the force flag was ignored (no reinstall happened). `--force` now re-fetches the release and reinstalls. Regression test added.
- **`X` cancels any select list.** Every interactive picker (`ohub check`, asset/version selection, candidate menus) now accepts `X` (in addition to `0`) to exit/cancel cleanly.

### Docs
- Removed real app names (`v2rayN`, `OnionHop`, `qBittorrent`, `qimgv`) from README and CHANGELOG; replaced with generic samples (`MyApp`, `MyTool`, `owner/myrepo`, `folder:myapp`).

## [0.7.6.1] - 2026-08-13

### Fixed
- **Folder/zip apps no longer prompt for an asset when already up to date.** `ohub check` was listing available ZIP assets and asking the user to pick one even when the app was already at the latest version (e.g. `MyApp` showing "Up to date" yet prompting `Select asset to track`). The asset picker now only appears when an update is actually available.

### Docs
- README: added two concrete custom-source examples (a GitHub repo source like `owner/myrepo`, and a non-GitHub JSON manifest source).

## [0.7.6.0] - 2026-08-13

### Added
- **Interactive install / update / uninstall.** On a TTY without `--yes`, ohub launches the installer/uninstaller **visibly** (no silent flags) so you drive the wizard; `--interactive` forces this, `--yes` stays silent for automation. (`ohub install/update/uninstall --interactive`)
- **Verify by system state, not exit code.** After the installer exits, ohub re-reads the Windows Registry / install location. Install is only recorded in `state.json` if the app is actually present; otherwise it reports `not detected` and does NOT write state. Uninstall already re-checked the registry and keeps the app managed on failure (from 0.7.5.0). This closes the gap for the long tail of apps ohub can't fully automate.

### Fixed
- `ohub check` re-reads the installed version from the system registry so updates performed outside ohub (including self-update) are detected (0.7.5.3).

### Docs
- README + new "Install / Uninstall: Interactive Mode & Verification" section explain the model and failure handling.

### Fixed
- **`ohub check` now detects versions updated OUTSIDE ohub.** Previously `ohub check` compared against its own stored version, so if you updated an app manually (or ohub self-updated), the recorded version stayed stale and `check` wrongly reported "up to date". `ohub check` now re-reads the actually-installed version from the system registry (Programs & Features) for every managed app and updates its state. Self-update is detected too: after the detached installer replaces `ohub.exe`, the next `ohub check` picks up the new version (registry name "ObtainHub X.Y.Z" matched against the stored "ObtainHub").

## [0.7.5.2] - 2026-08-13

### Fixed
- **`ohub check --all` single-select no longer scans everything.** A post-menu recompute of the unmanaged-app list was clobbering the "skip unmanaged scan" flag set when you pick a single managed app. Removed it. Verified by a regression test: selecting one managed app now checks only that app (`search_repositories` is never called for the other 60+ system apps).
- **`ohub check --all --candidates` timeout raised.** The per-repo GitHub search timeout was hard-capped at 60s (default 20s), so slow/unauthenticated searches timed out before returning candidates. Default is now **90s** and the cap is **300s** (`check_timeout_seconds` config validated 10-300; `--timeout` accepts up to 300). Pass `--timeout 180` for very slow links.

## [0.7.5.1] - 2026-08-13

### Fixed
- **`ohub self-update` no longer hangs.** The update installer is now launched **detached** (non-blocking) and `ohub` exits immediately afterward, so the installer can replace the running `ohub.exe` (which it couldn't while ohub was still running). Previously `ohub` waited on the installer, which waited on `ohub` to exit — a deadlock. The command now prints "Update started — ohub will exit" and you restart ohub once the install finishes.

## [0.7.5.0] - 2026-08-13

### Fixed
- **Manual removal of managed apps is now detected.** `ohub check` checks each managed app's install location (any type) and, for GitHub apps, also cross-checks the system registry (Programs & Features). A managed app that's gone is removed from ohub state with a clear message instead of being silently kept / erroring.
- **`ohub install` detects an already-installed app.** If the app is already in the system (installed by the user, not ohub), `ohub install` now says so and tells the user to run `ohub check` to let ohub manage it — instead of reinstalling and reporting false success. Use `ohub install owner/repo --force` to reinstall anyway.
- **`ohub uninstall` verifies completion.** After the uninstaller runs, ohub re-checks the system registry; if the app is still present it reports "still present / permission issue - run as administrator" and keeps it in ohub management so you can retry, instead of claiming success.

## [0.7.4.4] - 2026-08-13

### Fixed
- **Apps with messy names reliably found (hardening).** `search_repositories` no longer drops GitHub-matched results when the strict case-insensitive substring filter would leave zero hits — it now trusts GitHub's relevance ranking instead of nuking valid matches. `ohub check`'s progressive-query fallback also no longer aborts on a transient non-rate-limit error, so it keeps trying cleaner/shorter/raw-name queries.
- Verified end-to-end: `MyTool V3 version 3.7.10` -> cleaned `mytool` -> exact match `owner/MyTool` -> linked.

## [0.7.4.3] - 2026-08-13

### Fixed
- **`ohub check --all` no longer lists ohub itself.** The unmanaged-app filter now excludes any registry entry whose name starts with a managed app's name (so "ObtainHub 0.7.4.3" is hidden even though the managed name is "ObtainHub").
- **Apps with messy names are now found.** `ohub check` cleans the registry name before searching GitHub — stripping all version-like tokens (e.g. "MyTool V3 version 3.7.10" -> "MyTool") — and falls back through progressively shorter queries, then the raw name, until a repository is found. Names that mix letters and digits (e.g. "MyTool2") are kept.

## [0.7.4.2] - 2026-08-13

### Fixed
- **`ohub check --all --candidates` now works.** The candidate list is always shown when repositories are found (the exact-match fast path no longer skipped it). The exact match is marked with `<=` in the list.
- **Version numbers in app names no longer block matching.** The exact-match comparison now uses the version-stripped name (e.g. "MyTool 6.0" matches repo `MyTool`). A fallback search with the raw name runs when the stripped query finds nothing.

## [0.7.4.1] - 2026-08-13

### Fixed
- **`ohub check` crash** (`NameError: name 'a' is not defined`) — the unmanaged-app filter built its install-location set as a literal referencing an undefined comprehension variable. Now computed via proper comprehensions over the managed apps.

## [0.7.4.0] - 2026-08-13

### Fixed
- **Ohub now appears in the managed list.** Its own repo (`DavoudTeimouri/ObtainHub`) is registered as a managed app on startup, so `ohub list` / `ohub check` / `ohub update` include it and self-update stays consistent.
- **`ohub check` crash** ("cannot access local variable 'app'") fixed — renamed the leaked comprehension variable that shadowed the managed-app loop variable.
- **Cancel now aborts.** In `ohub update` and `ohub install`, selecting cancel (0) at the installer-choice prompt stops that app instead of continuing with a default.

## [0.7.3.0] - 2026-08-13

### Fixed
- **Self-managed apps no longer re-detected as unmanaged.** In `ohub check --all`, apps ohub already manages (by name or install location) are excluded from the system scan.
- **`ohub check` now handles folder/portable apps** like `ohub update` does — it searches GitHub by the app's name when no `owner/repo` is linked, instead of reporting "cannot resolve remote".
- **`ohub check` candidate fallback:** search query now strips version numbers (e.g. "App 1.2.3" → "App"). Without `--candidates`, the best-starred repo is offered as the match; with `--candidates` a numbered list is shown.

## [0.7.2.0] - 2026-08-13

### Fixed
- Extraction `PermissionError` now tells the user to **close the running app** and retry (or run as admin / pick an owned folder).
- Custom sources in the legacy top-level `sources` key are now migrated into `manifest_sources` (they were previously ignored). The bogus built-in `default` manifest source was removed.
- `ohub source add --type` is now stored; sources without installable content (no releases/assets, or non-JSON) are rejected.
- Global config directory (`%ProgramData%\ObtainHub`) is created automatically if missing.

### Changed
- Every interactive selection now offers a numbered **Cancel/Skip** option.

## [0.7.1.0] - 2026-08-13

### Added
- `ohub check` now also discovers unmanaged system apps in **custom sources** (non-GitHub). When a registry app's name matches a source entry, ohub offers to install/update it from that source; the match is recorded so future checks skip it.

## [0.7.0.0] - 2026-08-13

### Added
- **Install/update from custom sources (non-GitHub).** `ohub source add <name> <url> --type github|manifest` registers a source; `ohub install` / `ohub update` now fall back to these sources when a `owner/repo` is not found on GitHub.
  - `--type github` sources read releases/assets from any GitHub repo URL or `.../releases` API.
  - `--type manifest` sources read a JSON list of apps (`[{"name","version","url","installer_type","sha256?","size?"}]`) served over HTTP.
- Apps installed from a source are recorded with their `source` name; `ohub update` checks them against the source for newer versions. `ohub uninstall`/`ohub remove` drops them from ohub (the shared source stays).

### Changed
- `ohub source add` now stores the source `type` and validates reachability/contents before accepting it.
