"""Configuration management for ObtainHub."""

import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class ManifestSource:
    """A source for application manifests."""
    name: str
    url: str
    enabled: bool = True
    headers: Dict[str, str] = field(default_factory=dict)
    type: str = "github"         # "github" | "manifest"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManifestSource":
        return cls(**data)


@dataclass
class Config:
    """Main configuration for ObtainHub."""
    # GitHub API
    github_token: str = ""
    self_update_enabled: bool = True

    # Directories
    install_dir: str = str(Path.home() / "Applications" / "ObtainHub")
    download_dir: str = str(Path.home() / "Downloads" / "ObtainHub")
    config_dir: str = str(Path.home() / ".config" / "obtainhub")
    state_dir: str = str(Path.home() / ".local" / "share" / "obtainhub")

    # Update behavior
    update_interval_hours: int = 24
    auto_update: bool = True
    allow_prerelease: bool = False

    # Architecture preferences
    prefer_x64: bool = True
    allow_x86_fallback: bool = False

    # Manual uninstall handling
    auto_attempt_uninstall: bool = False

    # Custom sources
    sources: List[ManifestSource] = field(default_factory=list)
    
    # Network
    proxy: str = ""
    timeout_seconds: int = 30
    check_timeout_seconds: int = 20
    check_timeout_retries: int = 3
    max_parallel_downloads: int = 3
    
    # Logging
    log_level: str = "INFO"
    log_file: str = ""
    
    # Manifest sources
    manifest_sources: List[ManifestSource] = field(default_factory=lambda: [
        ManifestSource(
            name="default",
            url="https://raw.githubusercontent.com/DavoudTeimouri/ObtainHub/main/manifest.json",
            enabled=True
        )
    ])
    
    # Version
    schema_version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization."""
        data = asdict(self)
        # Convert ManifestSource objects to dicts
        data["manifest_sources"] = [ms.to_dict() for ms in self.manifest_sources]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create config from dictionary."""
        # Filter known fields to ignore unknown keys
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        
        # Convert manifest_sources
        if "manifest_sources" in filtered_data:
            filtered_data["manifest_sources"] = [
                ManifestSource.from_dict(ms) for ms in filtered_data["manifest_sources"]
            ]
        return cls(**filtered_data)

    def validate(self) -> List[str]:
        """Validate configuration, return list of errors."""
        errors = []
        
        if self.update_interval_hours < 1:
            errors.append("update_interval_hours must be >= 1")
        
        if self.timeout_seconds < 5:
            errors.append("timeout_seconds must be >= 5")
        
        if not (10 <= self.check_timeout_seconds <= 60):
            errors.append("check_timeout_seconds must be between 10 and 60")
        if not (1 <= self.check_timeout_retries <= 5):
            errors.append("check_timeout_retries must be between 1 and 5")
        
        if self.max_parallel_downloads < 1:
            errors.append("max_parallel_downloads must be >= 1")
        
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            errors.append(f"log_level must be one of: {valid_log_levels}")
        
        return errors


