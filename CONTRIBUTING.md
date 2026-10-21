# Contributing to ObtainHub

## Read these first

| File | What it is |
|---|---|
| **PROJECT.md** | Living reference: release rules, installer invariants, GUID, filesystem layout, config contract, command surface, security posture, work tracking. **The changelog template lives in §0.** |
| `CHANGELOG.md` | Per-version release notes. One `## [vX.Y.Z]` section per release. |
| `PLAN.md` | Numbered improvement plan. |

PROJECT.md is the source of truth. If code and PROJECT.md disagree, the code is
the bug. Update PROJECT.md in the same commit as any change it describes.

## Build

```bash
cargo build --release
./target/release/ohub --help
```

Cross-compile the Windows binary (what CI ships):

```bash
rustup target add x86_64-pc-windows-msvc
cargo build --release --target x86_64-pc-windows-msvc
```

## Test

```bash
cargo test
cargo check
```

## Style

- stdlib and already-present dependencies first; add a crate only when a few
  lines of existing code cannot do the job.
- Boring over clever. No abstraction without a second caller.
- Mark deliberate shortcuts with a `ponytail:` comment naming the ceiling and
  the upgrade path.

## Build the installers

**NSIS is pinned to 3.11.** 3.13 produced an installer that Windows rejects with
"Installer corrupted: invalid opcode" before any dialog. CI installs it via
`choco install nsis --version=3.11 --allow-downgrade` and asserts
`makensis -VERSION` reports 3.11. Use 3.11 locally too.

NSIS EXE (Linux or Windows, needs `makensis`):

```bash
cp target/x86_64-pc-windows-msvc/release/ohub.exe installer/ohub.exe
cp installer/icon.ico icon.ico
makensis installer/ObtainHub.nsi   # must emit zero warnings
# -> installer/ObtainHub-Setup.exe
```

MSI (Windows only, needs WiX Toolset v3):

```bash
candle -out ObtainHub.wixobj installer/setup.wxs
light -out ObtainHub.msi ObtainHub.wixobj
```

`wixl` (the Linux MSI builder) rejects the `<Condition>` node — a known gap in
wixl, not in WiX v3. Strip that one node to smoke-test the rest locally.

Both installers share the Product GUID and must stay in sync:
`{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}`. Changing it in one file without the
other breaks upgrade detection and mutual-refusal detection.

## Release

Full procedure and the changelog template are in **PROJECT.md §0**. Short form:

1. Write the `## [vX.Y.Z]` section in `CHANGELOG.md` (template in PROJECT.md §0).
2. Bump all four version sites — see PROJECT.md §2.
3. `cargo test` green; `makensis` emits zero warnings.
4. Tag pre-release first: `git tag vX.Y.Z-rc1 && git push origin vX.Y.Z-rc1`.
5. After you have installed it and confirmed it works, cut `vX.Y.Z`.

The tag can also be cut from the Actions tab: run the **Build Rust (Windows
x64)** workflow with the `tag` input set (for example `v3.0.64-rc1`). The
workflow creates the tag and pushes it, and the tag push starts the run that
builds the installers and publishes the release. The version bump has to be on
`main` first - the workflow tags what it checked out.

The release publishes `ObtainHub.msi`, `ObtainHub-Setup.exe`, and `SHA256SUMS`
only. Never add a standalone `ohub.exe` asset. The release body is the matching
`## [vX.Y.Z]` CHANGELOG section, extracted by the workflow — if a release has no
section, the build fails.

## Submitting

Open a PR against `main`. Keep one logical change per commit.

Update `CHANGELOG.md` only when cutting a release. For in-flight work, update
the `PLAN.md` table and the relevant `PROJECT.md` section.

Two known traps when working in this repo:

- **`installer/ObtainHub.nsi:253`** uses a *relative* `File` source
  (`File "/oname=..." "${APP_EXE}"`), which NSIS resolves against the **repo
  root**, not `installer/`. There is no `ohub.exe` there. Always
  `cp target/x86_64-pc-windows-msvc/release/ohub.exe installer/ohub.exe` before
  `makensis`, and confirm the installer contains the real binary.
- **`.github/workflows/build.yml` release job** needs its `actions/checkout`
  step. Without it there is no `CHANGELOG.md` in the workspace and the
  extraction step fails.

