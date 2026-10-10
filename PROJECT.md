# ObtainHub — Project Logic

Living reference for present and future work. Update this file in the same commit
as any change it describes. If code and this file disagree, the code is the bug.

Last verified against: `main` @ `7e8a852`.

---

## 0. Release rules (non-negotiable)

**Every release gets its own changelog section.** The release body is that
section verbatim — never GitHub's auto-generated commit list.

```markdown
## [vX.Y.Z] - YYYY-MM-DD
### Fixed
- what was broken, with the file:line or the error string

### Added
- new capability

### Changed
- behaviour that is different but not a fix
```

Sections go newest-first at the top. `v3.0.2` was shipped without one; that is
the failure this rule exists to prevent.

Before tagging:

1. All four version sites bumped — `Cargo.toml`, `installer/ObtainHub.nsi`
   `!define VERSION`, `installer/setup.wxs` (`Version` + `Comments`),
   `CHANGELOG.md`.
2. `## [vX.Y.Z]` section written and non-empty.
3. `cargo test` green.
4. `makensis installer/ObtainHub.nsi` — zero warnings.
5. CI green on all four jobs for the tagged commit.

**One release at a time.** Fix everything, then cut one tag. Do not ship a
sequence of patch releases each fixing the last one's bug.

**Tag as pre-release until tested.** Tag `vX.Y.Z-rc1` (the workflow sets
`prerelease` from the `-` in the tag). It only becomes a full release after you
have installed it and confirmed it works. Never cut a final tag on untested
code.

**Do not force-move a tag you have published.** Force-moving
`v3.0.5` was needed while nothing had downloaded it. Once users have the
artifact, a rewritten tag leaves them holding a binary that does not match the
tag they fetched. Cut a new version instead.

---

## 1. Identity

| Field | Value |
|---|---|
| Product | ObtainHub |
| Binary | `ohub.exe` (Windows x64 only) |
| Version | 3.0.0 |
| Language | Rust, edition 2021 |
| Release profile | `opt-level="z"`, `lto`, `codegen-units=1`, `strip`, `panic="abort"` |
| License | MIT |
| Repo | `DavoudTeimouri/ObtainHub` |

Python implementation was removed in v3.0.0. Do not reintroduce it.

---

## 2. Release artifacts

Exactly two assets are published. Never add a standalone binary.

| Asset | Built by | Job |
|---|---|---|
| `ObtainHub.msi` | WiX Toolset v3 (`candle` + `light`) | `installer-msi` |
| `ObtainHub-Setup.exe` | NSIS 3.13+ (`makensis`) | `installer-nsis` |

Pipeline: `build` → `installer-msi` + `installer-nsis` → `release`.
Trigger: tag `v*` or manual dispatch. `release` skips unless all three succeed,
so a failed installer job means no release is published — the tag still moves.

Build target is `x86_64-pc-windows-msvc` on `windows-latest`. A cross-compiled
`x86_64-pc-windows-gnu` binary is a local dev artifact only; never ship it.

### Version must be bumped in four places

1. `Cargo.toml` → `version`
2. `installer/ObtainHub.nsi` → `!define VERSION`
3. `installer/setup.wxs` → `<Product Version>` and `<Package Comments>`
4. `CHANGELOG.md` → new `## [X.Y.Z]` section

Miss one and the installer installs a binary that reports a different version.

---

## 3. Installer invariants

**Product GUID — must be identical in both installers:**

```
{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
```

This is the `UpgradeCode` in WiX and `PRODUCT_GUID` in NSIS. It is the only
thing that ties MSI upgrades and NSIS upgrades into one install identity. Change
it in one file and the two installers stop recognising each other.

**Install location:** `C:\Program Files\ObtainHub` (`$PROGRAMFILES64\${APP_NAME}`)

**Elevation:** machine-wide, admin-only. Both installers request it.

**Shortcuts:** none. Neither installer creates Start Menu or Desktop entries.

**PATH:** user scope (`HKCU\Environment\PATH`), appended at the end, removed
exactly on uninstall. MSI uses `<Environment System="no">`; NSIS edits the HKCU
value directly and broadcasts `WM_SETTINGCHANGE`.

**64-bit only:** NSIS aborts when `$PROGRAMFILES64` is unset. MSI declares
`Platform="x64"` — required, because `PathEnvironment` and `MainExecutable` are
both `Win64="yes"` and ICE80 rejects a 32-bit package containing 64-bit
components.

