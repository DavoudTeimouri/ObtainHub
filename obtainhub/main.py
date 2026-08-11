"""ObtainHub CLI entry point."""

import sys
import argparse
import signal
import time
from datetime import datetime
from typing import List, Optional

from obtainhub.core.config import get_config_manager, ConfigManager, ManifestSource
from obtainhub.core.state import get_state_manager, StateManager, CheckHistoryEntry
from obtainhub.core.logger import setup_logging, get_logger, LogLevel
from obtainhub.core.self_updater import SelfUpdater, check_and_update
from obtainhub.core.github_client import GitHubClient
from obtainhub.core.asset_matcher import AssetMatcher, InstallerType
from obtainhub.core.downloader import download_file, Downloader
from obtainhub.core.installer import install_app, InstallResult, SilentInstaller
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
        "--version", action="version", version="%(prog)s 0.1.0-beta.5"
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
    add_parser = subparsers.add_parser("add", help="Add a GitHub repository (owner/repo)")
    add_parser.add_argument("repo", help="Repository in owner/repo format")
    add_parser.add_argument("--name", help="Custom name (default: repo name)")

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


def cmd_install(
    parsed: argparse.Namespace,
    config_manager: ConfigManager,
    state_manager: StateManager,
    logger,
) -> int:
    """Handle install command."""
    app_id = parsed.app
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

    # Match asset
    matcher = AssetMatcher(
        allow_arm64=False,
        allow_x86_fallback=False,
        require_installer=not parsed.download_only,
    )
    match = matcher.get_best_match(release.get('assets', []))

    if not match:
        print(f"Error: No suitable asset found for {app_id}", file=sys.stderr)
        return 1

    print(f"Found: {match.name} ({match.architecture.value}, {match.installer_type.name})")

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
    if parsed.download_only or match.installer_type == InstallerType.ZIP:
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
        apps_to_update = [parsed.app]
    else:
        apps = state_manager.get_all_apps()
        apps_to_update = [app.id for app in apps]

    if not apps_to_update:
        print("No apps to update.")
        return 0

    print(f"Checking updates for {len(apps_to_update)} app(s)...\n")

    updated_count = 0
    for app_id in apps_to_update:
        try:
            app = state_manager.get_app(app_id)
            if not app:
                print(f"Skipping {app_id}: not found in state")
                continue

            owner, repo = app_id.split("/", 1)
            release = client.get_latest_release(owner, repo, include_prerelease=parsed.prerelease)

            if not release:
                print(f"Skipping {app_id}: no release found")
                continue

            current_version = app.version
            latest_version = release.get('tag_name', '').lstrip("v")
            has_update = latest_version > current_version

            if not has_update:
                print(f"  {app.name} ({app_id}): Up to date ({current_version})")
                continue

            match = matcher.get_best_match(release.get('assets', []))
            if not match:
                print(f"  {app.name} ({app_id}): No suitable asset")
                continue

            print(f"  {app.name} ({app_id}): {current_version} -> {latest_version}")
            print(f"    Downloading {match.name}...")

            downloaded_path = download_file(match.url, filename=match.name)

            # Install
            result, message = installer.install(
                downloaded_path,
                match.installer_type,
                app_id,
                force=True,
            )

            if result == InstallResult.SUCCESS:
                print(f"  Success: {message}")
                installer.record_update(
                    app_id=app_id,
                    version=release.get('tag_name', '').lstrip("v"),
                    installer_type=match.installer_type,
                    installer_path=str(downloaded_path),
                    source_url=release.get('html_url', ''),
                    tag=release.get('tag_name', ''),
                )
                updated_count += 1
            elif result == InstallResult.MANUAL_UNINSTALL_REQUIRED:
                print(f"  {message}")
            else:
                print(f"  Failed: {message}")

        except Exception as e:
            logger.error(f"Failed to update {app_id}: {e}")
            print(f"  Error updating {app_id}: {e}")

    print(f"\nDone. Updated {updated_count}/{len(apps_to_update)} app(s).")
    return 0


