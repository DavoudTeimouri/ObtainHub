"""ObtainHub CLI entry point."""

import sys
import argparse
import signal
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from obtainhub.core.config import get_config_manager, ConfigManager, ManifestSource
from obtainhub.core.state import get_state_manager, StateManager, CheckHistoryEntry
from obtainhub.core.logger import setup_logging, get_logger, LogLevel
from obtainhub.core.self_updater import SelfUpdater, check_and_update
from obtainhub.core.github_client import GitHubClient
from obtainhub.core.asset_matcher import AssetMatcher, AssetMatch, InstallerType
from obtainhub.core.downloader import download_file, Downloader
from obtainhub.core.installer import install_app, InstallResult, SilentInstaller
from obtainhub.core.local_apps import (
    add_zip_app,
    add_folder_app,
    extract_archive,
    is_restricted_folder,
    scan_root_for_apps,
)
from obtainhub.core.system_scanner import get_installed_system_apps
from obtainhub.core.exceptions import (
    ObtainHubError,
    InstallerError,
    PrereleaseConfirmationRequired,
    AssetNotFoundError,
    AssetMatchError,
    InstallerExecutionError,
    ManualUninstallRequired,
)
from obtainhub.utils.helpers import get_architecture as get_system_architecture
from obtainhub.utils.helpers import is_newer, is_windows_x64, parse_version

# Global flag for graceful shutdown
_shutdown_requested = False

def _signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global _shutdown_requested
    _shutdown_requested = True
    print("\n[!] Interrupted. Stopping gracefully...")
    sys.exit(130)

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def main(args: Optional[List[str]] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="ohub",
        description="ObtainHub - Manage Windows x64 apps via GitHub Releases",
    )
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase verbosity"
    )
    parser.add_argument(
        "--version", action="version",
        version="ObtainHub v0.7.6.10 - GitHub-based Package Updater and Manager for Windows x64\n"
                "Homepage: https://github.com/DavoudTeimouri/ObtainHub\n"
                "License: MIT"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # install
    install_parser = subparsers.add_parser("install", help="Install an app")
    install_parser.add_argument("app", help="App identifier (owner/repo)")
    install_parser.add_argument("--tag", help="Specific release tag")
    install_parser.add_argument(
        "--version", dest="version_arg", help="Install a specific older version (e.g. 1.2.3)"
    )
    install_parser.add_argument(
        "--prerelease", action="store_true", help="Allow prerelease versions"
    )
    install_parser.add_argument(
        "--force", action="store_true", help="Force reinstall"
    )
    install_parser.add_argument(
        "--interactive", action="store_true",
        help="Launch the installer visibly and let you drive it; ohub verifies the result (auto-on when run interactively without --yes)",
    )
    install_parser.add_argument(
        "--download-only", action="store_true", help="Only download, don't install"
    )
    install_parser.add_argument(
        "--yes", "-y", action="store_true", help="Auto-confirm prompts"
    )
    install_parser.add_argument(
        "--reset", action="store_true",
        help="Forget saved asset/repo choice for this app so prompts re-appear",
    )

    # update
    update_parser = subparsers.add_parser("update", help="Update installed apps")
    update_parser.add_argument("app", nargs="?", help="App to update (default: all)")
    update_parser.add_argument(
        "--prerelease", action="store_true", help="Allow prerelease versions"
    )
    update_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be updated"
    )
    update_parser.add_argument(
        "--yes", "-y", action="store_true", help="Auto-confirm prompts"
    )
    update_parser.add_argument(
        "--reset", action="store_true",
        help="Forget saved asset/repo choices so prompts re-appear",
    )
    update_parser.add_argument(
        "--interactive", action="store_true",
        help="Launch installers visibly and let you drive them; ohub verifies each result",
    )

    # check
    check_parser = subparsers.add_parser("check", help="Check for updates without installing")
    check_parser.add_argument("app", nargs="?", help="App to check (default: all)")
    check_parser.add_argument(
        "--prerelease", action="store_true", help="Include prerelease versions"
    )
    check_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )
    check_parser.add_argument(
        "--yes", "-y", action="store_true", help="Auto-confirm prompts"
    )
    check_parser.add_argument(
        "--all", action="store_true", help="Re-check all unmanaged applications, ignoring previous choices"
    )
    check_parser.add_argument(
        "--candidates", action="store_true",
        help="For unmanaged apps with no exact repo, offer candidate repositories by name to link",
    )
    check_parser.add_argument(
        "--reset", action="store_true",
        help="Forget saved asset/repo choices so prompts re-appear",
    )
    check_parser.add_argument(
        "--timeout", type=int, default=None,
        help="Per-repo search timeout in seconds (10-300; default from config)",
    )

    # list
    list_parser = subparsers.add_parser("list", help="List installed apps")
    list_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )
    list_parser.add_argument(
        "--all", action="store_true", help="Include system-installed apps from Windows Registry"
    )

    # uninstall
    uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall an app")
    uninstall_parser.add_argument("app", help="App identifier (owner/repo)")
    uninstall_parser.add_argument(
        "--yes", "-y", action="store_true", help="Auto-confirm prompts"
    )
    uninstall_parser.add_argument(
        "--keep-data", action="store_true", help="Keep downloaded installer files"
    )
    uninstall_parser.add_argument(
        "--interactive", action="store_true",
        help="Launch the uninstaller visibly and let you drive it; ohub verifies the result",
    )

    # remove
    remove_parser = subparsers.add_parser("remove", help="Remove an app/folder from ohub management")
    remove_parser.add_argument("app", help="App identifier or name (owner/repo, folder:..., or display name)")
    remove_parser.add_argument(
        "--yes", "-y", action="store_true", help="Auto-confirm"
    )

    # source
    source_parser = subparsers.add_parser("source", help="Manage custom sources")
    source_subparsers = source_parser.add_subparsers(dest="source_action")
    source_subparsers.add_parser("list", help="List configured sources")
    add_parser = source_subparsers.add_parser("add", help="Add a custom source")
    add_parser.add_argument("name", help="Source name")
    add_parser.add_argument("url", help="Source URL (GitHub API or manifest)")
    add_parser.add_argument(
        "--type", choices=["github", "manifest"], default="github", help="Source type"
    )
    remove_parser = source_subparsers.add_parser("remove", help="Remove a source")
    verify_parser = source_subparsers.add_parser("verify", help="Verify a custom source")
    verify_parser.add_argument("name", help="Source name to verify")
    remove_parser.add_argument("name", help="Source name")

    # add (shorthand for adding a GitHub repo by owner/repo)
    add_parser = subparsers.add_parser("add", help="Add a repository, archive, or local folder for management")
    add_parser.add_argument("repo", nargs="?", help="Repository in owner/repo format, or a local folder path (with --type folder)")
    add_parser.add_argument("--name", help="Custom name (default: repo name)")
    add_parser.add_argument(
        "--type", dest="add_type", choices=["github", "zip", "folder"],
        default="github", help="Add mode: github repo, zip archive repo, or local folder",
    )
    add_parser.add_argument(
        "--location", help="Destination folder for extracted zip apps (default: install dir/portable/<name>)",
    )
    add_parser.add_argument(
        "--as-source", action="store_true",
        help="Also register the repo as a manifest source",
    )
    add_parser.add_argument(
        "--recursive", action="store_true",
        help="(folder mode) scan the folder recursively for applications",
    )
    add_parser.add_argument(
        "--repo", dest="repo_arg",
        help="(folder mode) link the folder app to a GitHub repo (owner/repo) for updates",
    )

    # search
    search_parser = subparsers.add_parser("search", help="Search GitHub repositories")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--limit", type=int, default=10, help="Maximum results (default: 10)"
    )
    search_parser.add_argument(
        "--min-stars", type=int, default=0, help="Minimum star count filter (default: 0)"
    )
    search_parser.add_argument(
        "--active-only", action="store_true", default=True, help="Only active, non-archived repos (default: True)"
    )
    search_parser.add_argument(
        "--include-inactive", action="store_false", dest="active_only", help="Include archived/inactive repos"
    )
    search_parser.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # config
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_subparsers = config_parser.add_subparsers(dest="config_action")
    config_subparsers.add_parser("show", help="Show current config")
    config_subparsers.add_parser("edit", help="Open config in editor")
    set_parser = config_subparsers.add_parser("set", help="Set config value")
    set_parser.add_argument("key", help="Config key")
    set_parser.add_argument("value", help="Config value")
    get_parser = config_subparsers.add_parser("get", help="Get config value")
    get_parser.add_argument("key", help="Config key")

    # self-update
    self_update_parser = subparsers.add_parser("self-update", help="Update ohub itself")
    self_update_parser.add_argument(
        "--prerelease", action="store_true", help="Allow prerelease versions"
    )
    self_update_parser.add_argument(
        "--force", action="store_true", help="Force update even if same version"
    )

    parsed = parser.parse_args(args)

    if not parsed.command:
        parser.print_help()
        return 0

    # Setup logging
    log_level = LogLevel.WARNING
    if parsed.verbose == 1:
        log_level = LogLevel.INFO
    elif parsed.verbose >= 2:
        log_level = LogLevel.DEBUG
    setup_logging(level=log_level)
    logger = get_logger(__name__)

    try:
        config_manager = get_config_manager()
        state_manager = get_state_manager()

        # Keep ObtainHub itself managed: register its own repo so it shows in
        # list/check/update and self-update stays consistent (issue: "ohub not in list").
        if is_windows_x64():
            _SELF_REPO = "DavoudTeimouri/ObtainHub"
            if not state_manager.get_app(_SELF_REPO):
                from obtainhub import __version__
                state_manager.add_installed_app({
                    "id": _SELF_REPO,
                    "name": "ObtainHub",
                    "version": __version__,
                    "installer_type": "github",
                    "installer_path": "",
                    "source_url": "https://github.com/DavoudTeimouri/ObtainHub",
                    "tag": "",
                    "app_type": "github",
                })

        # Interactive install/uninstall: when run on a TTY without --yes, launch
        # the installer/uninstaller visibly and let the user drive it (ohub then
        # verifies the result against system state). --yes / --download-only stays silent.
        if parsed.command in ("install", "update", "uninstall") and not getattr(parsed, "interactive", False):
            if sys.stdin.isatty() and not parsed.yes and not getattr(parsed, "download_only", False):
                parsed.interactive = True

        if parsed.command == "install":
            return cmd_install(
                parsed, config_manager, state_manager, logger
            )
        elif parsed.command == "update":
            return cmd_update(
                parsed, config_manager, state_manager, logger
            )
        elif parsed.command == "check":
            return cmd_check(
                parsed, config_manager, state_manager, logger
            )
        elif parsed.command == "list":
            return cmd_list(parsed, state_manager)
        elif parsed.command == "uninstall":
            return cmd_uninstall(
                parsed, config_manager, state_manager, logger
            )
        elif parsed.command == "remove":
            return cmd_remove(
                parsed, config_manager, state_manager, logger
            )
        elif parsed.command == "source":
            return cmd_source(
                parsed, config_manager
            )
        elif parsed.command == "add":
            return cmd_add(
                parsed, config_manager, state_manager, logger
            )
        elif parsed.command == "search":
            return cmd_search(parsed, config_manager, logger)
        elif parsed.command == "config":
            return cmd_config(parsed, config_manager)
        elif parsed.command == "self-update":
            return cmd_self_update(parsed, config_manager, state_manager, logger)
        else:
            parser.print_help()
            return 1

    except ObtainHubError as e:
        logger.error(str(e))
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        logger.exception("Unexpected error")
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def _warn_repo_status(client: GitHubClient, app_id: str) -> None:
    """Print a warning (once) if the repo is archived or inactive."""
    try:
        status = client.get_repo_status(*app_id.split("/", 1))
    except Exception:
        return
    if not status:
        return
    if status["archived"]:
        print(f"  [!] Warning: {app_id} is ARCHIVED — no new releases will be published.")
    elif status["inactive"]:
        days = status.get("last_push_days")
        msg = f" (last push {days} days ago)" if days is not None else ""
        print(f"  [!] Warning: {app_id} appears INACTIVE{msg}.")


def _resolve_app_id(state_manager: StateManager, token: str) -> str:
    """Resolve a user-supplied token to a managed app id.

    Accepts either the exact app id (e.g. ``owner/repo`` or ``folder:...``)
    or the app's display name (case-insensitive).
    """
    if state_manager.get_app(token):
        return token
    for app in state_manager.get_all_apps():
        if app.name.lower() == token.lower():
            return app.id
    return token


def _remove_app_source(config_manager, app_id: str, app) -> None:
    """Remove a manifest source that was registered for this app (if any)."""
    name = app_id.split("/")[-1] if "/" in app_id else app_id
    try:
        config_manager.remove_manifest_source(name)
    except Exception:
        pass


def _detect_manual_removal(state_manager, app) -> bool:
    """If a managed app is gone from the system, treat it as manually uninstalled.

    For folder/zip apps the install location IS the app — if the folder is gone,
    it's removed. For GitHub (setup-installed) apps the registry (Programs &
    Features) is the source of truth: install_location is often empty or stale,
    so we only remove when the app is absent from the registry AND its cached
    installer is gone.
    """
    # Folder / zip / portable apps: the install_location folder IS the app.
    if app.app_type in ("folder", "zip"):
        if app.install_location and not Path(app.install_location).exists():
            print(f"  {app.name} ({app.id}): install location missing - assumed manually removed. Removing from ohub.")
            state_manager.remove_app(app.id)
            return True
        return False

    # GitHub / setup-installed apps: trust the registry, not install_location.
    if app.app_type == "github":
        reg_present = any(
            sa.name.lower() == app.name.lower() or app.name.lower() in sa.name.lower()
            for sa in get_installed_system_apps()
        )
        if reg_present:
            return False  # still installed (registry says so)
        # Not in registry — check if the cached installer is gone too
        installer_gone = bool(app.installer_path) and not Path(app.installer_path).exists()
        if installer_gone:
            print(f"  {app.name} ({app.id}): not in system registry and installer missing - assumed manually removed. Removing from ohub.")
            state_manager.remove_app(app.id)
            return True
    return False


def _refresh_installed_version(state_manager, app) -> None:
    """Update ``app.version`` (and install location) from the system registry.

    If the user updated the app outside ohub (or it self-updated), the recorded
    version in ohub state is stale. Re-reading the real installed version lets
    `ohub check` report correctly instead of comparing against an old value.
    """
    installed = [
        sa for sa in get_installed_system_apps()
        if sa.name.lower() == app.name.lower()
        or app.name.lower() in sa.name.lower()
    ]
    if not installed:
        return
    # A single app can appear under multiple registry keys (e.g. an EXE-setup
    # and an MSI install both write DisplayName="ObtainHub", or the same
    # product is present for per-user and per-machine). Pick the HIGHEST version
    # so we don't report an older copy as the installed version. This also fixes
    # the self-update case where ohub's own entry could be shadowed by a stale
    # second install of the same name.
    sys_app = max(installed, key=lambda sa: parse_version(sa.version))
    changed = False
    if sys_app.version and sys_app.version != app.version:
        app.version = sys_app.version
        changed = True
    if sys_app.install_location and sys_app.install_location != app.install_location:
        app.install_location = sys_app.install_location
        changed = True
    if changed:
        state_manager.add_installed_app(app)
        state_manager.save()
        print(f"  {app.name} ({app.id}): detected installed version {sys_app.version} (was {app.version})")


def _search_with_timeout(client, timeout, retries, **kwargs):
    """Run a GitHub search in a worker thread, aborting after ``timeout`` seconds.

    Retries up to ``retries`` times on timeout. Returns the search result dict,
    or ``{"error": "timeout", "items": []}`` if it never completed in time.
    """
    import concurrent.futures
    for attempt in range(max(1, retries)):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(lambda: client.search_repositories(**kwargs))
            try:
                return fut.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                fut.cancel()
                if attempt < max(1, retries) - 1:
                    continue
                return {"error": "timeout", "items": []}
            except Exception as e:
                return {"error": str(e), "items": []}
    return {"error": "timeout", "items": []}


def _clean_app_query(name: str) -> str:
    """Strip version-like tokens from an app/registry name for GitHub search.

    "OnionHop V3 version 3.7.10" -> "OnionHop"; "v2rayN 6.0" -> "v2rayN"
    (names that mix letters and digits, e.g. "v2rayN", are kept).
    """
    import re as _re
    toks = name.split()
    kept = []
    for t in toks:
        if _re.fullmatch(r"[vV]?\d+(\.\d+)*", t):        # V3 / 3.7.10
            continue
        if _re.fullmatch(r"version", t, _re.IGNORECASE):  # "version"
            continue
        if not _re.search(r"[A-Za-z]", t):                # pure version/punctuation, no letters
            continue
        kept.append(t)
    return " ".join(kept).strip() or name


def _progressive_queries(name: str) -> List[str]:
    """Search queries from cleanest to raw: drop trailing words until empty, then raw name."""
    base = _clean_app_query(name) or name
    out: List[str] = []
    cur = base
    while cur and cur not in out:
        out.append(cur)
        cur = " ".join(cur.split()[:-1])
    if name not in out:
        out.append(name)
    return out


def _pick_candidate(candidates, app_id, state_manager, parsed):
    """Choose a candidate asset for an app that has no strict installer.

    Interactive when stdin is a TTY and not --json/--yes; otherwise defaults
    to the first candidate. Saves the chosen asset pattern to state.
    """
    chosen = candidates[0]
    interactive = (
        not parsed.json
        and not getattr(parsed, "yes", False)
        and sys.stdin.isatty()
    )
    if interactive and len(candidates) > 1:
        sel = _select_from_options(candidates, "  Select asset to track")
        if sel:
            chosen = sel
    state_manager.update_app(app_id, asset_pattern=AssetMatcher.derive_asset_pattern(chosen))
    return chosen


def _apply_match(app_id, app, release, match, state_manager, installer, parsed, *, action=True, owner="", repo=""):
    """Download (and optionally install/extract) a chosen asset, then record it.

    Used by both `update` and `check` once a candidate asset is picked.
    Returns (applied: bool, message: str).
    """
    from obtainhub.core.local_apps import extract_archive

    print(f"    Downloading {match.name}...")
    downloaded_path = download_file(
        match.url, filename=match.name, expected_size=getattr(match, "size", None),
        reuse_callback=_reuse_prompt,
    )
    pattern = AssetMatcher.derive_asset_pattern(match)

    itype = match.installer_type
    if itype in (InstallerType.EXE_SETUP, InstallerType.MSI, InstallerType.ZIP_INSTALLER):
        if not action:
            return True, f"Downloaded to {downloaded_path}"
        result, message = installer.install(
            downloaded_path, itype, app_id, force=True,
            interactive=getattr(parsed, "interactive", False),
        )
        if result == InstallResult.SUCCESS:
            installer.record_update(
                app_id=app_id,
                version=release.get('tag_name', '').lstrip('v'),
                installer_type=itype,
                installer_path=str(downloaded_path),
                source_url=release.get('html_url', ''),
                tag=release.get('tag_name', ''),
            )
            state_manager.update_app(app_id, asset_pattern=pattern, github_repo=f"{owner}/{repo}" if owner else app.github_repo)
            return True, message
        return False, message

    # Portable archive (zip / exe standalone) -> extract to install location
    if itype == InstallerType.ZIP:
        dest = Path(app.install_location) if app.install_location else (Path(downloaded_path).parent / app.name)
        if dest.exists() and not parsed.yes:
            print(f"    Destination exists: {dest}")
            print(f"    Installation is just extracting the archive. Back up any config you want to keep first.")
            resp = input("    Delete the existing folder and re-extract? [y/N]: ").strip().lower()
            if resp != "y":
                return False, "Cancelled: existing installation kept"
            try:
                import shutil
                shutil.rmtree(dest, ignore_errors=True)
            except Exception as e:
                return False, f"Could not clear destination: {e}"
        try:
            extract_archive(downloaded_path, dest)
        except PermissionError as e:
            return False, (
                f"Extraction failed (permission denied): {e}. "
                f"The app may be running - close it and retry, or run ohub as administrator "
                f"and choose a folder you own (not Program Files / System32)."
            )
        except Exception as e:
            return False, f"Extraction failed: {e}"
        state_manager.update_app(
            app_id,
            app_type="zip",
            version=release.get('tag_name', '').lstrip('v'),
            install_location=str(dest),
            asset_pattern=pattern,
            preferred_asset=match.name,
            source_url=release.get('html_url', ''),
            tag=release.get('tag_name', ''),
            github_repo=f"{owner}/{repo}" if owner else app.github_repo,
        )
        return True, f"Extracted to {dest}"

    # EXE_STANDALONE (or UNKNOWN): just keep the downloaded file, remember pattern
    state_manager.update_app(
        app_id,
        app_type="zip" if itype == InstallerType.EXE_STANDALONE else app.app_type,
        version=release.get('tag_name', '').lstrip('v'),
        asset_pattern=pattern,
        preferred_asset=match.name,
        source_url=release.get('html_url', ''),
        tag=release.get('tag_name', ''),
        github_repo=f"{owner}/{repo}" if owner else app.github_repo,
    )
    return True, f"Downloaded to {downloaded_path}"


def _reset_choices(state_manager: StateManager, app_id: Optional[str] = None) -> None:
    """Forget saved asset/repo choices so the user is re-prompted.

    If ``app_id`` is given, only that app's choices are cleared; otherwise all.
    Also clears check history (which records unmanaged-app linking choices).
    """
    for app in state_manager.get_all_apps():
        if app_id and app.id != app_id:
            continue
        state_manager.update_app(
            app.id,
            asset_pattern="",
            preferred_asset="",
        )
    if not app_id:
        state_manager.clear_check_history()
    state_manager.save()



def _reuse_prompt(path: Path, size: int) -> bool:
    """Ask the user whether to reuse an existing download instead of re-downloading."""
    mb = size / (1024 * 1024)
    try:
        resp = input(f"    File already downloaded: {path.name} ({mb:.1f} MB). Reuse it? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return True
    return resp != "n"


def _select_from_options(opts, prompt, allow_default=False, allow_skip=False):
    """Prompt user to pick from a list. Returns the chosen item, or None.

    - ``allow_default``: choice 0 (or empty) picks ``opts[0]`` (recommended).
    - ``allow_skip``: choice 0 returns None (explicit skip) without picking.
    With neither, only 1..len(opts) are valid.
    """
    if not opts:
        return None
    try:
        if allow_skip:
            choice = input(prompt + f" [0-{len(opts)}, 0=Skip, X=Exit]: ").strip()
            if choice == "0" or choice.lower() == "x":
                return None
            if choice.isdigit() and 1 <= int(choice) <= len(opts):
                return opts[int(choice) - 1]
        elif allow_default:
            choice = input(prompt + f" [0-{len(opts)}, 0=Default, X=Exit]: ").strip()
            if choice == "" or choice == "0" or choice.lower() == "x":
                return opts[0]
            if choice.isdigit() and 1 <= int(choice) <= len(opts):
                return opts[int(choice) - 1]
        else:
            choice = input(prompt + f" [1-{len(opts)}, 0=Cancel, X=Exit]: ").strip()
            if choice == "0" or choice.lower() == "x":
                return None
            if choice.isdigit() and 1 <= int(choice) <= len(opts):
                return opts[int(choice) - 1]
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return None
    print("Invalid selection.")
    return None


def _resolve_repo_for_app(client, app, state_manager, parsed):
    """Return (owner, repo) for an app, resolving folder/zip apps by name.

    GitHub apps use their id directly. Folder/zip apps without an explicit
    ``github_repo`` link are resolved by searching GitHub for their display
    name; the result is stored on the app for future use. Returns
    ``(None, None)`` if no repository can be determined.
    """
    if app.app_type == "github" or app.github_repo:
        repo_id = app.id if app.app_type == "github" else app.github_repo
        owner, repo = repo_id.split("/", 1)
        # Verify the repo resolves (fixes case typos like 2dust/v2rayn vs v2rayN)
        release = None
        try:
            release = client.get_latest_release(owner, repo, include_prerelease=parsed.prerelease if hasattr(parsed, "prerelease") else False)
        except Exception:
            release = None
        if not release:
            fixed = _fix_repo_casing(client, owner, repo)
            if fixed:
                owner, repo = fixed
                if app.github_repo:
                    state_manager.update_app(app.id, github_repo=f"{owner}/{repo}")
        return owner, repo

    # Folder/zip app: try to find a repo by the app's display name
    print(f"  {app.name}: looking up GitHub repository by name '{app.name}'...")
    try:
        result = client.search_repositories(
            query=app.name, min_stars=0, ignore_case=True, active_only=False,
        )
    except Exception as e:
        print(f"    Search failed: {e}")
        return None, None
    if result.get("error"):
        print(f"    Search failed: {result['error']}")
        return None, None
    items = result.get("items", [])
    if not items:
        print(f"    No GitHub repository found for '{app.name}'.")
        print(f"    Tip: ohub remove {app.id}, then ohub add \"<path>\" --type folder --name {app.name} --repo owner/{app.name}")
        return None, None
    exact = next((r for r in items
                  if r.get("name", "").lower() == app.name.lower()
                  or r.get("full_name", "").lower().endswith("/" + app.name.lower())), None)
    repo_id = (exact or items[0])["full_name"]
    print(f"    Linked to: {repo_id}")
    state_manager.update_app(app.id, github_repo=repo_id)
    return repo_id.split("/", 1)


def _fix_repo_casing(client, owner, repo):
    """Try to resolve a repo name that may have wrong casing via search."""
    try:
        result = client.search_repositories(query=repo, min_stars=0, ignore_case=True, active_only=False)
    except Exception:
        return None
    if result.get("error") or not result.get("items"):
        return None
    match = next((r for r in result["items"]
                  if r.get("full_name", "").lower() == f"{owner}/{repo}".lower()), None)
    return match["full_name"].split("/", 1) if match else None


def _install_from_source(entry, source_name, parsed, config_manager, state_manager):
    """Install an app resolved from a custom (non-GitHub) source entry."""
    from obtainhub.core.sources import SourceAppEntry
    from obtainhub.core.local_apps import add_zip_app, extract_archive
    from obtainhub.core.asset_matcher import InstallerType

    app_id = entry.repo_id or f"source:{source_name}/{entry.name}"
    print(f"Installing {entry.name} v{entry.version} from source '{source_name}'")
    if _detect_source_version_warning(entry.version):
        print("Warning: installing a non-latest / older version - may be unstable.")

    existing = state_manager.get_app(app_id)
    if existing and not parsed.force:
        if not (entry.version or "") > (existing.version or ""):
            print(f"{app_id} is already managed by ohub and up to date ({existing.version}).")
            return 0

    target = None
    if entry.installer_type in ("zip", "zip_installer"):
        target = _download_entry(entry, config_manager, state_manager)
        if target is None:
            return 1
        location = parsed.location or (Path(config_manager.load().install_dir) / "portable" / entry.name)
        Path(location).mkdir(parents=True, exist_ok=True)
        try:
            extract_archive(target, Path(location))
        except PermissionError as e:
            print(f"Extraction failed (permission denied): {e}", file=sys.stderr)
            print("Run ohub as administrator, or choose a folder you own.", file=sys.stderr)
            return 1
        _record_source_app(app_id, entry, source_name, str(location), state_manager, app_type="zip")
        print(f"Installed portable app {entry.name} v{entry.version} at {location}")
        return 0

    # exe_setup / msi / exe_standalone -> download + install
    target = _download_entry(entry, config_manager, state_manager)
    if target is None:
        return 1
    if parsed.download_only or entry.installer_type == "exe_standalone":
        print(f"Download-only mode: {target}")
        _record_source_app(app_id, entry, source_name, str(target), state_manager)
        return 0
    installer = SilentInstaller()
    itype = InstallerType.EXE_SETUP if entry.installer_type == "exe_setup" else (
        InstallerType.MSI if entry.installer_type == "msi" else InstallerType.EXE_STANDALONE)
    result, message = installer.install(target, itype, app_id, force=True,
                                      interactive=getattr(parsed, "interactive", False))
    if result == InstallResult.SUCCESS:
        _record_source_app(app_id, entry, source_name, str(target), state_manager)
        print(f"Success: {message}")
        return 0
    print(f"Install failed: {message}")
    return 1


def _download_entry(entry, config_manager, state_manager):
    from obtainhub.core.downloader import download_file
    try:
        return download_file(
            entry.url, filename=entry.name, expected_sha256=entry.sha256 or None,
            expected_size=entry.size or None, reuse_callback=_reuse_prompt,
        )
    except Exception as e:
        print(f"Download failed: {e}", file=sys.stderr)
        return None


def _record_source_app(app_id, entry, source_name, path, state_manager, app_type="source"):
    state_manager.add_installed_app({
        "id": app_id,
        "name": entry.name,
        "version": entry.version,
        "installer_type": entry.installer_type,
        "installer_path": path,
        "source_url": entry.url,
        "tag": entry.version,
        "app_type": app_type,
        "source": source_name,
        "github_repo": entry.repo_id,
    })


def _detect_source_version_warning(version: str) -> bool:
    # crude: treat anything the user explicitly requested as potentially non-latest
    return False


def cmd_install(
    parsed: argparse.Namespace,
    config_manager: ConfigManager,
    state_manager: StateManager,
    logger,
) -> int:
    app_id = _resolve_app_id(state_manager, parsed.app)
    logger.info(f"Installing {app_id}")
    print(f"[*] Resolving {app_id} ...", flush=True)

    # Parse owner/repo
    if "/" not in app_id:
        print(f"Error: App must be in format 'owner/repo'", file=sys.stderr)
        return 1
    owner, repo = app_id.split("/", 1)

    # If the app is already installed on this system (by the user, not ohub),
    # don't reinstall - tell the user to let ohub take it over via `ohub check`.
    if not parsed.force:
        sys_installed = [
            sa for sa in get_installed_system_apps()
            if sa.name.lower() == repo.lower()
        ]
        if sys_installed and not state_manager.get_app(app_id):
            loc = sys_installed[0].install_location or "system"
            print(f"{app_id} appears already installed on this system (at {loc}).")
            print("Run 'ohub check' so ohub can detect and manage it (no reinstall needed).")
            print("Use 'ohub install {0} --force' to reinstall anyway.".format(app_id))
            return 0

    # Register the repo as a manifest source for future checks
    try:
        config_manager.add_manifest_source(repo, f"https://api.github.com/repos/{owner}/{repo}/releases")
    except Exception:
        pass

    # Get GitHub client
    token = config_manager.load().github_token
    client = GitHubClient(token=token)

    # Fetch release
    if parsed.version_arg:
        tag = f"v{parsed.version_arg}" if not parsed.version_arg.startswith("v") else parsed.version_arg
        release = client.get_release_by_tag(owner, repo, tag)
        if not release:
            print(f"Error: version {parsed.version_arg} not found for {app_id}", file=sys.stderr)
            return 1
        print(f"Installing older version {release.get('tag_name')} (may be unstable - use at your own risk).")
    elif parsed.tag:
        release = client.get_release_by_tag(owner, repo, parsed.tag)
    else:
        # Offer recent versions (max 3) for selection when interactive
        if sys.stdin.isatty() and not parsed.yes:
            try:
                recent = client.get_releases(owner, repo, per_page=10) or []
                recent = [r for r in recent if r.get("prerelease") == parsed.prerelease or (parsed.prerelease and True)]
                if recent:
                    print("Recent versions:")
                    for i, r in enumerate(recent[:3]):
                        print(f"  [{i+1}] {r.get('tag_name')}")
                    print(f"  [0] Latest ({'include prerelease' if parsed.prerelease else 'stable'})")
                    print(f"  [X] Cancel")
                    try:
                        choice = input("Select version [0-3, X=Cancel]: ").strip()
                    except (EOFError, KeyboardInterrupt):
                        choice = "0"
                    if choice.lower() == "x":
                        print("Cancelled.")
                        return 1
                    if choice.isdigit() and 1 <= int(choice) <= len(recent[:3]):
                        release = recent[int(choice) - 1]
                        print(f"Installing {release.get('tag_name')} (older version - may be unstable).")
                    else:
                        release = client.get_latest_release(owner, repo, include_prerelease=parsed.prerelease)
                else:
                    release = client.get_latest_release(owner, repo, include_prerelease=parsed.prerelease)
            except Exception:
                release = client.get_latest_release(owner, repo, include_prerelease=parsed.prerelease)
        else:
            release = client.get_latest_release(owner, repo, include_prerelease=parsed.prerelease)

    if not release:
        # Fall back to custom (non-GitHub) sources
        from obtainhub.core.sources import fetch_source_entries, find_in_sources
        try:
            entries = fetch_source_entries(config_manager.load())
        except Exception:
            entries = []
        found = find_in_sources(entries, app_id) if entries else None
        if found:
            entry, source_name = found
            return _install_from_source(entry, source_name, parsed, config_manager, state_manager)
        print(f"Error: No release found for {app_id}", file=sys.stderr)
        return 1

    # Check prerelease
    if release.get('prerelease') and not parsed.prerelease:
        print(f"Warning: {release.tag_name} is a prerelease. Use --prerelease to install.")
        if not parsed.yes:
            confirm = input("Continue anyway? [y/N]: ").strip().lower()
            if confirm != "y":
                print("Cancelled.")
                return 1

    # Check prerelease
    if release.get('prerelease') and not parsed.prerelease:
        print(f"Warning: {release.tag_name} is a prerelease. Use --prerelease to install.")
        if not parsed.yes:
            confirm = input("Continue anyway? [y/N]: ").strip().lower()
            if confirm != "y":
                print("Cancelled.")
                return 1

    # Archived / inactive warning
    _warn_repo_status(client, app_id)

    # If already managed by ohub, do not reinstall unless a newer version exists
    existing = state_manager.get_app(app_id)
    if existing:
        latest_version = release.get('tag_name', '').lstrip('v')
        if not (latest_version > (existing.version or '')):
            print(f"{app_id} is already managed by ohub and up to date ({existing.version}).")
            print("Use 'ohub update' to check for newer releases.")
            return 0
        print(f"{app_id} already managed but a newer version ({latest_version}) is available - updating.")

    # Match asset
    matcher = AssetMatcher(
        allow_arm64=False,
        allow_x86_fallback=False,
        require_installer=not parsed.download_only,
    )
    match = matcher.get_best_match(release.get('assets', []))

    # No strict installer? Offer candidate assets (ZIP/EXE/etc.) for selection
    if not match:
        candidates = matcher.get_installable_candidates(release.get('assets', []))
        if not candidates:
            print(f"Error: No suitable installer or asset found for {app_id}", file=sys.stderr)
            return 1
        print(f"No standard installer found for {app_id}. Available assets:")
        for i, opt in enumerate(candidates):
            print(f"  [{i+1}] {opt.name} ({opt.architecture.value}, {opt.installer_type.name}, {opt.size} bytes)")
        if parsed.yes:
            match = candidates[0]
        else:
            sel = _select_from_options(candidates, "Select asset to install")
            if not sel:
                return 1
            match = sel

    # If multiple strict installers, confirm the chosen one
    if not parsed.yes and not parsed.download_only:
        installer_options = matcher.get_installer_options(release.get('assets', []))
        if len(installer_options) > 1 and match not in installer_options:
            installer_options = [match] + installer_options
        if len(installer_options) > 1:
            print(f"Multiple installer assets found for {app_id}:")
            for i, opt in enumerate(installer_options):
                mark = " <=" if opt is match else ""
                print(f"  [{i+1}] {opt.name} ({opt.architecture.value}, {opt.installer_type.name}, {opt.size} bytes){mark}")
            print(f"  [0] Cancel")
            sel = _select_from_options(installer_options, "Select installer", allow_skip=True)
            if sel is None:
                print("Cancelled.")
                return 1
            match = sel

    print(f"Found: {match.name} ({match.architecture.value}, {match.installer_type.name})")

    # Portable archive (ZIP / standalone EXE chosen as target): extract to a folder
    if match.installer_type in (InstallerType.ZIP, InstallerType.ZIP_INSTALLER) and not parsed.download_only:
        try:
            app = add_zip_app(
                app_id, release,
                name=getattr(parsed, "name", "") or repo,
                prefer_asset=match,
            )
            version = release.get('tag_name', '').lstrip('v')
            print(f"Installed portable app {app.name} v{version} at {app.install_location}")
            return 0
        except Exception as e:
            print(f"Failed to install archive: {e}", file=sys.stderr)
            return 1

    # Download
    print(f"Downloading...")
    try:
        downloaded_path = download_file(
            match.url,
            filename=match.name,
            expected_sha256=None,
            expected_size=getattr(match, "size", None),
            reuse_callback=_reuse_prompt,
        )
    except Exception as e:
        print(f"Download failed: {e}", file=sys.stderr)
        return 1

    print(f"Downloaded to: {downloaded_path}")

    # Install
    if parsed.download_only or match.installer_type == InstallerType.EXE_STANDALONE:
        print(f"Download-only mode: {downloaded_path}")
        return 0

    result, message = install_app(
        downloaded_path,
        match.installer_type,
        app_id,
        force=parsed.force,
        interactive=parsed.interactive,
    )

    if result == InstallResult.SUCCESS:
        print(f"Success: {message}")
        # Record in state
        state_manager.add_installed_app({
            "id": app_id,
            "name": repo,
            "version": release.get('tag_name', '').lstrip("v"),
            "installer_type": match.installer_type.name.lower(),
            "installer_path": str(downloaded_path),
            "source_url": release.get('html_url', ''),
            "tag": release.get('tag_name', ''),
            "asset_pattern": matcher.derive_asset_pattern(match),
        })
    else:
        print(f"Install failed: {message}")
        return 1

    return 0


def _update_from_source(app, parsed, state_manager, config_manager):
    """Update an app that was installed from a custom source."""
    from obtainhub.core.sources import fetch_source_entries, entries_for_source

    try:
        entries = fetch_source_entries(config_manager.load())
    except Exception as e:
        print(f"  {app.name}: could not read sources: {e}")
        return
    src_entries = entries_for_source(entries, app.source)
    if not src_entries:
        print(f"  {app.name} ({app.id}): not found in source '{app.source}'")
        return
    if len(src_entries) == 1:
        entry = src_entries[0]
    else:
        # multiple assets for the same app: keep the current asset name if present
        entry = next((e for e in src_entries if e.name == app.preferred_asset), src_entries[0])

    if not is_newer(entry.version, app.version or ""):
        print(f"  {app.name} ({app.id}): Up to date ({app.version}) [source: {app.source}]")
        return
    print(f"  {app.name} ({app.id}): {app.version or '-'} -> {entry.version} [source: {app.source}]")
    if parsed.dry_run:
        return
    # Reuse install logic but keep the same app_id
    saved_app_id = app.id
    app_id_arg = parsed.app  # unused; we call internals directly
    # Download + apply using the same flow as install
    target = _download_entry(entry, config_manager, state_manager)
    if target is None:
        return
    from obtainhub.core.local_apps import extract_archive
    from obtainhub.core.asset_matcher import InstallerType
    if entry.installer_type in ("zip", "zip_installer"):
        location = app.install_location or (Path(config_manager.load().install_dir) / "portable" / entry.name)
        Path(location).mkdir(parents=True, exist_ok=True)
        try:
            extract_archive(target, Path(location))
        except Exception as e:
            print(f"  Failed: {e}")
            return
        state_manager.update_app(saved_app_id, version=entry.version, install_location=str(location),
                                 preferred_asset=entry.name, source_url=entry.url, tag=entry.version,
                                 app_type="zip", source=app.source)
        print(f"  Success: extracted to {location}")
    elif parsed.download_only or entry.installer_type == "exe_standalone":
        print(f"  Download-only mode: {target}")
        state_manager.update_app(saved_app_id, version=entry.version, installer_path=str(target),
                                 source_url=entry.url, tag=entry.version, source=app.source)
    else:
        installer = SilentInstaller()
        itype = InstallerType.EXE_SETUP if entry.installer_type == "exe_setup" else (
            InstallerType.MSI if entry.installer_type == "msi" else InstallerType.EXE_STANDALONE)
        result, message = installer.install(target, itype, saved_app_id, force=True,
                                          interactive=getattr(parsed, "interactive", False))
        if result == InstallResult.SUCCESS:
            state_manager.update_app(saved_app_id, version=entry.version, installer_path=str(target),
                                     source_url=entry.url, tag=entry.version, source=app.source)
            print(f"  Success: {message}")
        else:
            print(f"  Failed: {message}")


def cmd_update(
    parsed: argparse.Namespace,
    config_manager: ConfigManager,
    state_manager: StateManager,
    logger,
) -> int:
    """Handle update command."""
    print(f"[*] Checking updates for installed apps ...", flush=True)
    token = config_manager.load().github_token
    client = GitHubClient(token=token)
    matcher = AssetMatcher(allow_arm64=False, allow_x86_fallback=False, require_installer=True)
    installer = SilentInstaller()

    apps_to_update = []
    if parsed.app:
        apps_to_update = [_resolve_app_id(state_manager, parsed.app)]
    else:
        apps = state_manager.get_all_apps()
        apps_to_update = [app.id for app in apps]

    if not apps_to_update:
        print("No apps to update.")
        return 0

    print(f"Checking updates for {len(apps_to_update)} app(s)...\n")

    updated_count = 0
    if parsed.reset:
        _reset_choices(state_manager, app_id=parsed.app if parsed.app else None)
        print("Cleared saved choices." + ("" if parsed.app else " Re-run to re-prompt."))

    for app_id in apps_to_update:
        try:
            app = state_manager.get_app(app_id)
            if not app:
                print(f"Skipping {app_id}: not found in state")
                continue
            if _detect_manual_removal(state_manager, app):
                continue

            owner, repo = _resolve_repo_for_app(client, app, state_manager, parsed)
            if not owner:
                # Try custom (non-GitHub) sources for apps that came from one
                if app.source:
                    _update_from_source(app, parsed, state_manager, config_manager)
                continue

            release = client.get_latest_release(owner, repo, include_prerelease=parsed.prerelease)

            if not release:
                print(f"  Skipping {app_id}: no release found")
                continue

            # Archived / inactive warning
            _warn_repo_status(client, app_id)

            current_version = app.version
            latest_version = release.get('tag_name', '').lstrip("v")
            has_update = is_newer(latest_version, current_version)

            match = matcher.get_best_match(release.get('assets', []))
            if app.app_type == "zip" and not match:
                match = matcher.match_by_pattern(release.get('assets', []), app.asset_pattern)

            # No strict installer found: always offer candidate assets to pick from
            user_picked = False
            if not match:
                candidates = matcher.get_installable_candidates(release.get('assets', []))
                if candidates:
                    print(f"  {app.name} ({app_id}): no standard installer; available assets:")
                    for i, opt in enumerate(candidates):
                        print(f"    [{i+1}] {opt.name} ({opt.architecture.value}, {opt.installer_type.name}, {opt.size} bytes)")
                    chosen = candidates[0] if parsed.yes else (_select_from_options(candidates, "  Select asset") or candidates[0])
                    match = chosen
                    user_picked = True
                else:
                    print(f"  {app.name} ({app_id}): No suitable asset found in release {latest_version}")
                    continue

            # Standard installer present but app already up to date -> skip (unless user picked)
            if not user_picked and not has_update:
                print(f"  {app.name} ({app_id}): Up to date ({current_version})")
                continue

            # If there are multiple installer options, let user choose
            if not parsed.yes:
                installer_options = matcher.get_installer_options(release.get('assets', []))
                if len(installer_options) > 1:
                    print(f"  Multiple installer assets found for {app_id}:")
                    for i, opt in enumerate(installer_options):
                        print(f"    [{i+1}] {opt.name} ({opt.architecture.value}, {opt.installer_type.name}, {opt.size} bytes)")
                    print(f"    [0] Cancel")
                    sel = _select_from_options(installer_options, "  Select installer", allow_skip=True)
                    if sel is None:
                        print(f"    Skipped {app.name} ({app_id}) - cancelled by user.")
                        continue
                    match = sel

            print(f"  {app.name} ({app_id}): {current_version or '-'} -> {latest_version}")
            if parsed.dry_run:
                print(f"    Would download {match.name} ({match.installer_type.name})")
                updated_count += 1
                continue

            applied, message = _apply_match(
                app_id, app, release, match, state_manager, installer, parsed,
                action=True, owner=owner, repo=repo,
            )
            if applied:
                print(f"  Success: {message}")
                updated_count += 1
            else:
                print(f"  Failed: {message}")

        except Exception as e:
            logger.error(f"Failed to update {app_id}: {e}")
            print(f"  Error updating {app_id}: {e}")

    print(f"\nDone. Updated {updated_count}/{len(apps_to_update)} app(s).")
    return 0


def _check_record_ignored(state_manager, sys_app, has_github_repo=False, repo_id=""):
    """Record an unmanaged app as ignored in check history."""
    entry = CheckHistoryEntry(
        app_name=sys_app.name,
        app_version=sys_app.version,
        github_repo=repo_id,
        has_github_repo=has_github_repo,
        user_choice="ignored",
        checked_at=int(datetime.now().timestamp()),
    )
    state_manager.add_check_history(entry)
    state_manager.save()


def _check_add_or_ignore(parsed, state_manager, sys_app, repo_id):
    """Prompt to add a matched GitHub repo to ohub management during check."""
    from obtainhub.core.state import InstalledApp
    if not parsed.yes:
        confirm = input(f"    Add {repo_id} to ohub management? [y/N]: ").strip().lower()
        if confirm != "y":
            print(f"    Skipped - not adding to ohub")
            _check_record_ignored(state_manager, sys_app, has_github_repo=True, repo_id=repo_id)
            return
    owner, repo_name = repo_id.split("/", 1)
    app_state = InstalledApp(
        id=repo_id,
        name=repo_name,
        version=sys_app.version,
        installer_type="unknown",
        installer_path="",
        source_url=f"https://github.com/{owner}/{repo_name}",
        tag="",
        installed_at=int(datetime.now().timestamp()),
        updated_at=int(datetime.now().timestamp()),
        requires_manual_uninstall=False,
        architecture="x64",
    )
    state_manager.add_installed_app(app_state)
    print(f"    Added {repo_id} to ohub management" + (" (auto)" if parsed.yes else ""))
    entry = CheckHistoryEntry(
        app_name=sys_app.name,
        app_version=sys_app.version,
        github_repo=repo_id,
        has_github_repo=True,
        user_choice="managed",
        checked_at=int(datetime.now().timestamp()),
    )
    state_manager.add_check_history(entry)
    state_manager.save()


def cmd_check(
    parsed: argparse.Namespace,
    config_manager: ConfigManager,
    state_manager: StateManager,
    logger,
) -> int:
    """Handle check command - check for updates without installing.

    - Managed apps: check exact GitHub repo, warn if archived/inactive, and if no
      strict installer is found, list candidate assets for install/upgrade.
    - Unmanaged apps: try to find the EXACT matching GitHub repo; with --candidates a
      list of candidate repositories is offered for linking.
    """
    print(f"[*] Scanning for updates ...", flush=True)
    token = config_manager.load().github_token
    client = GitHubClient(token=token)
    matcher = AssetMatcher(allow_arm64=False, allow_x86_fallback=False, require_installer=True)

    # Unmanaged system apps for --all
    system_apps = get_installed_system_apps()
    ohub_apps = state_manager.get_all_apps()
    ohub_app_names = {a.name.lower() for a in ohub_apps}
    ohub_locations = {
        str(getattr(a, "install_location", "") or "").lower()
        for a in ohub_apps
    } | {
        str(getattr(a, "installer_path", "") or "").lower()
        for a in ohub_apps
    }
    ohub_locations.discard("")
    unmanaged_apps = [
        sa for sa in system_apps
        if not any(sa.name.lower().startswith(n) for n in ohub_app_names)
        and sa.install_location.lower() not in ohub_locations
    ]

    apps_to_check = []
    selected_unmanaged = None
    if parsed.app:
        apps_to_check = [parsed.app]
    elif sys.stdin.isatty():
        managed = state_manager.get_all_apps()
        menu = [(m.id, f"{m.name} ({m.id})", "managed") for m in managed]
        if parsed.all:
            menu += [(sa.name, f"{sa.name} (system)", "unmanaged") for sa in unmanaged_apps]
        if menu:
            print("Select app(s) to check:")
            for i, (_, label, _) in enumerate(menu):
                print(f"  [{i+1}] {label}")
            print(f"  [0] All ({len(menu)})")
            print(f"  [X] Exit (check nothing)")
            try:
                choice = input("Check > [0-{0}, X=Exit]: ".format(len(menu))).strip()
            except (EOFError, KeyboardInterrupt):
                choice = "0"
            if choice.lower() == "x":
                print("Cancelled.")
                return 0
            if choice == "0" or choice == "":
                apps_to_check = [app.id for app in managed]
            elif choice.isdigit() and 1 <= int(choice) <= len(menu):
                kind = menu[int(choice) - 1][2]
                if kind == "managed":
                    apps_to_check = [menu[int(choice) - 1][0]]
                    unmanaged_apps = []  # a single managed app was chosen; skip the unmanaged scan
                else:
                    selected_unmanaged = menu[int(choice) - 1][0]
                    apps_to_check = []  # check only the selected unmanaged app below
            else:
                print("Invalid selection - checking managed apps.")
                apps_to_check = [app.id for app in managed]
        else:
            apps_to_check = []
    else:
        apps_to_check = [app.id for app in state_manager.get_all_apps()]
    ohub_app_names = {a.name.lower() for a in state_manager.get_all_apps()}

    if parsed.all:
        if not apps_to_check and not unmanaged_apps:
            print("No apps to check.")
            return 0
    else:
        if not apps_to_check:
            print("No managed apps to check. Use --all to also scan system-installed apps.")
            return 0
        unmanaged_apps = []  # skip unmanaged scan unless --all

    # Managed apps
    print(f"Checking {len(apps_to_check)} managed app(s)...\n")

    results = []
    if parsed.reset:
        _reset_choices(state_manager, app_id=parsed.app if parsed.app else None)
        print("Cleared saved choices." + ("" if parsed.app else " Re-run to re-prompt."))

    for app_id in apps_to_check:
        try:
            app = state_manager.get_app(app_id)
            if not app:
                print(f"Skipping {app_id}: not found in state")
                continue
            if _detect_manual_removal(state_manager, app):
                continue

            # Re-read the actually-installed version from the system registry so
            # that updates performed OUTSIDE ohub (or a self-update) are detected.
            # Without this, ohub compares against its own stale stored version.
            _refresh_installed_version(state_manager, app)

            if app.app_type in ("folder", "zip"):
                # GitHub-linked folder/zip apps use their repo; otherwise search by name
                if app.github_repo and "/" in app.github_repo:
                    owner, repo = app.github_repo.split("/", 1)
                else:
                    print(f"  {app.name} ({app_id}): looking up GitHub repo by name...")
                    resolved = _resolve_repo_for_app(client, app, state_manager, parsed)
                    if not resolved[0]:
                        print(f"  {app.name} ({app_id}): folder/portable app, no remote match - skipping")
                        continue
                    owner, repo = resolved
            elif "/" in app_id:
                owner, repo = app_id.split("/", 1)
            else:
                print(f"  {app.name} ({app_id}): cannot resolve remote (no owner/repo)")
                continue
            release = client.get_latest_release(owner, repo, include_prerelease=parsed.prerelease)

            if not release:
                print(f"  {app.name} ({app_id}): no release found")
                continue

            current_version = app.version
            latest_version = release.get('tag_name', '').lstrip("v")
            has_update = is_newer(latest_version, current_version)

            _warn_repo_status(client, app_id)

            # Prefer saved asset pattern, then strict installer, then candidates
            match = matcher.get_best_match(release.get('assets', []))
            if app.app_type == "zip" and not match:
                match = matcher.match_by_pattern(release.get('assets', []), app.asset_pattern)

            candidates = matcher.get_installable_candidates(release.get('assets', []))

            if not parsed.json:
                if has_update:
                    asset_info = f"{match.name} ({match.installer_type.name})" if match else "No suitable installer"
                    print(f"  {app.name} ({app_id})")
                    print(f"    Current:  {current_version}")
                    print(f"    Latest:   {latest_version}")
                    print(f"    Status:   UPDATE AVAILABLE")
                    print(f"    Asset:    {asset_info}")
                    if not match and candidates:
                        print(f"    Available assets (install/upgrade candidates):")
                        for i, opt in enumerate(candidates):
                            print(f"      [{i+1}] {opt.name} ({opt.architecture.value}, {opt.installer_type.name}, {opt.size} bytes)")
                        chosen = _pick_candidate(candidates, app_id, state_manager, parsed)
                        print(f"    Saved asset pattern for future updates: {matcher.derive_asset_pattern(chosen)}")
                        if has_update and not parsed.json:
                            applied, message = _apply_match(
                                app_id, app, release, chosen, state_manager, SilentInstaller(), parsed,
                                action=True, owner=owner, repo=repo,
                            )
                            print(f"    Applied: {message}")
                    print()
                else:
                    print(f"  {app.name} ({app_id})")
                    print(f"    Current:  {current_version}")
                    print(f"    Latest:   {latest_version}")
                    print(f"    Status:   Up to date")
                    print()

            results.append({
                "app": app_id,
                "current_version": current_version,
                "latest_version": latest_version,
                "has_update": has_update,
                "prerelease": release.get('prerelease', False),
                "asset": f"{match.name} ({match.installer_type.name})" if match else "No suitable installer",
                "release_url": release.get('html_url', ''),
            })

        except Exception as e:
            logger.error(f"Failed to check {app_id}: {e}")
            if not parsed.json:
                print(f"  {app_id}: Error - {e}\n")
            else:
                results.append({"app": app_id, "error": str(e)})

    # Unmanaged apps: exact GitHub repo match only (no candidate list)
    if unmanaged_apps:
        cfg = config_manager.load()
        timeout = parsed.timeout if parsed.timeout is not None else cfg.check_timeout_seconds
        timeout = max(10, min(300, int(timeout)))
        retries = max(1, min(5, int(cfg.check_timeout_retries)))
        check_history = state_manager.get_check_history()
        if selected_unmanaged:
            print(f"\nChecking unmanaged application: {selected_unmanaged}\n")
        else:
            print(f"\nFound {len(unmanaged_apps)} unmanaged application(s) in system registry:\n")
        for sys_app in unmanaged_apps:
            if selected_unmanaged and sys_app.name != selected_unmanaged:
                continue
            history = check_history.get(sys_app.name.lower())
            if not parsed.all and history and history.user_choice in ("ignored", "managed"):
                label = "ignored by user" if history.user_choice == "ignored" else "already managed by ohub"
                print(f"  {sys_app.name} (v{sys_app.version}) - {label} (from history)")
                continue
            elif not parsed.all and history and history.error:
                print(f"  {sys_app.name} (v{sys_app.version}) - previous error: {history.error} (use --all to retry)")
                continue

            print(f"  {sys_app.name} (v{sys_app.version}) - not managed by ohub")
            print("    Searching GitHub for repository match...")

            # Build a clean search query by removing ALL version-like tokens
            # (e.g. "OnionHop V3 version 3.7.10" -> "OnionHop"), then try
            # progressively shorter queries and finally the raw name.
            queries = _progressive_queries(sys_app.name)
            search_result: dict = {"items": []}
            for q in queries:
                search_result = _search_with_timeout(
                    client, timeout, retries,
                    query=q, min_stars=0, ignore_case=True, active_only=False,
                )
                if search_result.get("items"):
                    break
                if search_result.get("error") == "rate_limit":
                    # Unauthenticated searches are tightly rate-limited; further
                    # queries in this pass will also fail, so stop here.
                    break

            query = _clean_app_query(sys_app.name) or sys_app.name
            if search_result.get("error") == "rate_limit":
                print("    [!] Rate limited - set a token with: ohub config set github_token <token>")
                state_manager.add_check_history(CheckHistoryEntry(
                    app_name=sys_app.name, app_version=sys_app.version,
                    user_choice="error", checked_at=int(datetime.now().timestamp()), error="rate_limit"))
                state_manager.save()
                continue
            if search_result.get("error") == "timeout":
                print(f"    Search timed out after {timeout}s (x{retries}) - skipping to next app.")
                state_manager.save()
                continue
            elif search_result.get("error"):
                print(f"    [!] Search failed: {search_result['error']}")
                state_manager.add_check_history(CheckHistoryEntry(
                    app_name=sys_app.name, app_version=sys_app.version,
                    user_choice="error", checked_at=int(datetime.now().timestamp()), error=search_result['error']))
                state_manager.save()
                continue

            # Exact match on the version-stripped name (repo name or owner/repo)
            q = query.lower()
            exact = next((r for r in search_result.get("items", [])
                          if r.get("name", "").lower() == q
                          or r.get("full_name", "").lower().endswith("/" + q)), None)
            if exact:
                repo_id = exact["full_name"]
                print(f"    Found exact match: {repo_id}")
                _check_add_or_ignore(parsed, state_manager, sys_app, repo_id)
            else:
                items = search_result.get("items", [])
                if items and parsed.candidates:
                    # --candidates: always show the list so the user picks
                    print(f"    Candidate repositories:")
                    for i, r in enumerate(items[:10]):
                        mark = " <=" if r is exact else ""
                        print(f"      [{i+1}] {r['full_name']} (★{r.get('stargazers_count', 0)}){mark}")
                    print(f"      [0] Skip - do not link")
                    sel = items[0] if parsed.yes else _select_from_options(items, "  Select repository to link", allow_skip=True)
                    if sel:
                        repo_id = sel["full_name"]
                        print(f"    Linking to: {repo_id}")
                        _check_add_or_ignore(parsed, state_manager, sys_app, repo_id)
                        continue
                    else:
                        print(f"    Skipped linking for '{sys_app.name}'.")
                        _check_record_ignored(state_manager, sys_app)
                elif exact:
                    repo_id = exact["full_name"]
                    print(f"    Found exact match: {repo_id}")
                    _check_add_or_ignore(parsed, state_manager, sys_app, repo_id)
                elif items:
                    # No --candidates: suggest the best-starred repo as the match
                    best = max(items, key=lambda r: r.get("stargazers_count", 0))
                    repo_id = best["full_name"]
                    print(f"    Best match by stars: {repo_id} (★{best.get('stargazers_count', 0)})")
                    confirm = "y" if parsed.yes else input(
                        f"    Link to {repo_id}? [y/N]: "
                    ).strip().lower()
                    if confirm == "y":
                        _check_add_or_ignore(parsed, state_manager, sys_app, repo_id)
                        continue
                    print(f"    Not linked.")
                else:
                    print(f"    No suitable GitHub repository found for '{sys_app.name}'.")
                    # Fall back to custom (non-GitHub) sources
                    if not _check_source_match(parsed, state_manager, sys_app):
                        print(f"    To manage it, add manually: ohub add <owner/{sys_app.name}>")
                        _check_record_ignored(state_manager, sys_app)

    if parsed.json:
        import json
        print(json.dumps(results, indent=2))

    return 0


def _check_source_match(parsed, state_manager, sys_app) -> bool:
    """During `ohub check`, see if an unmanaged app matches a custom source entry.

    Returns True if a source match was found (and acted on / recorded).
    """
    from obtainhub.core.sources import fetch_source_entries, entries_for_source

    try:
        config = get_config_manager().load()
        entries = fetch_source_entries(config)
    except Exception:
        return False
    if not entries:
        return False

    matches = [e for e in entries if e.name.lower() == sys_app.name.lower()]
    if not matches:
        return False

    # Group by source
    by_src: dict = {}
    for e in matches:
        by_src.setdefault(e.source_name, []).append(e)

    print(f"    Found in custom source(s): {', '.join(sorted(by_src))}")
    for src_name, src_entries in by_src.items():
        entry = src_entries[0]
        confirm = "y" if parsed.yes else input(
            f"    Install/update {entry.name} v{entry.version} from source '{src_name}'? [y/N]: "
        ).strip().lower()
        if confirm != "y":
            continue
        rc = _install_from_source(entry, src_name, parsed, get_config_manager(), state_manager)
        if rc == 0:
            state_manager.add_check_history(CheckHistoryEntry(
                app_name=sys_app.name, app_version=sys_app.version,
                github_repo=entry.repo_id, has_github_repo=bool(entry.repo_id),
                user_choice="managed", checked_at=int(datetime.now().timestamp())))
            state_manager.save()
            return True
    return True  # matched a source; don't fall through to "add manually"


def cmd_list(parsed: argparse.Namespace, state_manager: StateManager) -> int:
    """Handle list command."""
    apps = state_manager.get_all_apps()
    
    # By default show only ohub-managed apps, use --all to include unmanaged
    if not parsed.all:
        if parsed.json:
            import json
            print(json.dumps([a.to_dict() for a in apps], indent=2))
        else:
            if apps:
                print(f"{'Name':<40} {'Version':<15} {'Source':<15}")
                print("-" * 75)
                for app in apps:
                    print(f"{app.name:<40} {app.version:<15} {'ohub':<15}")
            else:
                print("No apps managed by ohub.")
                print("Use 'ohub list --all' to see all system-installed applications.")
        return 0
    
    # Show all system apps (managed + unmanaged) with --all flag
    system_apps = get_installed_system_apps()
    print(f"\nSystem-installed applications ({len(system_apps)} found):")
    
    # Find unmanaged apps (in registry but not in ohub state)
    ohub_app_ids = {app.id for app in apps}
    unmanaged_apps = []
    for sys_app in system_apps:
        # Check if this system app is already managed by ohub
        is_managed = False
        for app in apps:
            if app.name.lower() == sys_app.name.lower():
                is_managed = True
                break
        if not is_managed:
            unmanaged_apps.append(sys_app)

    if parsed.json:
        import json
        combined = [a.to_dict() for a in apps] + [a for a in unmanaged_apps]
        print(json.dumps(combined, indent=2))
    else:
        print(f"{'Name':<30} {'Version':<15} {'Type':<10} {'Source':<12}")
        print("-" * 70)
        for app in apps:
            loc = app.install_location if app.install_location else ""
            label = f"{app.app_type}"
            if loc:
                label += f" @ {loc}"
            print(f"{app.name:<30} {app.version:<15} {label:<10} {'ohub':<12}")
        for app in unmanaged_apps:
            print(f"{app.name:<30} {app.version:<15} {'-':<10} {'unmanaged':<12}")
        
        if unmanaged_apps:
            print(f"\n{len(unmanaged_apps)} unmanaged application(s) found.")
            print("Use 'ohub add <owner/repo>' to start managing them.")
    return 0


def cmd_uninstall(
    parsed: argparse.Namespace,
    config_manager: ConfigManager,
    state_manager: StateManager,
    logger,
) -> int:
    """Handle uninstall command."""
    app_id = _resolve_app_id(state_manager, parsed.app)

    if not parsed.yes:
        confirm = input(f"Uninstall {app_id}? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return 1

    app = state_manager.get_app(app_id)
    if not app:
        print(f"App not found in state: {app_id}", file=sys.stderr)
        return 1

    installer = SilentInstaller()
    success, message = installer.uninstall(app_id, interactive=parsed.interactive)

    if success:
        # Verify the app is actually gone from the system (EXE uninstallers may
        # return before finishing, and permission failures can surface late).
        still_present = any(
            sa.name.lower() == app.name.lower()
            for sa in get_installed_system_apps()
        )
        if still_present:
            print(f"Uninstall reported success but {app.name} is still present in the system.")
            print("It may still be running, or this is a permission issue - try running ohub as administrator.")
            return 1
        print(f"Success: {message}")
        state_manager.remove_app(app_id)
        _remove_app_source(config_manager, app_id, app)
        if not parsed.keep_data and app.installer_path:
            try:
                Path(app.installer_path).unlink(missing_ok=True)
            except Exception:
                pass
        print(f"Removed {app.name} from ohub management.")
        return 0

    # Uninstall produced no automatic method.
    print(f"Uninstall failed: {message}")
    if app.app_type == "github" and not app.install_location:
        # Never installed by ohub (added but no system uninstaller recorded),
        # or a portable EXE tracked only by ohub. Drop from management.
        state_manager.remove_app(app_id)
        _remove_app_source(config_manager, app_id, app)
        print(f"Removed {app.name} from ohub management (no system uninstaller was recorded).")
        return 0
    if "permission" in message.lower() or "access is denied" in message.lower():
        print("This looks like a permission issue - try running ohub as administrator.")
    else:
        print("Manual uninstall may be required. Use --keep-data to keep installer files.")
    return 1


def cmd_remove(
    parsed: argparse.Namespace,
    config_manager: ConfigManager,
    state_manager: StateManager,
    logger,
) -> int:
    """Remove an app/folder from ohub management (does NOT uninstall the app)."""
    app_id = _resolve_app_id(state_manager, parsed.app)

    app = state_manager.get_app(app_id)
    if not app:
        print(f"App not found in state: {app_id}", file=sys.stderr)
        return 1

    if not parsed.yes:
        confirm = input(f"Remove {app.name} ({app_id}) from ohub management? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return 1

    state_manager.remove_app(app_id)
    print(f"Removed {app.name} from ohub management.")
    return 0


def cmd_source(
    parsed: argparse.Namespace,
    config_manager: ConfigManager,
) -> int:
    """Handle source command."""
    config = config_manager.load()

    if parsed.source_action == "list":
        if not config.manifest_sources:
            print("No custom sources configured.")
        else:
            for src in config.manifest_sources:
                print(f"{src.name}: {src.url}")
        return 0

    elif parsed.source_action == "add":
        url = parsed.url.rstrip("/")
        src_type = getattr(parsed, "type", "github")
        # Validate the source actually serves installable content
        try:
            if src_type == "github":
                # Accept either a repo URL or a releases API URL
                if "/releases" in url and "api.github.com" in url:
                    api_url = url
                elif "github.com" in url and url.count("/") >= 4:
                    api_url = url.replace("https://github.com/", "https://api.github.com/repos/") + "/releases"
                else:
                    api_url = f"https://api.github.com/repos/{url}/releases"
                import requests
                resp = requests.get(api_url, timeout=20, headers={"Accept": "application/vnd.github.v3+json"})
                if resp.status_code == 404:
                    print(f"Error: GitHub repository not found: {url}", file=sys.stderr)
                    return 1
                resp.raise_for_status()
                releases = resp.json()
                if not isinstance(releases, list) or not releases or not releases[0].get("assets"):
                    print(f"Error: {url} has no releases/assets to install from.", file=sys.stderr)
                    return 1
            elif src_type == "manifest":
                import requests, json as _json
                resp = requests.get(url, timeout=20)
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, list):
                    print(f"Error: manifest source must be a JSON list of apps.", file=sys.stderr)
                    return 1
        except Exception as e:
            print(f"Error: could not validate source '{url}': {e}", file=sys.stderr)
            return 1
        config_manager.add_manifest_source(parsed.name, url, enabled=True, headers={}, src_type=src_type)
        print(f"Added source: {parsed.name} ({src_type}) -> {url}")
        return 0

    elif parsed.source_action == "remove":
        if config_manager.remove_manifest_source(parsed.name):
            print(f"Removed source: {parsed.name}")
        else:
            print(f"Source not found: {parsed.name}")
        return 0

    elif parsed.source_action == "verify":
        # Verify a custom source by fetching it and checking asset checksums
        from obtainhub.core.sources import fetch_source_entries
        config = config_manager.load()
        entries = fetch_source_entries(config)
        entry = None
        for e in entries:
            if e.name == parsed.name:
                entry = e
                break
        if not entry:
            print(f"Source not found: {parsed.name}", file=sys.stderr)
            return 1
        # Attempt a single GET to verify reachability and basic structure
        import requests, json as _json
        try:
            if entry.src_type == "github":
                api_url = entry.url.rstrip("/")
                resp = requests.get(api_url, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    # For GitHub releases API: check it has assets
                    if isinstance(data, list) and data and data[0].get("assets"):
                        print(f"Source '{parsed.name}' verified: GitHub releases with assets found")
                    elif isinstance(data, dict) and data.get("total_count", 0) > 0:
                        print(f"Source '{parsed.name}' verified: GitHub repo OK (total_count={data['total_count']})")
                    else:
                        print(f"Source '{parsed.name}' verified: GitHub repo reachable but no assets detected")
                else:
                    print(f"Source '{parsed.name}' verification failed: HTTP {resp.status_code}", file=sys.stderr)
                    return 1
            elif entry.src_type == "manifest":
                resp = requests.get(entry.url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    print(f"Source '{parsed.name}' verified: manifest list OK ({len(data)} entries)")
                else:
                    print(f"Source '{parsed.name}' verified: manifest reachable (non-list response)")
            else:
                print(f"Source '{parsed.name}' verification: OK (type={entry.src_type})")
        except Exception as e:
            print(f"Source '{parsed.name}' verification error: {e}", file=sys.stderr)
            return 1
        return 0

    else:
        print("Usage: ohub source <command> [options]")
        print("  list                 List configured sources")
        print("  add <name> <url>     Add a custom source (--type github|manifest)")
        print("  remove <name>        Remove a source")
    return 0


def cmd_add(
    parsed: argparse.Namespace,
    config_manager: ConfigManager,
    state_manager: StateManager,
    logger,
) -> int:
    """Handle add command.

    Modes (--type):
      github - add a GitHub repo for management (default)
      zip    - add a repo that only ships archive assets: download the archive,
               extract it to a folder, and track it for updates
      folder - add a local folder; --name (app name) is REQUIRED to find updates
    """
    if not parsed.repo:
        print("Error: specify a repository (owner/repo) or a folder path with --type folder", file=sys.stderr)
        return 1
    parsed.repo = parsed.repo.strip('"\'')

    # ---- Folder mode (local) ----
    if parsed.add_type == "folder":
        if not parsed.name:
            print("Error: --name is required for folder mode (the real application name).", file=sys.stderr)
            print("       Example: ohub add \"D:\\MyApp\" --type folder --name MyApp [--repo owner/MyApp]", file=sys.stderr)
            return 1
        folder = Path(parsed.repo).expanduser()
        if is_restricted_folder(folder):
            print(f"Error: refusing to scan '{folder}' - it is a filesystem root (e.g. C:\\).", file=sys.stderr)
            print("       ObtainHub only scans the folder root, never recursive child files/folders.", file=sys.stderr)
            return 1
        # Require the folder to actually contain a runnable app before tracking it
        if not scan_root_for_apps(folder):
            print(f"Error: '{folder}' does not contain an application yet (no .exe found).", file=sys.stderr)
            print("       Finish installing the application, then run 'ohub add' again.", file=sys.stderr)
            return 1
        try:
            add_folder_app(
                folder,
                name=parsed.name,
                repo=parsed.repo_arg or "",
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0

    # ---- GitHub / zip mode ----
    if "/" not in parsed.repo:
        print("Error: Repository must be in format 'owner/repo'", file=sys.stderr)
        return 1

    owner, repo_name = parsed.repo.split("/", 1)
    name = parsed.name or repo_name
    repo_id = f"{owner}/{repo_name}"

    token = config_manager.load().github_token
    client = GitHubClient(token=token)

    # Optional manifest source registration
    if parsed.as_source:
        from obtainhub.core.config import ManifestSource
        config = config_manager.load()
        config.sources.append(ManifestSource(
            name=name, url=f"https://api.github.com/repos/{owner}/{repo_name}", enabled=True, headers={}))
        config_manager.save(config)
        print(f"Registered source: {name} ({repo_id})")

    # Archived / inactive warning
    _warn_repo_status(client, repo_id)

    if parsed.add_type == "zip":
        release = client.get_latest_release(owner, repo_name, include_prerelease=parsed.prerelease)
        if not release:
            print(f"Error: No release found for {repo_id}", file=sys.stderr)
            return 1
        try:
            add_zip_app(repo_id, release, name=name, location=parsed.location)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0

    # github mode: just record the repo as managed (next check/install updates it)
    existing = state_manager.get_app(repo_id)
    if existing:
        print(f"{repo_id} is already managed.")
        return 0
    state_manager.add_installed_app({
        "id": repo_id,
        "name": name,
        "version": "",
        "installer_type": "github",
        "installer_path": "",
        "source_url": f"https://github.com/{owner}/{repo_name}",
        "tag": "",
        "app_type": "github",
    })
    print(f"Added {repo_id} to management. Run 'ohub install {repo_id}' or 'ohub check' to track versions.")
    return 0


def cmd_search(
    parsed: argparse.Namespace,
    config_manager: ConfigManager,
    logger,
) -> int:
    """Handle search command."""
    token = config_manager.load().github_token
    client = GitHubClient(token=token)
    
    result = client.search_repositories(
        query=parsed.query,
        min_stars=parsed.min_stars,
        ignore_case=True,
        active_only=parsed.active_only,
    )
    
    if result.get("error") == "rate_limit":
        print("[!] GitHub API rate limit exceeded (60 req/hr without token).")
        print("    Please set your GitHub token using: ohub config set github_token <your_token>")
        print("    This will increase your limit to 5000 req/hr.")
        return 1
    elif result.get("error"):
        print(f"[!] Search failed: {result['error']}")
        return 1
    
    repos = result.get("items", [])
    if not repos:
        print("No repositories found.")
        return 0
    
    repos = repos[:parsed.limit]
    
    if parsed.json:
        import json
        print(json.dumps(repos, indent=2))
    else:
        print(f"{'Repository':<40} {'Stars':<8} {'Latest Release':<18} {'Updated':<12} Description")
        print("-" * 105)
        for repo in repos:
            stars = repo.get("stargazers_count", 0)
            latest = repo.get("latest_release", "")
            if repo.get("latest_release_prerelease"):
                latest += " (pre)"
            updated = repo.get("updated_at", "")[:10] if repo.get("updated_at") else "N/A"
            desc = (repo.get("description") or "")[:45]
            print(f"{repo['full_name']:<40} {stars:<8} {latest:<18} {updated:<12} {desc}")
    
    return 0


def cmd_config(
    parsed: argparse.Namespace,
    config_manager: ConfigManager,
) -> int:
    """Handle config command."""
    config = config_manager.load()

    if parsed.config_action == "show":
        import json
        print(json.dumps(config.to_dict(), indent=2))
    elif parsed.config_action == "get":
        print(getattr(config, parsed.key, "Not found"))
    elif parsed.config_action == "set":
        setattr(config, parsed.key, parsed.value)
        config_manager.save(config)
        print(f"Set {parsed.key} = {parsed.value}")
    elif parsed.config_action == "edit":
        print("Editor not yet implemented. Use 'ohub config set' for now.")
    return 0


def cmd_self_update(
    parsed: argparse.Namespace,
    config_manager: ConfigManager,
    state_manager: StateManager,
    logger,
) -> int:
    """Handle self-update command."""
    from obtainhub import __version__
    import subprocess

    # Best-effort check: is ohub.exe already the running process?
    running = False
    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq ohub.exe', '/FO', 'LIST'],
            capture_output=True, text=True, timeout=10
        )
        running = 'ohub.exe' in result.stdout
    except Exception:
        running = False

    if running:
        print(
            'ohub is already running. Self-update will be performed the next '
            'time ohub exits. To check for updates in the background, add a '
            'Windows Task Scheduler trigger running '
            '"ohub check --all --timeout 300" periodically.'
        )
        return 0

    updater = SelfUpdater(config_manager, state_manager, current_version=__version__)
    result = updater.check_and_update(parsed.prerelease, parsed.force)
    if result:
        print(f"Update to {result} started. ohub will now exit so the installer can replace it.")
        print("Restart ohub after the update finishes.")
        # Return so main() exits and the detached installer can replace ohub.exe.
        return 0
    else:
        print("Already at latest version")
    return 0


if __name__ == "__main__":
    sys.exit(main())