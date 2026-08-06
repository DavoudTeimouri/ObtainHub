"""Tests for state module."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
import pytest

from obtainhub.core.state import InstalledApp, ManifestEntry, StateManager


class TestInstalledApp:
    """Tests for InstalledApp dataclass."""

    def test_default_values(self):
        """Test default values."""
        app = InstalledApp(
            name="TestApp",
            version="1.0.0",
            install_path="/path/to/app",
        )
        assert app.name == "TestApp"
        assert app.version == "1.0.0"
        assert app.install_path == "/path/to/app"
        assert app.executable_path == ""
        assert app.source_url == ""
        assert app.source_type == "github"
        assert app.manifest_name == ""
        assert app.architecture == "x64"
        assert app.requires_manual_uninstall is False
        assert app.uninstall_string == ""
        assert app.installed_by_ohub is True

    def test_full_constructor(self):
        """Test full constructor with all fields."""
        app = InstalledApp(
            name="TestApp",
            version="1.0.0",
            install_path="/path/to/app",
            executable_path="/path/to/app/app.exe",
            install_date="2024-01-01T00:00:00",
            source_url="https://github.com/owner/repo",
            source_type="github",
            manifest_name="default",
            architecture="x64",
            requires_manual_uninstall=True,
            uninstall_string="msiexec /x {guid}",
            installed_by_ohub=True,
        )
        assert app.executable_path == "/path/to/app/app.exe"
        assert app.source_url == "https://github.com/owner/repo"
        assert app.requires_manual_uninstall is True
        assert app.uninstall_string == "msiexec /x {guid}"

    def test_to_dict(self):
        """Test serialization."""
        app = InstalledApp(
            name="TestApp",
            version="1.0.0",
            install_path="/path/to/app",
            executable_path="/path/to/app/app.exe",
            architecture="x64",
        )
        data = app.to_dict()
        assert isinstance(data, dict)
        assert data["name"] == "TestApp"
        assert data["architecture"] == "x64"

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "name": "TestApp",
            "version": "1.0.0",
            "install_path": "/path/to/app",
            "executable_path": "/path/to/app/app.exe",
            "install_date": "2024-01-01T00:00:00",
            "source_url": "https://github.com/owner/repo",
            "source_type": "github",
            "manifest_name": "default",
            "architecture": "x64",
            "requires_manual_uninstall": False,
            "uninstall_string": "",
            "installed_by_ohub": True,
        }
        app = InstalledApp.from_dict(data)
        assert app.name == "TestApp"
        assert app.architecture == "x64"


class TestManifestEntry:
    """Tests for ManifestEntry dataclass."""

    def test_default_values(self):
        """Test default values."""
        entry = ManifestEntry(
            name="TestApp",
            owner="owner",
            repo="repo",
        )
        assert entry.name == "TestApp"
        assert entry.owner == "owner"
        assert entry.repo == "repo"
        assert entry.description == ""
        assert entry.homepage == ""
        assert entry.license == ""
        assert entry.tags == []
        assert entry.installer_name_pattern == ""
        assert entry.installer_args == ""
        assert entry.architecture == "x64"
        assert entry.requires_manual_uninstall is False
        assert entry.post_install_commands == []
        assert entry.uninstall_method == "auto"
        assert entry.uninstall_args == "/quiet /norestart"
        assert entry.prefer_x64 is True
        assert entry.allow_prerelease is False
        assert entry.known_checksums == {}

    def test_full_constructor(self):
        """Test full constructor."""
        entry = ManifestEntry(
            name="TestApp",
            owner="owner",
            repo="repo",
            description="Test app",
            homepage="https://example.com",
            license="MIT",
            tags=["editor", "utility"],
            installer_name_pattern="*x64*",
            installer_args="/quiet",
            architecture="x64",
            requires_manual_uninstall=True,
            post_install_commands=["cmd1", "cmd2"],
            uninstall_method="msi",
            uninstall_args="/quiet /norestart",
            prefer_x64=True,
            allow_prerelease=True,
            known_checksums={"1.0.0": "sha256..."},
        )
        assert entry.tags == ["editor", "utility"]
        assert entry.requires_manual_uninstall is True
        assert entry.known_checksums["1.0.0"] == "sha256..."

    def test_to_dict(self):
        """Test serialization."""
        entry = ManifestEntry(name="TestApp", owner="owner", repo="repo")
        data = entry.to_dict()
        assert isinstance(data, dict)
        assert data["name"] == "TestApp"
        assert data["owner"] == "owner"

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "name": "TestApp",
            "owner": "owner",
            "repo": "repo",
            "description": "Test",
            "homepage": "",
            "license": "",
            "tags": [],
            "installer_name_pattern": "",
            "installer_args": "",
            "architecture": "x64",
            "requires_manual_uninstall": False,
            "post_install_commands": [],
            "uninstall_method": "auto",
            "uninstall_args": "/quiet /norestart",
            "prefer_x64": True,
            "allow_prerelease": False,
            "known_checksums": {},
        }
        entry = ManifestEntry.from_dict(data)
        assert entry.name == "TestApp"
        assert entry.owner == "owner"


class TestStateManager:
    """Tests for StateManager."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def state_manager(self, temp_dir):
        """Create a StateManager with temp directory."""
        return StateManager(state_dir=temp_dir / "state")

    def test_load_creates_empty_when_no_file(self, state_manager):
        """Test loading creates empty state when no file exists."""
        # State manager loads on init
        assert state_manager.state_file.exists() is False
        assert state_manager._state["installed_apps"] == {}
        assert state_manager._state["download_history"] == []

    def test_save_and_load(self, state_manager):
        """Test save and load."""
        app = InstalledApp(
            name="TestApp",
            version="1.0.0",
            install_path="/path/to/app",
            executable_path="/path/to/app/app.exe",
        )
        state_manager.add_installed_app(app)

        # Create new manager and load
        new_manager = StateManager(state_dir=state_manager.state_dir)
        loaded_app = new_manager.get_installed_app("TestApp")

        assert loaded_app is not None
        assert loaded_app.name == "TestApp"
        assert loaded_app.version == "1.0.0"
        assert loaded_app.executable_path == "/path/to/app/app.exe"

    def test_add_installed_app(self, state_manager):
        """Test adding installed app."""
        app = InstalledApp(
            name="TestApp",
            version="1.0.0",
            install_path="/path/to/app",
        )
        state_manager.add_installed_app(app)

        assert state_manager.is_app_installed("TestApp")
        assert state_manager.get_installed_version("TestApp") == "1.0.0"

    def test_remove_installed_app(self, state_manager):
        """Test removing installed app."""
        app = InstalledApp(name="TestApp", version="1.0.0", install_path="/path")
        state_manager.add_installed_app(app)
        assert state_manager.is_app_installed("TestApp")

        result = state_manager.remove_installed_app("TestApp")
        assert result is True
        assert not state_manager.is_app_installed("TestApp")

        # Removing non-existent
        result = state_manager.remove_installed_app("NonExistent")
        assert result is False

    def test_get_installed_app(self, state_manager):
        """Test getting installed app."""
        app = InstalledApp(name="TestApp", version="1.0.0", install_path="/path")
        state_manager.add_installed_app(app)

        loaded = state_manager.get_installed_app("TestApp")
        assert loaded is not None
        assert loaded.name == "TestApp"

        # Case insensitive
        loaded = state_manager.get_installed_app("testapp")
        assert loaded is not None

        # Non-existent
        loaded = state_manager.get_installed_app("NonExistent")
        assert loaded is None

    def test_list_installed_apps(self, state_manager):
        """Test listing installed apps."""
        apps = [
            InstalledApp(name="App1", version="1.0.0", install_path="/path1"),
            InstalledApp(name="App2", version="2.0.0", install_path="/path2"),
        ]
        for app in apps:
            state_manager.add_installed_app(app)

        loaded = state_manager.list_installed_apps()
        assert len(loaded) == 2
        names = [a.name for a in loaded]
        assert "App1" in names
        assert "App2" in names

    def test_record_update_check(self, state_manager):
        """Test recording update check."""
        state_manager.record_update_check("TestApp", "2.0.0", True)

        check = state_manager.get_last_update_check("TestApp")
        assert check is not None
        assert check["version"] == "2.0.0"
        assert check["has_update"] is True

    def test_get_last_update_check(self, state_manager):
        """Test getting last update check."""
        state_manager.record_update_check("TestApp", "1.0.0", False)

        check = state_manager.get_last_update_check("TestApp")
        assert check is not None
        assert check["has_update"] is False

        # Non-existent
        check = state_manager.get_last_update_check("NonExistent")
        assert check is None

    def test_record_download(self, state_manager):
        """Test recording download."""
        state_manager.record_download(
            app_name="TestApp",
            version="1.0.0",
            url="https://example.com/app.msi",
            installer_type="msi",
            success=True,
            path="/downloads/app.msi",
        )

        history = state_manager.get_download_history("TestApp")
        assert len(history) == 1
        assert history[0]["app_name"] == "TestApp"
        assert history[0]["success"] is True

    def test_get_download_history(self, state_manager):
        """Test getting download history."""
        state_manager.record_download("App1", "1.0.0", "url1", "msi", True, "path1")
        state_manager.record_download("App1", "2.0.0", "url2", "exe", False, "path2")
        state_manager.record_download("App2", "1.0.0", "url3", "msi", True, "path3")

        history = state_manager.get_download_history("App1")
        assert len(history) == 2

        history_all = state_manager.get_download_history()
        assert len(history_all) == 3

    def test_cache_manifest(self, state_manager):
        """Test caching manifest."""
        manifest = {"apps": [{"name": "Test"}]}
        state_manager.cache_manifest("default", manifest)

        cached = state_manager.get_cached_manifest("default", max_age_hours=24)
        assert cached is not None
        assert cached == manifest

    def test_get_cached_manifest_expired(self, state_manager):
        """Test getting expired manifest cache."""
        manifest = {"apps": [{"name": "Test"}]}
        state_manager.cache_manifest("default", manifest)

        # Mock time to make it expired
        state_manager._state["manifest_cache"]["default"]["cached_at"] = \
            (datetime.now() - timedelta(hours=48)).isoformat()
        state_manager._save()

        cached = state_manager.get_cached_manifest("default", max_age_hours=24)
        assert cached is None

    def test_version_comparison(self, state_manager):
        """Test version comparison logic."""
        # Stable versions
        assert state_manager._version_greater("2.0.0", "1.0.0") is True
        assert state_manager._version_greater("1.1.0", "1.0.0") is True
        assert state_manager._version_greater("1.0.1", "1.0.0") is True
        assert state_manager._version_greater("1.0.0", "1.0.0") is False
        assert state_manager._version_greater("1.0.0", "2.0.0") is False

        # Prerelease vs release
        assert state_manager._version_greater("1.0.0", "1.0.0-alpha") is True
        assert state_manager._version_greater("1.0.0-alpha", "1.0.0") is False
        assert state_manager._version_greater("1.0.0-beta.2", "1.0.0-beta.1") is True

    def test_needs_update(self, state_manager):
        """Test needs_update check."""
        app = InstalledApp(name="TestApp", version="1.0.0", install_path="/path")
        state_manager.add_installed_app(app)

        # Newer version available
        assert state_manager.needs_update("TestApp", "2.0.0") is True
        assert state_manager.needs_update("TestApp", "1.0.0") is False
        assert state_manager.needs_update("TestApp", "1.0.0-alpha") is False

        # Non-existent app
        assert state_manager.needs_update("NonExistent", "1.0.0") is True

    def test_save_load_persists_data(self, state_manager, temp_dir):
        """Test that save/load properly persists all data."""
        # Add apps
        app1 = InstalledApp(
            name="App1",
            version="1.0.0",
            install_path="/path1",
            installer_type="msi",
            requires_manual_uninstall=True,
        )
        app2 = InstalledApp(
            name="App2",
            version="2.0.0",
            install_path="/path2",
            installer_type="exe",
        )
        state_manager.add_installed_app(app1)
        state_manager.add_installed_app(app2)

        # Record download history
        state_manager.record_download("App1", "1.0.0", "url1", "msi", True, "path1")

        # Cache manifest
        state_manager.cache_manifest("default", {"apps": []})

        # Create new manager and load
        new_manager = StateManager(state_dir=state_manager.state_dir)

        # Check apps
        assert new_manager.is_app_installed("App1")
        assert new_manager.is_app_installed("App2")
        loaded_app1 = new_manager.get_installed_app("App1")
        assert loaded_app1.requires_manual_uninstall is True

        # Check download history
        history = new_manager.get_download_history("App1")
        assert len(history) == 1

        # Check manifest cache
        cached = new_manager.get_cached_manifest("default", max_age_hours=24)
        assert cached is not None

    def test_reset(self, state_manager):
        """Test resetting state."""
        app = InstalledApp(name="TestApp", version="1.0.0", install_path="/path")
        state_manager.add_installed_app(app)

        state_manager._state = {
            "schema_version": 1,
            "installed_apps": {},
            "last_update_check": {},
            "download_history": [],
            "manifest_cache": {},
        }
        state_manager._save()

        new_manager = StateManager(state_dir=state_manager.state_dir)
        assert new_manager._state["installed_apps"] == {}
        assert new_manager._state["download_history"] == []