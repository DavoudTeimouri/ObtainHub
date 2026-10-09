# ObtainHub — Project Logic

Living reference for present and future work. Update this file in the same commit
as any change it describes. If code and this file disagree, the code is the bug.

Last verified against: `main` @ `66ff6ef` + uncommitted `installer/setup.wxs` fix.

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

`src/commands/check.rs:127` walks
`HKLM` and `HKCU` × `KEY_WOW64_64KEY` and `KEY_WOW64_32KEY` under
`SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`, collects entries with a
`DisplayName`, dedupes on `name|version`, and skips any name containing
`ObtainHub`. Non-Windows builds return an empty list.

---

## 9. Security posture

| Area | State |
|---|---|
| `self-update` | **No signature verification.** Downloads and runs the asset. Highest-risk gap in the project. |
| Update assets | `verify_checksums` is read but the check never fires — see below. |
| Archive extraction | Zip-slip guarded in `install.rs` and `update.rs` (`safe_join` / inline equivalent). Tar uses `tar::unpack`, which sanitizes internally. |
| GitHub token | Plaintext in config, not keyring. `reset.rs:24` claims to clear it from the keyring but prints "not implemented". |
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

### `verify_checksum` never verifies anything

`install.rs:244` builds the expected-checksum path with
`path.with_extension("sha256")`, where `path` is the downloaded asset inside the
newly created install directory. Nothing ever writes a `.sha256` file there, so
the `if checksum_path.exists()` branch is unreachable and every install falls
through to `warn!("No checksum file found")` and returns `Ok`.

`verify_checksums` defaults to `true`, so the warning fires on every install and
users learn to ignore it.

Fix: fetch a checksum asset from the release (`SHA256SUMS`, `*.sha256`) over HTTP
and compare against that, instead of looking for a local sidecar file.

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
| 2 | `update.rs` checksum TODO | Closed — but the real bug is in `install.rs`, see section 9 |
| 3 | `uninstall --purge` stub | **Done** — drops state metadata + group entries |
| 4 | Shared download/extract module | Open — deliberately, see rule 10 |
| 5 | Error messages | Partial — EPIPE panic in `completion` fixed |
| 6 | Configurable API timeout | Open — timeout is config-only, no CLI override |
| 7 | Consistent arch selection | Open |
| 8 | Config validation | **Done** — `sanitize()` + 2 tests |
| 9 | TUI discoverability | Closed — header already lists keybindings |
| 10 | Search pagination | Open |
| 11 | Self-update signature verification | Open — high risk |
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
- `keyring` dependency declared but never used; token stored in plaintext.
- `verify_checksums` is read at `install.rs:113` but can never match — section 9.
- `zip`/`tar` extraction does not guard against path traversal. → **Fixed** in
  `install.rs` + `update.rs`, see section 9.
- `src/commands/reset.rs:41` binds `token_path` and never uses it.
- `src/commands/backup.rs` backs up `config`, which can contain a GitHub token.
