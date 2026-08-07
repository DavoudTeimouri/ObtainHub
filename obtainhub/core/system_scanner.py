"""Windows Registry system software scanner for ObtainHub."""

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False
    winreg = None

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SystemApp:
    """Represents a system-installed application from Windows Registry."""
    name: str
    version: str
    publisher: str
    install_date: str
    uninstall_string: str
    install_location: str
    system_component: bool


def get_installed_system_apps() -> List[SystemApp]:
    """Scan Windows Registry for installed applications.
    
    Returns:
        List of SystemApp objects representing installed software.
    """
    if not WINREG_AVAILABLE:
        return []
    
    apps = []
    uninstall_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    
    for hkey, subkey_path in uninstall_keys:
        try:
            with winreg.OpenKey(hkey, subkey_path) as uninstall_key:
                for i in range(winreg.QueryInfoKey(uninstall_key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(uninstall_key, i)
                        with winreg.OpenKey(uninstall_key, subkey_name) as subkey:
                            # Skip system components
                            try:
                                system_component = winreg.QueryValueEx(subkey, "SystemComponent")[0]
                                if system_component:
                                    continue
                            except (FileNotFoundError, OSError):
                                pass
                            
                            # Get app info
                            name = _get_reg_value(subkey, "DisplayName")
                            if not name:
                                continue
                            
                            version = _get_reg_value(subkey, "DisplayVersion") or "Unknown"
                            publisher = _get_reg_value(subkey, "Publisher") or "Unknown"
                            install_date = _get_reg_value(subkey, "InstallDate") or ""
                            uninstall_string = _get_reg_value(subkey, "UninstallString") or ""
                            install_location = _get_reg_value(subkey, "InstallLocation") or ""
                            
                            apps.append(SystemApp(
                                name=name,
                                version=version,
                                publisher=publisher,
                                install_date=install_date,
                                uninstall_string=uninstall_string,
                                install_location=install_location,
                                system_component=False,
                            ))
                    except (FileNotFoundError, OSError, WindowsError):
                        continue
        except (FileNotFoundError, OSError, WindowsError):
            continue
    
    # Sort by name
    apps.sort(key=lambda x: x.name.lower())
    return apps


def _get_reg_value(key, value_name: str) -> Optional[str]:
    """Safely get a registry value."""
    try:
        value, _ = winreg.QueryValueEx(key, value_name)
        return str(value) if value else None
    except (FileNotFoundError, OSError, WindowsError):
        return None


def find_system_app_by_name(name: str) -> Optional[SystemApp]:
    """Find a system app by name (case-insensitive)."""
    apps = get_installed_system_apps()
    name_lower = name.lower()
    for app in apps:
        if app.name.lower() == name_lower:
            return app
    return None