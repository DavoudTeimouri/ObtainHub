"""Tests for config module."""

import json
import tempfile
from pathlib import Path
import pytest

from obtainhub.core.config import Config, ConfigManager


class TestConfig:
    """Tests for Config dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = Config()
        assert config.download_dir == str(Path.home() / "Downloads" / "ObtainHub")
        assert config.auto_update is True
        assert config.skip_self_update is False
        assert config.verbose is False
        assert config.log_level == "INFO"
        assert len(config.manifest_sources) == 1
        assert "ObtainHub/manifests" in config.manifest_sources[0]
    
    def test_config_to_dict(self):
        """Test config serialization to dict."""
        config = Config(download_dir="/custom/path", auto_update=False)
        data = config.to_dict()
        assert data["download_dir"] == "/custom/path"
        assert data["auto_update"] is False
        assert "manifest_sources" in data
    
    def test_config_from_dict(self):
        """Test config deserialization from dict."""
        data = {
            "download_dir": "/test/path",
            "auto_update": False,
            "skip_self_update": True,
            "manifest_sources": ["https://custom.com/manifest.json"],
        }
        config = Config.from_dict(data)
        assert config.download_dir == "/test/path"
        assert config.auto_update is False
        assert config.skip_self_update is True
        assert config.manifest_sources == ["https://custom.com/manifest.json"]
    
    def test_config_from_dict_ignores_unknown_keys(self):
        """Test that unknown keys are ignored."""
        data = {
            "download_dir": "/test",
            "unknown_key": "should_be_ignored",
        }
        config = Config.from_dict(data)
        assert config.download_dir == "/test"
        assert not hasattr(config, "unknown_key")
    
    def test_get_download_dir(self):
        """Test get_download_dir expands user and env vars."""
        config = Config(download_dir="~/Downloads/Test")
        path = config.get_download_dir()
        assert str(path).startswith(str(Path.home()))
    
    def test_set_download_dir(self):
        """Test setting download directory."""
        config = Config()
        config.set_download_dir("/new/path")
        assert config.download_dir == "/new/path"
    
    def test_add_remove_manifest_source(self):
        """Test adding and removing manifest sources."""
        config = Config(manifest_sources=["https://default.com/manifest.json"])
        config.add_manifest_source("https://custom.com/manifest.json")
        assert "https://custom.com/manifest.json" in config.manifest_sources
        assert len(config.manifest_sources) == 2
        
        result = config.remove_manifest_source("https://custom.com/manifest.json")
        assert result is True
        assert "https://custom.com/manifest.json" not in config.manifest_sources
        
        result = config.remove_manifest_source("https://nonexistent.com/manifest.json")
        assert result is False


class TestConfigManager:
    """Tests for ConfigManager."""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create a ConfigManager with temp directory."""
        return ConfigManager(config_dir=temp_config_dir)
    
    def test_load_creates_default_when_no_file(self, config_manager):
        """Test loading creates default config when no file exists."""
        config = config_manager.load()
        assert isinstance(config, Config)
        # Config is created in memory but not saved to disk until save() is called
        assert config_manager.config is not None
        assert config_manager.config.download_dir == str(Path.home() / "Downloads" / "ObtainHub")
    
    def test_load_existing_config(self, config_manager, temp_config_dir):
        """Test loading existing config file."""
        config_file = temp_config_dir / "config.json"
        config_data = {
            "download_dir": "/custom/path",
            "auto_update": False,
            "manifest_sources": ["https://custom.com/manifest.json"],
        }
        config_file.write_text(json.dumps(config_data))
        
        config = config_manager.load()
        assert config.download_dir == "/custom/path"
        assert config.auto_update is False
        assert config.manifest_sources == ["https://custom.com/manifest.json"]
    
    def test_load_invalid_json(self, config_manager, temp_config_dir):
        """Test loading invalid JSON falls back to defaults."""
        config_file = temp_config_dir / "config.json"
        config_file.write_text("{ invalid json }")
        
        config = config_manager.load()
        assert isinstance(config, Config)
        assert config.download_dir == str(Path.home() / "Downloads" / "ObtainHub")
    
    def test_save_config(self, config_manager, temp_config_dir):
        """Test saving configuration."""
        config_manager.config.download_dir = "/saved/path"
        config_manager.config.auto_update = False
        result = config_manager.save()
        
        assert result is True
        assert config_manager.config_file.exists()
        
        # Verify saved content
        saved_data = json.loads(config_manager.config_file.read_text())
        assert saved_data["download_dir"] == "/saved/path"
        assert saved_data["auto_update"] is False
    
    def test_reset_config(self, config_manager):
        """Test resetting configuration to defaults."""
        config_manager.config.download_dir = "/custom/path"
        config_manager.config.auto_update = False
        config_manager.save()
        
        config = config_manager.reset()
        assert config.download_dir == str(Path.home() / "Downloads" / "ObtainHub")
        assert config.auto_update is True
    
    def test_get_set_config_values(self, config_manager):
        """Test getting and setting individual config values."""
        assert config_manager.get("auto_update") is True
        assert config_manager.set("auto_update", False) is True
        assert config_manager.get("auto_update") is False
        
        # Unknown key
        assert config_manager.set("unknown_key", "value") is False
    
    def test_get_download_dir_creates_directory(self, config_manager, temp_config_dir):
        """Test get_download_dir creates the directory."""
        config_manager.config.download_dir = str(temp_config_dir / "downloads")
        download_dir = config_manager.get_download_dir()
        assert download_dir.exists()
        assert download_dir.is_dir()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])