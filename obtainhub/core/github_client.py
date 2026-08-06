"""GitHub API client for ObtainHub."""

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib import request, error

from obtainhub.core.logger import get_logger

logger = get_logger(__name__)

GITHUB_API_URL = "https://api.github.com"


@dataclass
class ReleaseInfo:
    """Information about a GitHub release."""
    tag_name: str
    name: str
    body: str
    published_at: str
    prerelease: bool
    draft: bool
    assets: List[Dict[str, Any]]
    html_url: str


class GitHubClient:
    """Client for interacting with GitHub REST API."""

    def __init__(self, token: Optional[str] = None):
        # Check environment variables for token
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("OBTAINHUB_TOKEN")
        self.session = request.build_opener()
        self._rate_limit_remaining = 60
        self._rate_limit_reset = 0

        if self.token:
            self.session.addheaders = [('Authorization', f'Bearer {self.token}')]
        self.session.addheaders = [
            ('Accept', 'application/vnd.github.v3+json'),
            ('User-Agent', 'ObtainHub/0.1.0')
        ]
        if self.token:
            self.session.addheaders.append(('Authorization', f'Bearer {self.token}'))

    def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make HTTP request to GitHub API with rate limit handling."""
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"

        req = request.Request(url)

        # Check rate limit before making request
        if self._rate_limit_remaining <= 1 and time.time() < self._rate_limit_reset:
            wait_time = self._rate_limit_reset - time.time() + 1
            logger.warning(f"Rate limit near exhaustion, waiting {wait_time:.0f}s")
            time.sleep(wait_time)

        try:
            with self.session.open(req, timeout=30) as response:
                # Update rate limit info from headers
                self._rate_limit_remaining = int(response.headers.get('x-ratelimit-remaining', 60))
                self._rate_limit_reset = int(response.headers.get('x-ratelimit-reset', time.time() + 3600))

                if response.status == 403 and self._rate_limit_remaining == 0:
                    raise error.HTTPError(url, 403, "Rate limit exceeded", response.headers, None)

                data = json.load(response)
                return data
        except error.HTTPError as e:
            # Update rate limit from error response headers
            if hasattr(e, 'headers') and e.headers:
                self._rate_limit_remaining = int(e.headers.get('x-ratelimit-remaining', self._rate_limit_remaining))
                self._rate_limit_reset = int(e.headers.get('x-ratelimit-reset', self._rate_limit_reset))
            
            if e.code == 403 and self._rate_limit_remaining == 0:
                reset_time = int(e.headers.get('x-ratelimit-reset', time.time() + 3600))
                wait_time = max(0, reset_time - time.time() + 1)
                logger.warning(f"GitHub API rate limit exceeded. Waiting {wait_time:.0f}s for reset.")
                time.sleep(wait_time)
                # Retry once
                return self._make_request(url, params)
            elif e.code == 403:
                logger.error("GitHub API rate limit exceeded. Set a GITHUB_TOKEN environment variable to increase limit from 60 to 5000 requests/hour.")
                return None
            elif e.code == 404:
                return None
            else:
                logger.error(f"GitHub API error: {e.code} {e.reason}")
                return None
        except error.URLError as e:
            logger.error(f"Network error: {e.reason}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    def get_repo(self, owner: str, repo: str) -> Optional[Dict]:
        """Get repository information."""
        url = f"{GITHUB_API_URL}/repos/{owner}/{repo}"
        return self._make_request(url)

    def get_releases(self, owner: str, repo: str, per_page: int = 10) -> List[Dict]:
        """Get all releases for a repository."""
        url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/releases"
        params = {"per_page": per_page}
        data = self._make_request(url, params)
        return data if isinstance(data, list) else []

    def get_latest_release(self, owner: str, repo: str, include_prerelease: bool = False) -> Optional[ReleaseInfo]:
        """Get the latest release for a repository as ReleaseInfo."""
        url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/releases"
        params = {"per_page": 10}
        data = self._make_request(url, params)
        if not data or not isinstance(data, list):
            return None

        for release in data:
            if release.get('draft'):
                continue
            if not include_prerelease and release.get('prerelease'):
                continue
            return self._parse_release(release)
        return None

    def get_release_by_tag(self, owner: str, repo: str, tag: str) -> Optional[Dict]:
        """Get a specific release by tag name."""
        url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/releases/tags/{tag}"
        return self._make_request(url)

    def _parse_release(self, release_data: Dict) -> ReleaseInfo:
        """Parse raw release data into ReleaseInfo dataclass."""
        assets = []
        for asset_data in release_data.get('assets', []):
            assets.append({
                'name': asset_data.get('name', ''),
                'browser_download_url': asset_data.get('browser_download_url', ''),
                'size': asset_data.get('size', 0),
            })

        return ReleaseInfo(
            tag_name=release_data.get('tag_name', ''),
            name=release_data.get('name', ''),
            body=release_data.get('body', ''),
            published_at=release_data.get('published_at', ''),
            prerelease=release_data.get('prerelease', False),
            draft=release_data.get('draft', False),
            assets=assets,
            html_url=release_data.get('html_url', ''),
        )

    def search_repositories(
        self,
        query: str,
        limit: int = 10,
        min_stars: int = 0,
        ignore_case: bool = True,
        active_only: bool = True
    ) -> List[Dict]:
        """Search GitHub repositories."""
        # Build search query
        search_query = query
        if min_stars > 0:
            search_query += f" stars:>={min_stars}"
        if active_only:
            search_query += " archived:false"

        url = f"{GITHUB_API_URL}/search/repositories"
        params = {
            "q": search_query,
            "sort": "stars",
            "order": "desc",
            "per_page": min(limit, 100)
        }

        data = self._make_request(url, params)
        if not data or "items" not in data:
            return []

        repos = data["items"]

        # Apply case-insensitive filtering if needed
        if ignore_case:
            query_lower = query.lower()
            repos = [r for r in repos if query_lower in r.get("name", "").lower() or
                     query_lower in r.get("description", "").lower()]

        return repos[:limit]

    def get_latest_release_parsed(self, owner: str, repo: str, include_prerelease: bool = False) -> Optional[ReleaseInfo]:
        """Get the latest release as ReleaseInfo object."""
        release = self.get_latest_release(owner, repo, include_prerelease)
        if release:
            return self._parse_release(release)
        return None

    def get_release_by_tag_parsed(self, owner: str, repo: str, tag: str) -> Optional[ReleaseInfo]:
        """Get a specific release by tag as ReleaseInfo object."""
        release = self.get_release_by_tag(owner, repo, tag)
        if release:
            return self._parse_release(release)
        return None

    def get_all_releases_parsed(self, owner: str, repo: str) -> List[ReleaseInfo]:
        """Get all releases as ReleaseInfo objects."""
        releases = self.get_releases(owner, repo)
        return [self._parse_release(r) for r in releases]

    def get_rate_limit_info(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        return {
            "remaining": self._rate_limit_remaining,
            "reset": self._rate_limit_reset,
            "has_token": bool(self.token)
        }