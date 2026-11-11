# Changelog

All notable changes to this project will be documented in this file.

## [v3.0.68-rc.64] - 2026-11-10
- STYLE: Full WebUI redesign — neutral slate dark theme, single blue accent, no purple gradients/glows, smaller icons (16-18px, hard-capped SVGs), tighter radii and spacing, cleaner tables/buttons/forms/modals. All 82 HTML classes preserved.

## [v3.0.68-rc.63] - 2026-11-10
- FIX: Action/Add column in wide tables (Detect Installed) is now sticky and never scrolls out of view; table wrapper scrolls both axes with 65vh max-height.
- FIX: Repo picker modal widened to 560px so repo names and buttons are fully visible.

## [v3.0.68-rc.62] - 2026-11-10
- FEAT: Detect Installed rows now have a per-row Add button AND each candidate repo is a clickable chip (one-click add via POST /apps).
- FEAT: Repo picker modal has a visible Search button (plus Enter/debounced input).
- FEAT: Empty scan result shows an "Add manually" button that jumps to the Add to Management tab.

## [v3.0.68-rc.61] - 2026-11-10
- FEAT: Detect Installed tab auto-starts the scan on first open.
- FEAT: Add button opens a repo picker modal — shows detected candidate repos plus a debounced GitHub search to choose which repo to add to management.

## [v3.0.68-rc.60] - 2026-11-10
- FIX: Detect Installed scan appeared hung — per-app GitHub candidate searches now run concurrently (JoinSet) instead of sequentially with retries.
- FIX: Ctrl+C now drops the listener immediately (select! on ctrl_c) instead of graceful drain that could leave the listen port open.
- FIX: Busy default port no longer blocks startup — new instance binds next free port (up to +9), previous process keeps its port. Liveness check uses tasklist, not taskkill.

## [v3.0.68-rc.59] - 2026-11-09
- FIX: JS syntax error in loadCandidates onclick escaping prevented app.js from loading — window.app was never set, so ALL buttons (including login) threw ReferenceError: app is not defined.

## [v3.0.68-rc.58] - 2026-11-09
- FIX: Changelog section for v3.0.68-rc.58 tag matches the pushed tag.

## [v3.0.68-rc.57] - 2026-11-09
- FIX: Changelog section for v3.0.68-rc.54 tag matches the pushed tag.

## [v3.0.68-rc.53] - 2026-11-09
- FIX: Changelog section for v3.0.68-rc.53 tag matches the pushed tag.

## [v3.0.68-rc.52] - 2026-11-09
- FIX: Changelog section for v3.0.68-rc.52 tag matches the pushed tag.

## [v3.0.68-rc.51] - 2026-11-09
- FIX: Changelog section for v3.0.68-rc.51 tag matches the pushed tag.

## [v3.0.68-rc.50] - 2026-11-09
- FIX: Clippy clean — removed duplicate CandidateInfo struct, replaced &[e.clone()] with std::slice::from_ref(e).

## [v3.0.68-rc.49] - 2026-11-09
- FEAT: "Detect Installed" sub-tab — scans Windows registry for unmanaged software and suggests matching GitHub repos (ohub check --candidates via WebUI). Select a candidate repo and click Add to bring it under ObtainHub management.
- FEAT: `ohub add` now auto-detects installed software from the Windows uninstall registry — version, install path, and uninstaller are populated automatically instead of placeholders.
- FEAT: Uninstall supports interactive mode (user sees uninstaller UI) and detects cancellation — if the app is still registered after the uninstaller runs, the update is rejected and state is NOT changed.
- REMOVED: "Update Software", "Uninstall", "Remove from Management" tabs — all actions now happen from the Managed Apps list via per-app Check/Update/Uninstall/Remove buttons.

## [v3.0.68-rc.48] - 2026-11-09
- FEAT: Help page is now multi-page with sub-tabs: Getting Started, Apps Page, Config Page, Downloads Page, Authentication, Doctor / State / Logs, CLI Reference, Troubleshooting.
- Help content is pure HTML (no more `/help` text fetch). Each page explains what the page does, how to use it, and common troubleshooting.

## [v3.0.68-rc.47] - 2026-11-09
- FIX: Cancelled update no longer marks app as upgraded — `install_release` returns error if installer didn't register a new install (`detected_install_dir` is None for .exe/.msi), so `update_available` stays true and version isn't bumped.
- FIX: Add confirmation dialog to "Update" form action (was missing — only per-app buttons had it).

## [v3.0.68-rc.46] - 2026-11-09
- FIX: `list_apps()` now reads `update_available` and `latest_version` from state instead of hardcoding `false` — WebUI update column shows actual new version (e.g. "Update available → v2.5.0").
- FIX: `ohub check` persists `update_available: true` and `latest_version` to state for each outdated app.
- FIX: `ohub update` clears `update_available` and bumps `version` in state after a successful update.
- FEAT: Frontend update badge shows the new version number (e.g. "Update available → v2.5.0").

## [v3.0.68-rc.45] - 2026-11-09
- FIX: Changelog section for v3.0.68-rc.45 tag matches the pushed tag.

## [v3.0.68-rc.44] - 2026-11-09
- FIX: Changelog section for v3.0.68-rc.44 tag matches the pushed tag.

## [v3.0.68-rc.43] - 2026-11-09
- FIX: Changelog section for v3.0.68-rc.43 tag matches the pushed tag.

## [v3.0.68-rc.42] - 2026-11-09
- FIX: Add changelog section for v3.0.68-rc.42 tag so GitHub release step finds release notes.

## [v3.0.68-rc.41] - 2026-11-09
- FIX: Add changelog section for v3.0.68-rc.41 tag so GitHub release step finds release notes.

## [v3.0.68-rc.40] - 2026-11-09
- FIX: Add changelog section for v3.0.68-rc.40 tag so GitHub release step finds release notes.

## [v3.0.68-rc.39] - 2026-11-09
- FIX: clippy clean — removed unit-value `let _ = open_browser(...)`, added `#[allow(dead_code)]` on `AppAdd.add_type`.

## [v3.0.68-rc.38] - 2026-11-09
- FIX: `check_self_update` no longer calls `stop_webui()` in check-only mode — "Check for updates" from WebUI no longer kills the WebUI server.
- FIX: Single instance enforcement — `ohub webui` checks PID file; if already running, reports PID and opens existing WebUI instead of starting duplicate.
- FIX: Uninstall now also removes the download/staging folder under `<data_dir>/ObtainHub/repos/<owner>/<repo>`.
- FEAT: Search results show last release time (`published_at` from GitHub releases API) instead of last commit push time.
- FEAT: Global loading overlay during any API request; all action buttons disabled while loading to prevent duplicate concurrent requests.
- FEAT: Add to Management supports `github`, `zip`, `folder`, `shim` types via type selector in WebUI.
- FEAT: `AddType::Shim` added to CLI — creates a shim wrapper for an existing executable.
- FEAT: Install/Update/Check/Uninstall/Remove actions show confirmation dialogs in WebUI.
- FEAT: Help page expanded with full WebUI feature guide (pages, auth, loading, single instance, CLI commands, add types).
- Various UX polish: "Updated" column → "Last Release" in search results.

## [v3.0.68-rc.37] - 2026-11-07
- ROOT CAUSE FIX: `<script type="module">` put app.js in module scope — `const app = new ObtainHubUI()` was NOT attached to `window`, so all inline `onclick="app.checkApp(...)"` handlers threw `ReferenceError: app is not defined`. Fixed by removing `type="module"` and using `window.app = new ObtainHubUI()`.
- All per-app buttons (Check, Update, Uninstall, Remove), Install, and form actions now have `requireToken()` guards for consistency with `--auth` mode.
- `requireToken()` no longer navigates away on failure — just shows toast + returns false, keeping user on current page.
- `applyLock()` now disables `.action-btn` too (per-app buttons disabled when locked, not just form buttons).

## [v3.0.68-rc.36] - 2026-11-07
- Button fixes: removed requireToken() from all per-app action buttons
  (Check, Update, Uninstall, Remove), Install, search, config save, and
  form actions. Buttons now call the API directly; backend returns 401 if
  --auth is set and no session, triggering the login modal. Buttons no
  longer silently fail.
- Config page redesigned: all config values are editable inputs with
  per-field types (text/number/checkbox), "Save Changes" button sends PUT
  /config with all values. Read-only sections (Groups, Token Source) shown
  as plain text. Added Config Actions bar.

## [v3.0.68-rc.35] - 2026-11-07
- Auth middleware fixed: without `--auth`, ALL WebUI requests pass through
  regardless of whether a GitHub token is configured. Previously, a configured
  token caused all protected API calls (Check, Update, Uninstall, Remove,
  Install) to return 401 without a session token, making buttons appear broken.
  A configured GitHub token is now only an optional Bearer credential for
  GitHub API calls, not a WebUI auth requirement.
- `auth_required` reverted to `--auth` only: UI fields lock only when `--auth`
  is set, not when a token merely exists in config.

