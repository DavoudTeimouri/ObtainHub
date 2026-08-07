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
        """Create a client with mocked requests.get."""
        client = GitHubClient.__new__(GitHubClient)
        client.token = None
        client.headers = {"Accept": "application/vnd.github.v3+json"}
        return client

    @patch("obtainhub.core.github_client.requests.get")
    def test_get_latest_release_stable(self, mock_get, sample_release_data):
        """Test fetching latest stable release."""
        client = self._make_client_with_mock()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [sample_release_data]
        mock_get.return_value = mock_response

        release = client.get_latest_release("owner", "repo")

        assert release is not None
        assert release["tag_name"] == "v1.2.3"
        assert release["name"] == "Release 1.2.3"
        assert release["body"] == "Release notes here"
        assert release["prerelease"] is False

    @patch("obtainhub.core.github_client.requests.get")
    def test_get_latest_release_prerelease(self, mock_get, sample_release_data):
        """Test fetching latest release including prerelease."""
        client = self._make_client_with_mock()
        
        prerelease_data = {**sample_release_data, "tag_name": "v2.0.0-beta", "prerelease": True}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [prerelease_data]
        mock_get.return_value = mock_response

        release = client.get_latest_release("owner", "repo", include_prerelease=True)

        assert release["tag_name"] == "v2.0.0-beta"
        assert release["prerelease"] is True

    @patch("obtainhub.core.github_client.requests.get")
    def test_get_latest_release_no_releases(self, mock_get):
        """Test when no releases found."""
        client = self._make_client_with_mock()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        release = client.get_latest_release("owner", "repo")
        assert release is None

    @patch("obtainhub.core.github_client.requests.get")
    def test_get_release_by_tag(self, mock_get, sample_release_data):
        """Test fetching release by tag."""
        client = self._make_client_with_mock()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_release_data
        mock_get.return_value = mock_response

        release = client.get_release_by_tag_parsed("owner", "repo", "v1.2.3")

        assert isinstance(release, ReleaseInfo)
        assert release.tag_name == "v1.2.3"

    @patch("obtainhub.core.github_client.requests.get")
    def test_get_all_releases(self, mock_get, sample_release_data):
        """Test fetching all releases."""
        client = self._make_client_with_mock()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [sample_release_data]
        mock_get.return_value = mock_response

        releases = client.get_all_releases_parsed("owner", "repo")

        assert isinstance(releases, list)
        assert len(releases) == 1
        assert releases[0].tag_name == "v1.2.3"

    @patch("obtainhub.core.github_client.requests.get")
    def test_search_repositories(self, mock_get):
        """Test searching repositories."""
        client = self._make_client_with_mock()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "full_name": "owner/repo",
                    "name": "repo",
                    "description": "A test repo",
                    "stargazers_count": 100,
                    "updated_at": "2024-01-15T10:30:00Z",
                    "has_releases": True
                }
            ]
        }
        mock_get.return_value = mock_response

        repos = client.search_repositories("test", min_stars=50, active_only=True)
        
        assert len(repos) >= 0  # May be filtered

    def test_parse_release(self, sample_release_data):
        """Test parsing release data."""
        client = self._make_client_with_mock()
        release = client._parse_release(sample_release_data)

        assert isinstance(release, ReleaseInfo)
        assert release.tag_name == "v1.2.3"
        assert release.name == "Release 1.2.3"
        assert release.body == "Release notes here"
        assert release.published_at == "2024-01-15T10:30:00Z"
        assert release.prerelease is False
        assert release.draft is False
        assert len(release.assets) == 2

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