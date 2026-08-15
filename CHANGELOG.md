# Changelog

All notable changes to ObtainHub will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.5.3] - 2026-08-13

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
- Verified end-to-end: `OnionHop V3 version 3.7.10` -> cleaned `onionhop` -> exact match `center2055/OnionHop` -> linked.

## [0.7.4.3] - 2026-08-13

### Fixed
- **`ohub check --all` no longer lists ohub itself.** The unmanaged-app filter now excludes any registry entry whose name starts with a managed app's name (so "ObtainHub 0.7.4.3" is hidden even though the managed name is "ObtainHub").
- **Apps with messy names are now found.** `ohub check` cleans the registry name before searching GitHub — stripping all version-like tokens (e.g. "OnionHop V3 version 3.7.10" -> "OnionHop") — and falls back through progressively shorter queries, then the raw name, until a repository is found. Names that mix letters and digits (e.g. "v2rayN") are kept.

## [0.7.4.2] - 2026-08-13

### Fixed
- **`ohub check --all --candidates` now works.** The candidate list is always shown when repositories are found (the exact-match fast path no longer skipped it). The exact match is marked with `<=` in the list.
- **Version numbers in app names no longer block matching.** The exact-match comparison now uses the version-stripped name (e.g. "v2rayN 6.0" matches repo `v2rayN`). A fallback search with the raw name runs when the stripped query finds nothing.

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
