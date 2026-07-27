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
        """Test default values."""
        app = InstalledApp(
            owner="test",
            repo="app",
            version="1.0.0",
            install_path="/path/to/app",
            installer_type="msi",
        )
        assert app.owner == "test"
        assert app.repo == "app"
        assert app.version == "1.0.0"
        assert app.installer_type == "msi"
        assert app.requires_manual_uninstall is False
        assert app.installed_at  # Should be set
        assert app.last_checked  # Should be set
    
    def test_full_name_property(self):
        """Test full_name property."""
        app = InstalledApp(owner="owner", repo="repo", version="1.0.0", 
                          install_path="/path", installer_type="exe")
        assert app.full_name == "owner/repo"
    
    def test_to_dict(self):
        """Test serialization."""
        app = InstalledApp(owner="owner", repo="repo", version="1.0.0",
                          install_path="/path", installer_type="msi")
        data = app.to_dict()
        assert data["owner"] == "owner"
        assert data["repo"] == "repo"
        assert data["version"] == "1.0.0"
        assert data["requires_manual_uninstall"] is False
    
    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "owner": "owner",
            "repo": "repo",
            "version": "1.0.0",
            "install_path": "/path",
            "installer_type": "exe",
            "requires_manual_uninstall": True,
        }
        app = InstalledApp.from_dict(data)
        assert app.owner == "owner"
        assert app.requires_manual_uninstall is True
    
    def test_from_dict_ignores_unknown_keys(self):
        """Test unknown keys are ignored."""
        data = {"owner": "o", "repo": "r", "version": "1.0.0", 
                "install_path": "/p", "installer_type": "msi", "unknown": "value"}
        app = InstalledApp.from_dict(data)
        assert app.owner == "o"


