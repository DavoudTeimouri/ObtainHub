"""GitHub REST API client for ObtainHub."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ReleaseInfo:
    """GitHub Release information."""

    tag_name: str
    name: str
    body: str
    published_at: str
    prerelease: bool
    draft: bool
    assets: List[dict]
    html_url: str


class GitHubClient:
    """GitHub REST API client with token auth and rate-limit handling."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None, timeout: int = 30):
        """
        Initialize GitHub client.

        Args:
            token: GitHub personal access token (optional)
            timeout: Request timeout in seconds
        """
        self.token = token
        self.timeout = timeout
        self.rate_limit_remaining = 5000
        self.rate_limit_reset = 0

    def _make_request(self, url: str) -> dict:
        """
        Make HTTP request to GitHub API.

        Args:
            url: Full API URL

        Returns:
            Parsed JSON response

        Raises:
            urllib.error.HTTPError: On HTTP errors
            ValueError: On rate limit exceeded
        """
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ObtainHub/0.1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                self.rate_limit_remaining = int(response.headers.get("X-RateLimit-Remaining", "5000"))
                self.rate_limit_reset = int(response.headers.get("X-RateLimit-Reset", "0"))
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 403 and "rate limit" in e.read().decode("utf-8", errors="ignore").lower():
                raise ValueError("GitHub API rate limit exceeded")
            raise
        except urllib.error.URLError as e:
            raise ValueError(f"Network error: {e}")

    def _wait_for_rate_limit(self):
        """Wait if rate limit is exhausted."""
        if self.rate_limit_remaining <= 0 and self.rate_limit_reset > 0:
            wait_time = max(0, self.rate_limit_reset - int(time.time())) + 1
            if wait_time > 0:
                time.sleep(wait_time)

    def _parse_release(self, data: dict) -> ReleaseInfo:
        """Parse release data from GitHub API."""
        return ReleaseInfo(
            tag_name=data.get("tag_name", ""),
            name=data.get("name", ""),
            body=data.get("body", "") or "",
            published_at=data.get("published_at", ""),
            prerelease=data.get("prerelease", False),
            draft=data.get("draft", False),
            assets=data.get("assets", []),
            html_url=data.get("html_url", ""),
        )

    def get_latest_release(self, owner: str, repo: str, include_prerelease: bool = False) -> ReleaseInfo:
        """
        Get the latest release for a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            include_prerelease: If True, include prereleases in search

        Returns:
            ReleaseInfo object with release details

        Raises:
            ValueError: If no releases found
        """
        self._wait_for_rate_limit()

        url = f"{self.BASE_URL}/repos/{owner}/{repo}/releases"

        if not include_prerelease:
            url += "?per_page=10"

        data = self._make_request(url)

        if not isinstance(data, list) or len(data) == 0:
            raise ValueError(f"No releases found for {owner}/{repo}")

        if include_prerelease:
            return self._parse_release(data[0])

        # Find first non-prerelease
        for release in data:
            if not release.get("prerelease", False):
                return self._parse_release(release)

        raise ValueError(f"No stable releases found for {owner}/{repo}")

    def get_release_by_tag(self, owner: str, repo: str, tag: str) -> ReleaseInfo:
        """
        Get a specific release by tag name.

        Args:
            owner: Repository owner
            repo: Repository name
            tag: Release tag name

        Returns:
            ReleaseInfo object
        """
        self._wait_for_rate_limit()

        url = f"{self.BASE_URL}/repos/{owner}/{repo}/releases/tags/{tag}"
        data = self._make_request(url)
        return self._parse_release(data)

    def get_all_releases(self, owner: str, repo: str) -> List[ReleaseInfo]:
        """
        Get all releases for a repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            List of ReleaseInfo objects
        """
        self._wait_for_rate_limit()

        url = f"{self.BASE_URL}/repos/{owner}/{repo}/releases"
        data = self._make_request(url)

        if not isinstance(data, list):
            raise ValueError(f"Unexpected response format for {owner}/{repo}")

        return [self._parse_release(r) for r in data]

    def get_asset_download_url(self, release: ReleaseInfo, asset_name: str) -> Optional[str]:
        """
        Get download URL for a specific asset in a release.

        Args:
            release: ReleaseInfo object
            asset_name: Exact asset filename

        Returns:
            Download URL or None if not found
        """
        for asset in release.assets:
            if asset.get("name") == asset_name:
                return asset.get("browser_download_url")
        return None

    def search_repositories(self, query: str, limit: int = 10) -> List[dict]:
        """
        Search GitHub repositories.

        Args:
            query: Search query
            limit: Maximum results to return

        Returns:
            List of repository dicts
        """
        self._wait_for_rate_limit()

        url = f"{self.BASE_URL}/search/repositories?q={urllib.parse.quote(query)}&per_page={limit}&sort=stars&order=desc"
        data = self._make_request(url)

        if not isinstance(data, dict) or "items" not in data:
            return []

        return data["items"]