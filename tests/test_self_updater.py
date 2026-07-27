"""Tests for self_updater module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from obtainhub.core.self_updater import ReleaseInfo, SelfUpdater, check_and_update
from obtainhub.core.exceptions import SelfUpdateFailedError, NetworkError


class TestReleaseInfo:
    """Tests for ReleaseInfo dataclass."""

    def test_properties(self):
        """Test ReleaseInfo properties."""
        assets = [
            {"name": "obtainhub-1.0.0.msi", "browser_download_url": "https://example.com/obtainhub-1.0.0.msi"},
            {"name": "obtainhub-1.0.0.exe", "browser_download_url": "https://example.com/obtainhub-1.0.0.exe"},
            {"name": "source.tar.gz", "browser_download_url": "https://example.com/source.tar.gz"},
        ]

        release = ReleaseInfo(
            version="1.0.0",
            name="Release 1.0.0",
            body="Release notes",
            prerelease=False,
            draft=False,
            published_at="2024-01-01T00:00:00Z",
            html_url="https://github.com/ObtainHub/ObtainHub/releases/tag/v1.0.0",
            assets=assets,
        )

        assert release.installer_asset is not None
        assert release.installer_asset["name"] == "obtainhub-1.0.0.msi"
        assert release.installer_download_url == "https://example.com/obtainhub-1.0.0.msi"
        assert release.installer_filename == "obtainhub-1.0.0.msi"

    def test_no_installer_asset(self):
        """Test when no installer asset is present."""
        assets = [
            {"name": "source.tar.gz", "browser_download_url": "https://example.com/source.tar.gz"},
            {"name": "source.zip", "browser_download_url": "https://example.com/source.zip"},
        ]

        release = ReleaseInfo(
            version="1.0.0",
            name="Release 1.0.0",
            body="",
            prerelease=False,
            draft=False,
            published_at="2024-01-01T00:00:00Z",
            html_url="https://github.com/ObtainHub/ObtainHub/releases/tag/v1.0.0",
            assets=assets,
        )

        assert release.installer_asset is None
        assert release.installer_download_url is None
        assert release.installer_filename is None


class TestSelfUpdater:
    """Tests for SelfUpdater class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config manager."""
        config = Mock()
        config.config = Mock()
        config.config.skip_self_update = False
        config.config.github_token = None
        return config

    def test_init(self):
        """Test SelfUpdater initialization."""
        updater = SelfUpdater(
            current_version="1.0.0",
            skip_check=True,
            github_token="test-token",
            timeout=60,
        )
        assert updater.current_version == "1.0.0"
        assert updater.skip_check is True
        assert updater.github_token == "test-token"
        assert updater.timeout == 60

    def test_version_comparison(self):
        """Test version comparison logic."""
        updater = SelfUpdater(current_version="1.0.0")

        assert updater._is_newer_version("2.0.0") is True
        assert updater._is_newer_version("1.1.0") is True
        assert updater._is_newer_version("1.0.1") is True
        assert updater._is_newer_version("1.0.0") is False
        assert updater._is_newer_version("0.9.0") is False
        assert updater._is_newer_version("v2.0.0") is True
        assert updater._is_newer_version("1.10.0") is True

    def test_compare_versions(self):
        """Test version comparison helper."""
        updater = SelfUpdater()

        assert updater._compare_versions("1.0.0", "2.0.0") == -1
        assert updater._compare_versions("2.0.0", "1.0.0") == 1
        assert updater._compare_versions("1.0.0", "1.0.0") == 0
        assert updater._compare_versions("1.10.0", "1.2.0") == 1
        assert updater._compare_versions("v1.0.0", "1.0.0") == 0
        assert updater._compare_versions("1.0.0-beta", "1.0.0") == 0

    def test_check_for_update_skipped(self):
        """Test check_for_update when skip_check is True."""
        updater = SelfUpdater(current_version="1.0.0", skip_check=True)
        result, release = updater.check_for_update()

        assert result is False
        assert release is None

    @patch("obtainhub.core.self_updater.urlopen")
    def test_fetch_latest_release(self, mock_urlopen):
        """Test fetching latest release from GitHub API."""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "tag_name": "v2.0.0",
            "name": "Release 2.0.0",
            "body": "Release notes",
            "prerelease": False,
            "draft": False,
            "published_at": "2024-01-01T00:00:00Z",
            "html_url": "https://github.com/ObtainHub/ObtainHub/releases/tag/v2.0.0",
            "assets": [
                {"name": "obtainhub-2.0.0.msi", "browser_download_url": "https://example.com/obtainhub-2.0.0.msi"}
            ],
        }).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        updater = SelfUpdater(current_version="1.0.0")
        release = updater._fetch_latest_release()

        assert release.version == "2.0.0"
        assert release.name == "Release 2.0.0"
        assert release.installer_filename == "obtainhub-2.0.0.msi"

    @patch("obtainhub.core.self_updater.urlopen")
    def test_fetch_latest_release_404(self, mock_urlopen):
        """Test fetch latest release when repo not found."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://api.github.com/repos/ObtainHub/ObtainHub/releases/latest",
            404, "Not Found", {}, None
        )

        updater = SelfUpdater(current_version="1.0.0")

        with pytest.raises(NetworkError) as exc_info:
            updater._fetch_latest_release()
        assert "not found" in str(exc_info.value).lower()

    @patch("obtainhub.core.self_updater.urlopen")
    def test_fetch_latest_release_rate_limit(self, mock_urlopen):
        """Test fetch latest release when rate limited."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://api.github.com/repos/ObtainHub/ObtainHub/releases/latest",
            403, "Forbidden", {}, None
        )

        updater = SelfUpdater(current_version="1.0.0")

        with pytest.raises(NetworkError) as exc_info:
            updater._fetch_latest_release()
        assert "rate limit" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()

    @patch("obtainhub.core.self_updater.urlopen")
    def test_download_installer(self, mock_urlopen):
        """Test downloading installer."""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.headers = {"Content-Length": "1024"}
        mock_response.read.side_effect = [b"chunk1", b"chunk2", b""]
        mock_urlopen.return_value.__enter__.return_value = mock_response

        release = ReleaseInfo(
            version="2.0.0",
            name="Release 2.0.0",
            body="",
            prerelease=False,
            draft=False,
            published_at="2024-01-01T00:00:00Z",
            html_url="https://github.com/ObtainHub/ObtainHub/releases/tag/v2.0.0",
            assets=[{"name": "obtainhub-2.0.0.msi", "browser_download_url": "https://example.com/obtainhub-2.0.0.msi"}],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            dest_dir = Path(tmpdir)
            updater = SelfUpdater(current_version="1.0.0")
            installer_path = updater.download_installer(release, dest_dir)

            assert installer_path.exists()
            assert installer_path.name == "obtainhub-2.0.0.msi"

    @patch("obtainhub.core.self_updater.urlopen")
    def test_download_installer_failure(self, mock_urlopen):
        """Test download installer failure handling."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Connection failed")

        release = ReleaseInfo(
            version="2.0.0",
            name="Release 2.0.0",
            body="",
            prerelease=False,
            draft=False,
            published_at="2024-01-01T00:00:00Z",
            html_url="https://github.com/ObtainHub/ObtainHub/releases/tag/v2.0.0",
            assets=[{"name": "obtainhub-2.0.0.msi", "browser_download_url": "https://example.com/obtainhub-2.0.0.msi"}],
        )

        updater = SelfUpdater(current_version="1.0.0")

        with pytest.raises(SelfUpdateFailedError) as exc_info:
            updater.download_installer(release, Path("/tmp"))
        assert "Download failed" in str(exc_info.value)

    def test_download_installer_no_asset(self):
        """Test download installer when no installer asset."""
        release = ReleaseInfo(
            version="2.0.0",
            name="Release 2.0.0",
            body="",
            prerelease=False,
            draft=False,
            published_at="2024-01-01T00:00:00Z",
            html_url="https://github.com/ObtainHub/ObtainHub/releases/tag/v2.0.0",
            assets=[{"name": "source.tar.gz", "browser_download_url": "https://example.com/source.tar.gz"}],
        )

        updater = SelfUpdater(current_version="1.0.0")

        with pytest.raises(SelfUpdateFailedError) as exc_info:
            updater.download_installer(release, Path("/tmp"))
        assert "No Windows installer found" in str(exc_info.value)

    @patch("obtainhub.core.self_updater.subprocess.Popen")
    def test_execute_installer_msi(self, mock_popen):
        """Test executing MSI installer."""
        mock_process = Mock()
        mock_popen.return_value = mock_process

        updater = SelfUpdater(current_version="1.0.0")

        with tempfile.NamedTemporaryFile(suffix=".msi", delete=False) as f:
            installer_path = Path(f.name)

        try:
            result = updater.execute_installer(installer_path)
            assert result is True
            mock_popen.assert_called_once()
            call_args = mock_popen.call_args[0][0]
            assert call_args[0] == "msiexec.exe"
            assert "/i" in call_args
            assert "/quiet" in call_args
            assert "/norestart" in call_args
        finally:
            installer_path.unlink(missing_ok=True)

    @patch("obtainhub.core.self_updater.subprocess.Popen")
    def test_execute_installer_exe(self, mock_popen):
        """Test executing EXE installer."""
        mock_process = Mock()
        mock_popen.return_value = mock_process

        updater = SelfUpdater(current_version="1.0.0")

        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            installer_path = Path(f.name)

        try:
            result = updater.execute_installer(installer_path)
            assert result is True
            mock_popen.assert_called_once()
            call_args = mock_popen.call_args[0][0]
            assert "/verysilent" in call_args
            assert "/norestart" in call_args
        finally:
            installer_path.unlink(missing_ok=True)

    def test_execute_installer_not_found(self):
        """Test executing installer when file doesn't exist."""
        updater = SelfUpdater(current_version="1.0.0")

        result = updater.execute_installer(Path("/nonexistent/installer.msi"))
        assert result is False

    def test_execute_installer_unsupported_type(self):
        """Test executing installer with unsupported extension."""
        updater = SelfUpdater(current_version="1.0.0")

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            installer_path = Path(f.name)

        try:
            result = updater.execute_installer(installer_path)
            assert result is False
        finally:
            installer_path.unlink(missing_ok=True)

    @patch("obtainhub.core.self_updater.SelfUpdater.check_for_update")
    @patch("obtainhub.core.self_updater.SelfUpdater.download_installer")
    @patch("obtainhub.core.self_updater.SelfUpdater.execute_installer")
    def test_perform_self_update_success(self, mock_execute, mock_download, mock_check):
        """Test successful self-update flow."""
        mock_check.return_value = (True, Mock(
            version="2.0.0",
            name="Release 2.0.0",
            body="Release notes",
            installer_download_url="https://example.com/installer.msi",
            installer_filename="installer.msi",
        ))
        mock_download.return_value = Path("/tmp/installer.msi")
        mock_execute.return_value = True

        updater = SelfUpdater(current_version="1.0.0")
        result = updater.perform_self_update()

        assert result is True
        mock_check.assert_called_once()
        mock_download.assert_called_once()
        mock_execute.assert_called_once()

    @patch("obtainhub.core.self_updater.SelfUpdater.check_for_update")
    def test_perform_self_update_not_needed(self, mock_check):
        """Test self-update when no update available."""
        mock_check.return_value = (False, None)

        updater = SelfUpdater(current_version="1.0.0")
        result = updater.perform_self_update()

        assert result is False

    @patch("obtainhub.core.self_updater.SelfUpdater.check_for_update")
    @patch("obtainhub.core.self_updater.SelfUpdater.download_installer")
    def test_perform_self_update_download_fails(self, mock_download, mock_check):
        """Test self-update when download fails."""
        mock_check.return_value = (True, Mock())
        mock_download.side_effect = SelfUpdateFailedError("Download failed")

        updater = SelfUpdater(current_version="1.0.0")
        result = updater.perform_self_update()

        assert result is False

    @patch("obtainhub.core.self_updater.SelfUpdater.check_for_update")
    @patch("obtainhub.core.self_updater.SelfUpdater.download_installer")
    @patch("obtainhub.core.self_updater.SelfUpdater.execute_installer")
    def test_perform_self_update_execute_fails(self, mock_execute, mock_download, mock_check):
        """Test self-update when installer execution fails."""
        mock_check.return_value = (True, Mock())
        mock_download.return_value = Path("/tmp/installer.msi")
        mock_execute.return_value = False

        updater = SelfUpdater(current_version="1.0.0")
        result = updater.perform_self_update()

        assert result is False


class TestCheckAndUpdate:
    """Tests for check_and_update convenience function."""

    @patch("obtainhub.core.self_updater.SelfUpdater.perform_self_update")
    @patch("obtainhub.core.self_updater.get_config_manager")
    def test_check_and_update_skip_from_config(self, mock_get_config, mock_perform):
        """Test check_and_update respects config skip_self_update."""
        mock_perform.return_value = True
        config = Mock()
        config.config = Mock()
        config.config.skip_self_update = True
        mock_get_config.return_value = config

        result = check_and_update(
            skip_check=False,
        )

        assert result is False
        mock_perform.assert_not_called()

    @patch("obtainhub.core.self_updater.SelfUpdater.perform_self_update")
    def test_check_and_update_explicit_skip(self, mock_perform):
        """Test check_and_update respects explicit skip_check."""
        mock_perform.return_value = True

        result = check_and_update(
            skip_check=True,
        )

        assert result is False
        mock_perform.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])