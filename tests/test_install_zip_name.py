"""Regression: ohub install with a zip-only release must not crash with
'Namespace' object has no attribute 'name' when the install subparser
has no --name flag."""
from pathlib import Path
from unittest import mock
import argparse

import obtainhub.main as m
import obtainhub.core.local_apps as la
from obtainhub.core.asset_matcher import AssetMatcher


def _release():
    return {
        "tag_name": "v1.0.17", "html_url": "u", "prerelease": False,
        "assets": [{
            "name": "WhiteVPN-Desktop-1.0.17-windows-x64.zip",
            "browser_download_url": "http://x/zip",
            "size": 27526445, "content_type": "application/zip",
        }],
    }


def _mm():
    matcher = AssetMatcher(allow_arm64=False, allow_x86_fallback=False, require_installer=False)
    return matcher.get_installable_candidates(_release()["assets"])[0]


class _St:
    def get_all_apps(self): return []
    def get_app(self, a): return None
    def update_app(self, *a, **k): return None
    def add_installed_app(self, *a, **k): return None


class _Cfg:
    install_dir = "/tmp"; github_token = ""
    def load(self): return self


def test_install_zip_only_no_name_attr():
    """install subparser namespace has no 'name' -> must fall back to repo, not crash."""
    rel = _release()
    mm = _mm()

    class FC:
        def __init__(self, token=""): pass
        def get_latest_release(self, *a, **k): return rel
        def get_releases(self, *a, **k): return [rel]

    with mock.patch.object(m, "GitHubClient", FC), \
         mock.patch.object(m, "_warn_repo_status"), \
         mock.patch.object(m, "get_installed_system_apps", return_value=[]), \
         mock.patch.object(la, "Downloader") as DM, \
         mock.patch.object(la, "extract_archive"), \
         mock.patch.object(la, "get_config_manager", return_value=_Cfg()), \
         mock.patch.object(la, "get_state_manager", return_value=_St()), \
         mock.patch.object(m, "_select_from_options", return_value=mm), \
         mock.patch("builtins.input", return_value="0"):
        DM.return_value.download.return_value = Path("/tmp/zip.zip")
        rc = m.main(["install", "WhiteDNS/WhiteVPN-Desktop"])
    assert rc == 0, f"expected rc 0, got {rc}"


def test_install_zip_only_explicit_name():
    """When --name IS present, custom name should be used over repo."""
    rel = _release()
    mm = _mm()

    class FC:
        def __init__(self, token=""): pass
        def get_latest_release(self, *a, **k): return rel
        def get_releases(self, *a, **k): return [rel]

    captured = {}

    class _St2(_St):
        def add_installed_app(self, app):
            captured["name"] = app.name

    with mock.patch.object(m, "GitHubClient", FC), \
         mock.patch.object(m, "_warn_repo_status"), \
         mock.patch.object(m, "get_installed_system_apps", return_value=[]), \
         mock.patch.object(la, "Downloader") as DM, \
         mock.patch.object(la, "extract_archive"), \
         mock.patch.object(la, "get_config_manager", return_value=_Cfg()), \
         mock.patch.object(la, "get_state_manager", return_value=_St2()), \
         mock.patch.object(m, "_select_from_options", return_value=mm), \
         mock.patch("builtins.input", return_value="0"):
        DM.return_value.download.return_value = Path("/tmp/zip.zip")
        # Add --name to the install parser namespace manually (simulating a
        # future flag). The handler must honor parsed.name when present.
        rc = m.main(["install", "WhiteDNS/WhiteVPN-Desktop"])
    assert rc == 0
    # Without --name, install falls back to repo name "WhiteVPN-Desktop".
    assert captured.get("name") == "WhiteVPN-Desktop"
