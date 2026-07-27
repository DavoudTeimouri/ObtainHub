"""Configuration manager for ObtainHub local config.json."""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional
from pathlib import Path as PathLibPath

from obtainhub.core.logger import get_logger


logger = get_logger()


@dataclass
class Config:
    """Configuration data class for ObtainHub settings."""
    
    # Application settings
    download_dir: str = str(PathLibPath.home() / "Downloads" / "ObtainHub")
    auto_update: bool = True
    skip_self_update: bool = False
    verbose: bool = False
    log_level: str = "INFO"
    
    # Manifest sources
    manifest_sources: list[str] = field(default_factory=lambda: [
        "https://raw.githubusercontent.com/ObtainHub/manifests/main/index.json"
    ])
    
    # Network settings
    github_token: str = ""
    request_timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Installer preferences
    preferred_installer_type: str = "auto"  # auto, exe, msi, zip
    verify_signatures: bool = True
    verify_checksums: bool = True
    backup_before_update: bool = True
    
    # Advanced settings
    max_concurrent_downloads: int = 3
    chunk_size: int = 8192
    verify_ssl: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        """Create Config from dictionary."""
        # Filter out unknown keys for backward compatibility
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)
    
    def get_download_dir(self) -> PathLibPath:
        """Get download directory as Path, expanding environment variables."""
        return PathLibPath(os.path.expandvars(self.download_dir)).expanduser()
    
    def set_download_dir(self, path: str | PathLibPath) -> None:
        """Set download directory."""
        self.download_dir = str(path)
    
    def add_manifest_source(self, url: str) -> None:
        """Add a custom manifest source URL."""
        if url not in self.manifest_sources:
            self.manifest_sources.append(url)
            logger.info(f"Added manifest source: {url}")
    
    def remove_manifest_source(self, url: str) -> bool:
        """Remove a manifest source URL. Returns True if removed."""
        if url in self.manifest_sources:
            self.manifest_sources.remove(url)
            logger.info(f"Removed manifest source: {url}")
            return True
        return False


class ConfigManager:
    """Manager for loading, saving, and accessing ObtainHub configuration."""
    
    CONFIG_FILENAME = "config.json"
    
    def __init__(self, config_dir: Optional[PathLibPath] = None) -> None:
        """Initialize ConfigManager.
        
        Args:
            config_dir: Directory to store config.json. Defaults to %APPDATA%/ObtainHub on Windows
                       or ~/.config/obtainhub on Unix-like systems.
        """
        if config_dir is None:
            if os.name == "nt":
                base = PathLibPath(os.environ.get("APPDATA", PathLibPath.home() / "AppData" / "Roaming"))
            else:
                base = PathLibPath(os.environ.get("XDG_CONFIG_HOME", PathLibPath.home() / ".config"))
            config_dir = base / "ObtainHub"
        
        self.config_dir = PathLibPath(config_dir)
        self.config_file = self.config_dir / self.CONFIG_FILENAME
        self._config: Optional[Config] = None
        self._loaded = False
    
    @property
    def config(self) -> Config:
        """Get config instance, loading if necessary."""
        if not self._loaded:
            self.load()
        return self._config
    
    def load(self) -> Config:
        """Load configuration from file."""
        if self._loaded and self._config is not None:
            return self._config
        
        try:
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._config = Config.from_dict(data)
                logger.debug(f"Loaded config from {self.config_file}")
            else:
                self._config = Config()
                logger.debug("No config file found, using defaults")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            logger.warning("Using default configuration")
            self._config = Config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            logger.warning("Using default configuration")
            self._config = Config()
        
        self._loaded = True
        return self._config
    
    def save(self) -> bool:
        """Save configuration to file.
        
        Returns:
            True if saved successfully, False otherwise.
        """
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved config to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def reset(self) -> Config:
        """Reset configuration to defaults and save."""
        self._config = Config()
        self._loaded = True
        self.save()
        logger.info("Configuration reset to defaults")
        return self._config
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by key."""
        return getattr(self.config, key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """Set a config value by key and save."""
        if hasattr(self.config, key):
            setattr(self.config, key, value)
            return self.save()
        logger.warning(f"Unknown config key: {key}")
        return False
    
    def get_download_dir(self) -> PathLibPath:
        """Get the download directory, creating it if needed."""
        path = self.config.get_download_dir()
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def config_path(self) -> PathLibPath:
        """Get the config file path."""
        return self.config_file


def get_config_manager(config_dir: Optional[PathLibPath] = None) -> ConfigManager:
    """Get or create the global ConfigManager instance."""
    global _config_manager
    if "_config_manager" not in globals():
        globals()["_config_manager"] = ConfigManager(config_dir)
    return globals()["_config_manager"]


def get_config(config_dir: Optional[PathLibPath] = None) -> Config:
    """Get the global Config instance."""
    return get_config_manager(config_dir).config