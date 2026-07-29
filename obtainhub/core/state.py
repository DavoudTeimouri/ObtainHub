"""State management for ObtainHub."""

import json
import datetime
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from obtainhub.core.config import get_config
from obtainhub.core.logger import get_logger


logger = get_logger(__name__)


@dataclass
class ManifestEntry:
    """Entry in application manifest."""
    name: str
    owner: str
    repo: str
    description: str = ""
    homepage: str = ""
    license: str = ""
    tags: List[str] = field(default_factory=list)
    # Install hints
    installer_name_pattern: str = ""
    installer_args: str = ""
    # Architecture
    architecture: str = "x64"
    # Manual uninstall required
    requires_manual_uninstall: bool = False
    # Post-install actions
    post_install_commands: List[str] = field(default_factory=list)
    # Uninstall
    uninstall_method: str = "auto"
    uninstall_args: str = "/quiet /norestart"
    # Preferences
    prefer_x64: bool = True
    allow_prerelease: bool = False
    # Known checksums
    known_checksums: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ManifestEntry":
        return cls(**data)


@dataclass
class InstalledApp:
    """Information about an installed application."""
    name: str
    version: str
    install_path: str
    executable_path: str = ""
    install_date: str = field(default_factory=lambda: datetime.now().isoformat())
    source_url: str = ""
    source_type: str = "github"  # github, manifest, manual
    manifest_name: str = ""
    # Architecture of installed app
    architecture: str = "x64"
    # Whether this app requires manual uninstall
    requires_manual_uninstall: bool = False
    # Uninstall string for MSI apps
    uninstall_string: str = ""
    # Installer type (msi, exe, zip)
    installer_type: str = ""
    # For tracking if app was installed by ohub
    installed_by_ohub: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "InstalledApp":
        return cls(**data)


class StateManager:
    """Manages persistent state for ObtainHub."""

    def __init__(self, state_dir: Optional[Path] = None):
        config = get_config()
        self.state_dir = state_dir or Path(config.state_dir)
        self.state_file = self.state_dir / "state.json"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self._state = {
            "schema_version": 1,
            "installed_apps": {},
            "last_update_check": {},
            "download_history": [],
            "manifest_cache": {},
        }
        self._load()

    def _load(self):
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._state = data
                logger.debug(f"Loaded state from {self.state_file}")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load state: {e}, starting fresh")
        else:
            logger.debug("No state file found, starting fresh")

    def _save(self):
        """Save state to file."""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved state to {self.state_file}")
        except OSError as e:
            logger.error(f"Failed to save state: {e}")

    # Installed apps management

    def add_installed_app(self, app: InstalledApp):
        """Add or update an installed app."""
        self._state["installed_apps"][app.name] = app.to_dict()
        self._save()
        logger.info(f"Registered installed app: {app.name} {app.version}")

    def remove_installed_app(self, name: str) -> bool:
        """Remove an installed app from state."""
        if name in self._state["installed_apps"]:
            del self._state["installed_apps"][name]
            self._save()
            logger.info(f"Removed installed app from state: {name}")
            return True
        return False

    def get_installed_app(self, name: str) -> Optional[InstalledApp]:
        """Get installed app info (case-insensitive)."""
        for stored_name, data in self._state["installed_apps"].items():
            if stored_name.lower() == name.lower():
                return InstalledApp.from_dict(data)
        return None

    def list_installed_apps(self) -> List[InstalledApp]:
        """List all installed apps."""
        return [
            InstalledApp.from_dict(data)
            for data in self._state["installed_apps"].values()
        ]

    def is_app_installed(self, name: str) -> bool:
        """Check if app is installed (case-insensitive)."""
        for stored_name in self._state["installed_apps"]:
            if stored_name.lower() == name.lower():
                return True
        return False

    def get_installed_version(self, name: str) -> Optional[str]:
        """Get installed version of app."""
        app = self.get_installed_app(name)
        return app.version if app else None

    # Update check tracking

    def record_update_check(self, app_name: str, version: str, has_update: bool):
        """Record an update check result."""
        self._state["last_update_check"][app_name] = {
            "checked_at": datetime.now().isoformat(),
            "version": version,
            "has_update": has_update,
        }
        self._save()

    def get_last_update_check(self, app_name: str) -> Optional[dict]:
        """Get last update check result."""
        return self._state["last_update_check"].get(app_name)

    # Download history

    def record_download(self, app_name: str, version: str, url: str,
                       installer_type: str, success: bool, path: str = ""):
        """Record a download attempt."""
        entry = {
            "app_name": app_name,
            "version": version,
            "url": url,
            "installer_type": installer_type,
            "success": success,
            "path": path,
            "timestamp": datetime.now().isoformat(),
        }
        self._state["download_history"].append(entry)
        # Keep only last 100 entries
        if len(self._state["download_history"]) > 100:
            self._state["download_history"] = self._state["download_history"][-100:]
        self._save()

    def get_download_history(self, app_name: Optional[str] = None,
                            limit: int = 10) -> List[dict]:
        """Get download history."""
        history = self._state["download_history"]
        if app_name:
            history = [h for h in history if h["app_name"] == app_name]
        return history[-limit:]

    # Manifest cache

    def cache_manifest(self, source_name: str, manifest: dict):
        """Cache manifest data."""
        self._state["manifest_cache"][source_name] = {
            "data": manifest,
            "cached_at": datetime.now().isoformat(),
        }
        self._save()

    def get_cached_manifest(self, source_name: str, max_age_hours: int = 24) -> Optional[dict]:
        """Get cached manifest if not expired."""
        cache = self._state["manifest_cache"].get(source_name)
        if not cache:
            return None

        cached_at = datetime.fromisoformat(cache["cached_at"])
        age = datetime.now() - cached_at
        if age.total_seconds() > max_age_hours * 3600:
            return None

        return cache["data"]

    # Version comparison

    def _normalize_version(self, version: str) -> tuple:
        """Normalize version string for comparison."""
        # Remove 'v' prefix
        version = version.lstrip('vV')

        # Split into numeric and prerelease parts
        parts = version.split('-', 1)
        main_version = parts[0]
        prerelease = parts[1] if len(parts) > 1 else None

        # Parse main version numbers
        version_parts = []
        for part in main_version.split('.'):
            try:
                version_parts.append(int(part))
            except ValueError:
                version_parts.append(0)

        # Pad to 3 parts for comparison
        while len(version_parts) < 3:
            version_parts.append(0)

        # Prerelease gets a negative modifier
        if prerelease:
            prerelease_parts = [prerelease]
            return tuple(version_parts) + (-1, prerelease)

        return tuple(version_parts) + (0, "")

    def _version_greater(self, v1: str, v2: str) -> bool:
        """Check if v1 > v2."""
        return self._normalize_version(v1) > self._normalize_version(v2)

    def needs_update(self, app_name: str, latest_version: str) -> bool:
        """Check if app needs update."""
        current = self.get_installed_version(app_name)
        if not current:
            return True
        return self._version_greater(latest_version, current)

    # Reset

    def reset(self):
        """Reset state to empty."""
        self._state = {
            "schema_version": 1,
            "installed_apps": {},
            "last_update_check": {},
            "download_history": [],
            "manifest_cache": {},
        }
        self._save()


# Global state manager instance
_state_manager: Optional[StateManager] = None


def get_state_manager(state_dir: Optional[str] = None) -> StateManager:
    """Get or create global state manager."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager(state_dir)
    return _state_manager