**Compression:** NSIS uses zlib with `CRCCheck on`. Do not switch to `/SOLID`
LZMA — it produced installers that Windows reported as corrupt
("Invalid opcode") on this project.

---

## 4. Known defects in mutual refusal

Both directions of the MSI ↔ NSIS mutual-refusal check are currently dead code.

**NSIS → MSI:** `installer/ObtainHub.nsi:65,69` reads
`HKLM\...\Uninstall\{PRODUCT_GUID}`. Windows Installer writes its uninstall entry
under the **ProductCode**, not the UpgradeCode, and `Product Id="*"` makes the
ProductCode a fresh GUID on every build. The key NSIS looks for does not exist, so
the "already installed via MSI" branch never fires.

**MSI → NSIS:** `installer/setup.wxs` searches
`Uninstall\{A1B2C3D4-...-EF1234567890}_is1`. NSIS writes to
`Uninstall\{A1B2C3D4-...-EF1234567890}` with no `_is1` suffix. The search never
matches.

**Consequence:** installing one installer over the other silently overwrites files
instead of prompting.

**Fix options, cheapest first:**

1. Pin the WiX `Product Id` to the shared GUID instead of `"*"`:
   `<Product Id="{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}">` and drop
   `<MajorUpgrade>` in favour of the NSIS-style prompt. One GUID, one key, both
   installers agree.
2. Give the NSIS uninstall key the `_is1` suffix WiX already searches for.
3. Detect by `InstallLocation` rather than by uninstall key.

Option 1 removes the whole class of bug and keeps the shared-GUID requirement.

---

## 5. Known defects in state cleanup

NSIS uninstall deletes only `Uninstall\{PRODUCT_GUID}` (`ObtainHub.nsi:277`). The
MSI writes an additional `HKLM\Software\ObtainHub\PathInstalled` key
(`setup.wxs:56`) as its component KeyPath, and the MSI overwrite path in
`ObtainHub.nsi:82-83` removes the Uninstall key but leaves `Software\ObtainHub`
behind.

Result: installing MSI then NSIS-over-it leaves an orphaned
`HKLM\Software\ObtainHub` key that no uninstaller removes.

Fix: have NSIS `DeleteRegKey HKLM "Software\ObtainHub"` on uninstall.

---

## 6. Filesystem layout

Resolved at runtime by `dirs`, not hardcoded:

| What | Path | Source |
|---|---|---|
| Config | `<config_dir>/ObtainHub/config.toml` | `src/core/config.rs:144` |
| State | `<data_dir>/ObtainHub/state.json` | `src/core/state.rs:32` |
| Install dir | `<data_dir>/ObtainHub/repos` | `src/core/config.rs:101` |
| Downloads | `<data_dir>/ObtainHub/downloads` | `src/core/config.rs:86` |
| Shims | `<home>/bin/obtainhub` | `src/core/config.rs:92` |

`dirs::config_dir()` on Windows is `%APPDATA%`, **not** `%LOCALAPPDATA%`. Earlier
README text claiming `config.json` was wrong on both counts — the file is TOML.

`state.json` is written atomically (temp file + rename) in `state.rs:59-64`.
Keep it that way; a truncated state file bricks every command.

---

## 7. Configuration contract

Zero-valued numeric settings are reset to defaults on load and on save
(`ConfigManager::sanitize`, `src/core/config.rs`). Guarded fields:
`parallel_downloads`, `timeout_seconds`, `update_check_interval_hours`,
`schedule.interval_hours`. A hand-edited config cannot set these to 0.

`github_token` is stored in plain config. It is **not** in the Windows keyring —
`keyring` is a declared dependency but unwired. Treat the token as a secret that
must not land in logs, backups, or `ohub config list` output.

---

## 8. Command surface

25 subcommands, defined in `src/cli.rs`, dispatched in `src/main.rs:28-50`.

Ownership note: `src/main.rs` passes `&ConfigManager` to most commands but
`&mut ConfigManager` to `config`, `source`, `schedule`, `group`, and `uninstall`.
A command needs `&mut` only when it writes config.

