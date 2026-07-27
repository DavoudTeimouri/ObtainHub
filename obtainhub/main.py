#!/usr/bin/env python3
"""Main CLI entry point for ObtainHub."""

import sys
import argparse
from pathlib import Path
from typing import Optional

from obtainhub import __version__
from obtainhub.core.config import get_config_manager, get_config
from obtainhub.core.state import get_state_manager
from obtainhub.core.logger import get_logger, setup_logging, LogLevel
from obtainhub.core.self_updater import check_and_update
from obtainhub.core.exceptions import CLIError, CLIArgumentError
from obtainhub.core.asset_matcher import is_windows_x64
from obtainhub.utils.helpers import parse_owner_repo

logger = get_logger()


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser."""
    parser = argparse.ArgumentParser(
        prog="ohub",
        description="ObtainHub - GitHub-based Package Updater and Manager for Windows x64",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ohub install microsoft/vscode
  ohub install owner/repo --download-only
  ohub update
  ohub check
  ohub source add my-source https://example.com/manifest.json
  ohub config --set download_dir=D:\\Downloads\\ObtainHub

Global Options:
  --skip-self-update    Skip ObtainHub self-update check on startup
  --prerelease, -p      Include prerelease versions in checks/updates
  --verbose, -v         Enable verbose output
  --config-dir PATH     Use custom configuration directory

Note: ObtainHub only supports Windows x64. It installs .msi and -Setup.exe files.
Portable .zip files are downloaded only (no auto-extract/install).
        """,
    )
    
    # Global options
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"ObtainHub {__version__}",
    )
    parser.add_argument(
        "--skip-self-update",
        action="store_true",
        help="Skip ObtainHub self-update check on startup",
    )
    parser.add_argument(
        "--prerelease", "-p",
        action="store_true",
        help="Include prerelease versions (requires confirmation)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        help="Custom configuration directory",
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    
    # install command
    install_parser = subparsers.add_parser(
        "install",
        help="Install an application from GitHub releases",
        description="Install an application from a GitHub repository's releases",
    )
    install_parser.add_argument(
        "repo",
        help="Repository in format 'owner/repo'",
    )
    install_parser.add_argument(
        "--download-only",
        action="store_true",
        help="Download installer only, do not execute",
    )
    install_parser.add_argument(
        "--version",
        help="Specific version to install (default: latest)",
    )
    install_parser.add_argument(
        "--source",
        help="Manifest source to use",
    )
    
    # update command
    update_parser = subparsers.add_parser(
        "update",
        help="Update all installed applications",
        description="Check for and install updates for all installed applications",
    )
    update_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check for updates without installing",
    )
    update_parser.add_argument(
        "--app",
        help="Update specific app only (owner/repo)",
    )
    
    # check command
    check_parser = subparsers.add_parser(
        "check",
        help="Check for available updates",
        description="Check for updates without installing",
    )
    check_parser.add_argument(
        "--app",
        help="Check specific app only (owner/repo)",
    )
    
    # source command
    source_parser = subparsers.add_parser(
        "source",
        help="Manage manifest sources",
        description="Add, remove, or list custom manifest sources",
    )
    source_subparsers = source_parser.add_subparsers(dest="source_action", metavar="ACTION")
    
    source_add = source_subparsers.add_parser("add", help="Add a manifest source")
    source_add.add_argument("name", help="Source name")
    source_add.add_argument("url", help="Manifest JSON URL")
    
    source_subparsers.add_parser("remove", help="Remove a manifest source").add_argument("name", help="Source name")
    source_subparsers.add_parser("list", help="List manifest sources")
    source_subparsers.add_parser("enable", help="Enable a manifest source").add_argument("name", help="Source name")
    source_subparsers.add_parser("disable", help="Disable a manifest source").add_argument("name", help="Source name")
    
    # config command
    config_parser = subparsers.add_parser(
        "config",
        help="View or modify configuration",
        description="Display or change ObtainHub configuration",
    )
    config_parser.add_argument("--get", help="Get a config value")
    config_parser.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), help="Set a config value")
    config_parser.add_argument("--list", action="store_true", help="List all config values")
    config_parser.add_argument("--reset", action="store_true", help="Reset config to defaults")
    
    return parser


def confirm_prerelease(version: str) -> bool:
    """Prompt user for prerelease confirmation."""
    print(f"\nWarning: Version {version} is a Prerelease.")
    print("Are you sure you want to proceed? [y/N] ", end='', flush=True)
    try:
        response = input().strip().lower()
        return response == 'y'
    except (EOFError, KeyboardInterrupt):
        return False


def confirm_manual_uninstall(app_name: str) -> int:
    """Prompt user for manual uninstall action.
    
    Returns:
        1 = Attempt auto-uninstall
        2 = Manual (user will do it)
        0 = Abort
    """
    print(f"\nNotice: {app_name} requires manual uninstallation of the previous version.")
    print("Installer downloaded. Do you want ohub to attempt auto-uninstalling the previous version, or will you perform it manually?")
    print("[1: Attempt Auto-Uninstall / 2: Manual / Abort] ", end='', flush=True)
    try:
        response = input().strip()
        if response == '1':
            return 1
        elif response == '2':
            return 2
        return 0
    except (EOFError, KeyboardInterrupt):
        return 0


