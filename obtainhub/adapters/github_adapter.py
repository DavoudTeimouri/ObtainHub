"""GitHub adapter implementing RepositorySource port."""

import os
import requests
from typing import Optional

from obtainhub.ports import RepositorySource, ReleaseInfo, SearchResult, RateLimitInfo


class GitHubAdapter(RepositorySource):
    """GitHub API implementation of RepositorySource."""

    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _request(self, method: str, path: str, **kwargs) -> Optional[requests.Response]:
        """Make an HTTP request to GitHub API."""
        url = f"{self.base_url}{path}"
        try:
            resp = requests.request(method, url, headers=self.headers, timeout=30, **kwargs)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            return None

    def _parse_release(self, data: dict) -> ReleaseInfo:
        """Parse GitHub release JSON into ReleaseInfo."""
        assets = []
        for asset in data.get("assets", []):
            assets.append({
                "name": asset.get("name", ""),
                "url": asset.get("browser_download_url", ""),
                "size": asset.get("size", 0),
                "sha256": "",  # GitHub doesn't provide SHA256 in release API
            })
        return ReleaseInfo(
            tag_name=data.get("tag_name", ""),
            version=data.get("tag_name", "").lstrip("v"),
            html_url=data.get("html_url", ""),
            body=data.get("body", "") or "",
            prerelease=data.get("prerelease", False),
            draft=data.get("draft", False),
            assets=assets,
            published_at=data.get("published_at", ""),
            checksums={},  # Would need separate API call
        )

    def get_latest_release(self, owner: str, repo: str, include_prerelease: bool = False) -> Optional[ReleaseInfo]:
        params = {"per_page": 10}
        resp = self._request("GET", f"/repos/{owner}/{repo}/releases", params=params)
        if not resp:
            return None
        releases = resp.json()
        if not releases:
            return None
        # Filter prereleases if not included
        for rel in releases:
            if include_prerelease or not rel.get("prerelease"):
                if not rel.get("draft"):
                    return self._parse_release(rel)
        return None

    def get_release_by_tag(self, owner: str, repo: str, tag: str) -> Optional[ReleaseInfo]:
        resp = self._request("GET", f"/repos/{owner}/{repo}/releases/tags/{tag}")
        if not resp:
            return None
        return self._parse_release(resp.json())

    def get_releases(self, owner: str, repo: str, per_page: int = 30) -> list[ReleaseInfo]:
        params = {"per_page": per_page}
        resp = self._request("GET", f"/repos/{owner}/{repo}/releases", params=params)
        if not resp:
            return []
        return [self._parse_release(r) for r in resp.json()]

    def search_repositories(
        self,
        query: str,
        min_stars: int = 0,
        ignore_case: bool = False,
        active_only: bool = True,
        per_page: int = 30,
    ) -> SearchResult:
        q = query
        if min_stars > 0:
            q += f" stars:>={min_stars}"
        if active_only:
            q += " archived:false"
        params = {"q": q, "per_page": per_page, "sort": "stars", "order": "desc"}
        resp = self._request("GET", "/search/repositories", params=params)
        if not resp:
            return SearchResult(items=[], error="Request failed")
        data = resp.json()
        return SearchResult(items=data.get("items", []))

    def get_repo_status(self, owner: str, repo: str) -> Optional[dict]:
        resp = self._request("GET", f"/repos/{owner}/{repo}")
        if not resp:
            return None
        data = resp.json()
        return {
            "archived": data.get("archived", False),
            "inactive": False,  # Would need additional check
            "last_push_days": None,
        }

    def get_rate_limit(self) -> RateLimitInfo:
        resp = self._request("GET", "/rate_limit")
        if not resp:
            return RateLimitInfo(limit=0, remaining=0, reset_at=0)
        data = resp.json().get("rate", {})
        return RateLimitInfo(
            limit=data.get("limit", 0),
            remaining=data.get("remaining", 0),
            reset_at=data.get("reset", 0),
        )