| Command | Notes |
|---|---|
| `search` | GitHub search; `--min-stars`, `--active-only`, `--sort-stars`, `--language`, `--case-insensitive`, `--dry-run` |
| `install` | `--file` local archive, `--url` direct download, `--dry-run` |
| `check` | `--all` enumerates installed Windows software and skips ObtainHub itself |
| `list` | `--format json` |
| `update` | `--dry-run`, `--force`, one repo or all |
| `uninstall` | `--yes`, `--purge` (drops state metadata + group membership) |
| `remove` | untrack, keep files |
| `add` | track without installing |
| `source` | custom manifest sources |
| `schedule` | background checks |
| `group` | app groups |
| `shim` | portable shims |
| `state` | export / import |
| `apps` | backup / restore app folders |
| `cleanup` | leftovers and scheduled tasks |
| `tui` | ratatui + crossterm; keybindings shown in the header |
| `config` | get / set / list |
| `backup`, `restore` | backup and restore |
| `self-update` | updates ohub; **no signature verification** |
| `completion` | bash, elvish, fish, powershell, zsh |
| `doctor` | environment diagnostics |
| `info` | repo metadata |
| `reset` | reset state and config |

### `check --all` semantics

`src/commands/check.rs` walks
`HKLM` and `HKCU` × `KEY_WOW64_64KEY` and `KEY_WOW64_32KEY` under
`SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`, collects entries with a
`DisplayName`, and dedupes on `name|version`. Non-Windows builds return an empty
list.

Entries are then partitioned by `partition_gitHub_managed`. Only programs matching
an entry in `state.json` are checked, because a `DisplayName` like
`NVIDIA Corporation` is not an `owner/repo`: the GitHub releases API would 404 on
every one of them, and the volume exhausts the unauthenticated rate limit after
roughly 60 requests. Unmatched programs are counted and reported as skipped.
ObtainHub itself is always skipped.

Two tests in `src/commands/check.rs` cover the self-skip and the tracked/unmanaged
split.

---

## 9. Security posture

| Area | State |
|---|---|
| `self-update` | Digest-verified against a published `SHA256SUMS`. No GPG/Authenticode signature check. |

| Update assets | Checksum verification now works for published digests — see below. `update` still does not verify. |
| Archive extraction | Zip-slip guarded in `install.rs` and `update.rs` (`safe_join` / inline equivalent). Tar uses `tar::unpack`, which sanitizes internally. |
| GitHub token | Plaintext in config, not keyring. No longer echoed by `config get`, and excluded from backups. |
| Signing | Neither installer is Authenticode signed. |

Anything above marked high-risk belongs on the fix list before the next feature.

### Zip-slip was exploitable — now fixed

`install.rs` did `install_dir.join(file.name())` on attacker-controlled zip
entries with no validation, so an entry named `../../evil.exe` wrote outside the
install directory. `install` and `install --url` both download archives from the
internet and extract them, so this was reachable.

`update.rs` had the same hole via `archive.extract()`, which the `zip` crate
documents as unsafe for untrusted input.

Both now normalize the joined path through `components()` before comparing with
`starts_with`. The normalization is required: a raw `dest/../x` still lexically
starts with `dest`, so a naive `starts_with` check passes it. Covered by
`safe_join_*` tests in `src/commands/install.rs`.

### GitHub token handling

The token is stored as plaintext `github_token` in `config.toml`. The `keyring`
crate is a declared dependency but nothing calls it.

What protects it now:

- `config get github_token` returns `[stored]`, never the value. The old code
  printed it verbatim, which leaks it into shell history, CI logs, and
  `ohub config list | tee`.
- `config auth` already reported presence only.
- `backup` and `reset --backup` strip the token from the archive. A backup is a
  file the user copies between machines; a plaintext token inside one is a
  credential in transit.

What does not: `config set github_token <value>` still takes the token as a
command-line argument, so it lands in shell history and process listings. Wiring
`keyring` for storage, and reading the token from stdin or the environment when
setting it, is the real fix. Until then, treat `config.toml` as a secret file.

### Self-update verification

`self-update` used to download a release asset, extract it, and overwrite the
running binary with nothing checked in between. It now hashes the download and
compares it against a digest published with the release (`<name>.sha256`, then
`SHA256SUMS`, then `checksums.txt`). A mismatch deletes the download and aborts.
If the release publishes no digest at all, the command refuses to run and tells
the user to install manually — failing closed is the only safe default here.

