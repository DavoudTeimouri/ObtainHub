# Contributing to ObtainHub

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

NSIS EXE (Linux or Windows, needs `makensis`):

```bash
cp target/x86_64-pc-windows-msvc/release/ohub.exe installer/ohub.exe
cp installer/icon.ico icon.ico
makensis installer/ObtainHub.nsi
# -> installer/ObtainHub-Setup.exe
```

MSI (Windows only, needs WiX Toolset v3):

```bash
candle -out ObtainHub.wixobj installer/setup.wxs
light -out ObtainHub.msi ObtainHub.wixobj
```

Both installers share the Product GUID and must stay in sync:
`{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}`. Changing it in one file without the
other breaks upgrade detection and mutual-refusal detection.

## Release

1. Update `CHANGELOG.md` with a `## [X.Y.Z]` section.
2. `git tag vX.Y.Z && git push origin vX.Y.Z`
3. The `Build Rust (Windows x64)` workflow builds both installers and publishes
   the release with only `ObtainHub.msi` and `ObtainHub-Setup.exe`. Do not add a
   standalone `ohub.exe` asset.

## Submitting

Open a PR against `main`. Keep one logical change per commit.