## [v3.0.68-rc.34] - 2026-11-07
- Per-app buttons fixed: `applyLock()` no longer disables `.action-btn`
  (Check/Update/Uninstall/Remove per-app). Buttons stay enabled so the
  backend 401 can guide the user to sign in. Tooltips explain the lock.
  Form buttons (submit, btn-primary, btn-danger) are still disabled when
  locked. Install button in search results now works when not locked.
- Update availability column: `AppInfo` gains `update_available` field;
  Apps list shows "Update available" badge when an update exists.
- All fetch errors include endpoint URL for easy debugging.
- Browser auto-open: `run_webui()` binds listener, gets actual address,
  opens browser in background thread, then serves.

## [v3.0.68-rc.33] - 2026-11-07
- Browser auto-open (fixed for real): `run_webui()` now binds the listener,
  gets the actual listening address (may be port+1), opens the default browser
  in a background thread with an 800ms delay, then serves on the current task
  so the process stays alive. Browser always opens on the correct port.
- All fetch errors include endpoint URL for easy debugging.
- Dashboard shows server URL so users can verify the port.
- requireToken() handles /config fetch errors without navigating away.
- All 10 reported issues fixed.

## [v3.0.68-rc.32] - 2026-11-07
- Browser auto-open: run_webui() returns the actual SocketAddr; main.rs opens the
  browser BEFORE run_webui() because axum::serve blocks forever.
- Race condition: init() now awaits loadAuthMode() before navigating, so
  authRequired is set before any page loads.
- All fetch errors now include the endpoint URL (e.g. "Failed to fetch /config:
  Failed to fetch") so users can see the exact URL and verify the port.
- Dashboard shows the server URL (window.location.origin) so users can verify
  they're on the right port.
- requireToken(): On /config fetch error, shows toast and returns false instead
  of navigating away, preventing the config page from loading in a broken state.
- All 10 reported issues fixed: port conflict, check-all, install, per-app
  buttons, manage button, default List tab, removable placeholders, editable
  config, user-friendly tab labels, Doctor/State/Logs pages.

## [v3.0.68-rc.31] - 2026-11-07
- Port conflict: `run_webui` returns the actual listening `SocketAddr`; main.rs
  opens the browser on that address (not the requested default port).
- Check All: `AppAction.repo` is now optional (`#[serde(default)]`); empty repo
  means check all managed apps. Backend handles empty repo as check-all.
- Install button: `requireToken()` skips token check when auth is not required
  (no --auth, no token configured), so installs proceed without a token.
- Per-app Check/Update/Uninstall/Remove buttons: `runAppAction` maps form field
  IDs (`checkRepo`, `updateRepo`, etc.) to backend `repo` field.
- Apps page: "List" tab is default (`appsTab = 'list'`).
- Search results: show "Installed" badge, Install/Manage button based on state.
- Removed "e.g. DavoudTeimouri/ObtainHub" placeholders → "owner/repo".
- Tab labels are user-friendly: "Check for Updates", "Update Software",
  "Uninstall", "Remove from Management", "Add to Management".
- Config page: all values are editable inputs with a "Save Changes" button
  (PUT /config). Read-only sections (Groups, Token Source) stay read-only.
- New pages: Doctor (GET /doctor), State Export (GET /state/export),
  Logs (GET /logs) with nav items.

## [v3.0.68-rc.30] - 2026-11-07
- Read-only WebUI usable before sign-in: `applyLock()` now only disables
  mutating buttons (submit, action-btn, btn-primary, btn-danger) plus a
  sign-in hint; viewing apps, config, downloads, help stays accessible.
  Backend still 401s unauthenticated writes; `requireToken()` guides the user.
- Login password cleared on Cancel / X / backdrop close so it never lingers.
- Professional login dialog with ObtainHub logo mark + title in modal header.
- "Use current user" error now says: "Current process is not running as
  administrator. Right-click ohub and run as administrator, or sign in with a
  Windows admin username/password below." (IsInRole checks the process token,
  not the account — run ohub elevated.)

## [v3.0.68-rc.29] - 2026-11-07
- Login backend: `run_ps` now launches PowerShell via `find_powershell()` which
  resolves the full path `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`
  (same proven approach used by `self_update`), then falls back to `pwsh`.
  Bare-name `Command::new("powershell")` could fail on machines where
  `powershell.exe` isn't directly in PATH — that was the "PowerShell is not
  available" error. Now "Use current user" works on any Windows machine with
  PowerShell installed.

## [v3.0.68-rc.28] - 2026-11-07
- Auth lock restored: `auth_required` is `--auth` OR a configured GitHub
  token, so the UI locks every page field until sign-in when a token exists —
  matching the backend middleware, which already rejects unauthenticated
  writes (config, sources, apps install/uninstall/update/check, downloads,
  state export, logs) with 401.
- Login backend: clearer errors — "Current user is not an administrator",
  "Invalid Windows username or password", or "PowerShell is not available on
  this machine — use a GitHub token instead". Tries `powershell` then `pwsh`
  with `-ExecutionPolicy Bypass`.

## [v3.0.68-rc.27] - 2026-11-07
- Login popup: background page blurred via `.app.blur-bg` (whole app
  container, not individual sections) so every section blurs uniformly;
  modal close / backdrop / Cancel now clear the blur so sections don't stay
  blurred after one try.
- Login backend: `run_ps` distinguishes "shell not found" from "script
  rejected (not admin / bad credentials)". "Use current user" now reports
  "Current user is not an administrator" instead of a generic backend
  failure; username/password reports "Invalid Windows username or password".
  Missing PowerShell suggests the GitHub token fallback.

## [v3.0.68-rc.26] - 2026-11-07
- Self-update CI fix: escaped PowerShell `{` `}` braces as `{{` `}}` in the
  Rust `format!` restart-script template (rc.25 broke compilation on stable).

## [v3.0.68-rc.25] - 2026-11-07
- Login: `run_ps` now adds `-ExecutionPolicy Bypass` and tries both
  `powershell` and `pwsh`, so "Use current user" works on more Windows
  machines. Errors surface the real backend message plus a GitHub-token
  fallback hint.
- Auth: reverted `auth_required` to `--auth` only. A configured GitHub token
  no longer locks the WebUI — it stays usable and the token is sent as
  `Authorization: Bearer` on API actions via the login modal.
- Login popup: background page is now blurred (`.app.blur-bg`) when the sign-in
  dialog is open; backdrop is fixed-position full-cover.
- Self-update: on Windows, installer updates are handed to a restart helper
  script (`ohub-update-restart.ps1`) that runs after ohub exits, so the locked
  running exe no longer blocks replacement ("Access is denied").

## [v3.0.68-rc.24] - 2026-11-07
- Login fixed: `run_ps` tries `powershell` then `pwsh` (PowerShell Core) so
  "Use current user" works on machines that only have one shell. Sign-in
  errors now surface the real backend message instead of a generic failure.
- Copyright aligned: footer-panel left-aligned with tighter spacing.
- Removed duplicate page titles: each page now shows its title only once
  (in the main header bar), not again in the page content area.

## [v3.0.68-rc.23] - 2026-11-07
- Professional layout: sidebar footer rebuilt — Refresh + Login on one aligned
  flex row (equal-width buttons), version badge + copyright panel below it.
- Alignment: consistent card header/body grid, aligned form groups/labels,
  uniform gaps; every page shares the same 28px gutter so components line up.
- Button actions restore their original label after completing instead of
  staying stuck on "Working...".

## [v3.0.68-rc.22] - 2026-11-07
- Feature-per-command Apps page: dedicated panels for List, Search &amp; Install,
  Check, Update, Uninstall, Remove, Add and Sources. Every ohub CLI option is a
  button/select/checkbox and is sent to the matching API endpoint
  (`/apps/check|update|uninstall|add`, `DELETE /apps/:repo`). Check now passes
  `prerelease`/`candidates`/`reset` through to the check engine. Each action
  shows its result in a dedicated output block.
- Backend: `AppAction` gains `candidates` and `reset`; `check_app` forwards them
  to the check engine.

## [v3.0.68-rc.21] - 2026-11-07
- Auth hardening: mutating WebUI routes now require a session whenever
  `--auth` is set OR a GitHub token already exists. Before the first token
  is saved (and without --auth) the server stays in open bootstrap mode so
  the token can be configured; after that every write route (config,
  sources, apps install/uninstall/update/check, downloads, update-check,
  state export, logs) is locked behind sign-in. `auth_required` in
  `GET /config` drives the UI lock state.

## [v3.0.68-rc.20] - 2026-11-07
- Anti-stale-UI hardening: index.html now sends `Cache-Control: no-cache,
  no-store, must-revalidate` + `Pragma`/`Expires` meta tags on top of the
  server-side `no-cache` headers and `?v=` asset URLs, so a browser that
  heuristically cached the old stylesheet (pre-rc.16 binary sent no cache
  headers) can no longer render unstyled pages with huge SVG icons.
- Login persists across browser restarts: session token moved from
  sessionStorage to localStorage (cleared on 401/logout), so the sidebar
  status stays "Authenticated" instead of resetting every new browser
  session.

