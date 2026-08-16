"""Regression test: uninstall runs the real uninstaller, not the install wizard."""
import sys
from pathlib import Path
from unittest import mock

import obtainhub.core.installer as inst
from obtainhub.core.asset_matcher import InstallerType
from obtainhub.core.state import InstalledApp


def _msa(name, uninstall_string):
    sa = mock.MagicMock()
    sa.name = name
    sa.uninstall_string = uninstall_string
    return sa


def test_registry_uninstall_cmd_parses_uninstall_string():
    installer = inst.SilentInstaller()
    sa = _msa("MyApp", '"C:\\Program Files\\MyApp\\unins000.exe" /SILENT')
    with mock.patch.object(inst, "get_installed_system_apps", return_value=[sa]):
        exe, args = installer._registry_uninstall_cmd("MyApp")
    assert exe == r"C:\Program Files\MyApp\unins000.exe"
    assert args == ["/SILENT"]


def test_uninstall_exe_uses_registry_not_setup_wizard():
    """Interactive uninstall must launch the registry uninstaller, never the
    cached setup.exe (which would open the install wizard)."""
    app = InstalledApp(
        id="owner/MyApp", name="MyApp", version="1.0.0",
        installer_type="exe_setup", installer_path="C:\\Downloads\\MyApp-Setup.exe",
        source_url="", tag="v1.0.0",
    )
    sa = _msa("MyApp", r'"C:\Program Files\MyApp\unins000.exe"')
    installer = inst.SilentInstaller()
    captured = {}

    def fake_run(*a, **k):
        captured["args"] = a[0]
        return mock.MagicMock(returncode=0)

    with mock.patch.object(inst, "get_installed_system_apps", return_value=[sa]), \
         mock.patch("obtainhub.core.installer.subprocess.run", side_effect=fake_run):
        ok, msg = installer._uninstall_exe(app, interactive=True)
    assert ok is True
    assert captured["args"][0] == r"C:\Program Files\MyApp\unins000.exe"
    # The setup wizard exe must NOT be launched
    assert "MyApp-Setup.exe" not in str(captured["args"])
