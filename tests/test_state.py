"""Tests for state module."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
import pytest

from obtainhub.core.state import InstalledApp, ManifestEntry, StateManager


class TestInstalledApp:
    """Tests for InstalledApp dataclass."""
    
    def test_default_values(self):
        """Test default values for installed app."""
        app = InstalledApp(
            name="TestApp",
            owner="owner",
            repo="repo",
            version="1.0.0",
        )
        assert app.name == "TestApp"
        assert app.owner == "owner"
        assert app.repo == "repo"
        assert app.version == "1.0.0"
        assert app.installer_type == "unknown"
        assert app.auto_update is True
        assert app.metadata == {}
    
    def test_full_name_property(self):
        """Test full_name property."""
        app = InstalledApp(name="Test", owner="owner", repo="repo", version="1.0.0")
        assert app.full_name == "owner/repo"
    
    def test_to_dict(self):
        """Test serialization to dict."""
        app = InstalledApp(
            name="TestApp",
            owner="owner",
            repo="repo",
            version="1.0.0",
            installer_type="msi",
            metadata={"key": "value"},
        )
        data = app.to_dict()
        assert data["name"] == "TestApp"
        assert data["owner"] == "owner"
        assert data["repo"] == "repo"
        assert data["version"] == "1.0.0"
        assert data["installer_type"] == "msi"
        assert data["metadata"] == {"key": "value"}
    
    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "name": "TestApp",
            "owner": "owner",
            "repo": "repo",
            "version": "2.0.0",
            "installer_type": "exe",
            "metadata": {"custom": "data"},
        }
        app = InstalledApp.from_dict(data)
        assert app.name == "TestApp"
        assert app.version == "2.0.0"
        assert app.installer_type == "exe"
        assert app.metadata == {"custom": "data"}
    
    def test_from_dict_ignores_unknown_keys(self):
        """Test from_dict ignores unknown keys."""
        data = {
            "name": "TestApp",
            "owner": "owner",
            "repo": "repo",
            "version": "1.0.0",
            "unknown_field": "ignored",
        }
        app = InstalledApp.from_dict(data)
        assert not hasattr(app, "unknown_field")


class TestManifestEntry:
    """Tests for ManifestEntry dataclass."""
    
    def test_default_values(self):
        """Test default values for manifest entry."""
        entry = ManifestEntry(
            name="TestApp",
            owner="owner",
            repo="repo",
            version="1.0.0",
        )
        assert entry.name == "TestApp"
        assert entry.version == "1.0.0"
        assert entry.installer_type == "auto"
        assert entry.prerequisites == []
        assert entry.tags == []
    
    def test_full_name_property(self):
        """Test full_name property."""
        entry = ManifestEntry(name="Test", owner="owner", repo="repo", version="1.0.0")
        assert entry.full_name == "owner/repo"
    
    def test_to_dict(self):
        """Test serialization to dict."""
        entry = ManifestEntry(
            name="TestApp",
            owner="owner",
            repo="repo",
            version="1.0.0",
            description="Test app",
            tags=["gui", "editor"],
        )
        data = entry.to_dict()
        assert data["description"] == "Test app"
        assert data["tags"] == ["gui", "editor"]
    
    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "name": "TestApp",
            "owner": "owner",
            "repo": "repo",
            "version": "2.0.0",
            "checksum": "abc123",
        }
        entry = ManifestEntry.from_dict(data)
        assert entry.version == "2.0.0"
        assert entry.checksum == "abc123"


class TestStateManager:
    """Tests for StateManager."""
    
    @pytest.fixture
    def temp_state_dir(self):
        """Create a temporary state directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def state_manager(self, temp_state_dir):
        """Create a StateManager with temp directory."""
        return StateManager(state_dir=temp_state_dir)
    
    def test_load_creates_empty_when_no_file(self, state_manager):
        """Test loading creates empty state when no file exists."""
        state_manager.load()
        assert state_manager.installed_apps == {}
        assert state_manager.manifest_cache == {}
    
    def test_save_and_load(self, state_manager):
        """Test saving and loading state."""
        app = InstalledApp(
            name="TestApp",
            owner="owner",
            repo="repo",
            version="1.0.0",
            installer_type="msi",
        )
        state_manager.add_app(app)
        
        # Create new manager to load from file
        new_manager = StateManager(state_dir=state_manager.state_dir)
        loaded_app = new_manager.get_app("owner", "repo")
        
        assert loaded_app is not None
        assert loaded_app.name == "TestApp"
        assert loaded_app.version == "1.0.0"
        assert loaded_app.installer_type == "msi"
    
    def test_add_app(self, state_manager):
        """Test adding an app."""
        app = InstalledApp(
            name="TestApp",
            owner="owner",
            repo="repo",
            version="1.0.0",
        )
        state_manager.add_app(app)
        
        assert state_manager.has_app("owner", "repo")
        retrieved = state_manager.get_app("owner", "repo")
        assert retrieved is not None
        assert retrieved.version == "1.0.0"
    
    def test_remove_app(self, state_manager):
        """Test removing an app."""
        app = InstalledApp(name="TestApp", owner="owner", repo="repo", version="1.0.0")
        state_manager.add_app(app)
        
        result = state_manager.remove_app("owner", "repo")
        assert result is True
        assert not state_manager.has_app("owner", "repo")
        
        # Removing non-existent
        result = state_manager.remove_app("owner", "nonexistent")
        assert result is False
    
    def test_get_app(self, state_manager):
        """Test getting an app."""
        app = InstalledApp(name="TestApp", owner="owner", repo="repo", version="1.0.0")
        state_manager.add_app(app)
        
        retrieved = state_manager.get_app("owner", "repo")
        assert retrieved is not None
        assert retrieved.name == "TestApp"
        
        # Non-existent
        retrieved = state_manager.get_app("owner", "nonexistent")
        assert retrieved is None
    
    def test_get_all_apps(self, state_manager):
        """Test getting all apps."""
        app1 = InstalledApp(name="App1", owner="owner", repo="repo1", version="1.0.0")
        app2 = InstalledApp(name="App2", owner="owner", repo="repo2", version="2.0.0")
        state_manager.add_app(app1)
        state_manager.add_app(app2)
        
        all_apps = state_manager.get_all_apps()
        assert len(all_apps) == 2
        names = {a.name for a in all_apps}
        assert names == {"App1", "App2"}
    
    def test_update_app_version(self, state_manager):
        """Test updating app version."""
        app = InstalledApp(name="TestApp", owner="owner", repo="repo", version="1.0.0")
        state_manager.add_app(app)
        
        result = state_manager.update_app_version("owner", "repo", "2.0.0")
        assert result is True
        
        retrieved = state_manager.get_app("owner", "repo")
        assert retrieved.version == "2.0.0"
        
        # Non-existent app
        result = state_manager.update_app_version("owner", "nonexistent", "1.0.0")
        assert result is False
    
    def test_manifest_cache(self, state_manager):
        """Test manifest cache operations."""
        entry = ManifestEntry(
            name="TestApp",
            owner="owner",
            repo="repo",
            version="2.0.0",
        )
        state_manager.add_manifest_entry(entry)
        
        cached = state_manager.get_manifest_entry("owner", "repo")
        assert cached is not None
        assert cached.version == "2.0.0"
        
        state_manager.clear_manifest_cache()
        assert state_manager.get_manifest_entry("owner", "repo") is None
    
    def test_get_outdated_apps(self, state_manager):
        """Test getting outdated apps."""
        # Installed app at version 1.0.0
        installed = InstalledApp(
            name="TestApp",
            owner="owner",
            repo="repo",
            version="1.0.0",
            auto_update=True,
        )
        state_manager.add_app(installed)
        
        # Manifest has version 2.0.0
        manifest = ManifestEntry(
            name="TestApp",
            owner="owner",
            repo="repo",
            version="2.0.0",
        )
        state_manager.add_manifest_entry(manifest)
        
        outdated = state_manager.get_outdated_apps()
        assert len(outdated) == 1
        assert outdated[0][0].version == "1.0.0"
        assert outdated[0][1].version == "2.0.0"
        
        # Test with auto_update disabled
        installed.auto_update = False
        state_manager.add_app(installed)
        outdated = state_manager.get_outdated_apps()
        assert len(outdated) == 0
    
    def test_version_comparison(self, state_manager):
        """Test version comparison logic."""
        assert state_manager._compare_versions("1.0.0", "2.0.0") == -1
        assert state_manager._compare_versions("2.0.0", "1.0.0") == 1
        assert state_manager._compare_versions("1.0.0", "1.0.0") == 0
        assert state_manager._compare_versions("1.10.0", "1.2.0") == 1
        assert state_manager._compare_versions("v1.0.0", "1.0.0") == 0
        assert state_manager._compare_versions("1.0.0-beta", "1.0.0") == 0
    
    def test_save_load_persists_data(self, state_manager, temp_state_dir):
        """Test that save/load correctly persists all data."""
        # Add app
        app = InstalledApp(
            name="TestApp",
            owner="owner",
            repo="repo",
            version="1.0.0",
            installer_type="msi",
            install_dir="/path/to/install",
            checksum="abc123",
        )
        state_manager.add_app(app)
        
        # Add manifest entry
        manifest = ManifestEntry(
            name="TestApp",
            owner="owner",
            repo="repo",
            version="2.0.0",
            description="Updated version",
        )
        state_manager.add_manifest_entry(manifest)
        
        # Create new manager and load
        new_manager = StateManager(state_dir=temp_state_dir)
        
        loaded_app = new_manager.get_app("owner", "repo")
        assert loaded_app is not None
        assert loaded_app.version == "1.0.0"
        assert loaded_app.installer_type == "msi"
        assert loaded_app.install_dir == "/path/to/install"
        assert loaded_app.checksum == "abc123"
        
        loaded_manifest = new_manager.get_manifest_entry("owner", "repo")
        assert loaded_manifest is not None
        assert loaded_manifest.version == "2.0.0"
        assert loaded_manifest.description == "Updated version"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])