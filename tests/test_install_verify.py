"""Regression test: install verifies against system state, not the exit code."""
from unittest import mock

import obtainhub.core.installer as inst
from obtainhub.core.asset_matcher import InstallerType
from obtainhub.core.state import InstalledApp


def _mk_state(temp_dir):
    from obtainhub.core.state import StateManager
    return StateManager(state_file=temp_dir / "state.json")


def test_verify_installed_finds_registry_app():
    state = _mk_state(__import__("pathlib").Path("/tmp"))
    sa = mock.MagicMock(version="3.1.4")
    sa.name = "MyApp"
    with mock.patch.object(inst, "get_installed_system_apps", return_value=[sa]):
        ok, ver = inst.SilentInstaller()._verify_installed("owner/MyApp")
    assert ok is True
    assert ver == "3.1.4"


def test_install_reports_failed_when_not_in_system():
    """A 'successful' installer exit that left no trace in the system must not
    be recorded as success."""
    import pathlib
    tmp = pathlib.Path("/tmp")
    exe = tmp / "fake.exe"
    exe.write_bytes(b"fake")
    state = mock.MagicMock()
    state.get_installed_app.return_value = None
    installer = inst.SilentInstaller(download_dir="/tmp")
    installer.state_manager = state
    # Simulate the subprocess exit code 0 but nothing installed
    with mock.patch.object(inst, "get_installed_system_apps", return_value=[]), \
         mock.patch("obtainhub.core.installer.subprocess.run",
                     return_value=mock.MagicMock(returncode=0)):
        result, message = installer.install(
            exe, InstallerType.EXE_STANDALONE, "owner/App", force=True,
        )
    exe.unlink(missing_ok=True)
    assert result == inst.InstallResult.FAILED
    assert "not detected" in message


def test_install_succeeds_when_registry_shows_app():
    import pathlib
    tmp = pathlib.Path("/tmp")
    exe = tmp / "fake.exe"
    exe.write_bytes(b"fake")
    state = mock.MagicMock()
    state.get_installed_app.return_value = None
    installer = inst.SilentInstaller(download_dir="/tmp")
    installer.state_manager = state
    sa = mock.MagicMock(version="2.0.0")
    sa.name = "App"
    with mock.patch.object(inst, "get_installed_system_apps", return_value=[sa]), \
         mock.patch("obtainhub.core.installer.subprocess.run",
                     return_value=mock.MagicMock(returncode=0)):
        result, message = installer.install(
            exe, InstallerType.EXE_STANDALONE, "owner/App", force=True,
        )
    exe.unlink(missing_ok=True)
    assert result == inst.InstallResult.SUCCESS
