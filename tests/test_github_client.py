"""Tests for GitHubClient."""

import json
from unittest.mock import MagicMock, patch

import pytest

from obtainhub.core.github_client import GitHubClient, ReleaseInfo


class TestGitHubClient:
    """Test GitHub REST API client."""

    @pytest.fixture
    def sample_release_data(self):
        """Sample release data from GitHub API."""
        return {
            "tag_name": "v1.2.3",
            "name": "Release 1.2.3",
            "body": "Release notes here",
            "published_at": "2024-01-15T10:30:00Z",
            "prerelease": False,
            "draft": False,
            "assets": [
                {
                    "name": "app-x64.msi",
                    "browser_download_url": "https://github.com/owner/repo/releases/download/v1.2.3/app-x64.msi",
                    "size": 1024000,
                },
                {
                    "name": "app-Setup.exe",
                    "browser_download_url": "https://github.com/owner/repo/releases/download/v1.2.3/app-Setup.exe",
                    "size": 2048000,
                },
            ],
            "html_url": "https://github.com/owner/repo/releases/tag/v1.2.3"
        }

    def _make_client_with_mock(self):
        """Create a client with mocked session."""
        client = GitHubClient.__new__(GitHubClient)
        client.token = None
        client._rate_limit_remaining = 5000
        client._rate_limit_reset = 9999999999
        client.session = MagicMock()
        return client

    @patch("obtainhub.core.github_client.request.build_opener")
    def test_get_latest_release_stable(self, mock_build_opener, sample_release_data):
        """Test fetching latest stable release."""
        client = self._make_client_with_mock()
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([sample_release_data]).encode()
        mock_response.headers = {"x-ratelimit-remaining": "5000", "x-ratelimit-reset": "9999999999"}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        client.session.open.return_value = mock_response

        release = client.get_latest_release("owner", "repo")

        assert isinstance(release, ReleaseInfo)
        assert release.tag_name == "v1.2.3"
        assert release.name == "Release 1.2.3"
        assert release.body == "Release notes here"
        assert release.prerelease is False

    @patch("obtainhub.core.github_client.request.build_opener")
    def test_get_latest_release_prerelease(self, mock_build_opener, sample_release_data):
        """Test fetching latest release including prerelease."""
        client = self._make_client_with_mock()
        
        prerelease_data = {**sample_release_data, "tag_name": "v2.0.0-beta", "prerelease": True}
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([prerelease_data]).encode()
        mock_response.headers = {"x-ratelimit-remaining": "5000", "x-ratelimit-reset": "9999999999"}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        client.session.open.return_value = mock_response

        release = client.get_latest_release("owner", "repo", include_prerelease=True)

        assert release.tag_name == "v2.0.0-beta"
        assert release.prerelease is True

    @patch("obtainhub.core.github_client.request.build_opener")
    def test_get_latest_release_no_releases(self, mock_build_opener):
        """Test when no releases found."""
        client = self._make_client_with_mock()
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([]).encode()
        mock_response.headers = {"x-ratelimit-remaining": "5000", "x-ratelimit-reset": "9999999999"}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        client.session.open.return_value = mock_response

        release = client.get_latest_release("owner", "repo")
        assert release is None

    @patch("obtainhub.core.github_client.request.build_opener")
    def test_get_release_by_tag(self, mock_build_opener, sample_release_data):
        """Test fetching release by tag."""
        client = self._make_client_with_mock()
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(sample_release_data).encode()
        mock_response.headers = {"x-ratelimit-remaining": "5000", "x-ratelimit-reset": "9999999999"}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        client.session.open.return_value = mock_response

        release = client.get_release_by_tag_parsed("owner", "repo", "v1.2.3")

        assert isinstance(release, ReleaseInfo)
        assert release.tag_name == "v1.2.3"

    @patch("obtainhub.core.github_client.request.build_opener")
    def test_get_all_releases(self, mock_build_opener, sample_release_data):
        """Test fetching all releases."""
        client = self._make_client_with_mock()
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([sample_release_data]).encode()
        mock_response.headers = {"x-ratelimit-remaining": "5000", "x-ratelimit-reset": "9999999999"}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        client.session.open.return_value = mock_response

        releases = client.get_all_releases_parsed("owner", "repo")

        assert isinstance(releases, list)
        assert len(releases) == 1
        assert releases[0].tag_name == "v1.2.3"

    def test_get_rate_limit_info(self):
        """Test rate limit info."""
        client = self._make_client_with_mock()
        info = client.get_rate_limit_info()
        assert "remaining" in info
        assert "reset" in info
        assert "has_token" in info


class TestReleaseInfo:
    """Test ReleaseInfo dataclass."""

    def test_release_info_creation(self):
        """Test creating ReleaseInfo."""
        release = ReleaseInfo(
            tag_name="v1.0.0",
            name="Test Release",
            body="Test body",
            published_at="2024-01-01T00:00:00Z",
            prerelease=False,
            draft=False,
            assets=[],
            html_url="https://github.com/owner/repo/releases/tag/v1.0.0",
        )

        assert release.tag_name == "v1.0.0"
        assert release.name == "Test Release"
        assert release.prerelease is False