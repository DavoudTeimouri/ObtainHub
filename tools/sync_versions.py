#!/usr/bin/env python3
"""Sync the project version into every file that needs it.

Single source of truth: ``obtainhub/__init__.py`` -> ``__version__``.

Run this before building so the Inno Setup, WiX MSI, and PyPI metadata
all carry the same version as the Python package. Prevents the recurring
bug where the built installer showed a stale version number.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def get_version() -> str:
    text = (ROOT / "obtainhub" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    if not m:
        print("ERROR: could not find __version__ in obtainhub/__init__.py", file=sys.stderr)
        sys.exit(1)
    return m.group(1)


def main() -> None:
    version = get_version()
    print(f"Syncing version {version}")

    # 1) installer/setup.iss  ->  #define AppVersion "..."
    iss = ROOT / "installer" / "setup.iss"
    iss_text = iss.read_text(encoding="utf-8")
    iss_text, n = re.subn(
        r'(#define\s+AppVersion\s+")[^"]*(")',
        lambda m: f'{m.group(1)}{version}{m.group(2)}',
        iss_text,
    )
    if n == 0:
        print("WARNING: AppVersion not found in setup.iss", file=sys.stderr)
    iss.write_text(iss_text, encoding="utf-8")

    # 2) installer/setup.wxs  ->  <Product ... Version="...">
    wxs = ROOT / "installer" / "setup.wxs"
    wxs_text = wxs.read_text(encoding="utf-8")
    wxs_text, n = re.subn(
        r'(Version=")[0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?(")',
        lambda m: f'{m.group(1)}{version}{m.group(2)}',
        wxs_text,
    )
    if n == 0:
        print("WARNING: Product Version not found in setup.wxs", file=sys.stderr)
    wxs.write_text(wxs_text, encoding="utf-8")

    # 3) pyproject.toml  ->  version = "..."
    pyproject = ROOT / "pyproject.toml"
    pp_text = pyproject.read_text(encoding="utf-8")
    pp_text, n = re.subn(
        r'(^version\s*=\s*")[^"]*(")',
        lambda m: f'{m.group(1)}{version}{m.group(2)}',
        pp_text,
        flags=re.MULTILINE,
    )
    if n == 0:
        print("WARNING: version not found in pyproject.toml", file=sys.stderr)
    pyproject.write_text(pp_text, encoding="utf-8")

    # 4) main.py --version string (ObtainHub vX.Y.Z ...)
    main_py = ROOT / "obtainhub" / "main.py"
    mp_text = main_py.read_text(encoding="utf-8")
    mp_text, n = re.subn(
        r'(version="ObtainHub v)[0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?',
        lambda m: f'{m.group(1)}{version}',
        mp_text,
    )
    if n == 0:
        print("WARNING: --version string not found in main.py", file=sys.stderr)
    main_py.write_text(mp_text, encoding="utf-8")

    print("Done.")


if __name__ == "__main__":
    main()
