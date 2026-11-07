# ObtainHub Improvement Plan — status as of v3.0.68-rc.10

## Done (this cycle)

- Auth middleware deduplicated; public-route match is exact-or-child (`/appsfoo`
  no longer matches `/apps`); `POST /config/github-token` is public only until
  a token exists (bootstrap), so an exposed `--bind 0.0.0.0 --auth` server
  cannot be re-keyed. `src/webui/auth.rs`
- WebUI downloads are real now: live registry in `AppState`, chunked ranged
  downloads with progress/speed/ETA, cancel via flag + `.part` cleanup, dest
  constrained to `download_dir` (file name only, both path separators), and
  `download_bandwidth_limit` honored. `src/webui/downloads.rs`
- `download_bandwidth_limit` honored in the CLI download path too
  (`core::download::streamed`). Was a config-only knob (`_config` unused).
- Single `USER_AGENT` const (`ObtainHub/<version>`) replaces 11 hardcoded
  `ObtainHub/3.0.0` / `ohub` strings.
- Orphaned `src/webui/spa.html` deleted (binary embeds `static/` only).
- Panicky unwraps on static progress templates → `expect`; chained
  `as_array().unwrap()` in `source.rs` → `is_some_and`.
- `ohub search` auto-paginates up to `--limit` (stops at GitHub's 1000-result
  cap); `--dry-run` now prints the query URL.
- CLI smoke tests in `tests/cli.rs` (assert_cmd: version/help/completions/
  search --dry-run). 53 unit + 4 integration tests green.
- README documents the auth surface, download sandboxing, fish completions.

## Already existed (verified, no work needed)

- Update uses config `install_dir` and verifies published checksums
  (`update.rs`); rollback command exists (`rollback.rs`); self-update verifies
  Ed25519 release signatures (`self_update.rs`); fish/zsh/etc. completions via
  clap_complete; config sanitize/clamp; CI release pipeline (test+clippy gate,
  MSI/NSIS on tag, CHANGELOG-extracted release notes).

## Remaining backlog

1. **Dependency manifests** (high effort): `InstalledRepo.dependencies` /
   `is_dependency` fields exist and `install_dependencies` runs, but nothing
   populates them from a release manifest yet. Wire manifest `dependencies`
   into state on install/update.
2. **Other registries** (high effort): install is GitHub-releases-only;
   `manifest_sources` supports custom GitHub-shaped APIs only.
3. **WebUI extras**: state export/import endpoints, log viewer, doctor status
   endpoint. UI polls `GET /downloads` every 2s — could move to SSE later.
4. **Consolidate fetch logic**: `check.rs` (1122 lines) and `tui.rs` (1470)
   each carry their own GitHub release-fetching code; `core/registries.rs`
   has the shared pieces. Extract as commands adopt them.
