"""State manager for tracking installed applications."""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from obtainhub.core.exceptions import StateError, StateNotFoundError, StateValidationError


@dataclass
class InstalledApp:
    """Represents an installed application."""
    owner: str
    repo: str
    version: str
    install_path: str
    installer_type: str  # msi, exe_setup, zip_portable
    installed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    last_checked: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    last_updated: str = ""
    metadata: dict = field(default_factory=dict)
    # Manual uninstall required flag
    requires_manual_uninstall: bool = False
    
    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'InstalledApp':
        # Filter unknown keys
        known_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_keys}
        return cls(**filtered)


@dataclass
class ManifestEntry:
    """Cached manifest entry."""
    owner: str
    repo: str
    latest_version: str
    latest_prerelease_version: str = ""
    release_url: str = ""
    release_notes: str = ""
    assets: list = field(default_factory=list)
    fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    is_prerelease: bool = False
    
    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ManifestEntry':
        known_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_keys}
        return cls(**filtered)


class StateManager:
    """Manages the state database of installed applications."""
    
    STATE_DIR = Path.home() / ".local" / "share" / "obtainhub"
    STATE_FILE = STATE_DIR / "state.json"
    
    def __init__(self, state_dir: Optional[Path] = None):
        self.state_dir = state_dir or self.STATE_DIR
        self.state_file = self.state_dir / "state.json"
        self.installed_apps: dict[str, InstalledApp] = {}
        self.manifest_cache: dict[str, ManifestEntry] = {}
        self._loaded = False
    
    def load(self) -> bool:
        """Load state from file."""
        if self._loaded:
            return True
        
        if not self.state_file.exists():
            self.installed_apps = {}
            self.manifest_cache = {}
            self._loaded = True
            return True
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Load installed apps
            for key, app_data in data.get('installed_apps', {}).items():
                self.installed_apps[key] = InstalledApp.from_dict(app_data)
            
            # Load manifest cache
            for key, entry_data in data.get('manifest_cache', {}).items():
                self.manifest_cache[key] = ManifestEntry.from_dict(entry_data)
            
            self._loaded = True
            return True
            
        except json.JSONDecodeError as e:
            raise StateValidationError(f"Invalid JSON in state file: {e}")
        except Exception as e:
            raise StateError(f"Failed to load state: {e}")
    
    def save(self) -> bool:
        """Save state to file."""
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            
            data = {
                'installed_apps': {
                    key: app.to_dict() for key, app in self.installed_apps.items()
                },
                'manifest_cache': {
                    key: entry.to_dict() for key, entry in self.manifest_cache.items()
                },
            }
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            return True
            
        except Exception as e:
            raise StateError(f"Failed to save state: {e}")
    
    def add_app(self, app: InstalledApp) -> None:
        """Add or update an installed app."""
        self.load()
        self.installed_apps[app.full_name] = app
        self.save()
    
    def remove_app(self, owner: str, repo: str) -> bool:
        """Remove an installed app."""
        self.load()
        key = f"{owner}/{repo}"
        if key in self.installed_apps:
            del self.installed_apps[key]
            self.save()
            return True
        return False
    
    def get_app(self, owner: str, repo: str) -> Optional[InstalledApp]:
        """Get an installed app by owner/repo."""
        self.load()
        return self.installed_apps.get(f"{owner}/{repo}")
    
    def has_app(self, owner: str, repo: str) -> bool:
        """Check if an app is installed."""
        self.load()
        return f"{owner}/{repo}" in self.installed_apps
    
    def get_all_apps(self) -> list[InstalledApp]:
        """Get all installed apps as a list."""
        self.load()
        return list(self.installed_apps.values())
    
    def update_app_version(self, owner: str, repo: str, new_version: str) -> bool:
        """Update the version of an installed app."""
        self.load()
        key = f"{owner}/{repo}"
        if key in self.installed_apps:
            app = self.installed_apps[key]
            app.version = new_version
            app.last_updated = datetime.utcnow().isoformat() + 'Z'
            self.save()
            return True
        return False
    
    def update_last_checked(self, owner: str, repo: str) -> bool:
        """Update the last_checked timestamp for an app."""
        self.load()
        key = f"{owner}/{repo}"
        if key in self.installed_apps:
            app = self.installed_apps[key]
            app.last_checked = datetime.utcnow().isoformat() + 'Z'
            self.save()
            return True
        return False
    
    def get_manifest_entry(self, owner: str, repo: str) -> Optional[ManifestEntry]:
        """Get a manifest cache entry."""
        self.load()
        return self.manifest_cache.get(f"{owner}/{repo}")
    
    def set_manifest_entry(self, entry: ManifestEntry) -> None:
        """Set a manifest cache entry."""
        self.load()
        self.manifest_cache[entry.full_name] = entry
        self.save()
    
    def get_outdated_apps(self) -> list[tuple[InstalledApp, ManifestEntry]]:
        """Get apps that have updates available."""
        self.load()
        outdated = []
        for app in self.installed_apps.values():
            entry = self.manifest_cache.get(app.full_name)
            if entry and self._version_greater(entry.latest_version, app.version):
                outdated.append((app, entry))
        return outdated
    
    def _version_greater(self, v1: str, v2: str) -> bool:
            """Compare two version strings."""
            def normalize(v: str) -> tuple:
                parts = []
                for part in v.lstrip('vV').split('.'):
                    if '-' in part:
                        num, pre = part.split('-', 1)
                        parts.append(int(num) if num.isdigit() else 0)
                        parts.append(pre)
                    else:
                        parts.append(int(part) if part.isdigit() else 0)
                return tuple(parts)
        
            n1 = normalize(v1)
            n2 = normalize(v2)
        
            # Pad shorter tuple with zeros
            max_len = max(len(n1), len(n2))
            n1 = list(n1) + [0] * (max_len - len(n1))
            n2 = list(n2) + [0] * (max_len - len(n2))
        
            for a, b in zip(n1, n2):
                if isinstance(a, str) or isinstance(b, str):
                    # Prerelease parts: release (int/empty) > prerelease (string)
                    # So "1.0.0" > "1.0.0-alpha"
                    if isinstance(a, str) and not isinstance(b, str):
                        return False  # a is prerelease, b is release -> a < b
                    if isinstance(b, str) and not isinstance(a, str):
                        return True  # a is release, b is prerelease -> a > b
                    if isinstance(a, str) and isinstance(b, str):
                        # Both are prerelease strings
                        if a > b:
                            return True
                        elif a < b:
                            return False
                else:
                    if a > b:
                        return True
                    elif a < b:
                        return False
            return False
_state_manager: Optional[StateManager] = None


def get_state_manager(state_dir: Optional[Path] = None) -> StateManager:
    """Get the global state manager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager(state_dir)
    return _state_manager