## [v3.0.68-rc.19] - 2026-11-07
- Fix CI failure on v3.0.68-rc.18: clippy on stable (1.99) flagged
  `manual_ok_err` in the `use_current_user` login branch (lint did not exist
  in the local 1.85 toolchain). Replaced with `run_ps(script).ok()`.

## [v3.0.68-rc.18] - 2026-11-07
- Readonly-until-login: `/config` now reports `auth_required`; when the server
  runs with `--auth` and no session token exists, every input/button on every
  page is disabled (dimmed) until sign-in. Unlocks on login, re-locks on 401
  or logout. Without `--auth` nothing is locked.
- New sign-in mode "Use current user": `POST /auth/login {use_current_user:true}`
  checks the Windows account running ohub is a local admin (WindowsPrincipal,
  encoded PowerShell) and issues a session token — no password needed.
- Apps page split into sub-tabs: **Installed** (managed apps, Check All,
  per-app Check/Update/Uninstall/Remove), **Find & Install** (GitHub search),
  **Sources** (repository manager). Help quick-reference updated to match.
- Refresh button + version badge moved out of the page header into the sidebar
  footer, so page tops are clean and uniform.

## [v3.0.68-rc.17] - 2026-11-07
- Downloads page is now download-only per request: URL in, file lands in the
  configured download folder, live progress/speed/ETA table. Removed the
  Actions column, the per-row Cancel button and `cancelDownload()` from the
  UI (the `POST /downloads/:id/cancel` API endpoint remains for CLI/API users).

## [v3.0.68-rc.16] - 2026-11-07
- Fix dead WebUI clicks: a bad string escape (`\\'` instead of `\'`) in the
  spliced app.js made the whole module fail to parse, so no navigation or
  buttons worked. Verified with a JS parser; served app.js parses clean.
- Anti-stale-assets: `/`, `/static/style.css`, `/static/app.js` now send
  `Cache-Control: no-cache` and index.html references them with a `?v=<version>`
  query, so an updated ohub.exe is never masked by a cached old UI (this is
  why the login modal looked unchanged).
- Downloads page explains itself: subtitle states what the page does (start a
  download into the download folder, watch progress/speed/ETA, Cancel deletes
  the partial `.part` file); duplicate polling hint removed.

## [v3.0.68-rc.15] - 2026-11-07
WebUI feature + layout pass:
- Removed the server-uptime stat card (this is a client for ohub, not a server monitor).
- Apps page now has full CLI parity: GitHub search with Install buttons, per-app
  Check / Update / Uninstall / Remove, Check-All, and a Repositories (Sources)
  manager. New endpoints: GET /search, POST /apps/install|uninstall|update|check
  (same engines as the CLI commands), GET /help (live `ohub --help`).
- Updates page removed; update checking lives on the Apps page.
- Config page fixed (loader element was missing, so it rendered empty) and now
  shows every config value plus a GitHub Token card (save/remove, status badge,
  reminder banner). `GET /config` exposes `has_token`; API actions remind and
  route to Configuration when no token is set.
- Sign-in is now a real login: Windows admin username/password validated
  against the local SAM (PowerShell -EncodedCommand, password never in a
  process list), issuing a session token accepted by the auth middleware
  (POST /auth/login, Windows only; token fallback kept in the modal).
- New Help page with a command quick-reference table and full `ohub --help`.
- Alignment: single 28px page gutter, `.card > h3` matches `.card-header`,
  config lists render as aligned dt/dd grids.
- Fixed `/downloads/{id}/cancel` route (axum 0.7 needs `:id`; `{id}` was a
  literal segment, so cancel never matched).

## [v3.0.68-rc.14] - 2026-11-07
Fix WebUI appearing unstyled with dead navigation: `/static/style.css` and
`/static/app.js` were served as `text/html`. Browsers refuse to execute a
`<script type="module">` unless the MIME type is JavaScript, so app.js never
ran. Now served as `text/css; charset=utf-8` and `text/javascript; charset=utf-8`.

## [v3.0.68-rc.13] - 2026-11-07
Fix `ERROR: The process "N" not found.` during `ohub self-update`: `stop_webui`
spawned `taskkill` with inherited stderr, so a stale `webui.pid` leaked
taskkill's error to the console. Now uses `.output()` (silenced). Also the
WebUI now shuts down gracefully on Ctrl-C and removes its PID file (only if it
still owns it), so stale PID files stop accumulating.

## [v3.0.68-rc.12] - 2026-11-07
WebUI redesign: full design-system rewrite of `style.css` — indigo/violet gradient
accent on deep-slate background with radial glows, glass sticky header, gradient
logo wordmark + logo mark, colored stat-icon chips, pill badges with status dots,
shimmer progress bars, slide-in toasts, centered glass modal, styled scrollbars,
focus-visible rings, off-canvas sidebar under 900px, `prefers-reduced-motion`
support. All previously unsized SVGs (nav icons) now explicitly sized. Added
`color-scheme`/`theme-color` meta and inline SVG favicon.

## [v3.0.68-rc.11] - 2026-11-07
WebUI visual fix: header icons (menu toggle, refresh) had no size and rendered at the SVG 300x150 default, breaking the header layout. All header icons now fixed at 20px (`width`/`height` attrs + `.header-actions svg` rule), version badge bumped, logo mark added to the sidebar, `:focus-visible` outlines for keyboard navigation, collapsed sidebar shows only the logo mark.

## [v3.0.68-rc.10] - 2026-11-07
RC release with WebUI hardening and real downloads:
- Auth middleware deduplicated; public-route match is exact-or-child path; `POST /config/github-token` is public only until a token exists (bootstrap), so an exposed `--bind 0.0.0.0 --auth` server cannot be re-keyed
- WebUI downloads are real: live job registry, chunked ranged downloads with progress/speed/ETA, cancel with `.part` cleanup; dest constrained to `download_dir` (file name only) so a no-auth localhost server is not an arbitrary-file-write primitive
- `download_bandwidth_limit` now honored in both WebUI and CLI download paths
- New WebUI endpoints: `GET /state/export`, `GET /logs?lines=N` (protected)
- Single `USER_AGENT` const from `CARGO_PKG_VERSION` replaces 11 hardcoded UA strings
- `ohub search` auto-paginates up to `--limit` (GitHub 1000-result cap respected); `--dry-run` prints the query URL
- Removed orphaned `src/webui/spa.html`; unwraps on static templates → `expect`; `source.rs` chained unwraps → `is_some_and`
- Added `tests/cli.rs` smoke tests (assert_cmd); 53 unit + 4 integration tests, clippy `-D warnings` clean
- PLAN.md rewritten to current status; README auth/download docs updated

## [v3.0.68-rc.9] - 2026-11-06
Docs: complete README rewrite with full command reference, corrected TUI key descriptions, fixed github_token storage documentation (OS credential store, not plain text), added missing commands (log, info, reset) to command table.

## [v3.0.68-rc.8] - 2026-11-06
RC release with WebUI professional redesign and CI fixes:
- WebUI: embedded static SPA (index.html/style.css/app.js) with dashboard, apps/config/sources/token CRUD, download progress, update check
- Auth: public read routes, Bearer token auth on mutating routes when `--auth` set
- Port conflict detection (tries next port), default port 8080
- Self-update: stops WebUI via PID file before binary replacement
- Fixed clippy `needless_borrow` in `delete_app` route (`-D warnings` CI gate)

## [v3.0.68-rc.7] - 2026-11-06
RC release with WebUI professional redesign and CI fixes:
- WebUI: embedded static SPA (index.html/style.css/app.js) with dashboard, apps/config/sources/token CRUD, download progress, update check
- Auth: public read routes, Bearer token auth on mutating routes when `--auth` set
- Port conflict detection (tries next port), default port 8080
- Self-update: stops WebUI via PID file before binary replacement
- Fixed clippy `needless_borrow` in `delete_app` route (`-D warnings` CI gate)

## [v3.0.68-rc.6] - 2026-11-06
RC release with WebUI professional redesign and CI fixes:
- WebUI: embedded static SPA (index.html/style.css/app.js) with dashboard, apps/config/sources/token CRUD, download progress, update check
- Auth: public read routes, Bearer token auth on mutating routes when `--auth` set
- Port conflict detection (tries next port), default port 8080
- Self-update: stops WebUI via PID file before binary replacement
- Fixed clippy `needless_borrow` in `delete_app` route (`-D warnings` CI gate)

## [v3.0.68-rc.5] - 2026-11-06
RC release with WebUI professional redesign and CI fixes:
- WebUI: embedded static SPA (index.html/style.css/app.js) with dashboard, apps/config/sources/token CRUD, download progress, update check
- Auth: public read routes, Bearer token auth on mutating routes when `--auth` set
- Port conflict detection (tries next port), default port 8080
- Self-update: stops WebUI via PID file before binary replacement
- Fixed clippy `needless_borrow` in `delete_app` route (`-D warnings` CI gate)

