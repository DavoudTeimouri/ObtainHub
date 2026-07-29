"""Tests for GitHub API client."""

import json
import pytest
from unittest.mock import patch, MagicMock, mock_open
from urllib.error import HTTPError, URLError

from obtainhub.core.github_client import (
    GitHubClient,
    ReleaseInfo,
    ReleaseAsset,
)


class TestGitHubClient:
    """Tests for GitHubClient class."""

    @pytest.fixture
    def client(self):
        """Create a GitHubClient instance."""
        return GitHubClient(token="test-token", timeout=10)

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
            "html_url": "https://github.com/owner/repo/releases/tag/v1.2.3",
            "assets": [
                {
                    "name": "app-1.2.3-x64.msi",
                    "browser_download_url": "https://github.com/owner/repo/releases/download/v1.2.3/app-1.2.3-x64.msi",
                    "size": 10485760,
                    "content_type": "application/octet-stream",
                },
                {
                    "name": "app-1.2.3-Setup.exe",
                    "browser_download_url": "https://github.com/owner/repo/releases/download/v1.2.3/app-1.2.3-Setup.exe",
                    "size": 12582912,
                    "content_type": "application/octet-stream",
                },
                {
                    "name": "app-1.2.3-win32.zip",
                    "browser_download_url": "https://github.com/owner/repo/releases/download/v1.2.3/app-1.2.3-win32.zip",
                    "size": 8388608,
                    "content_type": "application/zip",
                },
                {
                    "name": "app-1.2.3.sha256",
                    "browser_download_url": "https://github.com/owner/repo/releases/download/v1.2.3/app-1.2.3.sha256",
                    "size": 64,
                    "content_type": "text/plain",
                },
            ],
        }

    def test_init_with_token(self):
        """Test client initialization with token."""
        client = GitHubClient(token="my-token")
        assert client.token == "my-token"
        assert client._headers["Authorization"] == "token my-token"

    def test_init_with_env_token(self, monkeypatch):
        """Test client initialization with GITHUB_TOKEN env var."""
        monkeypatch.setenv("GITHUB_TOKEN", "env-token")
        client = GitHubClient()
        assert client.token == "env-token"

    def test_init_without_token(self, monkeypatch):
        """Test client initialization without token."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        client = GitHubClient()
        assert client.token is None
        assert "Authorization" not in client._headers

    @patch('urllib.request.urlopen')
    def test_get_latest_release_stable(self, mock_urlopen, client, sample_release_data):
        """Test fetching latest stable release."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(sample_release_data).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        mock_urlopen.return_value = mock_response

        release = client.get_latest_release("owner", "repo")

        assert isinstance(release, ReleaseInfo)
        assert release.tag_name == "v1.2.3"
        assert release.name == "Release 1.2.3"
        assert release.prerelease is False
        assert len(release.assets) == 4
        assert release.assets[0].name == "app-1.2.3-x64.msi"
        assert release.assets[0].size == 10485760

    @patch('urllib.request.urlopen')
    def test_get_latest_release_prerelease_allowed(self, mock_urlopen, client, sample_release_data):
        """Test fetching latest release including prereleases."""
        prerelease_data = sample_release_data.copy()
        prerelease_data["prerelease"] = True
        prerelease_data["tag_name"] = "v2.0.0-beta"
        
        # Return list of releases
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([prerelease_data, sample_release_data]).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        mock_urlopen.return_value = mock_response

        release = client.get_latest_release("owner", "repo", include_prerelease=True)

        assert release.tag_name == "v2.0.0-beta"
        assert release.prerelease is True

    @patch('urllib.request.urlopen')
    def test_get_latest_release_prerelease_excluded(self, mock_urlopen, client, sample_release_data):
        """Test fetching latest stable release when prereleases exist."""
        prerelease_data = sample_release_data.copy()
        prerelease_data["prerelease"] = True
        prerelease_data["tag_name"] = "v2.0.0-beta"
        
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([prerelease_data, sample_release_data]).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        mock_urlopen.return_value = mock_response

        release = client.get_latest_release("owner", "repo", include_prerelease=False)

        assert release.tag_name == "v1.2.3"
        assert release.prerelease is False

    @patch('urllib.request.urlopen')
    def test_get_latest_release_404(self, mock_urlopen, client):
        """Test 404 handling."""
        error = HTTPError("url", 404, "Not Found", {}, None)
        mock_urlopen.side_effect = error

        with pytest.raises(ValueError, match="not found"):
            client.get_latest_release("owner", "repo")

    @patch('urllib.request.urlopen')
    def test_get_latest_release_rate_limit(self, mock_urlopen, client):
        """Test rate limit handling."""
        headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1234567890"}
        error = HTTPError("url", 403, "Forbidden", headers, None)
        mock_urlopen.side_effect = error

        with pytest.raises(RuntimeError, match="rate limit"):
            client.get_latest_release("owner", "repo")

    @patch('urllib.request.urlopen')
    def test_get_latest_release_unauthorized(self, mock_urlopen, client):
        """Test invalid token handling."""
        error = HTTPError("url", 401, "Unauthorized", {}, None)
        mock_urlopen.side_effect = error

        with pytest.raises(RuntimeError, match="Invalid GitHub token"):
            client.get_latest_release("owner", "repo")

    @patch('urllib.request.urlopen')
    def test_get_latest_release_network_error(self, mock_urlopen, client):
        """Test network error handling."""
        error = URLError("Connection refused")
        mock_urlopen.side_effect = error

        with pytest.raises(RuntimeError, match="Network error"):
            client.get_latest_release("owner", "repo")

    @patch('urllib.request.urlopen')
    def test_get_latest_release_no_releases(self, mock_urlopen, client):
        """Test empty releases list."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([]).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        mock_urlopen.return_value = mock_response

        with pytest.raises(ValueError, match="No releases found"):
            client.get_latest_release("owner", "repo")

    @patch('urllib.request.urlopen')
    def test_get_release_by_tag(self, mock_urlopen, client, sample_release_data):
        """Test fetching release by tag."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(sample_release_data).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)
        mock_urlopen.return_value = mock_response

        release = client.get_release_by_tag("owner", "repo", "v1.2.3")

        assert release.tag_name == "v1.2.3"
        assert len(release.assets) == 4


class TestReleaseInfo:
    """Tests for ReleaseInfo dataclass."""

    def test_release_info_creation(self):
        """Test ReleaseInfo creation."""
        assets = [
            ReleaseAsset("test.msi", "url1", 100, "type1"),
            ReleaseAsset("test.exe", "url2", 200, "type2"),
        ]
        release = ReleaseInfo(
            tag_name="v1.0.0",
            name="Test Release",
            body="Notes",
            published_at="2024-01-01",
            prerelease=False,
            draft=False,
            html_url="https://github.com/owner/repo/releases/tag/v1.0.0",
            assets=assets,
        )
        assert release.tag_name == "v1.0.0"
        assert len(release.assets) == 2


class TestReleaseAsset:
    """Tests for ReleaseAsset dataclass."""

    def test_release_asset_creation(self):
        """Test ReleaseAsset creation."""
        asset = ReleaseAsset(
            name="test.msi",
            download_url="https://example.com/test.msi",
            size=1024,
            content_type="application/octet-stream",
        )
        assert asset.name == "test.msi"
        assert asset.size == 1024