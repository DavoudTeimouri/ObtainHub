"""Tests for remove command, reset of choices, and folder repo linking."""

import tempfile
import os

from obtainhub.core.state import StateManager, InstalledApp
from obtainhub.main import _reset_choices


def _make_state():
    d = tempfile.mkdtemp()
    sm = StateManager(state_file=os.path.join(d, "s.json"))
    sm.add_installed_app(InstalledApp(
        id="owner/repo", name="repo", version="1.0",
        installer_type="github", installer_path="", source_url="", tag="",
        app_type="github", asset_pattern="*x64*.exe", preferred_asset="a.exe",
    ))
    sm.add_installed_app(InstalledApp(
        id="folder:App", name="App", version="",
        installer_type="folder", installer_path="C:\\App", source_url="", tag="",
        app_type="folder", install_location="C:\\App", github_repo="owner/App",
    ))
    return sm


def test_remove_app():
    sm = _make_state()
    assert sm.remove_app("owner/repo") is True
    assert sm.get_app("owner/repo") is None


def test_reset_choices_clears_patterns_and_history():
    sm = _make_state()
    sm.add_check_history(__import__("obtainhub.core.state", fromlist=["CheckHistoryEntry"]).CheckHistoryEntry(
        app_name="sysapp", app_version="1", user_choice="ignored", checked_at=1,
    ))
    _reset_choices(sm)
    app = sm.get_app("owner/repo")
    assert app is not None
    assert app.asset_pattern == ""
    assert app.preferred_asset == ""
    assert sm.get_check_history() == {}


def test_folder_app_github_repo_field():
    sm = _make_state()
    app = sm.get_app("folder:App")
    assert app.github_repo == "owner/App"