## [v3.0.68-rc.4] - 2026-11-06
RC release with WebUI professional redesign and CI fixes:
- WebUI: embedded static SPA (index.html/style.css/app.js) with dashboard, apps/config/sources/token CRUD, download progress, update check
- Auth: public read routes, Bearer token auth on mutating routes when `--auth` set
- Port conflict detection (tries next port), default port 8080
- Self-update: stops WebUI via PID file before binary replacement
- Fixed clippy `needless_borrow` in `delete_app` route (`-D warnings` CI gate)

## [v3.0.68-rc.3] - 2026-11-05
Fix clippy `needless_borrow` warning in WebUI `delete_app` route that failed CI (`cargo clippy --all-targets -- -D warnings`). `remove_installed` takes `&str`; `repo` is already `&str` after `strip_prefix`, so pass it directly.

## [v3.0.68-rc.2] - 2026-11-05
WebUI professional redesign: modern dark-themed SPA with dashboard stats cards, responsive layout, toast notifications, auth login/logout modal, and full CRUD for apps/sources/token/config. Static assets (HTML/CSS/JS) embedded in the binary. Public routes (`GET /`, `GET /apps`, `GET /config`, `GET /config/sources`, `POST /config/github-token`) stay open; mutating routes require `Authorization: Bearer` when `--auth` is set. Catch-all path parameters for repo names containing `/` (`owner/repo`). Removed duplicate `### Added` section from previous release notes.

### Added
- Professional dark-themed WebUI SPA (vanilla JS, no build step)
- Dashboard with managed apps / downloads / updates / uptime stats
- Config editor (all keys) with inline save via PUT /config
- GitHub token add/remove via POST/DELETE /config/github-token
- Apps add/remove via POST/DELETE /apps
- Manifest sources add/remove via POST/DELETE /config/sources
- Download progress polling (2s) with progress bars and cancel
- Real GitHub API update check via POST /update-check
- Auth login/logout with Bearer token in browser sessionStorage
- Auto browser open on `ohub webui`
- WebUI PID file for self-update process termination
- Port conflict detection: tries next port if default is in use

## [v3.0.68-rc.1] - 2026-11-05
WebUI: `ohub webui` subcommand with `--port` (default 8080), `--bind`, `--auth` flags. Full-featured HTML single-page app at `GET /` with dashboard, apps table, config editor, token manager, source manager, download manager with progress bars, and update check. Protected API endpoints (`/config`, `/downloads/*`, `/update-check`, `POST/DELETE /apps`, `POST/DELETE /config/sources`) require `Authorization: Bearer <token>` matching the configured `github_token` when `--auth` is set; `/` and `GET /apps` stay public. Port conflict detection tries the next port if the default is in use. Default browser opens automatically on start. `ohub self-update` stops the WebUI before replacing the binary.

### Added
- WebUI HTTP server (Axum) with Bearer token auth middleware
- HTML single-page application (vanilla JS, no build step)
- Editable configuration (all keys) via PUT /config
- GitHub token add/remove via POST/DELETE /config/github-token
- Apps add/remove via POST/DELETE /apps
- Manifest sources add/remove via POST/DELETE /config/sources
- Download progress polling (2-second interval) with progress bars
- Auth login/logout with Bearer token in browser session
- Auto browser open on `ohub webui`
- WebUI PID file for self-update process termination

### Added
- WebUI HTTP server (Axum) with Bearer token auth middleware
- HTML single-page application (vanilla JS, no build step)
- `ohub webui --port 8080 --bind 127.0.0.1 --auth`
- Download progress polling (2-second interval) with progress bars
- Auth login/logout with Bearer token stored in browser session

## [v3.0.67] - 2026-10-23
Download-manager behaviour for slow and unreliable networks, plus download folder creation and clean cancellation.

### Fixed
- Downloads failed on slow networks because `minreq` buffered the whole body
  before reporting progress. Downloads now use Range requests in 1 MiB chunks,
  so a failed chunk is retried with exponential backoff and a partial file is
  resumed instead of restarted.
- Downloads did not survive a crash or restart. They now write to a
  `<file>.download` part file and resume from where they left off on the next
  run.
- Downloads stopped trying after a few retries. They now retry indefinitely
  until the download finishes or the user interrupts with Ctrl+C.
- No feedback when a download was stuck. A stall notification is printed to
  stderr after every 5 consecutive chunk failures.
- Download progress bar showed a spinner instead of real progress. It now
  shows bytes downloaded / total with ETA and download speed.
- The download folder was never created. `to_file` now creates the parent
  directory of the target before writing, so the first download of any repo
  no longer fails with "no such file or directory".
- Pressing Ctrl+C left a partial `<file>.download` part file behind. The
  download now listens for Ctrl+C and removes the part file before exiting,
  so nothing half-downloaded is left behind.

### Added
- `ohub log` shows the last N lines of the schedule log so users can diagnose
  failed scheduled checks without opening the log file in an editor.

## [v3.0.66] - 2026-10-23
Fixes for downloads failing on slow networks, a real download progress bar,
resume for interrupted downloads, and `ohub log` for diagnosing issues.

### Fixed
- Downloads failed on slow networks because `minreq` buffered the whole body
  before reporting progress. Downloads now use Range requests in 1 MiB chunks,
  so a failed chunk is retried with exponential backoff and a partial file is
  resumed instead of restarted.
- Download progress bar showed a spinner instead of real progress. It now
  shows bytes downloaded / total with ETA.

### Added
- `ohub log` shows the last N lines of the schedule log so users can diagnose
  failed scheduled checks without opening the log file in an editor.

## [v3.0.66] - 2026-10-23
Fixes for slow-network downloads, TUI notes scrolling and navigation, and
prerelease detection for install and self-update.

### Fixed
- Download progress bar filled instantly after the download finished (minreq
  buffers the whole body). A spinner now runs while the request is in flight
  and the bar shows the byte count when done.
- Requests failed on slow networks. Default HTTP timeout raised from 30 to
  300 seconds.
- TUI: pressing 'n' for release notes had no way back. 'n' now toggles the
  notes view open and closed.
- TUI: release notes longer than the screen could not be read. 'j'/'k' now
  scroll the notes while the details panel is open.
- TUI update failed with "request failed" on slow networks. Same timeout fix
  as the download path.

### Added
- `ohub install --prerelease` installs the latest release including
  pre-releases (was ignored; only the latest stable was ever found).
- `ohub self-update --prerelease` updates to the latest pre-release when no
  newer stable release exists.

## [v3.0.66-rc2] - 2026-10-22
Eight flags that were accepted and did nothing, a restore that put the apps
in a directory the tool never looks at, and one download implementation
instead of four. Plus a `--version` that says something useful and examples
in every command's help.

### Fixed
- `ohub restore` extracted the apps into `%APPDATA%\obtainhub\installed` while
  `ohub install` uses `config.install_dir`. The restored apps were invisible
  to `ohub list` and `ohub uninstall`. The apps now go where the config in
  effect says they go: the backed up config's `install_dir` when the config
  or the state is restored, the current one otherwise.
- `ohub self-uninstall --backup` printed "To restore, run: ohub self-uninstall
  --restore <file>". That flag did nothing: the command ignored it and
  uninstalled the tool instead of restoring it. The message now names the
  command that works, `ohub restore <file>`.
- `ohub update` verified the digest of the bytes it had in memory and only
  then wrote the file. The digest is now checked against the file on disk,
  and a file that does not match is deleted instead of left for the next run
  to install.
- The build stamp reported `Rust: unknown`. `build.rs` read a `RUSTC_VERSION`
  environment variable that Cargo never sets; it now asks the compiler it is
  driving.

### Added
- `--verbose` turns the log level up to debug. `RUST_LOG` still wins when it
  is set.
- `--no-color` drops the colours from the progress bar. `indicatif` has no
  `NO_COLOR` support, so the plain template is used instead.
- `ohub --version` prints what the tool is, its repository, licence, author,
  platform, build date and rustc version, and how it is installed. `ohub -V`
  still prints the bare version for scripts.
- Every command has examples in its help: `ohub install --help`,
  `ohub restore --help`, `ohub config --help` and the rest.

### Changed
- Every download goes through one implementation now (`core::download`). The
  registry path, `install --url` and `update` had four copies of it.
- The bandwidth limit (`download_bandwidth_limit`) applies to every download.
  Before, only the registry path honoured it: `install --url` and `update`
  downloaded at full speed.
- A download that cannot be rate limited now names the URL and says why: the
  server does not support range requests.
- Download failures name the URL and the path they were writing to, instead
  of "Failed to send request".

### Removed
- `search --include-inactive` and `search --case-insensitive`. Both were
  accepted and did nothing, and both claimed a default that does not exist:
  the search already includes inactive repositories, and GitHub's search is
  already case-insensitive.
- `self-uninstall --target-config`, `--target-state`, `--target-downloads`
  and `--no-token`. They belonged to a restore path that was never
  implemented. `--target-config` and `--target-state` now belong to
  `ohub restore`, where they work: the restored `config.toml` and
  `state.json` are written into the directory you name instead of the live
  one.