CI generates `SHA256SUMS` over both installers and publishes it as a third release
asset. That asset is what makes the check satisfiable; without it every
self-update would refuse.

What this does **not** cover: there is still no cryptographic signature check. A
checksum published by the same release it protects catches corruption and a
truncated download, not a compromised release account. Closing that requires
signing the release (GPG or a GitHub OIDC attestation), which is item 11 proper.

### Checksum verification

`verify_checksums` (config, default `true`) previously called `verify_checksum`,
which looked for `<archive>.sha256` **inside the newly created install directory**.
Nothing ever writes a file there, so the check was unreachable: every install fell
through to `warn!("No checksum file found")` and returned `Ok`. The warning fired
on every run, teaching users to ignore it, and `state.json` recorded
`checksum: None`.

Now:

- **GitHub releases** (`install <owner/repo>`) — `fetch_published_checksum` looks
  for a digest published alongside the asset: first a per-asset `<name>.sha256`,
  then a combined `SHA256SUMS` / `checksums.txt`. Manifest lines are matched on the
  **exact** filename; matching on the basename would let a `dist/app.zip` entry
  answer for a top-level `app.zip`. No published digest is a warning, not a failure
  — most repositories do not publish one.
- **Local archives** (`install --file`, `install --url`) — there is no release to
  consult, so `local_sidecar_digest` reads a `<archive>.sha256` the user placed
  next to the archive. A mismatch aborts the install.

Three tests cover the sidecar parser, the manifest parser, and the nested-filename
rejection.

---

## 10. Engineering rules

- stdlib and already-declared dependencies first. `Cargo.toml` currently pulls
  ~90 crates; do not grow it without justification.
- No abstraction before the second caller. `install.rs` and `update.rs` duplicate
  download/extract logic — leave it duplicated until a third caller appears.
- Deliberate shortcuts get a `ponytail:` comment naming the ceiling and the
  upgrade path. Examples: `update.rs` checksum note, `completion.rs` EPIPE note.
- Non-trivial logic ships one assert-based test. Current suite: 2 tests in
  `src/core/config.rs`.
- Build artifacts are gitignored: `ObtainHub.msi`,
  `installer/ObtainHub-Setup.exe`, `installer/ohub.exe`.

---

## 11. Work tracking

`PLAN.md` holds the numbered improvement plan. Status as of `66ff6ef`:

| # | Item | State |
|---|---|---|
| 1 | `update.rs` hardcoded install dir | **Done** — uses `config.install_dir` |
| 2 | Checksum verification | **Done** in `install.rs`; `update.rs` still unverified |
| 3 | `uninstall --purge` stub | **Done** — drops state metadata + group entries |
| 4 | Shared download/extract module | Open — deliberately, see rule 10 |
| 5 | Error messages | Partial — EPIPE panic in `completion` fixed |
| 6 | Configurable API timeout | Open — timeout is config-only, no CLI override |
| 7 | Consistent arch selection | Open |
| 8 | Config validation | **Done** — `sanitize()` + 2 tests |
| 9 | TUI discoverability | Closed — header already lists keybindings |
| 10 | Search pagination | Open |
| 11 | Self-update signature verification | **Partial** — SHA256SUMS gate done; signing still open |
| 12 | Fish completion | Closed — already supported |
| 13 | Dependency tracking | Open |
| 14 | Non-GitHub registries | Open |
| 15 | Update rollback | Open |
| 16 | Bandwidth throttling | Open |
| 17 | README examples | **Done** — added, plus fixed config path |
| 18 | CONTRIBUTING.md | **Done** |
| 19 | Automated release CI | Open — pipeline exists but tag push is manual |

### Untracked from PLAN.md

Discovered by inspection, not in the plan:

- MSI ↔ NSIS mutual refusal is dead code both directions — section 4.
- NSIS uninstall leaves `HKLM\Software\ObtainHub` orphaned — section 5.
- `keyring` declared but unwired; token is plaintext. Echoing and backups fixed, see section 9. Setting via CLI arg still leaks to shell history.
- `verify_checksums` could never match → **Fixed** in `install.rs`, see section 9.
- `update` downloads and extracts with no checksum check at all.
- `zip`/`tar` extraction does not guard against path traversal. → **Fixed** in
  `install.rs` + `update.rs`, see section 9.

- `backup` embedded the GitHub token in the archive → **Fixed**, see section 9.
