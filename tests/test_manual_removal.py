"""Regression test: github apps with missing install_location must NOT be
treated as manually removed when still present in the system registry."""
from unittest import mock

import obtainhub.main as m
from obtainhub.core.state import InstalledApp


def _mk(d):
    base = dict(
        id="owner/MyApp", name="MyApp", version="1.0.0",
        installer_type="exe_setup", installer_path="C:\\Downloads\\MyApp-Setup.exe",
        source_url="", tag="v1.0.0", app_type="github", install_location="",
    )
    base.update(d)
    return InstalledApp.from_dict(base)


def test_github_app_present_in_registry_not_removed():
    """Registry has the app but install_location is empty/missing -> keep it."""
    sa = mock.MagicMock()
    sa.name = "MyApp"
    sm = mock.MagicMock()
    sm.remove_app = mock.MagicMock()
    with mock.patch.object(m, "get_installed_system_apps", return_value=[sa]):
        removed = m._detect_manual_removal(sm, _mk({"install_location": ""}))
    assert removed is False
    sm.remove_app.assert_not_called()


def test_github_app_absent_from_registry_and_installer_gone_removed():
    sm = mock.MagicMock()
    sm.remove_app = mock.MagicMock()
    with mock.patch.object(m, "get_installed_system_apps", return_value=[]):
        removed = m._detect_manual_removal(
            sm, _mk({"installer_path": "C:\\missing\\MyApp-Setup.exe"})
        )
    assert removed is True
    sm.remove_app.assert_called_once_with("owner/MyApp")


def test_zip_app_missing_folder_removed():
    sm = mock.MagicMock()
    sm.remove_app = mock.MagicMock()
    app = _mk({"app_type": "folder", "id": "folder:myapp", "name": "myapp",
               "installer_type": "folder", "install_location": "C:\\missing\\myapp"})
    with mock.patch.object(m, "get_installed_system_apps", return_value=[]):
        removed = m._detect_manual_removal(sm, app)
    assert removed is True
    sm.remove_app.assert_called_once()
