"""Regression test: ohub check must detect versions updated OUTSIDE ohub."""
from unittest import mock

import obtainhub.main as m
from obtainhub.core.state import InstalledApp


def _mk(**kw):
    base = dict(
        id="owner/App", name="App", version="1.0.0", app_type="github",
        installer_type="exe_setup", installer_path="", source_url="",
        tag="v1.0.0", install_location="C:\\App",
    )
    base.update(kw)
    return InstalledApp(**base)


def test_refresh_installed_version_picks_up_external_upgrade():
    state = mock.MagicMock()
    app = _mk(version="1.0.0")
    # The system registry now shows a newer version installed by the user directly
    sys_app = mock.MagicMock(version="2.3.0", install_location="C:\\App")
    sys_app.name = "App"

    with mock.patch.object(m, "get_installed_system_apps", return_value=[sys_app]):
        m._refresh_installed_version(state, app)

    assert app.version == "2.3.0"
    state.add_installed_app.assert_called_once_with(app)
    state.save.assert_called_once()


def test_refresh_installed_version_name_with_version_suffix():
    # Self-update style: stored name "ObtainHub", registry "ObtainHub 0.7.5.2"
    state = mock.MagicMock()
    app = _mk(id="DavoudTeimouri/ObtainHub", name="ObtainHub", version="0.7.5.1")
    sys_app = mock.MagicMock(version="0.7.5.2", install_location="")
    sys_app.name = "ObtainHub 0.7.5.2"

    with mock.patch.object(m, "get_installed_system_apps", return_value=[sys_app]):
        m._refresh_installed_version(state, app)

    assert app.version == "0.7.5.2"
