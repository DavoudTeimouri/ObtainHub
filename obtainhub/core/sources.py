"""Resolve apps from custom manifest sources (non-GitHub installs/updates).

A *source* is either:
  * ``github``  - a GitHub repo URL/API; we read its releases and expose each
                  asset as an installable entry.
  * ``manifest`` - a JSON list of :class:`SourceAppEntry` dicts served over HTTP.
  * ``winget`` - Windows Package Manager (winget) CLI queries
  * ``scoop`` - Scoop package manager CLI queries
  * ``chocolatey`` - Chocolatey package manager CLI queries

Both are normalized to :class:`SourceAppEntry` so install/update can treat them
uniformly.
"""

import json
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict

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
    package_id: str = ""         # winget/scoop/choco package ID
    hooks: Dict[str, str] = field(default_factory=dict)  # pre_install, post_install, pre_uninstall, post_uninstall


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


def _run_cli(cmd: List[str], timeout: int = 30) -> Optional[str]:
    """Run a CLI command and return stdout if successful."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return result.stdout
    except Exception as e:
        logger.debug(f"CLI command failed: {cmd} - {e}")
    return None


def _fetch_winget(query: str = "") -> List[SourceAppEntry]:
    """Fetch packages from winget."""
    entries = []
    # winget search --accept-source-agreements <query>
    cmd = ["winget", "search", "--accept-source-agreements"]
    if query:
        cmd.append(query)
    output = _run_cli(cmd)
    if not output:
        return entries
    
    # Parse winget output (table format)
    # Name            Id                    Version   Source
    # ---------------------------------------------------------
    # 7-Zip           7zip.7zip             24.08     winget
    lines = output.strip().split('\n')
    for line in lines[2:]:  # Skip header lines
        parts = line.split()
        if len(parts) >= 3:
            name = parts[0]
            pkg_id = parts[1]
            version = parts[2]
            # For winget, we can't easily get direct download URL without install
            # We'll use a placeholder and handle install via winget CLI
            entries.append(SourceAppEntry(
                name=name,
                version=version,
                url=f"winget:{pkg_id}",  # Special URL scheme
                installer_type="exe_setup",
                source_name="winget",
                package_id=pkg_id,
            ))
    return entries


def _fetch_scoop(query: str = "") -> List[SourceAppEntry]:
    """Fetch packages from Scoop."""
    entries = []
    cmd = ["scoop", "search", query] if query else ["scoop", "search"]
    output = _run_cli(cmd)
    if not output:
        return entries
    
    # Parse scoop output (table format)
    lines = output.strip().split('\n')
    for line in lines[1:]:  # Skip header
        parts = line.split()
        if len(parts) >= 2:
            name = parts[0]
            version = parts[1]
            # Scoop doesn't easily give direct URLs
            entries.append(SourceAppEntry(
                name=name,
                version=version,
                url=f"scoop:{name}",  # Special URL scheme
                installer_type="exe_setup",
                source_name="scoop",
                package_id=name,
            ))
    return entries


def _fetch_chocolatey(query: str = "") -> List[SourceAppEntry]:
    """Fetch packages from Chocolatey."""
    entries = []
    # choco list <query> --limit-output
    cmd = ["choco", "list"]
    if query:
        cmd.append(query)
    cmd.extend(["--limit-output", "--exact"])
    output = _run_cli(cmd)
    if not output:
        return entries
    
    # Parse choco output (id|version format)
    # 7zip|24.08
    for line in output.strip().split('\n'):
        if '|' in line:
            pkg_id, version = line.split('|', 1)
            entries.append(SourceAppEntry(
                name=pkg_id,
                version=version,
                url=f"chocolatey:{pkg_id}",  # Special URL scheme
                installer_type="exe_setup",
                source_name="chocolatey",
                package_id=pkg_id,
            ))
    return entries


def fetch_source_entries(config) -> List[SourceAppEntry]:
    """Fetch and normalize entries from all enabled sources."""
    entries: List[SourceAppEntry] = []
    for src in [s for s in config.manifest_sources if s.enabled]:
        try:
            if src.type == "manifest":
                entries.extend(_fetch_manifest(src))
            elif src.type == "winget":
                entries.extend(_fetch_winget())
            elif src.type == "scoop":
                entries.extend(_fetch_scoop())
            elif src.type == "chocolatey":
                entries.extend(_fetch_chocolatey())
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
                hooks=src.hooks or {},
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
        # Include hooks from the manifest source
        hooks = e.get("hooks", {}) or {}
        out.append(SourceAppEntry(
            name=e.get("name", ""), version=str(e.get("version", "")),
            url=e.get("url", ""), installer_type=itype,
            sha256=e.get("sha256", "") or "", size=e.get("size", 0) or 0,
            source_name=src.name,
            hooks=hooks,
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
