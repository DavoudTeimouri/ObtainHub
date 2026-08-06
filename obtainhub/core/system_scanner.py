"""Windows Registry system software scanner for ObtainHub."""

import platform
import re
from dataclasses import dataclass
from typing import List, Optional

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False


@dataclass
class SystemApp:
    """Application found in Windows Registry."""
    name: str
    version: str
    publisher: str = ""
    install_location: str = ""
    uninstall_string: str = ""
    architecture: str = "x64"
    source: str = "registry"  # registry, ohub


class SystemScanner:
    """Scan Windows Registry for installed applications."""

    def __init__(self):
        self._cache: Optional[List[SystemApp]] = None
        self._uninstall_paths = self._get_uninstall_paths()

    def _get_uninstall_paths(self):
        """Get uninstall registry paths."""
        if not WINREG_AVAILABLE:
            return []
        import winreg
        return [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

    def is_windows(self) -> bool:
        """Check if running on Windows."""
        return platform.system() == "Windows"

    def scan(self, force_refresh: bool = False) -> List[SystemApp]:
        """Scan registry for installed applications."""
        if not self.is_windows() or not WINREG_AVAILABLE:
            return []

        if self._cache is not None and not force_refresh:
            return self._cache

        apps = []

        for hkey, path in self._uninstall_paths:
            try:
                apps.extend(self._scan_uninstall_key(hkey, path))
            except Exception:
                continue

        # Deduplicate by name (case-insensitive)
        seen = set()
        unique_apps = []
        for app in apps:
            key = app.name.lower()
            if key not in seen:
                seen.add(key)
                unique_apps.append(app)

        self._cache = unique_apps
        return unique_apps

    def _scan_uninstall_key(self, hkey, base_path: str) -> List[SystemApp]:
        """Scan a single uninstall registry key."""
        apps = []
        if not WINREG_AVAILABLE:
            return apps
        import winreg
        try:
            with winreg.OpenKey(hkey, base_path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name, 0, winreg.KEY_READ) as subkey:
                            app = self._parse_uninstall_entry(subkey)
                            if app and self._is_valid_app(app):
                                apps.append(app)
                    except Exception:
                        continue
        except Exception:
            pass
        return apps

    def _parse_uninstall_entry(self, subkey) -> Optional[SystemApp]:
        """Parse a single uninstall registry entry."""
        if not WINREG_AVAILABLE:
            return None
        import winreg
        def get_value(name: str, default: str = "") -> str:
            try:
                value, _ = winreg.QueryValueEx(subkey, name)
                return str(value) if value else default
            except Exception:
                return default

        name = get_value("DisplayName")
        if not name:
            return None

        version = get_value("DisplayVersion")
        publisher = get_value("Publisher")
        install_location = get_value("InstallLocation")
        uninstall_string = get_value("UninstallString")

        # Detect architecture
        architecture = "x64"
        try:
            parent = winreg.QueryInfoKey(subkey)
            # Check if it's in Wow6432Node path
            if "WOW6432Node" in str(subkey) or get_value("SystemComponent", "0") == "1":
                pass
        except Exception:
            pass

        return SystemApp(
            name=name,
            version=version,
            publisher=publisher,
            install_location=install_location,
            uninstall_string=uninstall_string,
            architecture=architecture,
            source="registry"
        )

    def _is_valid_app(self, app: SystemApp) -> bool:
        """Filter out system components, updates, and invalid entries."""
        if not app.name or len(app.name.strip()) < 2:
            return False

        # Skip system components
        skip_patterns = [
            r"^KB\d+",  # Windows updates
            r"^Security Update",
            r"^Update for",
            r"^Hotfix",
            r"^Service Pack",
            r"Microsoft Visual C\+\+ \d+ Redistributable",
            r"Microsoft .NET",
            r"Windows Driver Package",
            r"^Python \d+\.\d+",  # Python itself
        ]

        for pattern in skip_patterns:
            if re.match(pattern, app.name, re.IGNORECASE):
                return False

        # Skip entries with no version and no install location (likely system components)
        if not app.version and not app.install_location:
            return False

        return True

    def find_matching_apps(self, query: str, installed_apps: List[SystemApp]) -> List[SystemApp]:
        """Find system apps matching a query (case-insensitive)."""
        query_lower = query.lower()
        matches = []
        for app in installed_apps:
            if (query_lower in app.name.lower() or
                query_lower in app.publisher.lower()):
                matches.append(app)
        return matches


def get_system_scanner() -> SystemScanner:
    """Get singleton system scanner instance."""
    return SystemScanner()