- `self-uninstall --restore`. `ohub restore` is the command that restores.

## [v3.0.65] - 2026-10-21
The first final release. It carries every change from the release-candidate
cycle (v3.0.15-rc1 through v3.0.65-rc1): the commands that were
accepted and did nothing, the GitHub token moved out of the config file
into the OS credential store, and the plan items that were
declared but never acted on.

### Fixed
- `ohub install --dependencies a/b,c/d` recorded the dependencies in the state but never installed them. They are installed first now, and marked in the state so `ohub uninstall` will not remove a dependency on its own. One level deep on purpose: a dependency's own dependencies are not known until it is installed, and a cycle would recurse forever.
- `download_bandwidth_limit` was a config field that nothing read. The download is really paced now: the file is fetched in chunks, one chunk per second, as many bytes as the limit allows in that second. `minreq` buffers the whole body, so a single request cannot be slowed down - the server has to support Range requests.
- Checksum verification for non-GitHub registries was a TODO. crates.io publishes the sha256 of the `.crate` file, and it is verified now.
- `ohub config set download_bandwidth_limit 512` is a real setting now (KB per second; `none` clears it).
- The GitHub token was stored in plain text in `config.toml`. It now goes into the Windows Credential Manager, and the plain text copy is removed from the config file. A token left behind by an older version moves into the credential store on the first run.
- `ohub config set github_token <token>` echoed the token to the terminal and to the log file. It prints `[stored]` now.
- `ohub config show` printed the token. It is masked now.
- `ohub self-uninstall` printed "GitHub token removal from keyring not implemented in this version" and left the credential behind. It removes the credential now.
- `ohub reset` cleared the config but not the credential store. Both are cleared now, and `--keep-token` puts the token back.
- `--arch` was ignored by `install`, `update` and `rollback`: the asset was picked by the machine's architecture, not the one you asked for. It is honoured now, and `rollback` gained the flag it was missing. The old matcher also accepted an arm64 asset on an x64 machine - that cannot happen any more.
- `ohub check --timeout N` was accepted and did nothing. The timeout is now one setting for the whole run: every GitHub call uses it, and the value is validated (10-300 seconds).
- `ohub add --add-type zip` printed "not yet implemented". It extracts the archive into the managed tree and tracks it.
- `ohub add --as-source` printed that it "would need config manager mutable access". The source is registered now.
- `ohub check --notes` and `ohub update --notes` were accepted and did nothing - `fetch_release_notes` lived in the TUI, so the CLI path had nothing to call. The helper moved to `core::registries` and is now shared: `check --notes` prints the release notes of every outdated repo, `update --notes` prints them for every repo that was updated.
- `ohub restore --config` printed "Config restore not yet implemented (requires ConfigManager save)". `ConfigManager::save()` has existed all along - the saved config is now written back.
- The clippy gate (`-D warnings`) fired on a nested `if` in the check summary, which blocked the whole release. The `if` is collapsed and the `--force` branch in `update` is flattened the same way.
- `ohub update --force` was passed down to the installer and then ignored, so it did nothing. It now reinstalls the app even when it is already on the latest version, and says so (`Force reinstalling 3.9`).
- The dead `force` parameter of `install_release` was removed rather than left as a no-op.
- Two clippy findings in the new path lookup: `manual_strip` in `core/winreg.rs` (`strip_prefix` instead of `starts_with` + slice) and `type_complexity` in `commands/list.rs` (the row type is now named). Both are behaviour-neutral, so the v3.0.56-rc1 binary is unaffected.
- `ohub list` still showed the wrong folder for some apps. The install path is now resolved through a cascade: `InstallLocation` (only when the folder really exists on disk), then `DisplayIcon` - the program's own exe path, which is the only answer for the many apps that leave `InstallLocation` empty - then the folder holding the uninstaller. Uninstaller paths in a `bin` subfolder resolve to the app folder, and quoted paths that contain spaces (`C:\Program Files\...`) are no longer truncated.
- `ohub list` now writes the resolved path back to `state.json`, so the TUI, `ohub uninstall` and every later run agree on where the app lives instead of each re-deriving it.
- The registry lookup is version-aware: when an old install is left behind next to a new one, the entry matching the recorded version wins.
- TUI: the app list is a table - one row per app with aligned Installed / Latest / Status columns - so the whole list is visible at a glance instead of one long line per app. The header and footer are one line each, giving the table the rest of the screen.
- TUI: `^` marks the apps that need an update, the Status column is red and bold for them, and the panel title says how many need one.
- TUI: `remove` and `add` corrupted the screen because the command printed into the alternate screen while the TUI was still in raw mode. The TUI now leaves the alternate screen for the duration of the command and comes back afterwards.
- TUI: while a filter is active, every printable key was swallowed by the command shortcuts, so `q`, `a`, `r`, `u`, `x` and `c` could not be typed into the filter. The command keys are now guarded off while filtering, and only Esc, Enter, Backspace and the arrow keys stay live.
- `ohub check --all` and `--candidates` explain their purpose in plain words, with an example, and end with a summary line: managed / unmanaged / outdated / up to date.
- `ohub list` passed `&repo` where `repo` was already a reference, which clippy rejected (`needless_borrow`). The binary in v3.0.54-rc1 was unaffected - only the CI lint gate was red.
- `ohub list` showed ObtainHub's own download folder instead of where the app actually lives. The path is now read from the Windows uninstall registry (`C:\Users\x\AppData\Local\Programs\OnionHop V3\`), falling back to the stored path when Windows does not know the app.
- `ohub add` now records the app's real install folder instead of `repos\<owner>\<repo>\`. The "path already exists" prompt only fires for folders inside ObtainHub's own tree.
- TUI: the app list was rendered into a 3-row strip when no filter was active, so only one app was visible at a time. The list now gets the whole main area and the filter bar row collapses when not filtering.
- TUI: install/remove printed to stdout, which landed inside the alternate screen and left the command output mixed into the UI. The screen is now wiped and repainted after those actions.
- TUI: up-to-date apps were shown as "Update" because the GitHub tag (`v3.9`) and the installed version (`3.9`) were compared as raw strings. Versions are now normalized before comparing.
- `ohub update` stored the raw tag (`v3.9`) as the installed version, which then differed from the registry version. The stored version is now normalized.
- `ohub rollback` looked up the release tag as `3.8.6` when the tag on GitHub is `v3.8.6`. It now tries both forms.
- 75 clippy findings cleared across 16 files: needless borrows, redundant field names, no-op `..Default::default()` struct updates, `sort_by` → `sort_by_key`, `iter().any()` → `contains()`, `iter().cloned().collect()` → `to_vec()`, `Iterator::last` → `next_back`, collapsible `if` blocks and match arms, unnecessary casts, a dead `GitHubRepoInfo` struct, and an unused type parameter on the TUI draw function.
- Windows build broke in two places, both hidden from Linux because the code sits behind `#[cfg(windows)]`:
  - `src/core/elevate.rs` called `Result::context()` — a trait method — but only imported `anyhow::Result` (E0599). `anyhow::Context` is now imported under `#[cfg(windows)]`.
  - `src/commands/check.rs` moved `entry.display_name` out of the registry entry and then borrowed the whole entry again for `entry.install_dir()` (E0382: borrow of partially moved value). The install path and uninstaller are now read before the move.
