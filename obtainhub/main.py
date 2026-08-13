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
        version="ObtainHub v0.3.0.0 - GitHub-based Package Updater and Manager for Windows x64\n"
                "Homepage: https://github.com/DavoudTeimouri/ObtainHub\n"
                "License: MIT"
    )
    parser.add_argument(
        "--skip-self-update", action="store_true", help="Skip self-update check on startup"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # install
    install_parser = subparsers.add_parser("install", help="Install an app")
    install_parser.add_argument("app", help="App identifier (owner/repo)")
    install_parser.add_argument("--tag", help="Specific release tag")
    install_parser.add_argument(
        "--prerelease", action="store_true", help="Allow prerelease versions"
    )
    install_parser.add_argument(
        "--force", action="store_true", help="Force reinstall"
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

        # Self-update check (unless skipped)
        if not parsed.skip_self_update and parsed.command != "self-update":
            config = config_manager.load()
            if config.self_update_enabled:
                try:
                    from obtainhub import __version__
                    updater = SelfUpdater(config_manager, state_manager, current_version=__version__)
                    result = updater.check_and_update(parsed.prerelease if hasattr(parsed, 'prerelease') else False, False)
                    if result:
                        print(f"Self-updated to {result}. Please re-run command.")
                        return 0
                except Exception:
                    logger.debug("Self-update check failed, continuing")

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
    downloaded_path = download_file(match.url, filename=match.name)
    pattern = AssetMatcher.derive_asset_pattern(match)

    itype = match.installer_type
    if itype in (InstallerType.EXE_SETUP, InstallerType.MSI, InstallerType.ZIP_INSTALLER):
        if not action:
            return True, f"Downloaded to {downloaded_path}"
        result, message = installer.install(
            downloaded_path, itype, app_id, force=True,
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
        try:
            extract_archive(downloaded_path, dest)
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



def _select_from_options(opts, prompt, allow_default=False):
    """Prompt user to pick from a list of AssetMatch options.

    Returns the chosen AssetMatch, or None to cancel. If ``allow_default`` is
    set, choice 0 selects ``opts[0]`` (the recommended default).
    """
    if not opts:
        return None
    try:
        if allow_default:
            choice = input(prompt + f" [0-{len(opts)}]: ").strip()
            if choice == "" or choice == "0":
                return opts[0]
            if choice.isdigit() and 1 <= int(choice) <= len(opts):
                return opts[int(choice) - 1]
        else:
            choice = input(prompt + f" [1-{len(opts)}]: ").strip()
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
        return repo_id.split("/", 1)

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


def cmd_install(
    parsed: argparse.Namespace,
    config_manager: ConfigManager,
    state_manager: StateManager,
    logger,
) -> int:
    app_id = _resolve_app_id(state_manager, parsed.app)
    logger.info(f"Installing {app_id}")

    # Parse owner/repo
    if "/" not in app_id:
        print(f"Error: App must be in format 'owner/repo'", file=sys.stderr)
        return 1
    owner, repo = app_id.split("/", 1)

    # Get GitHub client
    token = config_manager.load().github_token
    client = GitHubClient(token=token)

    # Fetch release
    if parsed.tag:
        release = client.get_release_by_tag(owner, repo, parsed.tag)
    else:
        release = client.get_latest_release(owner, repo, include_prerelease=parsed.prerelease)
    
    if not release:
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
            print(f"  [0] Use current selection: {match.name}")
            sel = _select_from_options(installer_options, "Select installer", allow_default=True)
            if sel:
                match = sel

    print(f"Found: {match.name} ({match.architecture.value}, {match.installer_type.name})")

    # Portable archive (ZIP / standalone EXE chosen as target): extract to a folder
    if match.installer_type in (InstallerType.ZIP, InstallerType.ZIP_INSTALLER) and not parsed.download_only:
        try:
            app = add_zip_app(
                app_id, release,
                name=parsed.name or repo,
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


def cmd_update(
    parsed: argparse.Namespace,
    config_manager: ConfigManager,
    state_manager: StateManager,
    logger,
) -> int:
    """Handle update command."""
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

            owner, repo = _resolve_repo_for_app(client, app, state_manager, parsed)
            if not owner:
                continue

            release = client.get_latest_release(owner, repo, include_prerelease=parsed.prerelease)

            if not release:
                print(f"  Skipping {app_id}: no release found")
                continue

            # Archived / inactive warning
            _warn_repo_status(client, app_id)

            current_version = app.version
            latest_version = release.get('tag_name', '').lstrip("v")
            has_update = latest_version > current_version

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
                    print(f"    [0] Use default: {match.name} ({match.architecture.value}, {match.installer_type.name})")
                    sel = _select_from_options(installer_options, "  Select installer", allow_default=True)
                    if sel:
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
    - Unmanaged apps: try to find the EXACT matching GitHub repo; candidates list
      removed by design - only an exact match is offered for linking.
    """
    token = config_manager.load().github_token
    client = GitHubClient(token=token)
    matcher = AssetMatcher(allow_arm64=False, allow_x86_fallback=False, require_installer=True)

    apps_to_check = []
    if parsed.app:
        apps_to_check = [parsed.app]
    else:
        apps = state_manager.get_all_apps()
        apps_to_check = [app.id for app in apps]

    # Unmanaged system apps - only scanned with --all (avoid re-scanning everything)
    system_apps = get_installed_system_apps()
    ohub_app_names = {app.name.lower() for app in state_manager.get_all_apps()}
    unmanaged_apps = [sa for sa in system_apps if sa.name.lower() not in ohub_app_names]

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

            if app.app_type == "folder":
                if app.github_repo:
                    owner, repo = app.github_repo.split("/", 1)
                else:
                    print(f"  {app.name} ({app_id}): folder-managed, no remote check")
                    continue
            else:
                owner, repo = app_id.split("/")
            release = client.get_latest_release(owner, repo, include_prerelease=parsed.prerelease)

            if not release:
                print(f"  {app.name} ({app_id}): no release found")
                continue

            current_version = app.version
            latest_version = release.get('tag_name', '').lstrip("v")
            has_update = latest_version > current_version

            _warn_repo_status(client, app_id)

            # Prefer saved asset pattern, then strict installer, then candidates
            match = matcher.get_best_match(release.get('assets', []))
            if app.app_type == "zip" and not match:
                match = matcher.match_by_pattern(release.get('assets', []), app.asset_pattern)

            candidates = matcher.get_installable_candidates(release.get('assets', []))
            strict = [m for m in candidates if m.installer_type in (InstallerType.EXE_SETUP, InstallerType.MSI, InstallerType.ZIP_INSTALLER)]

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
                    if not strict and candidates:
                        print(f"  {app.name} ({app_id})")
                        print(f"    Current:  {current_version}")
                        print(f"    Latest:   {latest_version}")
                        print(f"    Status:   Up to date")
                        print(f"    No installer package - available assets:")
                        for i, opt in enumerate(candidates):
                            print(f"      [{i+1}] {opt.name} ({opt.architecture.value}, {opt.installer_type.name}, {opt.size} bytes)")
                        _pick_candidate(candidates, app_id, state_manager, parsed)
                        print()
                    elif parsed.all:
                        print(f"  {app.name} ({app_id}): Up to date ({current_version})")

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
        check_history = state_manager.get_check_history()
        print(f"\nFound {len(unmanaged_apps)} unmanaged application(s) in system registry:\n")
        for sys_app in unmanaged_apps:
            history = check_history.get(sys_app.name.lower())
            if not parsed.all and history and history.user_choice in ("ignored", "managed"):
                label = "ignored by user" if history.user_choice == "ignored" else "already managed by ohub"
                print(f"  {sys_app.name} (v{sys_app.version}) - {label} (from history)")
                continue
            elif not parsed.all and history and history.error:
                print(f"  {sys_app.name} (v{sys_app.version}) - previous error: {history.error} (use --all to retry)")
                continue

            print(f"  {sys_app.name} (v{sys_app.version}) - not managed by ohub")
            print("    Searching GitHub for EXACT repository match...")

            search_result = client.search_repositories(
                query=sys_app.name, min_stars=0, ignore_case=True, active_only=False,
            )
            if search_result.get("error") == "rate_limit":
                print("    [!] Rate limited - set a token with: ohub config set github_token <token>")
                state_manager.add_check_history(CheckHistoryEntry(
                    app_name=sys_app.name, app_version=sys_app.version,
                    user_choice="error", checked_at=int(datetime.now().timestamp()), error="rate_limit"))
                state_manager.save()
                continue
            elif search_result.get("error"):
                print(f"    [!] Search failed: {search_result['error']}")
                state_manager.add_check_history(CheckHistoryEntry(
                    app_name=sys_app.name, app_version=sys_app.version,
                    user_choice="error", checked_at=int(datetime.now().timestamp()), error=search_result['error']))
                state_manager.save()
                continue

            # Exact full_name match only
            exact = next((r for r in search_result.get("items", [])
                          if r.get("name", "").lower() == sys_app.name.lower()
                          or r.get("full_name", "").lower().endswith("/" + sys_app.name.lower())), None)
            if exact:
                repo_id = exact["full_name"]
                print(f"    Found exact match: {repo_id}")
                _check_add_or_ignore(parsed, state_manager, sys_app, repo_id)
            else:
                if parsed.candidates:
                    items = search_result.get("items", [])
                    if items:
                        print(f"    No exact match. Candidate repositories:")
                        for i, r in enumerate(items[:10]):
                            print(f"      [{i+1}] {r['full_name']} (★{r.get('stargazers_count', 0)})")
                        sel = items[0] if parsed.yes else (_select_from_options(items, "  Select repository to link") or items[0])
                        if sel:
                            repo_id = sel["full_name"]
                            print(f"    Linking to: {repo_id}")
                            _check_add_or_ignore(parsed, state_manager, sys_app, repo_id)
                            continue
                print(f"    No exact GitHub repository found for '{sys_app.name}'.")
                print(f"    To manage it, add manually: ohub add <owner/{sys_app.name}>")
                _check_record_ignored(state_manager, sys_app)

    if parsed.json:
        import json
        print(json.dumps(results, indent=2))

    return 0


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

    # Non-installer apps (zip/folder) have no MSI/EXE to remove
    if app.app_type in ("zip", "folder"):
        print(f"Removing tracked app: {app.name} ({app.app_type})")
        if app.install_location and not parsed.keep_data:
            try:
                import shutil
                shutil.rmtree(app.install_location, ignore_errors=True)
                print(f"Removed files at: {app.install_location}")
            except Exception as e:
                print(f"Could not remove files at {app.install_location}: {e}")
        state_manager.remove_app(app_id)
        return 0

    installer = SilentInstaller()
    success, message = installer.uninstall(app_id)

    if success:
        print(f"Success: {message}")
        # Remove from state
        state_manager.remove_app(app_id)
        # Optionally remove installer file
        if not parsed.keep_data and app.installer_path:
            try:
                Path(app.installer_path).unlink(missing_ok=True)
            except Exception:
                pass
        return 0
    else:
        print(f"Uninstall failed: {message}")
        print("Manual uninstall required. Use --keep-data to keep installer files.")
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
        config_manager.add_manifest_source(parsed.name, parsed.url, enabled=True, headers={})
        print(f"Added source: {parsed.name}")
        return 0

    elif parsed.source_action == "remove":
        if config_manager.remove_manifest_source(parsed.name):
            print(f"Removed source: {parsed.name}")
        else:
            print(f"Source not found: {parsed.name}")
        return 0

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
        try:
            add_folder_app(
                folder,
                name=parsed.name,
                recursive=parsed.recursive,
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
    updater = SelfUpdater(config_manager, state_manager, current_version=__version__)
    result = updater.check_and_update(parsed.prerelease, parsed.force)
    if result:
        print(f"Updated to {result}")
    else:
        print("Already at latest version")
    return 0


if __name__ == "__main__":
    sys.exit(main())