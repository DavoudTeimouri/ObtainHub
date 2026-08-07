"""Windows Registry system software scanner for ObtainHub."""

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    WINREG_AVAILABLE = False
    winreg = None


def get_installed_system_apps():
    apps = []
    if not WINREG_AVAILABLE:
        return apps
    
    uninstall_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
    ]
    
    for root_key, subkey_path in uninstall_keys:
        try:
            with winreg.OpenKey(root_key, subkey_path) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        sub_key_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, sub_key_name) as sub_key:
                            name, _ = winreg.QueryValueEx(sub_key, "DisplayName")
                            version, _ = winreg.QueryValueEx(sub_key, "DisplayVersion")
                            if name:
                                apps.append({"name": name, "version": version or "Unknown", "source": "System Registry"})
                    except OSError:
                        continue
        except OSError:
            continue
    return apps