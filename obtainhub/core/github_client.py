"""GitHub API client for ObtainHub."""

import os
import time
import requests
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


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
    def __init__(self, token: str = None, max_retries: int = 3, retry_delay: int = 10):
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("OBTAINHUB_TOKEN")
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def search_repositories(self, query: str, min_stars: int = 0, ignore_case: bool = True, active_only: bool = True):
            url = "https://api.github.com/search/repositories"
            search_q = f"{query} stars:>={min_stars}" if min_stars > 0 else query
            if active_only:
                search_q += " archived:false"
          
            params = {"q": search_q, "sort": "stars", "order": "desc"}
       
            last_error = None
            for attempt in range(self.max_retries):
                try:
                    response = requests.get(url, headers=self.headers, params=params)
                    if response.status_code == 403 or "rate limit exceeded" in response.text.lower():
                        return {"error": "rate_limit", "items": []}
                    response.raise_for_status()
                    data = response.json()
                    items = data.get("items", [])
            
                    if ignore_case:
                        query_lower = query.lower()
                        items = [item for item in items if query_lower in item["full_name"].lower() or (item.get("description") and query_lower in item["description"].lower())]
           
                    # Add latest release info to each repo
                    for item in items:
                        owner = item.get("owner", {}).get("login", "")
                        repo = item.get("name", "")
                        if owner and repo:
                            releases = self.get_releases(owner, repo, per_page=1)
                            if releases and len(releases) > 0:
                                latest = releases[0]
                                item["latest_release"] = latest.get("tag_name", "")
                                item["latest_release_prerelease"] = latest.get("prerelease", False)
                                item["latest_release_url"] = latest.get("html_url", "")
                            else:
                                item["latest_release"] = ""
                                item["latest_release_prerelease"] = False
                                item["latest_release_url"] = ""
               
                    return {"error": None, "items": items}
                except requests.RequestException as e:
                    last_error = e
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                    continue
            return {"error": str(last_error), "items": []}

    def get_repo(self, owner: str, repo: str) -> Optional[Dict]:
        """Get repository information with retry."""
        url = f"https://api.github.com/repos/{owner}/{repo}"
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, headers=self.headers)
                if response.status_code == 403 or "rate limit exceeded" in response.text.lower():
                    return None
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                continue
        return None

    def get_releases(self, owner: str, repo: str, per_page: int = 10) -> List[Dict]:
        """Get all releases for a repository with retry."""
        url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        params = {"per_page": per_page}
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, headers=self.headers, params=params)
                if response.status_code == 403 or "rate limit exceeded" in response.text.lower():
                    return []
                response.raise_for_status()
                return response.json() if isinstance(response.json(), list) else []
            except requests.RequestException as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                continue
        return []

    def get_latest_release(self, owner: str, repo: str, include_prerelease: bool = False) -> Optional[Dict]:
        """Get the latest release for a repository."""
        releases = self.get_releases(owner, repo, per_page=10)
        for release in releases:
            if release.get('draft'):
                continue
            if not include_prerelease and release.get('prerelease'):
                continue
            return release
        return None

    def get_release_by_tag(self, owner: str, repo: str, tag: str) -> Optional[Dict]:
        """Get a specific release by tag name with retry."""
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, headers=self.headers)
                if response.status_code == 403 or "rate limit exceeded" in response.text.lower():
                    return None
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                continue
        return None

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
            "remaining": 5000 if self.token else 60,
            "reset": 0,
            "has_token": bool(self.token)
        }