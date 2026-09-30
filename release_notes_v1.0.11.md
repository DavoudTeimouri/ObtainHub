## ObtainHub v1.0.11 — Fixed arch_preference for folder/zip apps

### Fixed
- **`arch_preference` not defined error when updating folder/zip apps** — The `_apply_match` function now properly reads `arch_preference` from app state when the CLI `--arch` flag is "auto" (the default). This fixes the error:
  ```
  ERROR [__main__] Failed to update folder:v2rayN: name 'arch_preference' is not defined
  ```

### What Changed
- Modified `_apply_match` in `obtainhub/main.py` to safely handle cases where `parsed.arch` is not defined (e.g., when called from update paths that don't have the `--arch` argument). The fix uses `getattr(parsed, "arch", "auto")` with a fallback to the app's stored `arch_preference`.

### Version Bump
- All version files updated to 1.0.11:
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