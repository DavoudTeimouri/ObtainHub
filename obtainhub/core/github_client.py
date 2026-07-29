"""GitHub API client for fetching release information."""

import os
import json
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path


logger = logging.getLogger(__name__)


@dataclass
class ReleaseAsset:
    """Represents a GitHub release asset."""
    name: str
    download_url: str
    size: int
    content_type: str


@dataclass
class ReleaseInfo:
    """Represents a GitHub release."""
    tag_name: str
    name: str
    body: str
    published_at: str
    prerelease: bool
    draft: bool
    html_url: str
    assets: List[ReleaseAsset]


class GitHubClient:
    """Client for interacting with GitHub REST API."""

    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: Optional[str] = None, timeout: int = 30):
        """
        Initialize GitHub client.
        
        Args:
            token: GitHub Personal Access Token (optional)
            timeout: Request timeout in seconds
        """
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.timeout = timeout
        self._headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ObtainHub/1.0",
        }
        if self.token:
            self._headers["Authorization"] = f"token {self.token}"

    def _make_request(self, url: str) -> dict:
        """Make HTTP request to GitHub API."""
        req = urllib.request.Request(url, headers=self._headers)
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = response.read().decode('utf-8')
                return json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ValueError(f"Repository or release not found: {url}")
            elif e.code == 403:
                # Check for rate limit
                remaining = e.headers.get("X-RateLimit-Remaining", "0")
                if remaining == "0":
                    reset_time = e.headers.get("X-RateLimit-Reset", "")
                    raise RuntimeError(f"GitHub API rate limit exceeded. Resets at {reset_time}")
                raise RuntimeError(f"GitHub API access forbidden: {e.reason}")
            elif e.code == 401:
                raise RuntimeError("Invalid GitHub token")
            else:
                raise RuntimeError(f"GitHub API error ({e.code}): {e.reason}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}")

    def get_latest_release(self, owner: str, repo: str, include_prerelease: bool = False) -> ReleaseInfo:
        """
        Get the latest release for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            include_prerelease: If True, include prereleases in search
            
        Returns:
            ReleaseInfo object with release details
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/releases"
        
        if not include_prerelease:
            url += "?per_page=10"  # Fetch a few to find latest stable
        
        data = self._make_request(url)
        
        if not isinstance(data, list) or len(data) == 0:
            raise ValueError(f"No releases found for {owner}/{repo}")
        
        # Find the appropriate release
        for release in data:
            if release.get("draft", False):
                continue
            if not include_prerelease and release.get("prerelease", False):
                continue
            
            # Found the latest matching release
            assets = []
            for asset in release.get("assets", []):
                assets.append(ReleaseAsset(
                    name=asset.get("name", ""),
                    download_url=asset.get("browser_download_url", ""),
                    size=asset.get("size", 0),
                    content_type=asset.get("content_type", ""),
                ))
            
            return ReleaseInfo(
                tag_name=release.get("tag_name", ""),
                name=release.get("name", "") or release.get("tag_name", ""),
                body=release.get("body", "") or "",
                published_at=release.get("published_at", ""),
                prerelease=release.get("prerelease", False),
                draft=release.get("draft", False),
                html_url=release.get("html_url", ""),
                assets=assets,
            )
        
        # If we get here, no suitable release was found
        raise ValueError(f"No suitable release found for {owner}/{repo} (prerelease={'allowed' if include_prerelease else 'excluded'})")

    def get_release_by_tag(self, owner: str, repo: str, tag: str) -> ReleaseInfo:
        """Get a specific release by tag name."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/releases/tags/{tag}"
        data = self._make_request(url)
        
        assets = []
        for asset in data.get("assets", []):
            assets.append(ReleaseAsset(
                name=asset.get("name", ""),
                download_url=asset.get("browser_download_url", ""),
                size=asset.get("size", 0),
                content_type=asset.get("content_type", ""),
            ))
        
        return ReleaseInfo(
            tag_name=data.get("tag_name", ""),
            name=data.get("name", "") or data.get("tag_name", ""),
            body=data.get("body", "") or "",
            published_at=data.get("published_at", ""),
            prerelease=data.get("prerelease", False),
            draft=data.get("draft", False),
            html_url=data.get("html_url", ""),
            assets=assets,
        )