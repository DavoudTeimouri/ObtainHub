"""Resolve apps from custom manifest sources (non-GitHub installs/updates).

A *source* is either:
  * ``github``  - a GitHub repo URL/API; we read its releases and expose each
                  asset as an installable entry.
  * ``manifest`` - a JSON list of :class:`SourceAppEntry` dicts served over HTTP.

Both are normalized to :class:`SourceAppEntry` so install/update can treat them
uniformly.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import requests

from obtainhub.core.config import ConfigManager, ManifestSource
from obtainhub.core.logger import get_logger


logger = get_logger(__name__)


@dataclass
class SourceAppEntry:
    """A single installable asset served by a custom source."""
    name: str
    version: str
    url: str
    installer_type: str          # "exe_setup" | "msi" | "zip" | "exe_standalone"
    sha256: str = ""
    size: int = 0
    source_name: str = ""        # the configured source name
    repo_id: str = ""            # owner/repo for github-type sources


def _classify(name: str) -> str:
    n = (name or "").lower()
    if n.endswith(".msi"):
        return "msi"
    if n.endswith(".zip"):
        return "zip"
    if "setup" in n or "install" in n:
        return "exe_setup"
    if n.endswith(".exe"):
        return "exe_standalone"
    return "unknown"


def _github_releases_url(url: str) -> str:
    u = (url or "").rstrip("/")
    if "api.github.com" in u and u.endswith("/releases"):
        return u
    if "github.com" in u:
        u = u.replace("https://github.com/", "https://api.github.com/repos/")
        u = u.replace("http://github.com/", "https://api.github.com/repos/")
        if not u.endswith("/releases"):
            u += "/releases"
        return u
    if "/releases" not in u:
        return u + "/releases"
    return u


def fetch_source_entries(config) -> List[SourceAppEntry]:
    """Fetch and normalize entries from all enabled sources."""
    entries: List[SourceAppEntry] = []
    for src in [s for s in config.manifest_sources if s.enabled]:
        try:
            if src.type == "manifest":
                entries.extend(_fetch_manifest(src))
            else:
                entries.extend(_fetch_github(src))
        except Exception as e:
            logger.warning(f"Failed to read source '{src.name}': {e}")
    return entries


def _fetch_github(src: ManifestSource) -> List[SourceAppEntry]:
    url = _github_releases_url(src.url)
    resp = requests.get(
        url, headers={"Accept": "application/vnd.github.v3+json"}, timeout=30,
    )
    resp.raise_for_status()
    releases = resp.json()
    repo_id = ""
    if "github.com" in src.url:
        # derive owner/repo from the original (non-api) url
        parts = src.url.rstrip("/").split("/")
        if len(parts) >= 2:
            repo_id = f"{parts[-2]}/{parts[-1]}"
    out = []
    for rel in releases:
        tag = str(rel.get("tag_name", "")).lstrip("v")
        for a in rel.get("assets", []):
            itype = _classify(a.get("name", ""))
            if itype == "unknown":
                continue
            out.append(SourceAppEntry(
                name=a.get("name", ""), version=tag, url=a.get("browser_download_url", ""),
                installer_type=itype, sha256=a.get("sha256", "") or "", size=a.get("size", 0) or 0,
                source_name=src.name, repo_id=repo_id,
            ))
    return out


def _fetch_manifest(src: ManifestSource) -> List[SourceAppEntry]:
    resp = requests.get(src.url, headers=dict(src.headers or {}), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise ValueError("manifest source must be a JSON list")
    out = []
    for e in data:
        itype = (e.get("installer_type") or _classify(e.get("url", ""))).lower()
        if itype == "unknown":
            continue
        out.append(SourceAppEntry(
            name=e.get("name", ""), version=str(e.get("version", "")),
            url=e.get("url", ""), installer_type=itype,
            sha256=e.get("sha256", "") or "", size=e.get("size", 0) or 0,
            source_name=src.name,
        ))
    return out


def find_in_sources(entries: List[SourceAppEntry], query: str) -> Optional[Tuple[SourceAppEntry, str]]:
    """Find a single app across sources by source name, repo id, or app name."""
    q = (query or "").strip().lower()
    # exact source-name match (single-app source)
    by_src = [e for e in entries if e.source_name.lower() == q]
    if by_src:
        return by_src[0], by_src[0].source_name
    for e in entries:
        if e.repo_id.lower() == q or e.name.lower() == q:
            return e, e.source_name
    return None


def entries_for_source(entries: List[SourceAppEntry], source_name: str) -> List[SourceAppEntry]:
    return [e for e in entries if e.source_name == source_name]