def cmd_check(
    parsed: argparse.Namespace,
    config_manager: ConfigManager,
    state_manager: StateManager,
    logger,
) -> int:
    """Handle check command - check for updates without installing.
    
    Also checks unmanaged system apps and offers to add them to ohub management.
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

    # Also check unmanaged system apps
    system_apps = get_installed_system_apps()
    ohub_app_names = {app.name.lower() for app in state_manager.get_all_apps()}
    unmanaged_apps = [sa for sa in system_apps if sa.name.lower() not in ohub_app_names]

    if not apps_to_check and not unmanaged_apps:
        print("No apps to check.")
        return 0

    print(f"Checking updates for {len(apps_to_check)} managed app(s)...\n")

    results = []
    for app_id in apps_to_check:
        try:
            app = state_manager.get_app(app_id)
            if not app:
                print(f"Skipping {app_id}: not found in state")
                continue

            owner, repo = app_id.split("/", 1)
            release = client.get_latest_release(owner, repo, include_prerelease=parsed.prerelease)

            if not release:
                print(f"Skipping {app_id}: no release found")
                continue

            current_version = app.version
            latest_version = release.get('tag_name', '').lstrip("v")
            has_update = latest_version > current_version

            match = matcher.get_best_match(release.get('assets', []))
            asset_info = f"{match.name} ({match.installer_type.name})" if match else "No suitable asset"

            result = {
                "app": app_id,
                "current_version": current_version,
                "latest_version": latest_version,
                "has_update": has_update,
                "prerelease": release.get('prerelease', False),
                "asset": asset_info,
                "release_url": release.get('html_url', ''),
            }
            results.append(result)

            if not parsed.json:
                status = "UPDATE AVAILABLE" if has_update else "Up to date"
                prerelease_str = " (prerelease)" if release.get('prerelease', False) else ""
                print(f"  {app.name} ({app_id})")
                print(f"    Current:  {current_version}")
                print(f"    Latest:   {latest_version}{prerelease_str}")
                print(f"    Status:   {status}")
                print(f"    Asset:    {asset_info}")
                print()

        except Exception as e:
            logger.error(f"Failed to check {app_id}: {e}")
            result = {
                "app": app_id,
                "error": str(e),
            }
            results.append(result)
            if not parsed.json:
                print(f"  {app_id}: Error - {e}\n")

    # Check unmanaged apps
    if unmanaged_apps:
        check_history = state_manager.get_check_history()
        print(f"\nFound {len(unmanaged_apps)} unmanaged application(s) in system registry:\n")
        for sys_app in unmanaged_apps:
            # Check history first
            history = check_history.get(sys_app.name.lower())
            if history and history.user_choice == "ignored":
                print(f"  {sys_app.name} (v{sys_app.version}) - ignored by user")
                continue
            elif history and history.user_choice == "managed":
                print(f"  {sys_app.name} (v{sys_app.version}) - already managed by ohub")
                continue
            elif history and history.error:
                print(f"  {sys_app.name} (v{sys_app.version}) - previous error, retrying...")

            # Try to find GitHub repo for this app
            print(f"  {sys_app.name} (v{sys_app.version}) - not managed by ohub")
            print("    Checking GitHub for matching repository...")
            
            # Search for the app on GitHub with retry
            search_result = None
            for attempt in range(3):
                try:
                    search_result = client.search_repositories(
                        query=sys_app.name,
                        min_stars=0,
                        ignore_case=True,
                        active_only=True,
                    )
                    if search_result.get("error") != "rate_limit":
                        break
                except Exception as e:
                    if attempt < 2:
                        print(f"    [!] Search failed (attempt {attempt+1}/3): {e}, retrying in 10s...")
                        time.sleep(10)
                    else:
                        print(f"    [!] Search failed after 3 attempts: {e}")
                        search_result = {"error": str(e), "items": []}
            
            if not search_result:
                search_result = {"error": "timeout", "items": []}

            if search_result.get("error") == "rate_limit":
                print("    [!] Rate limited - skipping")
                entry = CheckHistoryEntry(
                    app_name=sys_app.name,
                    app_version=sys_app.version,
                    user_choice="error",
                    checked_at=int(datetime.now().timestamp()),
                    error="rate_limit"
                )
                state_manager.add_check_history(entry)
                continue
            elif search_result.get("error"):
                print(f"    [!] Search failed: {search_result['error']}")
                entry = CheckHistoryEntry(
                    app_name=sys_app.name,
                    app_version=sys_app.version,
                    user_choice="error",
                    checked_at=int(datetime.now().timestamp()),
                    error=search_result['error']
                )
                state_manager.add_check_history(entry)
                continue
            
            search_results = search_result.get("items", [])
            if search_results:
                # Try to find exact match
                exact_match = None
                for repo in search_results[:5]:
                    if repo.get('name', '').lower() == sys_app.name.lower():
                        exact_match = repo
                        break
                
                if exact_match:
                    owner = exact_match['owner']['login']
                    repo_name = exact_match['name']
                    print(f"    Found: {owner}/{repo_name}")
                    repo_id = f"{owner}/{repo_name}"
                    if not parsed.yes:
                        confirm = input(f"    Add {repo_id} to ohub management? [y/N]: ").strip().lower()
                        if confirm == "y":
                            # Add to state as managed app
                            from obtainhub.core.state import InstalledApp
                            from datetime import datetime
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
                                architecture="x64"
                            )
                            state_manager.add_installed_app(app_state)
                            print(f"    Added {repo_id} to ohub management")
                            entry = CheckHistoryEntry(
                                app_name=sys_app.name,
                                app_version=sys_app.version,
                                github_repo=repo_id,
                                has_github_repo=True,
                                user_choice="managed",
                                checked_at=int(datetime.now().timestamp())
                            )
                            state_manager.add_check_history(entry)
                        else:
                            print(f"    Skipped - not adding to ohub")
                            entry = CheckHistoryEntry(
                                app_name=sys_app.name,
                                app_version=sys_app.version,
                                github_repo=repo_id,
                                has_github_repo=True,
                                user_choice="ignored",
                                checked_at=int(datetime.now().timestamp())
                            )
                            state_manager.add_check_history(entry)
                    else:
                        # Auto-add with --yes
                        from obtainhub.core.state import InstalledApp
                        from datetime import datetime
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
                            architecture="x64"
                        )
                        state_manager.add_installed_app(app_state)
                        print(f"    Added {repo_id} to ohub management (auto)")
                        entry = CheckHistoryEntry(
                            app_name=sys_app.name,
                            app_version=sys_app.version,
                            github_repo=repo_id,
                            has_github_repo=True,
                            user_choice="managed",
                            checked_at=int(datetime.now().timestamp())
                        )
                        state_manager.add_check_history(entry)
                else:
                    print(f"    No exact match found on GitHub")
                    entry = CheckHistoryEntry(
                        app_name=sys_app.name,
                        app_version=sys_app.version,
                        has_github_repo=False,
                        user_choice="ignored",
                        checked_at=int(datetime.now().timestamp())
                    )
                    state_manager.add_check_history(entry)
            else:
                print(f"    Not found on GitHub")
                entry = CheckHistoryEntry(
                    app_name=sys_app.name,
                    app_version=sys_app.version,
                    has_github_repo=False,
                    user_choice="ignored",
                    checked_at=int(datetime.now().timestamp())
                )
                state_manager.add_check_history(entry)

    if parsed.json:
        import json
        print(json.dumps(results, indent=2))

    return 0


def cmd_list(parsed: argparse.Namespace, state_manager: StateManager) -> int:
    """Handle list command."""
    apps = state_manager.get_all_apps()

    # Include system apps by default
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
        print(f"{'Name':<40} {'Version':<15} {'Source':<15}")
        print("-" * 75)
        for app in apps:
            print(f"{app.name:<40} {app.version:<15} {'ohub':<15}")
        for app in unmanaged_apps:
            print(f"{app.name:<40} {app.version:<15} {'unmanaged':<15}")
        
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
    app_id = parsed.app

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
    """Handle add command - add a GitHub repository by owner/repo."""
    repo = parsed.repo
    
    if "/" not in repo:
        print(f"Error: Repository must be in format 'owner/repo'", file=sys.stderr)
        return 1
    
    owner, repo_name = repo.split("/", 1)
    name = parsed.name or repo_name
    
    # Create a source entry for this repo
    from obtainhub.core.config import ManifestSource
    source = ManifestSource(name=name, url=f"https://api.github.com/repos/{owner}/{repo_name}", enabled=True, headers={})
    
    config = config_manager.load()
    config.sources.append(source)
    config_manager.save(config)
    
    print(f"Added source: {name} ({owner}/{repo_name})")
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
        print("[!] GitHub API rate limit exceeded. Set GITHUB_TOKEN env var to increase limit.")
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