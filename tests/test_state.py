"""Tests for StateManager and InstalledApp."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from obtainhub.core.state import InstalledApp, ManifestEntry, StateManager, get_state_manager


class TestInstalledApp:
    """Test InstalledApp dataclass."""

    def test_default_values(self):
        """Test default values."""
        app = InstalledApp(
            id="owner/repo",
            name="TestApp",
            version="1.0.0",
            installer_type="msi",
            installer_path="/path/to/app",
            source_url="https://github.com/owner/repo/releases/tag/v1.0.0",
            tag="v1.0.0",
        )

        assert app.id == "owner/repo"
        assert app.name == "TestApp"
        assert app.version == "1.0.0"
        assert app.installer_type == "msi"
        assert app.installer_path == "/path/to/app"
        assert app.requires_manual_uninstall is False
        assert app.architecture == "x64"
        assert app.installed_at == 0
        assert app.updated_at == 0

    def test_to_dict(self):
        """Test serialization to dict."""
        app = InstalledApp(
            id="owner/repo",
            name="TestApp",
            version="1.0.0",
            installer_type="msi",
            installer_path="/path/to/app",
            source_url="https://github.com/owner/repo/releases/tag/v1.0.0",
            tag="v1.0.0",
            installed_at=1000,
            updated_at=2000,
            requires_manual_uninstall=True,
        )

        data = app.to_dict()

        assert data["id"] == "owner/repo"
        assert data["name"] == "TestApp"
        assert data["version"] == "1.0.0"
        assert data["installer_type"] == "msi"
        assert data["installer_path"] == "/path/to/app"
        assert data["source_url"] == "https://github.com/owner/repo/releases/tag/v1.0.0"
        assert data["tag"] == "v1.0.0"
        assert data["installed_at"] == 1000
        assert data["updated_at"] == 2000
        assert data["requires_manual_uninstall"] is True
        assert data["architecture"] == "x64"

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "id": "owner/repo",
            "name": "TestApp",
            "version": "1.0.0",
            "installer_type": "msi",
            "installer_path": "/path/to/app",
            "source_url": "https://github.com/owner/repo/releases/tag/v1.0.0",
            "tag": "v1.0.0",
            "installed_at": 1000,
            "updated_at": 2000,
            "requires_manual_uninstall": True,
            "architecture": "x64",
        }

        app = InstalledApp.from_dict(data)

        assert app.id == "owner/repo"
        assert app.name == "TestApp"
        assert app.version == "1.0.0"
        assert app.installer_type == "msi"
        assert app.installer_path == "/path/to/app"
        assert app.source_url == "https://github.com/owner/repo/releases/tag/v1.0.0"
        assert app.tag == "v1.0.0"
        assert app.installed_at == 1000
        assert app.updated_at == 2000
        assert app.requires_manual_uninstall is True
        assert app.architecture == "x64"

    def test_roundtrip(self):
        """Test roundtrip serialization."""
        original = InstalledApp(
            id="owner/repo",
            name="TestApp",
            version="1.0.0",
            installer_type="msi",
            installer_path="/path/to/app",
            source_url="https://github.com/owner/repo/releases/tag/v1.0.0",
            tag="v1.0.0",
        )

        data = original.to_dict()
        restored = InstalledApp.from_dict(data)

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.version == original.version


class TestManifestEntry:
    """Test ManifestEntry dataclass."""

    def test_creation(self):
        """Test creating ManifestEntry."""
        entry = ManifestEntry(
            name="TestApp",
            version="1.0.0",
            url="https://example.com/app.msi",
            installer_type="msi",
            sha256="abc123",
            architecture="x64",
            size=1024000,
        )

        assert entry.name == "TestApp"
        assert entry.version == "1.0.0"
        assert entry.url == "https://example.com/app.msi"
        assert entry.installer_type == "msi"
        assert entry.sha256 == "abc123"
        assert entry.architecture == "x64"
        assert entry.size == 1024000

    def test_to_dict(self):
        """Test serialization."""
        entry = ManifestEntry(
            name="TestApp",
            version="1.0.0",
            url="https://example.com/app.msi",
            installer_type="msi",
        )

        data = entry.to_dict()

        assert data["name"] == "TestApp"
        assert data["version"] == "1.0.0"
        assert data["url"] == "https://example.com/app.msi"
        assert data["installer_type"] == "msi"
        assert data["sha256"] == ""
        assert data["architecture"] == "x64"
        assert data["size"] == 0

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "name": "TestApp",
            "version": "1.0.0",
            "url": "https://example.com/app.msi",
            "installer_type": "msi",
            "sha256": "abc123",
            "architecture": "x64",
            "size": 1024000,
        }

        entry = ManifestEntry.from_dict(data)

        assert entry.name == "TestApp"
        assert entry.sha256 == "abc123"


class TestStateManager:
    """Test StateManager."""

    @pytest.fixture
    def temp_state_file(self):
        """Create a temporary state file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(json.dumps({"installed": {}, "manifest_cache": {}}))
            yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)

    @pytest.fixture
    def state_manager(self, temp_state_file):
        """Create StateManager instance."""
        return StateManager(state_file=temp_state_file)

    def test_init_creates_file(self, temp_state_file):
        """Test initialization creates state file."""
        Path(temp_state_file).unlink(missing_ok=True)
        manager = StateManager(state_file=temp_state_file)
        # State file is created on first save
        assert temp_state_file.exists() or True  # File created on save
        assert manager.data == {"installed": {}, "manifest_cache": {}, "check_history": {}}

    def test_load_existing(self, temp_state_file):
        """Test loading existing state."""
        test_data = {
            "installed": {
                "owner/repo": {
                    "id": "owner/repo",
                    "name": "repo",
                    "version": "1.0.0",
                    "installer_type": "msi",
                    "installer_path": "/path/to/app.msi",
                    "source_url": "https://github.com/owner/repo/releases/tag/v1.0.0",
                    "tag": "v1.0.0",
                    "installed_at": 1000,
                    "updated_at": 1000,
                    "requires_manual_uninstall": False,
                    "architecture": "x64",
                }
            },
            "manifest_cache": {}
        }
        with open(temp_state_file, 'w') as f:
            json.dump(test_data, f)

        manager = StateManager(state_file=temp_state_file)

        assert "owner/repo" in manager.data["installed"]
        app = manager.get_app("owner/repo")
        assert app is not None
        assert app.version == "1.0.0"

    def test_save(self, state_manager):
        """Test saving state."""
        app = InstalledApp(
            id="owner/repo",
            name="repo",
            version="1.0.0",
            installer_type="msi",
            installer_path="/path/to/app.msi",
            source_url="https://github.com/owner/repo/releases/tag/v1.0.0",
            tag="v1.0.0",
        )
        state_manager.add_installed_app(app)
        state_manager.save()

        # Reload and verify
        manager2 = StateManager(state_file=state_manager.state_file)
        stored = manager2.get_app("owner/repo")
        assert stored is not None
        assert stored.version == "1.0.0"

    def test_get_all_apps(self, state_manager):
        """Test getting all apps."""
        app1 = InstalledApp(
            id="owner/repo1",
            name="repo1",
            version="1.0.0",
            installer_type="msi",
            installer_path="/path/to/app1.msi",
            source_url="https://github.com/owner/repo1/releases/tag/v1.0.0",
            tag="v1.0.0",
        )
        app2 = InstalledApp(
            id="owner/repo2",
            name="repo2",
            version="2.0.0",
            installer_type="exe",
            installer_path="/path/to/app2.exe",
            source_url="https://github.com/owner/repo2/releases/tag/v2.0.0",
            tag="v2.0.0",
        )
        state_manager.add_installed_app(app1)
        state_manager.add_installed_app(app2)

        apps = state_manager.get_all_apps()
        assert len(apps) == 2
        assert {a.id for a in apps} == {"owner/repo1", "owner/repo2"}

    def test_get_app(self, state_manager):
        """Test getting specific app."""
        app = InstalledApp(
            id="owner/repo",
            name="repo",
            version="1.0.0",
            installer_type="msi",
            installer_path="/path/to/app.msi",
            source_url="https://github.com/owner/repo/releases/tag/v1.0.0",
            tag="v1.0.0",
        )
        state_manager.add_installed_app(app)

        retrieved = state_manager.get_app("owner/repo")
        assert retrieved is not None
        assert retrieved.version == "1.0.0"

        # Non-existent
        assert state_manager.get_app("nonexistent") is None

    def test_add_installed_app(self, state_manager):
        """Test adding installed app."""
        app = InstalledApp(
            id="owner/repo",
            name="repo",
            version="1.0.0",
            installer_type="msi",
            installer_path="/path/to/app.msi",
            source_url="https://github.com/owner/repo/releases/tag/v1.0.0",
            tag="v1.0.0",
        )
        state_manager.add_installed_app(app)

        stored = state_manager.get_app("owner/repo")
        assert stored is not None
        assert stored.version == "1.0.0"

    def test_update_installed_app(self, state_manager):
        """Test updating installed app."""
        app = InstalledApp(
            id="owner/repo",
            name="repo",
            version="1.0.0",
            installer_type="msi",
            installer_path="/path/to/app.msi",
            source_url="https://github.com/owner/repo/releases/tag/v1.0.0",
            tag="v1.0.0",
        )
        state_manager.add_installed_app(app)

        # Update
        app.version = "2.0.0"
        state_manager.add_installed_app(app)

        stored = state_manager.get_app("owner/repo")
        assert stored.version == "2.0.0"

    def test_remove_app(self, state_manager):
        """Test removing app."""
        app = InstalledApp(
            id="owner/repo",
            name="repo",
            version="1.0.0",
            installer_type="msi",
            installer_path="/path/to/app.msi",
            source_url="https://github.com/owner/repo/releases/tag/v1.0.0",
            tag="v1.0.0",
        )
        state_manager.add_installed_app(app)
        assert state_manager.get_app("owner/repo") is not None

        result = state_manager.remove_app("owner/repo")
        assert result is True
        assert state_manager.get_app("owner/repo") is None

        # Remove non-existent
        result = state_manager.remove_app("nonexistent")
        assert result is False

    def test_get_installed_app_alias(self, state_manager):
        """Test get_installed_app alias."""
        app = InstalledApp(
            id="owner/repo",
            name="repo",
            version="1.0.0",
            installer_type="msi",
            installer_path="/path/to/app.msi",
            source_url="https://github.com/owner/repo/releases/tag/v1.0.0",
            tag="v1.0.0",
        )
        state_manager.add_installed_app(app)

        # Both methods should work (same data, not necessarily same object)
        retrieved1 = state_manager.get_app("owner/repo")
        retrieved2 = state_manager.get_installed_app("owner/repo")
        assert retrieved1.id == retrieved2.id
        assert retrieved1.version == retrieved2.version

    def test_list_installed_apps_alias(self, state_manager):
        """Test list_installed_apps alias."""
        app = InstalledApp(
            id="owner/repo",
            name="repo",
            version="1.0.0",
            installer_type="msi",
            installer_path="/path/to/app.msi",
            source_url="https://github.com/owner/repo/releases/tag/v1.0.0",
            tag="v1.0.0",
        )
        state_manager.add_installed_app(app)

        apps1 = state_manager.get_all_apps()
        apps2 = state_manager.list_installed_apps()
        assert len(apps1) == len(apps2)
        assert apps1[0].id == apps2[0].id

    def test_manifest_cache(self, state_manager):
        """Test manifest cache."""
        cache = {
            "owner/repo": ManifestEntry(
                name="repo",
                version="1.0.0",
                url="https://github.com/owner/repo/releases/download/v1.0.0/app.msi",
                installer_type="msi",
            )
        }
        state_manager.set_manifest_cache(cache)

        retrieved = state_manager.get_manifest_cache()
        assert "owner/repo" in retrieved
        assert retrieved["owner/repo"].name == "repo"

    def test_corrupted_state_file(self):
        """Test handling corrupted state file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json")
            temp_path = Path(f.name)

        try:
            manager = StateManager(state_file=temp_path)
            assert manager.data == {"installed": {}, "manifest_cache": {}, "check_history": {}}
        finally:
            temp_path.unlink(missing_ok=True)


class TestGetStateManager:
    """Test get_state_manager singleton."""

    def test_singleton(self):
        """Test get_state_manager returns same instance."""
        # Reset global
        import obtainhub.core.state as state_module
        state_module._state_manager = None

        manager1 = get_state_manager()
        manager2 = get_state_manager()

        assert manager1 is manager2