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
from obtainhub.core.system_scanner import get_installed_system_apps


logger = get_logger(__name__)

# How long to wait for an interactive (visible) installer to finish.
INTERACTIVE_TIMEOUT = 900


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
        interactive: bool = False,
    ) -> Tuple[InstallResult, str]:
        """
        Install an application.

        Args:
            file_path: Path to installer file
            installer_type: Type of installer
            app_id: App identifier (owner/repo)
            force: Force reinstall even if already installed
            download_only: Only download, don't install
            interactive: Launch the installer visibly (no silent flags) and let the
                user drive it; ohub then verifies the result against system state.

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
            result, message = self._install_msi(file_path, app_id, interactive=interactive)
        elif installer_type in (InstallerType.EXE_SETUP, InstallerType.EXE_STANDALONE):
            result, message = self._install_exe(file_path, app_id, interactive=interactive)
        else:
            return InstallResult.FAILED, f"Unsupported installer type: {installer_type}"

        # Trust reality, not the exit code: verify the app is actually present
        # in the system before reporting success (installers can lie / hang / spawn).
        # Dry runs skip verification (nothing was actually installed).
        if not self.dry_run and result == InstallResult.SUCCESS:
            ok, detected = self._verify_installed(app_id)
            if not ok:
                return InstallResult.FAILED, (
                    f"Installer exited but {app_id} was not detected in the system "
                    f"(registry / install location). State not changed - re-run "
                    f"'ohub check' if it did install."
                )
            if detected:
                message = f"Successfully installed {file_path.name} (system version {detected})"
        return result, message

    def _verify_installed(self, app_id: str):
        """Check the system (registry / install location) for the installed app.

        Returns (detected: bool, detected_version: Optional[str]). We trust the
        system of record, not the installer's exit code.
        """
        repo = app_id.split("/", 1)[-1].lower()
        try:
            for sa in get_installed_system_apps():
                if sa.name.lower() == repo or repo in sa.name.lower():
                    return True, getattr(sa, "version", "") or ""
        except Exception as e:
            logger.debug(f"Registry scan failed during verification: {e}")
        # Fall back to a recorded install location that still exists on disk
        existing = self.state_manager.get_installed_app(app_id)
        if existing and getattr(existing, "install_location", ""):
            if Path(existing.install_location).exists():
                return True, getattr(existing, "version", "") or ""
        return False, None

    def _install_msi(self, file_path: Path, app_id: str, interactive: bool = False) -> Tuple[InstallResult, str]:
        """Install MSI package silently (or interactively when requested)."""
        logger.info(f"Installing MSI: {file_path}")

        if self.dry_run:
            return InstallResult.SUCCESS, f"[DRY RUN] Would install MSI: {file_path}"

        args = ["msiexec"] + self.MSI_INSTALL_ARGS + [str(file_path)]

        if interactive:
            # Visible, basic-UI install the user drives themselves; ohub waits.
            logger.info(f"Interactive MSI install: {file_path}")
            try:
                result = subprocess.run(
                    ["msiexec", "/i", str(file_path), "/qb!"],
                    timeout=INTERACTIVE_TIMEOUT,
                )
                if result.returncode == 0 or result.returncode in (1641, 3010):
                    return InstallResult.SUCCESS, f"Installer completed (interactive): {file_path.name}"
                return InstallResult.FAILED, f"Interactive MSI exited with code {result.returncode}"
            except subprocess.TimeoutExpired:
                return InstallResult.FAILED, "Interactive install timed out (installer still running?)"
            except Exception as e:
                return InstallResult.FAILED, f"Interactive install error: {e}"

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

    def _install_exe(self, file_path: Path, app_id: str, interactive: bool = False) -> Tuple[InstallResult, str]:
        """Install EXE installer silently with detected flags."""
        logger.info(f"Installing EXE: {file_path}")

        if self.dry_run:
            return InstallResult.SUCCESS, f"[DRY RUN] Would install EXE: {file_path}"

        if interactive:
            # Visible wizard the user drives; ohub waits for it to finish.
            logger.info(f"Interactive EXE install: {file_path}")
            try:
                result = subprocess.run([str(file_path)], timeout=INTERACTIVE_TIMEOUT)
                if result.returncode == 0:
                    return InstallResult.SUCCESS, f"Installer completed (interactive): {file_path.name}"
                return InstallResult.FAILED, f"Interactive install exited with code {result.returncode}"
            except subprocess.TimeoutExpired:
                return InstallResult.FAILED, "Interactive install timed out (installer still running?)"
            except Exception as e:
                return InstallResult.FAILED, f"Interactive install error: {e}"

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
        interactive: bool = False,
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

        # MSI uninstall (via product code / cached installer)
        if app and app.installer_type == InstallerType.MSI.value and app.install_path:
            return self._uninstall_msi(app, interactive=interactive)

        # EXE setup uninstall (via cached installer)
        if app and app.installer_type in (InstallerType.EXE_SETUP.value, InstallerType.EXE_STANDALONE.value) and app.installer_path:
            return self._uninstall_exe(app, interactive=interactive)

        # Portable / zip / archive apps: delete the extracted folder.
        if app:
            target = app.install_location
            if target:
                try:
                    import shutil
                    shutil.rmtree(target, ignore_errors=True)
                    return True, f"Removed portable app files at {target}"
                except Exception as e:
                    return False, f"Could not remove files at {target}: {e} (manual removal required)"

        return False, "No uninstall method available (manual uninstall required)"

    def _registry_uninstall_cmd(self, app_name: str):
        """Return (exe, args) for an app's real uninstaller from the registry.

        The cached ``installer_path`` is the *setup* exe we downloaded; running it
        re-opens the install wizard. The genuine uninstall command lives in the
        registry ``UninstallString`` (e.g. ``"C:\\...\\unins000.exe"``). Returns
        None when no registry entry matches.
        """
        try:
            for sa in get_installed_system_apps():
                if not sa.uninstall_string:
                    continue
                if sa.name.lower() == app_name.lower() or app_name.lower() in sa.name.lower():
                    cmd = sa.uninstall_string.strip()
                    # Common form: "C:\Path\unins000.exe" /SILENT  (quoted exe + args)
                    if cmd.startswith('"'):
                        end = cmd.index('"', 1)
                        exe = cmd[1:end]
                        rest = cmd[end + 1:].strip()
                    else:
                        parts = cmd.split(None, 1)
                        exe = parts[0]
                        rest = parts[1] if len(parts) > 1 else ""
                    args = rest.split() if rest else []
                    return exe, args
        except Exception as e:
            logger.debug(f"Registry uninstall lookup failed for {app_name}: {e}")
        return None

    def _uninstall_msi(self, app: InstalledApp, interactive: bool = False) -> Tuple[bool, str]:
        """Uninstall MSI package."""
        logger.info(f"Uninstalling MSI: {app.name}")

        if self.dry_run:
            return True, f"[DRY RUN] Would uninstall MSI: {app.name}"

        # Try to find MSI product code from installer path
        installer_path = Path(app.installer_path) if app.installer_path else None

        if installer_path and installer_path.exists():
            if interactive:
                try:
                    result = subprocess.run(
                        ["msiexec", "/x", str(installer_path), "/qb!"],
                        timeout=INTERACTIVE_TIMEOUT,
                    )
                    if result.returncode in (0, 1641, 3010):
                        return True, f"Uninstaller completed (interactive): {app.name}"
                    return False, f"Interactive MSI uninstall exited with code {result.returncode}"
                except subprocess.TimeoutExpired:
                    return False, "Interactive uninstall timed out (still running?)"
                except Exception as e:
                    return False, f"Interactive uninstall error: {e}"

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

    def _uninstall_exe(self, app: InstalledApp, interactive: bool = False) -> Tuple[bool, str]:
        """Uninstall EXE installer."""
        logger.info(f"Uninstalling EXE: {app.name}")

        if self.dry_run:
            return True, f"[DRY RUN] Would uninstall EXE: {app.name}"

        installer_path = Path(app.installer_path) if app.installer_path else None

        # Prefer the real uninstaller from the registry (UninstallString) instead
        # of the cached setup.exe — running the setup exe re-opens the install
        # wizard, not the uninstaller. Looked up regardless of installer_path.
        reg_cmd = self._registry_uninstall_cmd(app.name)

        if interactive:
            target_cmd = reg_cmd
            if not target_cmd and installer_path and installer_path.exists():
                target_cmd = (str(installer_path), [])
            if target_cmd:
                exe, base_args = target_cmd
                try:
                    result = subprocess.run([exe] + base_args, timeout=INTERACTIVE_TIMEOUT)
                    if result.returncode == 0:
                        return True, f"Uninstaller completed (interactive): {app.name}"
                    return False, f"Interactive uninstall exited with code {result.returncode}"
                except subprocess.TimeoutExpired:
                    return False, "Interactive uninstall timed out (still running?)"
                except Exception as e:
                    return False, f"Interactive uninstall error: {e}"
            return False, f"No uninstaller found in registry for {app.name} (manual uninstall required)"

        # Silent: try the registry uninstaller with silent flags, then the cached
        # setup.exe as a last resort (some Inno setups support it).
        if reg_cmd:
            exe, base_args = reg_cmd
            for flags in [["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], ["/S"], ["/silent"], ["/quiet"], []]:
                try:
                    result = subprocess.run(
                        [exe] + base_args + flags,
                        capture_output=True, text=True, timeout=300,
                    )
                    if result.returncode == 0:
                        logger.info(f"Registry uninstall successful: {app.name}")
                        return True, f"Successfully uninstalled {app.name}"
                except Exception:
                    continue
            return False, f"Registry uninstall failed for {app.name} (manual uninstall required)"

        if installer_path and installer_path.exists():
            # Fall back to cached installer path with silent flags
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
    interactive: bool = False,
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
    return installer.install(file_path, installer_type, app_id, force, download_only, interactive)