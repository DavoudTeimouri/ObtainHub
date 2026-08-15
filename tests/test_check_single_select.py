"""Regression test: `ohub check --all` single-select must not scan all apps."""
from unittest import mock

import obtainhub.main as m


def test_check_all_single_managed_select_skips_unmanaged_scan():
    """Picking one managed app in the TTY menu must check only that app,
    not run the unmanaged (system registry) GitHub search for every app."""
    cfg = mock.MagicMock()
    cfg.github_token = ""
    cfg.check_timeout_seconds = 90
    cfg.check_timeout_retries = 3
    state = mock.MagicMock()
    managed = [
        mock.MagicMock(id="owner/App", name="App", install_location="",
                       installer_path="", app_type="github", version="1.0.0"),
        mock.MagicMock(id="owner/Other", name="Other", install_location="",
                       installer_path="", app_type="github", version="1.0.0"),
    ]
    state.get_all_apps.return_value = managed
    state.get_app.side_effect = lambda i: next((a for a in managed if a.id == i), None)

    searches = []
    fake_client = mock.MagicMock()
    fake_client.get_latest_release.return_value = {"tag_name": "v1.0.0", "assets": []}

    with mock.patch.object(m, "get_installed_system_apps", return_value=[
        # a system app that is NOT ohub-managed
        mock.MagicMock(name="Some System App", version="1.0", install_location="C:\\x"),
    ]), mock.patch.object(m, "GitHubClient", return_value=fake_client), \
         mock.patch.object(m, "AssetMatcher") as matchers, \
         mock.patch("sys.stdin.isatty", return_value=True), \
         mock.patch("builtins.input", return_value="1"), \
         mock.patch("builtins.print"), \
         mock.patch.object(m, "get_config_manager", return_value=cfg), \
         mock.patch.object(m, "get_state_manager", return_value=state):
        matchers.return_value.get_best_match.return_value = None
        matchers.return_value.get_installable_candidates.return_value = []
        parsed = mock.MagicMock()
        parsed.all = True
        parsed.app = None
        parsed.yes = True
        parsed.json = False
        parsed.reset = False
        parsed.prerelease = False
        parsed.candidates = False
        parsed.timeout = None
        parsed.keep_data = False
        m.cmd_check(parsed, cfg, state, mock.MagicMock())

    # Only the selected managed app should have been checked via get_latest_release
    assert fake_client.get_latest_release.call_count == 1
    assert fake_client.get_latest_release.call_args.args == ("owner", "App")
    # search_repositories must NOT be called (no unmanaged scan ran)
    assert fake_client.search_repositories.call_count == 0