- The v3.0.50-rc1 and v3.0.51-rc1 releases never published an installer: the Windows CI build failed on the same errors, so no MSI or NSIS EXE was attached. Use v3.0.52-rc1 instead.
- `ohub check` ran its self-update check against a throwaway `ConfigManager`/`StateManager`, so the user's GitHub token was ignored and every self-update check hit the anonymous 60 req/hr limit. It now uses the real config and state.
- `ohub update` reported success when an installer failed because the app was still running. The Windows uninstall registry is now snapshotted before and after the installer runs, and the result is verified against it.
- `ohub update` prints a progress bar while downloading and shows the download directory it actually uses.
- `ohub update` sets `install_path` to install directory (`repos\owner\repo\`) instead of downloaded setup file (`repos\owner\repo\OnionHop-Setup-v3.exe`). `ohub list` Path column now shows the install folder, not the downloaded .exe/.msi file.
- Consistent 403 error message across ALL commands: "GitHub API rate limited or access denied (403). Set a token: ohub config set github_token <token>"
  - check (check.rs, find_candidate_repos)
  - update (update.rs, find_candidate_repos)
  - self_update (self_update.rs - releases/latest, releases list, tags)
  - install (install.rs - fetch_repo_info, fetch_latest_release, fetch_release_by_tag, search_github_repos)
  - info (info.rs)
  - source (source.rs)
  - tui (tui.rs)
  - add (add.rs)
  - search (search.rs)
- `ohub update` showed wrong directory (download_dir instead of install_dir where files are actually stored)
- CI compile error E0716: `format!()` temporary dropped before `Command::args()` used it in `run_installer` (update.rs) and self-update elevation (self_update.rs). Now binds `format!()` result to a named variable before passing its reference to `.args()`.
- `ohub update` 403 error now says "rate limited or access denied" with token hint
- `ohub update` runs installer for .exe/.msi assets (was only saving to disk)
- CI: NSIS install uses winget → Chocolatey → GitHub releases (SourceForge returned HTML error pages instead of binaries). Size validation raised to 2MB. Accepts NSIS 3.10.1 or 3.11.
- CI: NSIS install robustness — multiple SourceForge mirrors, `-UseBasicParsing`, file size validation; accepts NSIS 3.10.1 or 3.11 (prevents corrupted-download build failures)
- `ohub update` asset detection: if no arch-specific installer (.exe/.msi matching `x64`, `win64`, `windows`, etc.) is found, falls back to ALL `.exe`/`.msi` assets. Asset naming varies across repos — some use `Setup.exe` with no arch token — fallback ensures installers are never missed.
- `ohub update` arch detection now matches `x64`, `64-bit`, `64bit` tokens in addition to `x86_64`, `amd64`, `aarch64`, `arm64` — Windows assets named `Setup-x64.exe` / `Setup-64bit.msi` are now detected
- Same arch tokens added to `install.rs` `select_asset` for consistency
- `ohub update` dependency update call passes new `selected_asset` parameter
- `fetch_published_checksum` call uses local `InstallGitHubRelease` conversion
- `src/commands/check.rs`: removed duplicate managed-repo checking code that was accidentally inside `--candidates` block
- `src/commands/check.rs`: added `extract_vendor()` helper for vendor name detection from installed program names
- `ohub self-update` EXE/MSI installer now replaces running `ohub.exe` correctly. Renames running exe to `ohub.exe.old` before launching installer, restores on failure, deletes on success. Fixes "ohub.exe not replaced — Control Panel shows new version but file is old".
- RC build for self-update test: verifies elevated EXE/MSI installer launch via `find_powershell()` path resolution
- `ohub self-update` EXE/MSI elevation: `powershell` not found → "program not found". Now resolves `powershell.exe` from explicit paths (`C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`, `C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe`) then falls back to PATH.
- `src/commands/check.rs`: added missing `use std::path::PathBuf;` import — CI compile error `E0433: cannot find type PathBuf in this scope`
- `ohub list` Path column now shows install folder (from Windows `InstallLocation` or `UninstallString` directory), not `uninstall.exe` path
- `ohub check --all` documented: scans ALL installed Windows programs, lets user select unmanaged ones to add, offers candidate GitHub repos for each, then checks for updates
- `ohub check --all` now reads installed version from Windows registry scan (`DisplayVersion`) instead of stale `state.json` version from previous runs — `ohub list` shows correct installed version
- `ohub check --all` syncs corrected versions back to `state.json` when registry scan differs from stored version
- `ohub update` dependency version comparison now uses `normalize_version` (strips `v`/`V` prefix)
- `ohub check` fall-through version comparison uses `normalize_version` so `v3.9` vs `3.9` matches correctly
- `ohub check --candidates` / `ohub check --all` no longer overwrites installed `version` with GitHub's latest tag when adding repos - `ohub list` now shows correct installed version and `ohub update` correctly detects outdated repos
- Version comparison in `--candidates`/`--all` fall-through now strips `v`/`V` prefix (`normalize_version`) so `v3.9` vs `3.9` matches correctly
- `ohub check --candidates` / `ohub check --all` no longer lists duplicate managed repos (dedup via `already_checked` set)
- Added repos keep their real `install_path` and `version` from Windows registry scan instead of `unknown` / empty PathBuf
- `ohub list` now shows correct installed version and path (populated from registry scan at add time)
- `ohub update` correctly detects outdated repos (version normalization strips `v`/`V` prefix; installed version no longer overwritten by GitHub tag)
- `ohub self-update` / `ohub check` / `ohub update` no longer crash with "unexpected end of file" on empty GitHub API responses — validates body before JSON parsing
- `ohub self-update` launches MSI/EXE installers elevated via PowerShell `Start-Process -Verb RunAs` — fixes "The requested operation requires elevation" (os error 740)
- `ohub check`/`ohub self-update` give clear 403 error: "Rate limited or access denied. Set GitHub token with 'ohub config set github_token <token>'"
- `ohub self-update` now launches MSI/EXE installers elevated via PowerShell `Start-Process -Verb RunAs` — fixes "The requested operation requires elevation" (os error 740) on Windows
- `ohub self-update` no longer crashes with "unexpected end of file" when GitHub API returns empty body - now checks status code and body length before parsing JSON
- `ohub check --candidates` and `ohub update` no longer crash with "unexpected end of file" on GitHub API errors or empty responses - non-2xx status codes return empty candidate list instead of erroring
- All GitHub API JSON parsing now reads raw bytes first and validates non-empty body before deserializing
- `ohub check --candidates` and `ohub update` now strip noise words (`version`, `edition`, `x64`, `x86`, `64-bit`, `32-bit`, etc.) from app names so "OnionHop V3 version 3.8.6" cleans to "OnionHop"
- `find_candidate_repos` tries multiple search term variations: cleaned name, first word of cleaned name, original with digits/dots stripped, then original name — maximizing hit rate for apps with public GitHub repos
- `ohub self-update` no longer tries to extract `.exe`/`.msi` installer assets as zip - now runs MSI (`msiexec /i /qn /norestart`) and NSIS EXE (`/S`) installers silently instead
- `ohub update` defaults to checking only managed repositories (from state.json) - no longer scans all installed software by default
- Version comparison now strips `v`/`V` prefix (e.g. `v3.0.25` == `3.0.25`) so `ohub check`/`ohub update` correctly detects outdated repos
- `ohub install` no longer fails with "missing field tag_name" when registry API omits tag_name - now defaults to "unknown"
- `ohub self-update` lists available assets with manual download URL when no platform-specific zip found
- `ohub self-update` no longer bails with "No suitable release asset found" when no platform-specific zip exists - now lists available assets and provides manual download URL
- `ohub self-update` falls back to any asset when no platform-specific zip found
- `ohub check --candidates` now shows ALL unmanaged apps with candidate repositories found via GitHub search
- `ohub check --candidates` cleans app names (strips version numbers like " V3 3.8.6") for better GitHub search results
- `ohub check --candidates` allows manual `owner/repo` entry when no candidates found
- `ohub check --candidates` falls through to show check results for newly added repos
- `ohub check --all` 404 - `fetch_latest_release` returns `Option<GitHubRelease>`, skips repos without releases gracefully
- `ohub check --candidates` no longer returns early - falls through to show check results for newly added repos
- `ohub update` 404 - same `Option<GitHubRelease>` handling with retry logic
- `ohub tui` now fetches latest versions from GitHub, shows Current/Update/Unknown/Unmanaged status
- `ohub tui` 'r' key actually refreshes app list from GitHub
- Self-update 404 - falls back to releases list, then tags when no releases published
- Check command: `fetch_latest_release` returns `Option<GitHubRelease>` - no longer errors on 404, skips repos without releases gracefully
- Check command: `--candidates` shows ALL unmanaged apps (not just those with candidates), lets user choose both software AND candidate repository
- Add command: verifies GitHub repository exists before adding to management
- Version output uses standardized template
- Build constants generated without vergen dependency (Rust 1.85 compatible)
- Self-update 404 - fixed GitHub API endpoint (ObtainHub repo name case)
- Check command: `--all` no longer 404s on ObtainHub's own repo (skipped during check)
- NSIS installer detects installed version and offers upgrade/uninstall options
- Colors: Only green removed - uses terminal default colors everywhere
- Self-update check 404 - fixed GitHub API endpoint and added retry logic
- Check command: `--candidates` now shows all unmanaged apps with their candidate repositories
- Check command: `--all` now shows all unmanaged apps with interactive selection
- Colors: Only green for selection checkboxes/ticks, default color for all other text
- Added retry logic for all HTTP requests, configurable via config (http_retries, http_retry_delay_ms, http_retry_backoff)
- More informative output - progress bars for scanning and candidate searching with detailed messages
- Self-update check now uses retry config and proper error handling
- Check command: `--candidates` works independently of `--all`
- Check command: Shows candidate repositories for unmanaged apps with GitHub search
- Check command: Self-update check when no specific repo specified
- Check command: `--quiet` flag to suppress non-error output
- NSIS "Installer corrupted: invalid opcode" - pinned NSIS 3.11 with SourceForge fallback
- NSIS PathHasEntry Exch → Push fix for NSIS 3.13 stack-exchange bug
- Check command: shows candidate repositories for unmanaged apps with GitHub search
- Check command: self-update check when no specific repo specified
- Check command: `--all` now checks unmanaged apps by finding GitHub repos by name
- Check command: `--candidates` now works independently of `--all`
- Check command: added self-update check when no specific repo specified
- Check command: added `--candidates` flag to find GitHub repos for unmanaged apps
- Check command: added `--quiet` flag to suppress non-error output
- NSIS "Installer corrupted: invalid opcode" — replaced `Exch $R0` with `Push $R0` in `PathHasEntry` / `un.PathHasEntry` to avoid NSIS 3.13 stack-exchange bug triggered by compiler optimization `+2`
- NSIS pinned to 3.11 with SourceForge fallback (fixes "Installer corrupted: invalid opcode")
- The NSIS installer failed on Windows with "Installer corrupted: invalid opcode" before showing any dialog. v3.0.4 and v3.0.5 were both built with NSIS 3.13, which winget installs by default. The published file was not corrupt in transit: its SHA-256 matched the published `SHA256SUMS`, the MZ header was intact, the `NullsoftInst` magic sat at the expected offset, and the sizes matched what CI built. The fault was in how 3.13 emitted this script.
- The build toolchain was unpinned. `winget install NSIS.NSIS` resolves to whatever "latest" is, so the NSIS version could change between runs with no diff to review. NSIS is now pinned to 3.11, the installer download is verified by SHA-256 before use, and the build asserts `makensis -VERSION` reports 3.11 before running.
- Checksum verification never verified anything. `verify_checksum` looked for a `<archive>.sha256` file inside the newly created install directory, where nothing ever writes one, so every install warned and returned `Ok`. `install` now reads a digest published with the release (`<name>.sha256`, `SHA256SUMS`, `checksums.txt`) and compares against it; `install --file` and `--url` read a sidecar next to the archive. Mismatches abort the install.
- `self-update` downloaded a release asset and overwrote the running binary with nothing verified. It now requires a published digest and refuses to run when none exists, failing closed.
- `config get github_token` printed the token verbatim, leaking it into shell history and CI logs. It now returns `[stored]`.
- `backup` and `reset --backup` embedded the plaintext GitHub token in the archive. Both strip it and report that they did.
- `reset --move-token` and `--keep-token` were stubs that printed "not implemented". The token is now captured before the reset: `--keep-token` restores it, `--move-token` writes it to the given path with 0600 on Unix.
- Mutual refusal was dead code in both directions.
  - NSIS looked for the MSI under `Uninstall\{UpgradeCode}`, but Windows Installer registers under the ProductCode and `setup.wxs` uses `Id="*"`, so that key holds a different GUID on every build. NSIS now detects the MSI through its stable marker `HKLM\Software\ObtainHub\PathInstalled`, and clears that marker on uninstall.
  - The MSI searched `Uninstall\{...}_is1`, but NSIS only appends `_is1` when the app id is not already a GUID. The key never existed, so the search could not match. Fixed the key and restored the launch Condition.
- `check --all` sent every installed Windows program's `DisplayName` to the GitHub releases API. `NVIDIA Corporation` is not `owner/repo`, so every lookup 404'd and the request volume exhausted the unauthenticated rate limit. Only programs tracked in `state.json` are now queried; the rest are reported as skipped.
- Silent-install conflict handling never compiled: `StrCmp $Silent 1` was rejected as an unknown variable, so the auto-uninstall-MSI and upgrade-in-place branches were silently dropped. Replaced with the `IfSilent` instruction.
- Silent-install conflict handling never compiled. `StrCmp $Silent 1` was rejected by makensis as an unknown variable, and the compiler silently ignored both occurrences, so the auto-uninstall-MSI and upgrade-in-place branches were dropped from the binary. Replaced with the `IfSilent` instruction.
- Version numbers had drifted: the v3.0.1 tag was cut while `Cargo.toml`, `installer/ObtainHub.nsi`, and `installer/setup.wxs` all still said 3.0.0, so the published installers reported the wrong version. All four sites are now bumped together and `PROJECT.md` §2 records the rule.
- MSI build: `installer/setup.wxs` was missing `Platform="x64"`, so ICE80 rejected the package (LGHT0204) because `PathEnvironment` and `MainExecutable` are both `Win64="yes"`. Removed the 32-bit `RegistrySearch` too — a 64-bit package cannot carry a 32-bit Locator (LGHT1076).
- Zip-slip: `install.rs` joined attacker-controlled zip entry names onto the install directory without validation, so an entry named `../../evil.exe` wrote outside it. Reachable via `install` and `install --url`, which fetch archives from the internet. `update.rs` had the same hole through `archive.extract()`. Both now normalize the path through `Path::components()` before the containment check, with three tests covering parent traversal, absolute paths, and normal entries.
- `uninstall --purge` now drops the repository's state metadata and its membership in any group, instead of printing "not yet fully implemented".
- `update` installs to `config.install_dir` instead of a hardcoded `ObtainHub/repos` path, so a custom install directory is respected.
- `ohub completion` no longer panics on a broken pipe (`ohub completion fish | head`).
- Config values that would hang or divide by zero (`parallel_downloads`, `timeout_seconds`, `update_check_interval_hours`, `schedule.interval_hours`) are reset to defaults on load and on save.
- NSIS installer corruption: replaced `/SOLID LZMA` with per-file LZMA/zlib and CRCCheck on to avoid CRC bug
- MSI build: removed unsupported `Platform` and `Schedule` attributes from WiX XML
- Missing imports in TUI modules: `anyhow::Result` in `src/tui/mod.rs`; `ratatui::Frame`, `ratatui::Terminal`, `ratatui::backend::CrosstermBackend` in `src/commands/tui.rs`; `tracing::subscriber::registry` in `src/core/logger.rs`
- Dependency compilation hang: removed `build.rs` workaround, cleaned Cargo.toml, used offline builds with proper target directory
- Silent mutual refusal: EXE and MSI both respect `/S` flag for silent uninstall during conflict resolution
- NSIS installer binary path now uses relative 'ohub.exe' to ensure the binary is correctly picked up from installer/ directory
- Checksum verification now works in `update` command by fetching published SHA256SUMS/checksums.txt from release assets
- Search command now supports pagination (`--page`, `--per-page`) and per-repo timeout configuration
- Architecture selection now consistent across install/update commands (Plan #7)

### Added
- `ohub check --candidates` searches GitHub up to four times per installed app, on every run. The result is now cached for a day (`%APPDATA%\obtainhub\candidate-cache.json`), so a second run costs no API calls and does not eat the rate limit.
- The release workflow can be dispatched from the Actions tab with a tag: it creates the tag, and the tag push starts a fresh run that builds, checks and publishes the release.
- `--timeout` on `install` and `update` (the `check` flag existed and did nothing).
- `--arch` on `rollback`.
- `ohub group install|update|check|uninstall` now run the real command for every member of the group, one at a time, instead of printing "Bulk X integration pending". The group config model was already there - only the loop was missing.
- `ohub schedule enable` registers a real Windows Task Scheduler task (`ObtainHubScheduledCheck`) that runs `ohub check --quiet --log` on the configured interval. `disable` removes it, `status` shows the task's next run time, and `run` does the check now and writes the same report the scheduled task would. The task name is the one `ohub cleanup tasks` already looks for.
- `ohub check --log <PATH>` appends a run report (outdated apps, errors, summary) to a file. The report is written even when the console output is suppressed, so a scheduled run leaves a record.
- TUI: mark apps with `Space` and update them together with `U`, or update every outdated app with `A`. Marked rows show `[x]`, the panel title counts them.
- TUI: `s` cycles the status filter - all / outdated / current / unknown - and the panel title says which one is active.
- TUI: `R` refreshes only the selected app. `r` still refreshes every app, which is one GitHub call per app.
- TUI: `n` shows the release notes of the selected app in the details panel.
- TUI: `y` copies the selected app's install path to the Windows clipboard.
- Update and remove now ask for confirmation: the status line shows what will happen (`Update OnionHop 3.8.6 -> 3.9?`), `Enter` confirms, `Esc` or any other key cancels.
- README: a table of the TUI keys.
- TUI layout regression tests. The TUI is rendered into a `ratatui` `TestBackend` and asserted: every app gets its own row, the table fills the main area (the list used to be squeezed into a 3-row strip where only one app was visible), apps needing an update carry the `^` marker and are counted in the title, and the filter narrows the table.
- `ohub update --quiet` suppresses progress output; `--log <PATH>` appends a run report to a file. Scheduled runs now leave a record behind.
- `ohub rollback` re-downloads and reinstalls the recorded `previous_version` from its GitHub release tag instead of copying files around. Supports `--yes` (skip confirmation) and `--quiet`.
- `ohub doctor` rewritten: checks Install / Download / Shim directories for existence **and** writability, reports proxy, GitHub token state plus remaining rate limit, and verifies the install and shim directories are on `PATH`. New `--strict` flag exits non-zero when issues are found.
- `ohub check` offers to update outdated apps in one go (skipped under `--quiet` / `--outdated_only`, auto-confirmed with `--yes`).
- New `src/core/elevate.rs`: one shared elevated-launch helper for installers and uninstallers (PowerShell `Start-Process -Verb RunAs -Wait`).
- CI: separate `check` job on pull requests — `cargo check --all-targets`, `cargo test`, `cargo clippy --all-targets -- -D warnings`.
- Track real install location + uninstaller for third-party installers. `ohub update` snapshots the Windows uninstall registry before and after running an installer, then records where the app landed and how to remove it.
- `ohub uninstall` now runs the app's own registered uninstaller (elevated) instead of only deleting ObtainHub's download folder. Handles NSIS (`unins000.exe`), MSI (`MsiExec /X{GUID}`) and Burn bundles (`/I` → `/X`).
- New `src/core/winreg.rs`: uninstall-registry scanning and change detection (new entry or version bump), with 4 unit tests.
- New `src/core/elevate.rs`: shared elevated-launch helper for installers and uninstallers (PowerShell `Start-Process -Verb RunAs -Wait`).
- `state.json`: new `uninstaller` field on each managed app (optional; old state files still load).
- TUI: Interactive update (`u`) - updates selected app with update available
- TUI: Remove from management (`x`) - removes selected app from tracked list
- TUI: Filter apps (`/`) - filter by name, repo, or status with live filtering
- TUI: Clear filter (`c`) - clears active filter
- TUI: App details (`Enter`) - shows full app info including install path
- TUI: Shows available version arrow (→ v3.9) next to outdated apps
- TUI: Filter bar shows active filter text
- TUI: Updated key bindings in help screen
- `ohub update` skip download if file already exists with matching size + SHA256 checksum (prevents redownload)
- `ohub update` removes old file with same name before writing new one
- `ohub update` shows both Install directory and Download directory at start
- `ohub update` download folder cleanup: keeps only latest versioned file per base name, removes older duplicates
- `ohub update` progress bar on download (indicatif)
- `ohub update` shows download directory at start
- `ohub update` verifies installation succeeded (file exists, non-zero, correct size)
- `ohub update` runs .exe/.msi installer after download with elevation
- `ohub update` interactive asset selection: Select dialog lists only `.exe` (setup) and `.msi` installer assets matching current architecture. `.msi` preferred over `.exe` (sorted first, default selection). Other file types (.zip, .tar.gz, etc.) hidden.
- `GitHubAsset` in update.rs now derives `Clone`
- `ohub check --candidates` vendor exclusion: MultiSelect before GitHub search lets user exclude vendors (Microsoft, Adobe, Oracle, Apple, Intel, NVIDIA, AMD pre-selected) to keep candidate search efficient
- README command reference: detailed descriptions for every command, `--all`/`--candidates` flows, version comparison rules
- `ohub search` now shows interactive selection - select repos from search results, then add to managed list or install immediately
- `ohub install` falls back to GitHub search when exact repo not found, offers interactive selection of candidates
- `ohub update` auto-detects unmanaged apps on the system and offers to add them as managed repositories before updating
- `ohub check --all` shows sorted list of unmanaged apps, then after confirming selections offers candidate repositories for each
- Retry logic for `ohub update` (configurable via http_retries, http_retry_delay_ms, http_retry_backoff)
- `ohub add --type folder` - manage portable applications from local folders
- Folder mode scans for executables (.exe on Windows, executable permission on Unix)
- `--recursive` flag for subdirectory scanning
- `--repo-arg` to link folder app to a GitHub repo for updates
- Creates shims in shim_dir for each executable found
- Adds each executable to state.json for tracking
- Shows PATH instructions for using apps from anywhere
- Retry logic for `ohub add` repository availability check
- Configurable retry via `http_retries`, `http_retry_delay_ms`, `http_retry_backoff` in config
- CLI message templates module for consistent output formatting
- Version templates with build metadata (timestamp, rustc version, git info)
- Build script emits vergen-compatible constants without external dependency
- Error/Warning/Info/Success message templates
- Progress/Status templates for long-running operations
- Repository info, install result, update availability templates
- Search result, list item, uninstall confirmation templates
- Rollback info, config, dry run templates
- More informative output - detailed progress/info messages for all operations
- Check command: Shows "Checking ObtainHub self-update..." before self-update check
- Check command: Shows "Checking N managed repositories for updates..."
- Check command: Shows "Scanning Windows registry for installed programs..."
- NSIS installer: Displays installed version vs new version in conflict dialogs
- Uses terminal default colors - no custom color overrides
- Progress bars for scanning installed programs and finding candidates
- Green tick marks and gray checkboxes in interactive MultiSelect
- Interactive `--all` offers selectable list for unmanaged apps
- Interactive `--candidates` offers selectable list to add apps to management
- After selecting app, immediately checks candidates and offers repository selection
- Added `dialoguer`, `console`, `indicatif` dependencies for interactive prompts and progress bars
- Retry configuration in config.json (http_retries=3, http_retry_delay_ms=1000, http_retry_backoff=2.0)
- Check command: Removed timestamp from command output (clean output)
- Check command: Progress bars for scanning and candidate searching
- Check command: Green tick marks and gray checkboxes in interactive selection (MultiSelect)
- Check command: Interactive `--all` offers selectable list for unmanaged apps
- Check command: Interactive `--candidates` offers selectable list to add apps to management
- Check command: After selecting app, immediately checks candidates and offers repository selection
- Check command: `--all` now offers interactive selectable list for unmanaged apps
- Check command: `--candidates` now offers interactive selection to add apps to management
- Added `dialoguer` and `console` dependencies for interactive prompts
- RC build for v3.0.9 with all v3.0.8 features
- RC build for v3.0.8 with all v3.0.7 features
- Releases now publish `SHA256SUMS` alongside both installers, which is what makes self-update's verification satisfiable.
- Tests for the digest parsers and the manifest filename match: 13 total.
- `PROJECT.md`: living reference for installer invariants, GUID requirements, filesystem layout, config contract, and security posture.
- `CONTRIBUTING.md`: build, test, installer, and release procedure.
- README: examples for every major command; corrected config path.
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

### Changed
- `ohub config auth` reports where the token actually lives: "credential store", "config file" or "not set".
- A machine with no credential store keeps the token in the config file and says so.
- README: `--notes` and the `backup` / `restore` commands are documented.
- PROJECT.md: three stale claims corrected - `update.rs` does verify the published SHA256, and `ohub rollback` is implemented.
- `ohub group` and `ohub schedule` take a mutable state manager, so the bulk actions can install, update and uninstall for real.
- README: the group and schedule commands are documented, and the wrong `ohub group create` example is now `ohub group add`.
- The version comparison that decides the Status column lives in one place (`status_for`), so the TUI list, the `^` marker, the update counters and the status filter can no longer disagree about what needs an update.
- `ohub check --all` and `ohub check --candidates` now print what they are about to do before doing it, so the purpose of a full registry scan is obvious.
- `normalize_version()` moved to `core::state` and is shared by check, update and tui instead of being copied three times.
- CI uploads `check.log` / `test.log` / `clippy.log` / `build.log` as workflow artifacts when a job fails. Job logs are admin-only in the public API, so before this a failed Windows build could not be diagnosed without repo access.
- Clippy is a hard gate again (`-D warnings`) now that the lint backlog is cleared.
- Compiler warnings: **91 → 0**. Unused parameters renamed to `_`, dead serde fields marked `#[allow(dead_code)]`, `partition_gitHub_managed` renamed to `partition_git_hub_managed` (clippy `snake_case`).
- Dead code deleted instead of maintained: `src/cli/templates.rs`, `src/tui/mod.rs`, `assets.rs::{download_with_progress, verify_checksum, download_verify_extract}`, `logger.rs::init_with_level`, `registries.rs::Registry::registry_type`, `install.rs::{fetch_repo_info, fetch_latest_release, fetch_release_by_tag}`, `update.rs::{enumerate_all_installed_software, find_candidate_repos, clean_app_name}`.
- `ohub list` Path column now shows the app's real install folder (e.g. `C:\Users\x\AppData\Local\Programs\OnionHop V3\`) instead of ObtainHub's download folder.
- `ohub check --all` / `--candidates` capture each app's uninstaller from the registry, so `ohub uninstall` works for apps tracked without an update.
- `check.rs` registry scan now delegates to `core::winreg` (removed ~40 lines of duplicated code).
- NSIS pinned to 3.11 with SourceForge fallback
- Updated CHANGELOG for RC release
- The release job now checks out the repository. It previously ran the changelog extraction against an empty workspace, so `awk: cannot open file 'CHANGELOG.md'` failed every release.
- NSIS installer now builds with zero warnings (was 2).
- The NSIS installer builds with zero warnings (was 2).
- ObtainHub-rs repository deleted after migration (code now in main repo)
- Build process: uses `cargo build --release --target x86_64-pc-windows-gnu` for Windows binaries
- Installer scripts: NSIS uses zlib compression with CRC; WiX uses standard heat/candle/light
- Version: bumped to 3.0.0 for major rewrite

### Removed
- Standalone ohub.exe from releases (only installers)
- Python implementation and related scripts
- ObtainHub-rs submodule/repository

### Security
- The token no longer lands in a config backup (`ohub config backup`, `ohub reset --backup`) or in a restored config file.

### Notes
- This is a release candidate. Install `ObtainHub-Setup.exe` and confirm it completes before v3.0.6 is cut.
