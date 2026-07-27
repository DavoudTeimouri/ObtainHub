"""State manager for tracking installed applications."""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from pathlib import Path as PathLibPath

from obtainhub.core.logger import get_logger
from obtainhub.core.exceptions import ConfigError


logger = get_logger()


@dataclass
class InstalledApp:
    """Data class representing an installed application."""
    
    # Required fields
    name: str
    owner: str
    repo: str
    version: str
    installed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Optional fields
    installer_type: str = "unknown"  # exe, msi, zip, portable
    installer_path: str = ""
    install_dir: str = ""
    executable_path: str = ""
    manifest_url: str = ""
    manifest_version: str = ""
    release_url: str = ""
    release_notes: str = ""
    checksum: str = ""
    checksum_algorithm: str = "sha256"
    file_size: int = 0
    auto_update: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Windows-specific
    registry_key: str = ""
    uninstall_string: str = ""
    publisher: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InstalledApp":
        """Create InstalledApp from dictionary."""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)
    
    @property
    def full_name(self) -> str:
        """Get full name as owner/repo."""
        return f"{self.owner}/{self.repo}"
    
    @property
    def install_dir_path(self) -> PathLibPath:
        """Get install directory as Path."""
        return PathLibPath(self.install_dir) if self.install_dir else PathLibPath()
    
    @property
    def executable_path_path(self) -> PathLibPath:
        """Get executable path as Path."""
        return PathLibPath(self.executable_path) if self.executable_path else PathLibPath()
    
    @property
    def is_installed(self) -> bool:
        """Check if app appears to be installed (files exist)."""
        if self.executable_path and PathLibPath(self.executable_path).exists():
            return True
        if self.install_dir and PathLibPath(self.install_dir).exists():
            return True
        return False


@dataclass
class ManifestEntry:
    """Data class representing a manifest entry for an available app."""
    
    name: str
    owner: str
    repo: str
    version: str
    description: str = ""
    installer_type: str = "auto"
    download_url: str = ""
    checksum: str = ""
    checksum_algorithm: str = "sha256"
    file_size: int = 0
    release_date: str = ""
    release_notes: str = ""
    prerequisites: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    homepage: str = ""
    license: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ManifestEntry":
        """Create ManifestEntry from dictionary."""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)
    
    @property
    def full_name(self) -> str:
        """Get full name as owner/repo."""
        return f"{self.owner}/{self.repo}"


