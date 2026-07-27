"""Tests for config module."""

import json
import tempfile
from pathlib import Path
import pytest

from obtainhub.core.config import Config, ConfigManager, ManifestSource


class TestConfig:
    """Tests for Config dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = Config()
        assert config.github_token == ""
        assert "ObtainHub" in config.install_dir
        assert "ObtainHub" in config.download_dir
        assert config.update_interval_hours == 24
        assert config.proxy == ""
        assert config.auto_update is True
        assert config.log_level == "INFO"
        assert config.max_parallel_downloads == 3
        assert len(config.manifest_sources) == 1
        assert config.manifest_sources[0].name == "default"
        assert config.preferred_arch == "x64"
        assert config.allow_prerelease is False
        assert config.skip_self_update is False
        assert config.auto_confirm_prerelease is False
    
    def test_config_to_dict(self):
        """Test config serialization."""
        config = Config()
        data = config.to_dict()
        
        assert isinstance(data, dict)
        assert "github_token" in data
        assert "manifest_sources" in data
        assert isinstance(data["manifest_sources"], list)
        assert data["manifest_sources"][0]["name"] == "default"
    
    def test_config_from_dict(self):
        """Test config deserialization."""
        data = {
            "github_token": "test-token",
            "install_dir": "/custom/install",
            "download_dir": "/custom/download",
            "update_interval_hours": 12,
            "proxy": "http://proxy:8080",
            "auto_update": False,
            "log_level": "DEBUG",
            "max_parallel_downloads": 5,
            "manifest_sources": [
                {"name": "test", "url": "https://example.com/manifest.json", "enabled": True}
            ],
            "preferred_arch": "x64",
            "allow_prerelease": True,
            "skip_self_update": True,
            "auto_confirm_prerelease": True,
        }
        config = Config.from_dict(data)
        
        assert config.github_token == "test-token"
        assert config.install_dir == "/custom/install"
        assert config.update_interval_hours == 12
        assert config.auto_update is False
        assert config.log_level == "DEBUG"
        assert config.max_parallel_downloads == 5
        assert len(config.manifest_sources) == 1
        assert config.manifest_sources[0].name == "test"
        assert config.preferred_arch == "x64"
        assert config.allow_prerelease is True
        assert config.skip_self_update is True
        assert config.auto_confirm_prerelease is True
    
    def test_config_from_dict_ignores_unknown_keys(self):
        """Test that unknown keys are ignored."""
        data = {"unknown_key": "value", "github_token": "test"}
        config = Config.from_dict(data)
        assert config.github_token == "test"
    
    def test_get_download_dir(self):
        """Test download directory property."""
        config = Config()
        config.download_dir = "/tmp/test_download"
        assert config.download_dir == "/tmp/test_download"
    
    def test_set_download_dir(self):
        """Test setting download directory."""
        config = Config()
        config.download_dir = "/new/path"
        assert config.download_dir == "/new/path"
    
    def test_add_remove_manifest_source(self):
        """Test adding and removing manifest sources."""
        config = Config()
        config.manifest_sources = []
        
        config.manifest_sources.append(ManifestSource(name="test1", url="https://test1.com"))
        config.manifest_sources.append(ManifestSource(name="test2", url="https://test2.com"))
        
        assert len(config.manifest_sources) == 2
        
        # Remove
        config.manifest_sources = [ms for ms in config.manifest_sources if ms.name != "test1"]
        assert len(config.manifest_sources) == 1
        assert config.manifest_sources[0].name == "test2"


class TestConfigManager:
    """Tests for ConfigManager."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def config_manager(self, temp_dir):
        """Create a ConfigManager with temp directory."""
        return ConfigManager(config_dir=temp_dir / "config")
    
    def test_load_creates_default_when_no_file(self, config_manager):
        """Test loading creates default config when no file exists."""
        config = config_manager.load()
        assert isinstance(config, Config)
        assert config.github_token == ""
        assert config_manager.config_file.exists()
    
    def test_load_existing_config(self, config_manager):
        """Test loading existing config file."""
        # Create config file
        config_manager.config_dir.mkdir(parents=True)
        test_config = {
            "github_token": "test-token",
            "update_interval_hours": 12,
        }
        with open(config_manager.config_file, 'w') as f:
            json.dump(test_config, f)
        
        config = config_manager.load()
        assert config.github_token == "test-token"
        assert config.update_interval_hours == 12
    
    def test_load_invalid_json(self, config_manager):
        """Test loading invalid JSON raises error."""
        config_manager.config_dir.mkdir(parents=True)
        with open(config_manager.config_file, 'w') as f:
            f.write("{ invalid json }")
        
        with pytest.raises(Exception):  # ConfigError
            config_manager.load()
    
    def test_save_config(self, config_manager):
        """Test saving config."""
        config = config_manager.load()
        config.github_token = "new-token"
        config_manager.save()
        
        # Reload and verify
        new_manager = ConfigManager(config_dir=config_manager.config_dir)
        new_config = new_manager.load()
        assert new_config.github_token == "new-token"
    
    def test_reset_config(self, config_manager):
        """Test resetting config to defaults."""
        config = config_manager.load()
        config.github_token = "test-token"
        config_manager.save()
        
        config_manager.reset()
        new_config = config_manager.load()
        assert new_config.github_token == ""
    
    def test_get_set_config_values(self, config_manager):
        """Test getting and setting config values."""
        config_manager.load()
        config_manager.set("github_token", "test-token")
        assert config_manager.get("github_token") == "test-token"
        
        config_manager.set("update_interval_hours", 6)
        assert config_manager.get("update_interval_hours") == 6
    
    def test_get_download_dir_creates_directory(self, config_manager):
        """Test get_download_dir creates directory."""
        download_dir = config_manager.get_download_dir()
        assert download_dir.exists()
        assert download_dir.is_dir()
    
    def test_add_manifest_source(self, config_manager):
        """Test adding manifest source."""
        config_manager.add_manifest_source("test", "https://test.com/manifest.json")
        config = config_manager.load()
        assert len(config.manifest_sources) == 2  # default + test
        assert any(ms.name == "test" for ms in config.manifest_sources)
    
    def test_remove_manifest_source(self, config_manager):
        """Test removing manifest source."""
        config_manager.add_manifest_source("test", "https://test.com/manifest.json")
        assert config_manager.remove_manifest_source("test") is True
        assert config_manager.remove_manifest_source("nonexistent") is False
    
    def test_get_enabled_manifest_sources(self, config_manager):
        """Test getting enabled manifest sources."""
        config_manager.add_manifest_source("disabled", "https://disabled.com", enabled=False)
        config_manager.add_manifest_source("enabled", "https://enabled.com", enabled=True)
        sources = config_manager.get_enabled_manifest_sources()
        assert len(sources) == 2  # default + enabled
        assert all(s.enabled for s in sources)
    
    def test_validation_errors(self, config_manager):
        """Test config validation."""
        # Test invalid update interval
        config = Config(update_interval_hours=0)
        errors = config.validate()
        assert any("update_interval_hours" in e for e in errors)
        
        # Test invalid log level
        config = Config(log_level="INVALID")
        errors = config.validate()
        assert any("log_level" in e for e in errors)
        
        # Test invalid preferred_arch
        config = Config(preferred_arch="invalid")
        errors = config.validate()
        assert any("preferred_arch" in e for e in errors)


class TestManifestSource:
    """Tests for ManifestSource."""
    
    def test_to_dict(self):
        """Test serialization."""
        ms = ManifestSource(name="test", url="https://test.com", enabled=True)
        data = ms.to_dict()
        assert data["name"] == "test"
        assert data["url"] == "https://test.com"
        assert data["enabled"] is True
    
    def test_from_dict(self):
        """Test deserialization."""
        data = {"name": "test", "url": "https://test.com", "enabled": False}
        ms = ManifestSource.from_dict(data)
        assert ms.name == "test"
        assert ms.url == "https://test.com"
        assert ms.enabled is False