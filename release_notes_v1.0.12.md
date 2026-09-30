## ObtainHub v1.0.12 — ohub update delegates to SelfUpdater for self-updates

### Changed
- **`ohub update` now delegates self-updates to the SelfUpdater mechanism** when detecting ObtainHub itself in the managed apps list
  - Uses detached silent installer (Inno EXE or MSI) with `/VERYSILENT` / `/quiet` flags
  - Auto-exits ohub so the installer can replace the running executable
  - Consistent behavior with `ohub self-update` command
  - Fixes the issue where `ohub update` would show interactive installer dialog for self-updates

### Version Bump
- All version files updated to 1.0.12:
  - `obtainhub/__init__.py`
  - `pyproject.toml`
  - `installer/setup.iss`
  - `installer/setup.wxs`
  - `obtainhub/main.py` (--version string)

### Assets
This release includes the standard Windows x64 installers:
- `ObtainHub-Setup.exe` (Inno Setup)
- `ObtainHub.msi` (WiX)

No standalone `ohub.exe` is published as a release asset per project policy.