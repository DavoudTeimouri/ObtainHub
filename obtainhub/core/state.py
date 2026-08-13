"""State management for ObtainHub."""

import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class InstalledApp:
    """Information about an installed application."""
    id: str
    name: str
    version: str
    installer_type: str
    installer_path: str
    source_url: str
    tag: str
    installed_at: int = 0
    updated_at: int = 0
    requires_manual_uninstall: bool = False
    architecture: str = "x64"
    # New fields (optional, backward compatible)
    app_type: str = "github"      # "github" | "zip" | "folder"
    install_location: str = ""    # extracted folder for zip/folder apps
    asset_pattern: str = ""       # glob pattern to re-pick the same asset on update
    preferred_asset: str = ""     # selected asset name for zip/exe apps
    github_repo: str = ""         # owner/repo linked to a folder app for updates

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "InstalledApp":
        # Tolerate missing keys from older state files
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class ManifestEntry:
    """Manifest entry for custom sources."""
    name: str
    version: str
    url: str
    installer_type: str
    sha256: str = ""
    architecture: str = "x64"
    size: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ManifestEntry":
        return cls(**data)


@dataclass
class CheckHistoryEntry:
    """Record of a check operation for an unmanaged app."""
    app_name: str
    app_version: str
    github_repo: str = ""  # owner/repo if found
    has_github_repo: bool = False
    user_choice: str = ""  # "managed", "ignored", "error"
    checked_at: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CheckHistoryEntry":
        return cls(**data)


class StateManager:
    def __init__(self, state_file=None):
        if not state_file:
            appdata = os.environ.get("APPDATA") or str(Path.home() / ".config")
            base_dir = Path(appdata) / "ObtainHub"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.state_file = base_dir / "state.json"
        else:
            self.state_file = Path(state_file)
            
        self.data = self._load_state()

    def _load_state(self):
        if not self.state_file.exists():
            return {"installed": {}, "manifest_cache": {}, "check_history": {}}
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"installed": {}, "manifest_cache": {}, "check_history": {}}

    def save(self):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def get_all_apps(self):
        """Get all installed apps as InstalledApp objects."""
        apps = []
        for app_data in self.data.get("installed", {}).values():
            apps.append(InstalledApp.from_dict(app_data))
        return apps

    def get_apps_by_type(self, app_type: str):
        """Get installed apps filtered by app_type ('github'|'zip'|'folder')."""
        return [a for a in self.get_all_apps() if a.app_type == app_type]

    def update_app(self, app_id: str, **changes) -> Optional[InstalledApp]:
        """Update fields on an existing app and save."""
        app = self.get_app(app_id)
        if not app:
            return None
        for k, v in changes.items():
            if hasattr(app, k):
                setattr(app, k, v)
        self.add_installed_app(app)
        return app

    def get_app(self, app_id: str) -> Optional[InstalledApp]:
        """Get a specific installed app by ID."""
        app_data = self.data.get("installed", {}).get(app_id)
        if app_data:
            return InstalledApp.from_dict(app_data)
        return None

    def add_installed_app(self, app: InstalledApp):
        """Add or update an installed app."""
        if isinstance(app, InstalledApp):
            self.data.setdefault("installed", {})[app.id] = app.to_dict()
        else:
            self.data.setdefault("installed", {})[app["id"]] = app
        self.save()

    def remove_app(self, app_id: str) -> bool:
        """Remove an app from state."""
        if app_id in self.data.get("installed", {}):
            del self.data["installed"][app_id]
            self.save()
            return True
        return False

    # Alias for backward compatibility
    get_installed_app = get_app
    list_installed_apps = get_all_apps
    
    def get_manifest_cache(self) -> Dict[str, ManifestEntry]:
        """Get cached manifest entries."""
        cache = {}
        for key, data in self.data.get("manifest_cache", {}).items():
            cache[key] = ManifestEntry.from_dict(data)
        return cache
    
    def set_manifest_cache(self, cache: Dict[str, ManifestEntry]):
        """Update manifest cache."""
        self.data["manifest_cache"] = {k: v.to_dict() for k, v in cache.items()}
        self.save()

    def get_check_history(self) -> Dict[str, CheckHistoryEntry]:
        """Get check history for unmanaged apps."""
        cache = {}
        for key, data in self.data.get("check_history", {}).items():
            cache[key] = CheckHistoryEntry.from_dict(data)
        return cache

    def set_check_history(self, cache: Dict[str, CheckHistoryEntry]):
        """Update check history."""
        self.data["check_history"] = {k: v.to_dict() for k, v in cache.items()}
        self.save()

    def add_check_history(self, entry: CheckHistoryEntry):
        """Add or update a check history entry."""
        self.data.setdefault("check_history", {})[entry.app_name] = entry.to_dict()
        self.save()

    def clear_check_history(self) -> None:
        """Forget all unmanaged-app linking choices (used by --reset)."""
        self.data["check_history"] = {}
        self.save()


# Module-level singleton instance
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """Get the global StateManager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager