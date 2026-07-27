#!/usr/bin/env python3
"""Main CLI entry point for ObtainHub."""

import sys
import argparse
from pathlib import Path
from typing import Optional

from obtainhub import __version__
from obtainhub.core.config import get_config_manager
from obtainhub.core.state import get_state_manager
from obtainhub.core.logger import get_logger, setup_logging, LogLevel
from obtainhub.core.self_updater import check_and_update
from obtainhub.core.exceptions import CLIError, CLIArgumentError
from obtainhub.utils.helpers import parse_owner_repo


logger = get_logger()


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser."""
    parser = argparse.ArgumentParser(
        prog="ohub",
        description="ObtainHub - GitHub-based Package Updater and Manager for Windows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ohub install microsoft/vscode
  ohub install owner/repo --download-only
  ohub update
  ohub check
  ohub source add my-source https://example.com/manifest.json

For more information, visit: https://github.com/ObtainHub/ObtainHub
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
        help="Skip self-update check on startup",
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
        help="Install an application from GitHub",
        description="Install an application from a GitHub repository",
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
        help="Update specific app only (format: owner/repo)",
    )
    update_parser.add_argument(
        "--force",
        action="store_true",
        help="Force update even if version appears same",
    )
    
    # check command
    check_parser = subparsers.add_parser(
        "check",
        help="Check for updates without installing",
        description="Check for available updates for installed applications",
    )
    check_parser.add_argument(
        "--app",
        help="Check specific app only (format: owner/repo)",
    )
    check_parser.add_argument(
        "--all",
        action="store_true",
        help="Check all apps including those with auto_update disabled",
    )
    
    # source command
    source_parser = subparsers.add_parser(
        "source",
        help="Manage manifest sources",
        description="Add, remove, or list custom manifest sources",
    )
    source_subparsers = source_parser.add_subparsers(dest="source_command", metavar="SUBCOMMAND")
    
    source_add = source_subparsers.add_parser("add", help="Add a manifest source")
    source_add.add_argument("name", help="Name for the source")
    source_add.add_argument("url", help="URL of the manifest source")
    
    source_remove = source_subparsers.add_parser("remove", help="Remove a manifest source")
    source_remove.add_argument("name", help="Name of the source to remove")
    
    source_list = source_subparsers.add_parser("list", help="List all manifest sources")
    
    # list command
    list_parser = subparsers.add_parser(
        "list",
        help="List installed applications",
        description="List all applications installed via ObtainHub",
    )
    list_parser.add_argument(
        "--outdated",
        action="store_true",
        help="Show only outdated applications",
    )
    
    # info command
    info_parser = subparsers.add_parser(
        "info",
        help="Show information about an installed application",
        description="Display detailed information about an installed application",
    )
    info_parser.add_argument(
        "repo",
        help="Repository in format 'owner/repo'",
    )
    
    # uninstall command
    uninstall_parser = subparsers.add_parser(
        "uninstall",
        help="Uninstall an application",
        description="Uninstall an application installed via ObtainHub",
    )
    uninstall_parser.add_argument(
        "repo",
        help="Repository in format 'owner/repo'",
    )
    uninstall_parser.add_argument(
        "--keep-data",
        action="store_true",
        help="Keep application data and configuration",
    )
    
    return parser


def handle_self_update(args: argparse.Namespace, config_manager) -> bool:
    """Handle self-update check.
    
    Returns:
        True if update was performed and process should exit, False otherwise.
    """
    skip = args.skip_self_update or config_manager.config.skip_self_update
    return check_and_update(
        skip_check=skip,
        config_manager=config_manager,
    )


def cmd_install(args: argparse.Namespace, config_manager, state_manager) -> int:
    """Handle install command."""
    logger.section("Install Application")
    
    try:
        owner, repo = parse_owner_repo(args.repo)
    except ValueError as e:
        raise CLIArgumentError(str(e))
    
    logger.info(f"Installing {owner}/{repo}...")
    logger.warning("Install command not yet implemented")
    logger.info("This will be implemented in Step 2")
    return 0


def cmd_update(args: argparse.Namespace, config_manager, state_manager) -> int:
    """Handle update command."""
    logger.section("Update Applications")
    logger.warning("Update command not yet implemented")
    logger.info("This will be implemented in Step 2")
    return 0


def cmd_check(args: argparse.Namespace, config_manager, state_manager) -> int:
    """Handle check command."""
    logger.section("Check for Updates")
    logger.warning("Check command not yet implemented")
    logger.info("This will be implemented in Step 2")
    return 0


def cmd_source(args: argparse.Namespace, config_manager, state_manager) -> int:
    """Handle source command."""
    if args.source_command == "add":
        config_manager.config.add_manifest_source(args.url)
        config_manager.save()
        logger.success(f"Added manifest source '{args.name}': {args.url}")
    elif args.source_command == "remove":
        if config_manager.config.remove_manifest_source(args.url):
            config_manager.save()
            logger.success(f"Removed manifest source: {args.name}")
        else:
            logger.error(f"Source not found: {args.name}")
            return 1
    elif args.source_command == "list":
        logger.section("Manifest Sources")
        for i, source in enumerate(config_manager.config.manifest_sources, 1):
            logger.info(f"  {i}. {source}")
    else:
        logger.error("Unknown source subcommand")
        return 1
    return 0


def cmd_list(args: argparse.Namespace, config_manager, state_manager) -> int:
    """Handle list command."""
    logger.section("Installed Applications")
    
    apps = state_manager.get_all_apps()
    if not apps:
        logger.info("No applications installed")
        return 0
    
    if args.outdated:
        outdated = state_manager.get_outdated_apps()
        if not outdated:
            logger.info("All applications are up to date")
            return 0
        logger.info(f"Found {len(outdated)} outdated application(s):")
        for app, manifest in outdated:
            logger.info(f"  {app.full_name}: {app.version} -> {manifest.version}")
    else:
        logger.info(f"Found {len(apps)} installed application(s):")
        for app in apps:
            status = "✓" if app.is_installed else "✗"
            logger.info(f"  {status} {app.full_name} v{app.version} ({app.installer_type})")
    
    return 0


def cmd_info(args: argparse.Namespace, config_manager, state_manager) -> int:
    """Handle info command."""
    try:
        owner, repo = parse_owner_repo(args.repo)
    except ValueError as e:
        raise CLIArgumentError(str(e))
    
    app = state_manager.get_app(owner, repo)
    if not app:
        logger.error(f"Application not found: {owner}/{repo}")
        return 1
    
    logger.section(f"Application Info: {app.full_name}")
    logger.info(f"  Version:       {app.version}")
    logger.info(f"  Installer:     {app.installer_type}")
    logger.info(f"  Install Dir:   {app.install_dir or 'N/A'}")
    logger.info(f"  Executable:    {app.executable_path or 'N/A'}")
    logger.info(f"  Installed:     {app.installed_at}")
    logger.info(f"  Manifest URL:  {app.manifest_url or 'N/A'}")
    logger.info(f"  Release URL:   {app.release_url or 'N/A'}")
    logger.info(f"  Checksum:      {app.checksum or 'N/A'} ({app.checksum_algorithm})")
    logger.info(f"  File Size:     {app.file_size} bytes")
    logger.info(f"  Auto-update:   {'Yes' if app.auto_update else 'No'}")
    logger.info(f"  Status:        {'Installed' if app.is_installed else 'Not found'}")
    
    if app.metadata:
        logger.subsection("Metadata")
        for key, value in app.metadata.items():
            logger.info(f"  {key}: {value}")
    
    return 0


def cmd_uninstall(args: argparse.Namespace, config_manager, state_manager) -> int:
    """Handle uninstall command."""
    try:
        owner, repo = parse_owner_repo(args.repo)
    except ValueError as e:
        raise CLIArgumentError(str(e))
    
    app = state_manager.get_app(owner, repo)
    if not app:
        logger.error(f"Application not found: {owner}/{repo}")
        return 1
    
    logger.section(f"Uninstall: {app.full_name}")
    logger.warning("Uninstall command not yet implemented")
    logger.info("This will be implemented in Step 2")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)
    
    # Initialize config manager early for self-update check
    config_manager = get_config_manager(args.config_dir)
    config_manager.load()
    
    # Setup logging
    setup_logging(
        console_level=LogLevel.DEBUG if args.verbose else LogLevel.INFO,
        verbose=args.verbose,
    )
    
    # Handle self-update BEFORE any other command
    if handle_self_update(args, config_manager):
        return 0
    
    # If no command provided, show help
    if not args.command:
        parser.print_help()
        return 0
    
    # Initialize state manager
    state_manager = get_state_manager(config_manager.config_dir)
    state_manager.load()
    
    # Route to command handler
    command_handlers = {
        "install": cmd_install,
        "update": cmd_update,
        "check": cmd_check,
        "source": cmd_source,
        "list": cmd_list,
        "info": cmd_info,
        "uninstall": cmd_uninstall,
    }
    
    handler = command_handlers.get(args.command)
    if not handler:
        logger.error(f"Unknown command: {args.command}")
        parser.print_help()
        return 1
    
    try:
        return handler(args, config_manager, state_manager)
    except CLIArgumentError as e:
        logger.error(str(e))
        return 1
    except CLIError as e:
        logger.error(str(e))
        return 1
    except KeyboardInterrupt:
        logger.warning("\nOperation cancelled by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())