class TestManifestEntry:
    """Tests for ManifestEntry dataclass."""
    
    def test_default_values(self):
        """Test default values."""
        entry = ManifestEntry(owner="owner", repo="repo", latest_version="1.0.0")
        assert entry.owner == "owner"
        assert entry.latest_version == "1.0.0"
        assert entry.latest_prerelease_version == ""
        assert entry.is_prerelease is False
        assert entry.fetched_at  # Should be set
    
    def test_full_name_property(self):
        """Test full_name property."""
        entry = ManifestEntry(owner="owner", repo="repo", latest_version="1.0.0")
        assert entry.full_name == "owner/repo"
    
    def test_to_dict(self):
        """Test serialization."""
        entry = ManifestEntry(owner="o", repo="r", latest_version="1.0.0")
        data = entry.to_dict()
        assert data["owner"] == "o"
        assert data["latest_version"] == "1.0.0"
    
    def test_from_dict(self):
        """Test deserialization."""
        data = {"owner": "o", "repo": "r", "latest_version": "2.0.0", "is_prerelease": True}
        entry = ManifestEntry.from_dict(data)
        assert entry.latest_version == "2.0.0"
        assert entry.is_prerelease is True


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
        state_manager.load()
        assert state_manager.installed_apps == {}
        assert state_manager.manifest_cache == {}
        assert state_manager.state_file.exists() is False
    
    def test_save_and_load(self, state_manager):
        """Test saving and loading state."""
        app = InstalledApp(owner="owner", repo="repo", version="1.0.0",
                          install_path="/path", installer_type="msi")
        state_manager.add_app(app)
        
        # Create new manager with same dir
        new_manager = StateManager(state_dir=state_manager.state_dir)
        new_manager.load()
        
        loaded_app = new_manager.get_app("owner", "repo")
        assert loaded_app is not None
        assert loaded_app.version == "1.0.0"
        assert loaded_app.owner == "owner"
    
    def test_add_app(self, state_manager):
        """Test adding an app."""
        app = InstalledApp(owner="owner", repo="repo", version="1.0.0",
                          install_path="/path", installer_type="msi")
        state_manager.add_app(app)
        
        assert state_manager.has_app("owner", "repo")
        loaded = state_manager.get_app("owner", "repo")
        assert loaded is not None
        assert loaded.version == "1.0.0"
    
    def test_remove_app(self, state_manager):
        """Test removing an app."""
        app = InstalledApp(owner="owner", repo="repo", version="1.0.0",
                          install_path="/path", installer_type="msi")
        state_manager.add_app(app)
        assert state_manager.has_app("owner", "repo")
        
        result = state_manager.remove_app("owner", "repo")
        assert result is True
        assert not state_manager.has_app("owner", "repo")
        
        # Remove non-existent
        result = state_manager.remove_app("owner", "nonexistent")
        assert result is False
    
    def test_get_app(self, state_manager):
        """Test getting an app."""
        app = InstalledApp(owner="owner", repo="repo", version="1.0.0",
                          install_path="/path", installer_type="msi")
        state_manager.add_app(app)
        
        loaded = state_manager.get_app("owner", "repo")
        assert loaded is not None
        assert loaded.version == "1.0.0"
        
        # Non-existent
        loaded = state_manager.get_app("owner", "nonexistent")
        assert loaded is None
    
    def test_get_all_apps(self, state_manager):
        """Test getting all apps."""
        state_manager.add_app(InstalledApp(owner="o1", repo="r1", version="1.0.0",
                                          install_path="/p1", installer_type="msi"))
        state_manager.add_app(InstalledApp(owner="o2", repo="r2", version="2.0.0",
                                          install_path="/p2", installer_type="exe"))
        
        apps = state_manager.get_all_apps()
        assert len(apps) == 2
    
    def test_update_app_version(self, state_manager):
        """Test updating app version."""
        app = InstalledApp(owner="owner", repo="repo", version="1.0.0",
                          install_path="/path", installer_type="msi")
        state_manager.add_app(app)
        
        result = state_manager.update_app_version("owner", "repo", "2.0.0")
        assert result is True
        
        loaded = state_manager.get_app("owner", "repo")
        assert loaded.version == "2.0.0"
        assert loaded.last_updated
        
        # Non-existent
        result = state_manager.update_app_version("owner", "nonexistent", "2.0.0")
        assert result is False
    
    def test_update_last_checked(self, state_manager):
        """Test updating last_checked timestamp."""
        app = InstalledApp(owner="owner", repo="repo", version="1.0.0",
                          install_path="/path", installer_type="msi")
        state_manager.add_app(app)
        original_checked = app.last_checked
        
        # Wait a moment
        import time
        time.sleep(0.01)
        
        result = state_manager.update_last_checked("owner", "repo")
        assert result is True
        
        loaded = state_manager.get_app("owner", "repo")
        assert loaded.last_checked != original_checked
    
    def test_manifest_cache(self, state_manager):
        """Test manifest cache operations."""
        entry = ManifestEntry(owner="owner", repo="repo", latest_version="1.0.0")
        state_manager.set_manifest_entry(entry)
        
        loaded = state_manager.get_manifest_entry("owner", "repo")
        assert loaded is not None
        assert loaded.latest_version == "1.0.0"
    
    def test_get_outdated_apps(self, state_manager):
        """Test getting outdated apps."""
        # Add installed app v1.0.0
        app = InstalledApp(owner="owner", repo="repo", version="1.0.0",
                          install_path="/path", installer_type="msi")
        state_manager.add_app(app)
        
        # Add manifest with v2.0.0
        entry = ManifestEntry(owner="owner", repo="repo", latest_version="2.0.0")
        state_manager.set_manifest_entry(entry)
        
        outdated = state_manager.get_outdated_apps()
        assert len(outdated) == 1
        assert outdated[0][0].version == "1.0.0"
        assert outdated[0][1].latest_version == "2.0.0"
        
        # Test with same version (not outdated)
        entry = ManifestEntry(owner="owner", repo="repo", latest_version="1.0.0")
        state_manager.set_manifest_entry(entry)
        
        outdated = state_manager.get_outdated_apps()
        assert len(outdated) == 0
    
    def test_version_comparison(self, state_manager):
        """Test version comparison logic."""
        assert state_manager._version_greater("2.0.0", "1.0.0") is True
        assert state_manager._version_greater("1.1.0", "1.0.0") is True
        assert state_manager._version_greater("1.0.1", "1.0.0") is True
        assert state_manager._version_greater("1.0.0", "1.0.0") is False
        assert state_manager._version_greater("1.0.0", "2.0.0") is False
        assert state_manager._version_greater("1.0.0-alpha", "1.0.0") is False
        assert state_manager._version_greater("1.0.0", "1.0.0-alpha") is True
    
    def test_save_load_persists_data(self, state_manager, temp_dir):
        """Test that save/load properly persists all data."""
        # Add apps and manifest entries
        app1 = InstalledApp(owner="owner1", repo="repo1", version="1.0.0",
                           install_path="/path1", installer_type="msi",
                           requires_manual_uninstall=True)
        app2 = InstalledApp(owner="owner2", repo="repo2", version="2.0.0",
                           install_path="/path2", installer_type="exe")
        state_manager.add_app(app1)
        state_manager.add_app(app2)
        
        entry1 = ManifestEntry(owner="owner1", repo="repo1", latest_version="1.1.0",
                              is_prerelease=False)
        entry2 = ManifestEntry(owner="owner2", repo="repo2", latest_version="2.0.0",
                              is_prerelease=True)
        state_manager.set_manifest_entry(entry1)
        state_manager.set_manifest_entry(entry2)
        
        # Create completely new manager
        new_manager = StateManager(state_dir=state_manager.state_dir)
        new_manager.load()
        
        # Verify apps
        assert new_manager.has_app("owner1", "repo1")
        assert new_manager.has_app("owner2", "repo2")
        loaded_app1 = new_manager.get_app("owner1", "repo1")
        assert loaded_app1.requires_manual_uninstall is True
        assert loaded_app1.version == "1.0.0"
        
        # Verify manifest cache
        loaded_entry1 = new_manager.get_manifest_entry("owner1", "repo1")
        assert loaded_entry1.latest_version == "1.1.0"
        assert loaded_entry1.is_prerelease is False
        
        loaded_entry2 = new_manager.get_manifest_entry("owner2", "repo2")
        assert loaded_entry2.is_prerelease is True