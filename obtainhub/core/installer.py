"""Windows silent installer engine for ObtainHub."""

import os
import subprocess
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Tuple

from obtainhub.core.asset_matcher import InstallerType
from obtainhub.core.config import get_config_manager
from obtainhub.core.exceptions import (
    InstallerError,
    InstallerExecutionError,
    InstallerUnsupportedTypeError,
    ManualUninstallRequired,
)
from obtainhub.core.logger import get_logger
from obtainhub.core.state import get_state_manager, InstalledApp


logger = get_logger(__name__)


class InstallResult(Enum):
    """Result of installation attempt."""
    SUCCESS = "success"
    DOWNLOAD_ONLY = "download_only"
    MANUAL_UNINSTALL_REQUIRED = "manual_uninstall_required"
    FAILED = "failed"


class SilentInstaller:
    """Execute Windows installers silently."""

    MSI_INSTALL_ARGS = ["/i", "/qn", "/norestart"]
    MSI_UNINSTALL_ARGS = ["/x", "/qn", "/norestart"]

    INNO_SETUP_FLAGS = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"]
    NSIS_FLAGS = ["/S"]
    WISE_FLAGS = ["/S"]
    INSTALLSHIELD_FLAGS = ["/s", "/v/qn"]
    GENERIC_EXE_FLAGS = ["/silent", "/quiet", "/q"]

    def __init__(
        self,
        download_dir: Optional[str] = None,
        dry_run: bool = False,
    ):
        """
        Initialize installer.

        Args:
            download_dir: Directory containing downloaded installers
            dry_run: If True, don't actually execute installers
        """
        self.dry_run = dry_run

        if download_dir:
            self.download_dir = Path(download_dir)
        else:
            config = get_config_manager().load()
            self.download_dir = Path(config.download_dir)

        self.state_manager = get_state_manager()

    def install(
        self,
        file_path: Path,
        installer_type: InstallerType,
        app_id: str,
        force: bool = False,
        download_only: bool = False,
    ) -> Tuple[InstallResult, str]:
        """
        Install an application.

        Args:
            file_path: Path to installer file
            installer_type: Type of installer
            app_id: App identifier (owner/repo)
            force: Force reinstall even if already installed
            download_only: Only download, don't install

        Returns:
            Tuple of (InstallResult, message)
        """
        if not file_path.exists():
            return InstallResult.FAILED, f"Installer not found: {file_path}"

        # Check for existing installation
        existing = self.state_manager.get_installed_app(app_id)
        if existing and not force:
            # Check if manual uninstall is required
            if existing.requires_manual_uninstall:
                return InstallResult.MANUAL_UNINSTALL_REQUIRED, (
                    f"Notice: {existing.name} requires manual uninstallation of the previous version.\n"
                    f"Installer downloaded to: {file_path}\n"
                    f"Options: [1] Attempt auto-uninstall [2] Cancel / Manual uninstall"
                )

        # Handle download-only mode
        if download_only or installer_type == InstallerType.ZIP:
            return InstallResult.DOWNLOAD_ONLY, (
                f"Downloaded {file_path.name} to {file_path}. "
                f"ZIP files are download-only."
            )

        # Execute installer based on type
        if installer_type == InstallerType.MSI:
            return self._install_msi(file_path, app_id)
        elif installer_type == InstallerType.EXE:
            return self._install_exe(file_path, app_id)
        else:
            return InstallResult.FAILED, f"Unsupported installer type: {installer_type}"

    def _install_msi(self, file_path: Path, app_id: str) -> Tuple[InstallResult, str]:
        """Install MSI package silently."""
        logger.info(f"Installing MSI: {file_path}")

        if self.dry_run:
            return InstallResult.SUCCESS, f"[DRY RUN] Would install MSI: {file_path}"

        args = ["msiexec"] + self.MSI_INSTALL_ARGS + [str(file_path)]

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                logger.info(f"MSI install successful: {file_path}")
                return InstallResult.SUCCESS, f"Successfully installed {file_path.name}"
            elif result.returncode == 1605:
                # ERROR_UNKNOWN_PRODUCT - not installed, try install anyway
                logger.warning(f"MSI product not found for uninstall, continuing: {result.stderr}")
                return InstallResult.FAILED, f"MSI install failed (product unknown): {result.stderr}"
            elif result.returncode == 1618:
                # ERROR_INSTALL_ALREADY_RUNNING
                raise InstallerExecutionError(
                    "Another installation is in progress",
                    exit_code=result.returncode,
                    details={"stdout": result.stdout, "stderr": result.stderr},
                )
            elif result.returncode == 1641:
                # ERROR_SUCCESS_REBOOT_INITIATED
                logger.info(f"MSI install requires reboot: {file_path}")
                return InstallResult.SUCCESS, f"Installed {file_path.name} (reboot required)"
            elif result.returncode == 3010:
                # ERROR_SUCCESS_REBOOT_REQUIRED
                logger.info(f"MSI install requires reboot: {file_path}")
                return InstallResult.SUCCESS, f"Installed {file_path.name} (reboot required)"
            else:
                logger.error(f"MSI install failed (exit {result.returncode}): {result.stderr}")
                raise InstallerExecutionError(
                    f"MSI install failed with exit code {result.returncode}",
                    exit_code=result.returncode,
                    details={"stdout": result.stdout, "stderr": result.stderr},
                )

        except subprocess.TimeoutExpired:
            raise InstallerExecutionError("MSI installation timed out")
        except InstallerExecutionError:
            raise
        except Exception as e:
            raise InstallerExecutionError(f"MSI installation error: {e}")

    def _install_exe(self, file_path: Path, app_id: str) -> Tuple[InstallResult, str]:
        """Install EXE installer silently with detected flags."""
        logger.info(f"Installing EXE: {file_path}")

        if self.dry_run:
            return InstallResult.SUCCESS, f"[DRY RUN] Would install EXE: {file_path}"

        # Try different silent flag combinations
        flag_sets = [
            self.INNO_SETUP_FLAGS,
            self.NSIS_FLAGS,
            self.WISE_FLAGS,
            self.INSTALLSHIELD_FLAGS,
            self.GENERIC_EXE_FLAGS,
        ]

        last_error = None
        for flags in flag_sets:
            args = [str(file_path)] + flags
            logger.debug(f"Trying flags: {flags}")

            try:
                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                if result.returncode == 0:
                    logger.info(f"EXE install successful with flags {flags}: {file_path}")
                    return InstallResult.SUCCESS, f"Successfully installed {file_path.name}"
                else:
                    logger.debug(f"Flags {flags} failed (exit {result.returncode}): {result.stderr}")
                    last_error = f"Exit {result.returncode}: {result.stderr}"

            except subprocess.TimeoutExpired:
                last_error = "Installation timed out"
                continue
            except Exception as e:
                last_error = str(e)
                continue

        # If all flag sets failed, try without flags
        logger.warning(f"All silent flag sets failed for {file_path}, trying without flags")
        try:
            result = subprocess.run(
                [str(file_path)],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                logger.info(f"EXE install successful without flags: {file_path}")
                return InstallResult.SUCCESS, f"Successfully installed {file_path.name}"
        except Exception as e:
            logger.error(f"EXE install without flags also failed: {e}")

        raise InstallerExecutionError(
            f"EXE installation failed with all silent flag combinations. Last error: {last_error}",
            exit_code=result.returncode if 'result' in locals() else None,
        )

    def uninstall(
        self,
        app_id: str,
        force: bool = False,
    ) -> Tuple[bool, str]:
        """
        Uninstall an application.

        Args:
            app_id: App identifier (owner/repo)
            force: Force uninstall even if not tracked

        Returns:
            Tuple of (success, message)
        """
        app = self.state_manager.get_installed_app(app_id)
        if not app and not force:
            return False, f"App not found in state: {app_id}"

        # Try MSI uninstall first if we have the product code
        if app and app.installer_type == InstallerType.MSI.value and app.install_path:
            return self._uninstall_msi(app)

        # Try EXE uninstall
        if app and app.installer_type == InstallerType.EXE.value and app.install_path:
            return self._uninstall_exe(app)

        return False, "No uninstall method available (manual uninstall required)"

    def _uninstall_msi(self, app: InstalledApp) -> Tuple[bool, str]:
        """Uninstall MSI package."""
        logger.info(f"Uninstalling MSI: {app.name}")

        if self.dry_run:
            return True, f"[DRY RUN] Would uninstall MSI: {app.name}"

        # Try to find MSI product code from installer path
        installer_path = Path(app.installer_path) if app.installer_path else None

        if installer_path and installer_path.exists():
            args = ["msiexec"] + self.MSI_UNINSTALL_ARGS + [str(installer_path)]

            try:
                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                if result.returncode == 0:
                    logger.info(f"MSI uninstall successful: {app.name}")
                    return True, f"Successfully uninstalled {app.name}"
                else:
                    logger.error(f"MSI uninstall failed (exit {result.returncode}): {result.stderr}")
                    return False, f"MSI uninstall failed: {result.stderr}"

            except subprocess.TimeoutExpired:
                return False, "MSI uninstall timed out"
            except Exception as e:
                return False, f"MSI uninstall error: {e}"

        return False, "MSI installer file not found for uninstall"

    def _uninstall_exe(self, app: InstalledApp) -> Tuple[bool, str]:
        """Uninstall EXE installer."""
        logger.info(f"Uninstalling EXE: {app.name}")

        if self.dry_run:
            return True, f"[DRY RUN] Would uninstall EXE: {app.name}"

        installer_path = Path(app.installer_path) if app.installer_path else None

        if installer_path and installer_path.exists():
            # Common uninstall flags
            uninstall_flags = [
                ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                ["/S"],
                ["/silent"],
                ["/quiet"],
                ["/uninstall", "/quiet"],
            ]

            for flags in uninstall_flags:
                args = [str(installer_path)] + flags
                try:
                    result = subprocess.run(
                        args,
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    if result.returncode == 0:
                        logger.info(f"EXE uninstall successful: {app.name}")
                        return True, f"Successfully uninstalled {app.name}"
                except Exception:
                    continue

        return False, "EXE uninstall failed (manual uninstall required)"

    def record_installation(
        self,
        app_id: str,
        name: str,
        version: str,
        installer_type: InstallerType,
        installer_path: str,
        source_url: str,
        tag: str,
    ) -> InstalledApp:
        """
        Record successful installation in state.

        Args:
            app_id: App identifier (owner/repo)
            name: App display name
            version: Version string
            installer_type: Type of installer
            installer_path: Path to installer file
            source_url: GitHub release URL
            tag: Release tag

        Returns:
            InstalledApp object
        """
        import time
        app = InstalledApp(
            id=app_id,
            name=name,
            version=version,
            installer_type=installer_type.value,
            installer_path=installer_path,
            source_url=source_url,
            tag=tag,
            installed_at=int(time.time()),
            updated_at=int(time.time()),
        )

        self.state_manager.add_installed_app(app)
        logger.info(f"Recorded installation: {app_id} v{version}")
        return app

    def record_update(
        self,
        app_id: str,
        version: str,
        installer_type: InstallerType,
        installer_path: str,
        source_url: str,
        tag: str,
    ) -> InstalledApp:
        """
        Record app update in state.

        Args:
            app_id: App identifier (owner/repo)
            version: New version string
            installer_type: Type of installer
            installer_path: Path to installer file
            source_url: GitHub release URL
            tag: Release tag

        Returns:
            Updated InstalledApp object
        """
        import time
        app = self.state_manager.get_installed_app(app_id)
        if not app:
            raise InstallerError(f"App not found for update: {app_id}")

        app.version = version
        app.installer_type = installer_type.value
        app.installer_path = installer_path
        app.source_url = source_url
        app.tag = tag
        app.updated_at = int(time.time())

        self.state_manager.add_installed_app(app)
        logger.info(f"Recorded update: {app_id} v{version}")
        return app


def install_app(
    file_path: Path,
    installer_type: InstallerType,
    app_id: str,
    download_only: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> Tuple[InstallResult, str]:
    """
    Convenience function to install an app.

    Args:
        file_path: Path to installer
        installer_type: Type of installer
        app_id: App identifier
        download_only: Only download, don't install
        force: Force reinstall
        dry_run: Don't actually execute

    Returns:
        Tuple of (InstallResult, message)
    """
    installer = SilentInstaller(dry_run=dry_run)
    return installer.install(file_path, installer_type, app_id, force, download_only)