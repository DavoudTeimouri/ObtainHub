# AGENTS.md

Instructions for any AI agent or human contributor working in this repository.
Read this file first; it points at everything else.

## Order of reading

1. **This file** — orientation.
2. **PROJECT.md** — the source of truth. Release rules (§0), installer
   invariants (§3), filesystem layout (§6), config contract (§7), command
   surface (§8), security posture (§9), work tracking (§11).
3. **CHANGELOG.md** — one `## [vX.Y.Z]` section per release.
4. **CONTRIBUTING.md** — build, test, installer, release commands.
5. **PLAN.md** — numbered improvement plan with per-item status.

If code and PROJECT.md disagree, **the code is the bug**. Update PROJECT.md in
the same commit as any change it describes — it is a living document, not a
snapshot.

## Hard rules

- **Never publish a standalone `ohub.exe`.** Releases carry exactly
  `ObtainHub.msi`, `ObtainHub-Setup.exe`, and `SHA256SUMS`.
- **Never change the Product GUID** in one installer without the other. It is
  `{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}` in both `installer/setup.wxs`
  (`UpgradeCode`) and `installer/ObtainHub.nsi` (`PRODUCT_GUID`).
- **Every release gets a changelog section.** The release body is that section
  verbatim. Template in PROJECT.md §0. A release with no section fails CI.
- **Bump all four version sites together** — `Cargo.toml`,
  `installer/ObtainHub.nsi` `!define VERSION`, `installer/setup.wxs`
  (`Version` + `Comments`), `CHANGELOG.md`. Exception for prerelease tags in
  PROJECT.md §0: MSI `Product Version` must be numeric.
- **Tag pre-release first.** `vX.Y.Z-rc1` ships, gets tested, and only then is
  `vX.Y.Z` cut. Never cut a final tag on untested code.
- **Do not force-move a tag that has been published.** Cut a new version.
- **NSIS is pinned to 3.11.** 3.13 emitted an installer Windows rejects with
  "Installer corrupted: invalid opcode".

## Verifying your work

Do not claim success from a self-report. Run it:

```bash
cargo test                      # 13 tests expected green
cargo check                     # zero errors
makensis installer/ObtainHub.nsi # must emit zero warnings
```

For installers, confirm the artifact rather than the build log:

```bash
gh release download <tag> --dir /tmp/check
cd /tmp/check && sha256sum -c SHA256SUMS
```

## Traps

- `installer/ObtainHub.nsi:253` uses a relative `File` source that NSIS resolves
  against the **repo root**, not `installer/`. Copy the binary to
  `installer/ohub.exe` before `makensis` or you will ship a broken installer.
- The release job in `.github/workflows/build.yml` requires its
  `actions/checkout` step; without it there is no `CHANGELOG.md`.
- `wixl` (Linux MSI builder) rejects the `<Condition>` node. That is a wixl gap,
  not a WiX v3 error — CI uses `candle`/`light`.
- `wixl` accepts `Version="3.0.6-rc1"` but real WiX v3 does not. MSI versions are
  numeric.

## Style

- stdlib and already-present dependencies first. `Cargo.toml` pulls ~90 crates;
  do not grow it without justification.
- No abstraction before the second caller.
- Deliberate shortcuts get a `ponytail:` comment naming the ceiling and the
  upgrade path.
- Non-trivial logic ships one assert-based test.
- Shortest working diff. Deletion over addition.