class ConfigManager:
    """Manages configuration loading, saving, and migration."""
    
    DEFAULT_CONFIG_FILENAME = "config.json"
    
    def __init__(self, config_dir: Optional[str] = None):
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path.home() / ".config" / "obtainhub"
        
        self.config_file = self.config_dir / self.DEFAULT_CONFIG_FILENAME
        self._config: Optional[Config] = None

    @property
    def config(self) -> Config:
        """Get current config, loading if necessary."""
        if self._config is None:
            self._config = self.load()
        return self._config

    def load(self) -> Config:
        """Load configuration from file.

        A shared global config (same for every user on the machine) is read
        first, then the per-user config is overlaid on top of it so individual
        users can override settings. The GitHub token stays per-user only.
        """
        # Start from global (machine-wide) config if present
        global_file = self._global_config_file()
        if global_file and global_file.exists():
            try:
                with open(global_file, "r", encoding="utf-8") as f:
                    gdata = json.load(f)
                base = self._migrate(gdata)
            except Exception:
                base = Config()
        else:
            base = Config()

        if not self.config_file.exists():
            self.save(base)
            return base

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Treat any user-set value as an override; token is always per-user.
            config = self._migrate(data)
            # Overlay user values onto the global base (None fields keep global)
            merged = base.to_dict()
            for k, v in config.to_dict().items():
                if v is not None:
                    merged[k] = v
            config = Config.from_dict(merged)

            errors = config.validate()
            if errors:
                raise ValueError(f"Config validation failed: {errors}")

            self._config = config
            return config

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load config: {e}")

    def _global_config_file(self) -> Optional[Path]:
        """Machine-wide config shared by all users (token is NOT read from here)."""
        env = os.environ.get("OBTAINHUB_GLOBAL_CONFIG")
        if env:
            return Path(env)
        if os.name == "nt":
            base = os.environ.get("ProgramData")
            if base := (base or r"C:\ProgramData"):
                return Path(base) / "ObtainHub" / self.DEFAULT_CONFIG_FILENAME
        return Path("/etc/obtainhub") / self.DEFAULT_CONFIG_FILENAME

    def _migrate(self, data: Dict[str, Any]) -> Config:
        """Migrate config from older schema versions."""
        schema_version = data.get("schema_version", 1)
        
        # Add defaults for new fields if missing
        if schema_version < 2:
            data.setdefault("prefer_x64", True)
            data.setdefault("allow_x86_fallback", False)
            data.setdefault("auto_attempt_uninstall", False)
            data["schema_version"] = 2
        
        return Config.from_dict(data)

    def save(self, config: Optional[Config] = None) -> None:
        """Save configuration to file."""
        if config is None:
            config = self.config
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Validate before saving
        errors = config.validate()
        if errors:
            raise ValueError(f"Config validation failed: {errors}")
        
        # Write atomically
        temp_file = self.config_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(config.to_dict(), f, indent=2)
            temp_file.replace(self.config_file)
            self._config = config
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink()
            raise ValueError(f"Failed to save config: {e}")

    def reset(self) -> Config:
        """Reset to default configuration."""
        config = Config()
        self.save(config)
        return config

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by key."""
        return getattr(self.config, key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a config value."""
        if not hasattr(self.config, key):
            raise KeyError(f"Unknown config key: {key}")
        setattr(self.config, key, value)
        self.save()

    def add_manifest_source(self, name: str, url: str, enabled: bool = True, headers: Optional[Dict[str, str]] = None) -> None:
        """Add a manifest source."""
        # Remove existing with same name
        self.config.manifest_sources = [ms for ms in self.config.manifest_sources if ms.name != name]
        # Add new
        self.config.manifest_sources.append(ManifestSource(name=name, url=url, enabled=enabled, headers=headers or {}))
        self.save()

    def remove_manifest_source(self, name: str) -> bool:
        """Remove a manifest source by name."""
        original_len = len(self.config.manifest_sources)
        self.config.manifest_sources = [ms for ms in self.config.manifest_sources if ms.name != name]
        if len(self.config.manifest_sources) < original_len:
            self.save()
            return True
        return False

    def get_enabled_manifest_sources(self) -> List[ManifestSource]:
        """Get all enabled manifest sources."""
        return [ms for ms in self.config.manifest_sources if ms.enabled]

    def get_download_dir(self) -> Path:
        """Get download directory, creating it if it doesn't exist."""
        download_dir = Path(self.config.download_dir).expanduser()
        download_dir.mkdir(parents=True, exist_ok=True)
        return download_dir


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_dir: Optional[str] = None) -> ConfigManager:
    """Get or create global config manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_dir)
    return _config_manager


def get_config(config_dir: Optional[str] = None) -> Config:
    """Get current configuration."""
    return get_config_manager(config_dir).config