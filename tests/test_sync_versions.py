"""Ensure the version string is consistent across all surfaces.

Single source of truth: obtainhub/__init__.py __version__.
tools/sync_versions.py propagates it to setup.iss, setup.wxs, pyproject.toml, main.py.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(p):
    return (ROOT / p).read_text(encoding="utf-8")


def test_version_consistent():
    version = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)',
        _read("obtainhub/__init__.py"), re.MULTILINE,
    ).group(1)

    assert version in _read("installer/setup.iss"), "setup.iss AppVersion out of sync"
    assert f'Version="{version}"' in _read("installer/setup.wxs"), "setup.wxs ProductVersion out of sync"
    assert f'version = "{version}"' in _read("pyproject.toml"), "pyproject version out of sync"
    assert f"ObtainHub v{version}" in _read("obtainhub/main.py"), "main.py --version out of sync"
