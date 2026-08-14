"""Local/portable app management: archive (ZIP) extraction and folder scanning.

Supports two non-installer workflows for ObtainHub:
  * ``zip``  - a GitHub release that only ships an archive (e.g. an archived repo);
               the ZIP is downloaded and extracted to a folder, then tracked.
  * ``folder`` - a user-specified local folder; ObtainHub scans its *root* for
                 applications (subfolders or .exe files) and tracks them.
"""

import os
import zipfile
import sys
from pathlib import Path
from typing import List, Dict, Optional

from obtainhub.core.downloader import Downloader
from obtainhub.core.config import get_config_manager
from obtainhub.core.state import get_state_manager, InstalledApp
from obtainhub.core.asset_matcher import AssetMatcher, AssetMatch, InstallerType
from obtainhub.core.logger import get_logger


logger = get_logger(__name__)

# Folders/extensions that are clearly not applications
_IGNORED_DIRS = {
    "node_modules", "downloads", "temp", "tmp", ".git", ".svn",
    ".vs", ".idea", "__pycache__", "bin", "obj",
}


def extract_archive(archive_path: Path, dest_dir: Path) -> Path:
    """Extract an archive into ``dest_dir``.

    If the archive contains a single top-level directory, its contents are
    flattened into ``dest_dir`` (common for portable ZIPs). Returns ``dest_dir``.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    suffix = archive_path.suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(archive_path, "r") as zf:
            names = zf.namelist()
            top = {n.split("/", 1)[0] for n in names if "/" in n}
            has_single_top = len(top) == 1 and all(
                n.startswith(tuple(top)) for n in names
            )
            if has_single_top:
                # Flatten the single wrapper directory
                prefix = next(iter(top)) + "/"
                for member in names:
                    if not member.startswith(prefix):
                        continue
                    rel = member[len(prefix):]
                    if not rel:
                        continue
                    target = dest_dir / rel
                    if member.endswith("/"):
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src, open(target, "wb") as out:
                            out.write(src.read())
            else:
                zf.extractall(dest_dir)
    else:
        raise ValueError(f"Unsupported archive type: {archive_path.name}")
    return dest_dir


def _looks_like_app(path: Path) -> bool:
    """Heuristic: is this root entry an application?"""
    if path.is_file():
        return path.suffix.lower() == ".exe"
    if path.is_dir():
        if path.name.lower() in _IGNORED_DIRS:
            return False
        # A folder is an app if it contains at least one .exe (any depth, cheap check)
        for child in path.iterdir():
            if child.is_file() and child.suffix.lower() == ".exe":
                return True
        return False
    return False


def scan_root_for_apps(folder: Path, recursive: bool = False) -> List[Dict[str, str]]:
    """Scan ``folder`` for applications.

    When ``recursive`` is True, subfolders are scanned too (one level deep into
    each subfolder). Otherwise only direct children are considered. Returns a
    list of ``{"name": str, "path": str, "kind": "exe"|"folder"}``.
    """
    folder = Path(folder)
    if not folder.is_dir():
        return []
    found = []
    entries = sorted(folder.iterdir())
    for entry in entries:
        if entry.name.startswith("."):
            continue
        if entry.is_dir() and entry.name.lower() in _IGNORED_DIRS:
            continue
        if _looks_like_app(entry):
            found.append({
                "name": entry.name,
                "path": str(entry),
                "kind": "exe" if entry.is_file() else "folder",
            })
        elif recursive and entry.is_dir():
            # One level deeper into subfolders
            for child in sorted(entry.iterdir()):
                if child.name.startswith("."):
                    continue
                if child.is_dir() and child.name.lower() in _IGNORED_DIRS:
                    continue
                if _looks_like_app(child):
                    found.append({
                        "name": f"{entry.name}/{child.name}",
                        "path": str(child),
                        "kind": "exe" if child.is_file() else "folder",
                    })
    return found


def _pick_zip_asset(matcher: AssetMatcher, assets: List[dict], pattern: str = "") -> Optional[AssetMatch]:
    """Pick a ZIP/archive asset: saved pattern first, else best candidate."""
    if pattern:
        m = matcher.match_by_pattern(assets, pattern)
        if m:
            return m
    candidates = [m for m in matcher.get_installable_candidates(assets)
                  if m.installer_type in (InstallerType.ZIP, InstallerType.ZIP_INSTALLER, InstallerType.EXE_STANDALONE)]
    return candidates[0] if candidates else None


def add_zip_app(
    repo_id: str,
    release: dict,
    *,
    location: Optional[str] = None,
    name: Optional[str] = None,
    force: bool = False,
    prefer_asset: Optional[AssetMatch] = None,
) -> InstalledApp:
    """Download the archive asset from a release and extract it to a folder.

    Records the app as ``app_type='zip'`` with ``install_location`` set so it can
    be updated later via the saved ``asset_pattern``.
    """
    owner, repo_name = repo_id.split("/", 1)
    name = name or repo_name
    config = get_config_manager().load()
    state = get_state_manager()

    matcher = AssetMatcher(allow_arm64=False, allow_x86_fallback=False, require_installer=False)
    assets = release.get("assets", [])
    existing_app = state.get_app(repo_id)
    pattern = getattr(existing_app, "asset_pattern", "") if existing_app else ""
    match = prefer_asset if getattr(prefer_asset, "url", None) else _pick_zip_asset(matcher, assets, pattern=pattern)

    if not match:
        raise ValueError(f"No archive asset found for {repo_id}")

    if location:
        install_location = Path(location) / name
    else:
        existing = state.get_app(repo_id)
        if existing and existing.install_location:
            install_location = Path(existing.install_location)
        else:
            default = Path(config.install_dir) / "portable" / name
            if sys.stdin.isatty():
                resp = input(f"Extract destination [{default}]: ").strip()
                install_location = Path(resp) / name if resp else default
            else:
                install_location = default
    install_location.mkdir(parents=True, exist_ok=True)

    print(f"Downloading archive: {match.name}")
    from obtainhub.main import _reuse_prompt
    downloaded = Downloader().download(
        match.url, filename=match.name, expected_size=getattr(match, "size", None),
        reuse_callback=_reuse_prompt,
    )
    try:
        extract_archive(downloaded, install_location)
    except PermissionError as e:
        print(f"Extraction failed (permission denied): {e}", file=sys.stderr)
        print("Run ohub as administrator, or choose a destination you own (not Program Files / System32).", file=sys.stderr)
        raise

    app_id = repo_id
    existing = state.get_app(app_id)
    version = release.get("tag_name", "").lstrip("v")
    if existing:
        app = state.update_app(
            app_id,
            version=version,
            tag=release.get("tag_name", ""),
            source_url=release.get("html_url", ""),
            install_location=str(install_location),
            asset_pattern=matcher.derive_asset_pattern(match),
            preferred_asset=match.name,
            app_type="zip",
        )
    else:
        app = InstalledApp(
            id=app_id,
            name=name,
            version=version,
            installer_type="zip",
            installer_path=str(downloaded),
            source_url=release.get("html_url", ""),
            tag=release.get("tag_name", ""),
            install_location=str(install_location),
            asset_pattern=matcher.derive_asset_pattern(match),
            preferred_asset=match.name,
            app_type="zip",
        )
        state.add_installed_app(app)
    print(f"Added portable app: {name} -> {install_location}")
    return app


def add_folder_app(folder: Path, *, name: Optional[str] = None, repo: str = "") -> List[InstalledApp]:
    """Track a local folder as an app managed by its linked GitHub repo.

    The app is identified by ``name`` (mandatory, the real application name) and
    must be linked to a GitHub ``repo`` (owner/repo) so it can be checked/updated.
    The folder is NOT scanned for executables - the user-supplied name and repo
    are the single source of truth.

    Returns the list of registered/updated InstalledApp objects (one entry).
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError(f"Folder not found: {folder}")
    if not name:
        raise ValueError("A application name (--name) is required for folder mode.")
    if not repo:
        raise ValueError("A GitHub repository (--repo owner/repo) is required for folder mode.")
    state = get_state_manager()

    base_id = name
    app_id = f"folder:{base_id}"
    existing = state.get_app(app_id)
    if existing:
        app = state.update_app(
            app_id, install_location=str(folder), app_type="folder",
            name=name, github_repo=repo,
        )
    else:
        app = InstalledApp(
            id=app_id,
            name=name,
            version="",
            installer_type="folder",
            installer_path="",
            source_url="",
            tag="",
            install_location=str(folder),
            app_type="folder",
            github_repo=repo,
        )
        state.add_installed_app(app)
    print(f"Linked folder app '{name}' ({folder}) to GitHub repo: {repo}")
    return [app]


def is_restricted_folder(folder: Path) -> bool:
    """True for filesystem roots that must not be scanned (e.g. C:\\)."""
    folder = Path(folder)
    # A drive root on Windows or '/' on POSIX
    if folder.parent == folder:  # '/' or drive root
        return True
    return False