def handle_install(args, config, state_mgr) -> int:
    """Handle install command."""
    # Parse repo
    try:
        owner, repo = parse_owner_repo(args.repo)
    except ValueError as e:
        raise CLIArgumentError(str(e))
    
    logger.info(f"Installing {owner}/{repo}", repo=args.repo)
    
    # TODO: Implement actual install logic
    # This would:
    # 1. Fetch release info from GitHub
    # 2. Use asset_matcher to find best installer
    # 3. Handle prerelease confirmation
    # 4. Handle ZIP download-only fallback
    # 5. Handle manual uninstall prompt
    # 6. Download and execute installer
    # 7. Update state
    
    print(f"Install command for {owner}/{repo} - not yet implemented")
    if args.download_only:
        print("  (download-only mode)")
    if args.version:
        print(f"  (version: {args.version})")
    if args.source:
        print(f"  (source: {args.source})")
    
    return 0


def handle_update(args, config, state_mgr) -> int:
    """Handle update command."""
    logger.info("Checking for updates")
    
    if args.dry_run:
        print("Update check (dry-run) - not yet implemented")
    else:
        print("Update - not yet implemented")
    if args.app:
        print(f"  (app: {args.app})")
    
    return 0


def handle_check(args, config, state_mgr) -> int:
    """Handle check command."""
    logger.info("Checking for updates")
    print("Check for updates - not yet implemented")
    if args.app:
        print(f"  (app: {args.app})")
    return 0


def handle_source(args, config_mgr) -> int:
    """Handle source command."""
    if args.source_action == "add":
        config_mgr.add_manifest_source(args.name, args.url)
        print(f"Added manifest source: {args.name} -> {args.url}")
    elif args.source_action == "remove":
        if config_mgr.remove_manifest_source(args.name):
            print(f"Removed manifest source: {args.name}")
        else:
            print(f"Source not found: {args.name}")
            return 1
    elif args.source_action == "list":
        sources = config_mgr.get_enabled_manifest_sources()
        if sources:
            for s in sources:
                status = "enabled" if s.enabled else "disabled"
                print(f"  {s.name} ({status}): {s.url}")
        else:
            print("No manifest sources configured")
    elif args.source_action == "enable":
        # TODO: implement
        print(f"Enable source: {args.name} - not yet implemented")
    elif args.source_action == "disable":
        # TODO: implement
        print(f"Disable source: {args.name} - not yet implemented")
    else:
        print("Source action required: add, remove, list, enable, disable")
        return 1
    return 0


def handle_config(args, config_mgr) -> int:
    """Handle config command."""
    config = config_mgr.load()
    
    if args.list:
        data = config.to_dict()
        for key, value in sorted(data.items()):
            if key == "github_token" and value:
                value = "***REDACTED***"
            print(f"  {key}: {value}")
    elif args.get:
        value = getattr(config, args.get, None)
        if value is not None:
            if args.get == "github_token" and value:
                print("***REDACTED***")
            else:
                print(value)
        else:
            print(f"Unknown config key: {args.get}")
            return 1
    elif args.set:
        key, value = args.set
        # Type conversion
        if key in ("update_interval_hours", "max_parallel_downloads"):
            value = int(value)
        elif key in ("auto_update", "allow_prerelease", "skip_self_update", "auto_confirm_prerelease"):
            value = value.lower() in ("true", "1", "yes", "on")
        config_mgr.set(key, value)
        print(f"Set {key} = {value}")
    elif args.reset:
        config_mgr.reset()
        print("Configuration reset to defaults")
    else:
        print("Config action required: --get, --set, --list, or --reset")
        return 1
    return 0


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Platform check - ObtainHub only runs on Windows x64
    if not is_windows_x64():
        print("Error: ObtainHub only supports Windows x64 (64-bit).", file=sys.stderr)
        print(f"Current platform: {sys.platform}, architecture: {__import__('platform').machine()}", file=sys.stderr)
        return 1
    
    # Set up logging
    log_level = LogLevel.DEBUG if args.verbose else LogLevel.INFO
    config_mgr = get_config_manager(args.config_dir)
    try:
        config = config_mgr.load()
        log_level = LogLevel[config.log_level]
    except Exception:
        pass
    setup_logging(level=log_level)
    
    # Initialize state manager
    state_mgr = get_state_manager()
    
    # Global options
    skip_self_update = args.skip_self_update or config.skip_self_update
    allow_prerelease = args.prerelease or config.allow_prerelease
    
    # Self-update check (before any subcommand)
    if not skip_self_update and args.command != "config":
        try:
            updated = check_and_update(
                current_version=__version__,
                allow_prerelease=allow_prerelease,
                skip_self_update=skip_self_update,
            )
            if updated:
                # If self-update happened, we should have exited
                return 0
        except Exception as e:
            logger.warning(f"Self-update check failed: {e}")
            # Continue anyway
    
    # Handle commands
    if not args.command:
        parser.print_help()
        return 0
    
    try:
        if args.command == "install":
            return handle_install(args, config, state_mgr)
        elif args.command == "update":
            return handle_update(args, config, state_mgr)
        elif args.command == "check":
            return handle_check(args, config, state_mgr)
        elif args.command == "source":
            return handle_source(args, config_mgr)
        elif args.command == "config":
            return handle_config(args, config_mgr)
        else:
            parser.print_help()
            return 1
    except CLIError as e:
        logger.error(str(e))
        return 1
    except KeyboardInterrupt:
        print("\nAborted.")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())