class StateManager:
    """Manager for loading, saving, and accessing installed app state."""
    
    STATE_FILENAME = "state.json"
    
    def __init__(self, state_dir: Optional[PathLibPath] = None) -> None:
        """Initialize StateManager.
        
        Args:
            state_dir: Directory to store state.json. Defaults to same as config dir.
        """
        if state_dir is None:
            if os.name == "nt":
                base = PathLibPath(os.environ.get("APPDATA", PathLibPath.home() / "AppData" / "Roaming"))
            else:
                base = PathLibPath(os.environ.get("XDG_CONFIG_HOME", PathLibPath.home() / ".config"))
            state_dir = base / "ObtainHub"
        
        self.state_dir = PathLibPath(state_dir)
        self.state_file = self.state_dir / self.STATE_FILENAME
        self._installed_apps: dict[str, InstalledApp] = {}
        self._manifest_cache: dict[str, ManifestEntry] = {}
        self._loaded = False
    
    @property
    def installed_apps(self) -> dict[str, InstalledApp]:
        """Get installed apps, loading if necessary."""
        if not self._loaded:
            self.load()
        return self._installed_apps
    
    @property
    def manifest_cache(self) -> dict[str, ManifestEntry]:
        """Get manifest cache, loading if necessary."""
        if not self._loaded:
            self.load()
        return self._manifest_cache
    
    def load(self) -> None:
        """Load state from file."""
        if self._loaded:
            return
        
        try:
            if self.state_file.exists():
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Load installed apps
                apps_data = data.get("installed_apps", {})
                self._installed_apps = {
                    k: InstalledApp.from_dict(v) for k, v in apps_data.items()
                }
                
                # Load manifest cache
                manifest_data = data.get("manifest_cache", {})
                self._manifest_cache = {
                    k: ManifestEntry.from_dict(v) for k, v in manifest_data.items()
                }
                
                logger.debug(f"Loaded state from {self.state_file}: {len(self._installed_apps)} apps")
            else:
                logger.debug("No state file found, starting fresh")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in state file: {e}")
            logger.warning("Starting with empty state")
            self._installed_apps = {}
            self._manifest_cache = {}
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            logger.warning("Starting with empty state")
            self._installed_apps = {}
            self._manifest_cache = {}
        
        self._loaded = True
    
    def save(self) -> bool:
            """Save state to file.
        
            Returns:
                True if saved successfully, False otherwise.
            """
            try:
                self.state_dir.mkdir(parents=True, exist_ok=True)
                data = {
                    "installed_apps": {k: v.to_dict() for k, v in self._installed_apps.items()},
                    "manifest_cache": {k: v.to_dict() for k, v in self._manifest_cache.items()},
                    "last_updated": datetime.now().isoformat(),
                }
                with open(self.state_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                logger.debug(f"Saved state to {self.state_file}")
                return True
            except Exception as e:
                logger.error(f"Failed to save state: {e}")
                return False
    
    def add_app(self, app: InstalledApp) -> None:
        """Add or update an installed app."""
        key = app.full_name
        self._installed_apps[key] = app
        self.save()
        logger.info(f"Added/updated app: {key} v{app.version}")
    
    def remove_app(self, owner: str, repo: str) -> bool:
        """Remove an installed app.
        
        Returns:
            True if app was removed, False if not found.
        """
        key = f"{owner}/{repo}"
        if key in self._installed_apps:
            del self._installed_apps[key]
            self.save()
            logger.info(f"Removed app: {key}")
            return True
        return False
    
    def get_app(self, owner: str, repo: str) -> Optional[InstalledApp]:
        """Get an installed app by owner/repo."""
        return self.installed_apps.get(f"{owner}/{repo}")
    
    def has_app(self, owner: str, repo: str) -> bool:
        """Check if an app is installed."""
        return f"{owner}/{repo}" in self.installed_apps
    
    def get_all_apps(self) -> list[InstalledApp]:
        """Get all installed apps as a list."""
        return list(self.installed_apps.values())
    
    def update_app_version(self, owner: str, repo: str, version: str) -> bool:
        """Update the version of an installed app.
        
        Returns:
            True if updated, False if app not found.
        """
        key = f"{owner}/{repo}"
        if key in self._installed_apps:
            self._installed_apps[key].version = version
            self.save()
            logger.info(f"Updated {key} to version {version}")
            return True
        return False
    
    def add_manifest_entry(self, entry: ManifestEntry) -> None:
        """Add or update a manifest cache entry."""
        key = entry.full_name
        self._manifest_cache[key] = entry
        self.save()
        logger.debug(f"Cached manifest entry: {key} v{entry.version}")
    
    def get_manifest_entry(self, owner: str, repo: str) -> Optional[ManifestEntry]:
        """Get a manifest cache entry."""
        return self.manifest_cache.get(f"{owner}/{repo}")
    
    def clear_manifest_cache(self) -> None:
        """Clear the manifest cache."""
        self._manifest_cache.clear()
        self.save()
        logger.debug("Cleared manifest cache")
    
    def get_outdated_apps(self) -> list[tuple[InstalledApp, ManifestEntry]]:
        """Get list of outdated apps with their latest manifest entries.
        
        Returns:
            List of (installed_app, manifest_entry) tuples where manifest version > installed version.
        """
        outdated = []
        for app in self._installed_apps.values():
            if not app.auto_update:
                continue
            manifest = self._manifest_cache.get(app.full_name)
            if manifest and self._compare_versions(app.version, manifest.version) < 0:
                outdated.append((app, manifest))
        return outdated
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings. Returns -1 if v1 < v2, 0 if equal, 1 if v1 > v2."""
        def parse_version(v: str) -> list[int]:
            # Remove 'v' prefix if present
            v = v.lstrip('v')
            parts = []
            for part in v.split('.'):
                # Extract numeric part
                num = ''.join(c for c in part if c.isdigit())
                parts.append(int(num) if num else 0)
            return parts
        
        p1 = parse_version(v1)
        p2 = parse_version(v2)
        
        # Pad shorter version with zeros
        max_len = max(len(p1), len(p2))
        p1.extend([0] * (max_len - len(p1)))
        p2.extend([0] * (max_len - len(p2)))
        
        if p1 < p2:
            return -1
        elif p1 > p2:
            return 1
        return 0
    
    @property
    def state_path(self) -> PathLibPath:
        """Get the state file path."""
        return self.state_file


def get_state_manager(state_dir: Optional[PathLibPath] = None) -> StateManager:
    """Get or create the global StateManager instance."""
    global _state_manager
    if "_state_manager" not in globals():
        globals()["_state_manager"] = StateManager(state_dir)
    return globals()["_state_manager"]