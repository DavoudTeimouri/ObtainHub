"""Configuration manager for ObtainHub."""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

from obtainhub.core.exceptions import ConfigError, ConfigValidationError


@dataclass
class ManifestSource:
    """A manifest source for application definitions."""
    name: str
    url: str
    enabled: bool = True
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ManifestSource':
        return cls(**data)


@dataclass
class Config:
    """ObtainHub configuration."""
    # GitHub API token for higher rate limits
    github_token: str = ""
    
    # Installation directory for applications
    install_dir: str = str(Path.home() / "Applications" / "ObtainHub")
    
    # Download directory for installers
    download_dir: str = str(Path.home() / "Downloads" / "ObtainHub")
    
    # Update check interval in hours
    update_interval_hours: int = 24
    
    # Proxy settings
    proxy: str = ""
    
    # Auto-update ObtainHub itself
    auto_update: bool = True
    
    # Log level: DEBUG, INFO, WARNING, ERROR
    log_level: str = "INFO"
    
    # Maximum parallel downloads
    max_parallel_downloads: int = 3
    
    # Manifest sources
    manifest_sources: list[ManifestSource] = field(default_factory=lambda: [
        ManifestSource(
            name="default",
            url="https://raw.githubusercontent.com/ObtainHub/manifests/main/manifest.json",
        )
    ])
    
    # Preferred architecture (x64, x86, arm64)
    preferred_arch: str = "x64"
    
    # Allow prereleases by default
    allow_prerelease: bool = False
    
    # Skip self-update check
    skip_self_update: bool = False
    
    # Auto-confirm prerelease prompts (for CI/CD)
    auto_confirm_prerelease: bool = False
    
    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        data = asdict(self)
        # Don't serialize the manifest_sources as dataclass objects
        data['manifest_sources'] = [ms.to_dict() for ms in self.manifest_sources]
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Config':
        """Create config from dictionary."""
        # Convert manifest_sources
        if 'manifest_sources' in data:
            data['manifest_sources'] = [
                ManifestSource.from_dict(ms) for ms in data['manifest_sources']
            ]
        # Filter unknown keys
        known_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_keys}
        return cls(**filtered)
    
    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        if self.update_interval_hours < 1:
            errors.append("update_interval_hours must be >= 1")
        
        if self.max_parallel_downloads < 1:
            errors.append("max_parallel_downloads must be >= 1")
        
        if self.log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            errors.append("log_level must be one of: DEBUG, INFO, WARNING, ERROR")
        
        if self.preferred_arch not in ("x64", "x86", "arm64"):
            errors.append("preferred_arch must be one of: x64, x86, arm64")
        
        # Validate paths
        try:
            Path(self.install_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Invalid install_dir: {e}")
        
        try:
            Path(self.download_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"Invalid download_dir: {e}")
        
        return errors


class ConfigManager:
    """Manages ObtainHub configuration."""
    
    CONFIG_DIR = Path.home() / ".config" / "obtainhub"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or self.CONFIG_DIR
        self.config_file = self.config_dir / "config.json"
        self._config: Optional[Config] = None
    
    def load(self) -> Config:
        """Load configuration from file."""
        if self._config is not None:
            return self._config
        
        if not self.config_file.exists():
            self._config = Config()
            self.save()
            return self._config
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._config = Config.from_dict(data)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            raise ConfigError(f"Failed to load config: {e}")
        
        # Validate
        errors = self._config.validate()
        if errors:
            raise ConfigValidationError(f"Config validation failed: {'; '.join(errors)}")
        
        return self._config
    
    def save(self) -> None:
        """Save configuration to file."""
        if self._config is None:
            return
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config.to_dict(), f, indent=2)
        except Exception as e:
            raise ConfigError(f"Failed to save config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        config = self.load()
        return getattr(config, key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        config = self.load()
        if not hasattr(config, key):
            raise ConfigError(f"Unknown configuration key: {key}")
        setattr(config, key, value)
        self.save()
    
    def reset(self) -> None:
        """Reset configuration to defaults."""
        self._config = Config()
        self.save()
    
    @property
    def config(self) -> Config:
        """Get the current configuration (load if needed)."""
        if self._config is None:
            self.load()
        return self._config
    
    def add_manifest_source(self, name: str, url: str, enabled: bool = True) -> None:
        """Add a manifest source."""
        config = self.load()
        # Remove existing with same name
        config.manifest_sources = [ms for ms in config.manifest_sources if ms.name != name]
        config.manifest_sources.append(ManifestSource(name=name, url=url, enabled=enabled))
        self.save()
    
    def remove_manifest_source(self, name: str) -> bool:
        """Remove a manifest source. Returns True if removed."""
        config = self.load()
        original_len = len(config.manifest_sources)
        config.manifest_sources = [ms for ms in config.manifest_sources if ms.name != name]
        if len(config.manifest_sources) < original_len:
            self.save()
            return True
        return False
    
    def get_enabled_manifest_sources(self) -> list[ManifestSource]:
        """Get all enabled manifest sources."""
        config = self.load()
        return [ms for ms in config.manifest_sources if ms.enabled]
    
    def get_download_dir(self) -> Path:
        """Get download directory as Path, creating if needed."""
        config = self.load()
        path = Path(config.download_dir).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_install_dir(self) -> Path:
        """Get install directory as Path, creating if needed."""
        config = self.load()
        path = Path(config.install_dir).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_dir: Optional[Path] = None) -> ConfigManager:
    """Get the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_dir)
    return _config_manager


def get_config() -> Config:
    """Get the current configuration."""
    return get_config_manager().load()