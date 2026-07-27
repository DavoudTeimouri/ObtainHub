"""Self-updater module for ObtainHub."""

import os
import sys
import json
import subprocess
import tempfile
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
from pathlib import Path as PathLibPath
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from obtainhub.core.logger import get_logger
from obtainhub.core.exceptions import SelfUpdateError, SelfUpdateFailedError, NetworkError
from obtainhub.core.config import ConfigManager, get_config_manager
from obtainhub import __version__ as CURRENT_VERSION


logger = get_logger()


@dataclass
class ReleaseInfo:
    """Information about a GitHub release."""
    version: str
    name: str
    body: str
    prerelease: bool
    draft: bool
    published_at: str
    html_url: str
    assets: list[dict]
    
    @property
    def installer_asset(self) -> Optional[dict]:
        """Find the Windows installer asset (MSI or EXE)."""
        for asset in self.assets:
            name = asset.get("name", "").lower()
            if name.endswith((".msi", ".exe")) and "obtainhub" in name:
                return asset
        return None
    
    @property
    def installer_download_url(self) -> Optional[str]:
        """Get the download URL for the installer."""
        asset = self.installer_asset
        return asset.get("browser_download_url") if asset else None
    
    @property
    def installer_filename(self) -> Optional[str]:
        """Get the installer filename."""
        asset = self.installer_asset
        return asset.get("name") if asset else None


class SelfUpdater:
    """Handles self-update checks and execution for ObtainHub."""
    
    REPO_OWNER = "ObtainHub"
    REPO_NAME = "ObtainHub"
    GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    
    def __init__(
        self,
        current_version: str = CURRENT_VERSION,
        skip_check: bool = False,
        github_token: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        """Initialize SelfUpdater.
        
        Args:
            current_version: Current version of ObtainHub.
            skip_check: Whether to skip the update check.
            github_token: Optional GitHub token for authenticated API requests.
            timeout: Request timeout in seconds.
        """
        self.current_version = current_version
        self.skip_check = skip_check
        self.github_token = github_token
        self.timeout = timeout
        self._latest_release: Optional[ReleaseInfo] = None
    
    def check_for_update(self) -> Tuple[bool, Optional[ReleaseInfo]]:
        """Check if a newer version is available.
        
        Returns:
            Tuple of (update_available, release_info).
            If skip_check is True, returns (False, None).
        """
        if self.skip_check:
            logger.debug("Self-update check skipped (--skip-self-update flag)")
            return False, None
        
        try:
            release = self._fetch_latest_release()
            self._latest_release = release
            
            if self._is_newer_version(release.version):
                logger.info(f"New version available: {release.version} (current: {self.current_version})")
                return True, release
            
            logger.debug(f"Already on latest version: {self.current_version}")
            return False, release
            
        except NetworkError as e:
            logger.warning(f"Failed to check for updates: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected error during update check: {e}")
            return False, None
    
    def _fetch_latest_release(self) -> ReleaseInfo:
        """Fetch latest release info from GitHub API."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"ObtainHub/{self.current_version}",
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        req = Request(self.GITHUB_API_URL, headers=headers)
        
        try:
            with urlopen(req, timeout=self.timeout) as response:
                if response.status != 200:
                    raise NetworkError(f"GitHub API returned {response.status}")
                data = json.load(response)
        except HTTPError as e:
            if e.code == 404:
                raise NetworkError("Repository or releases not found")
            elif e.code == 403:
                raise NetworkError("GitHub API rate limit exceeded or forbidden")
            raise NetworkError(f"GitHub API error: {e.code}", status_code=e.code)
        except URLError as e:
            raise NetworkError(f"Network error: {e.reason}")
        except json.JSONDecodeError as e:
            raise NetworkError(f"Invalid JSON response: {e}")
        
        return ReleaseInfo(
            version=data.get("tag_name", "").lstrip("v"),
            name=data.get("name", ""),
            body=data.get("body", ""),
            prerelease=data.get("prerelease", False),
            draft=data.get("draft", False),
            published_at=data.get("published_at", ""),
            html_url=data.get("html_url", ""),
            assets=data.get("assets", []),
        )
    
    def _is_newer_version(self, latest_version: str) -> bool:
        """Compare versions. Returns True if latest > current."""
        return self._compare_versions(self.current_version, latest_version) < 0
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings. Returns -1 if v1 < v2, 0 if equal, 1 if v1 > v2."""
        def parse_version(v: str) -> list[int]:
            v = v.lstrip('v')
            parts = []
            for part in v.split('.'):
                num = ''.join(c for c in part if c.isdigit())
                parts.append(int(num) if num else 0)
            return parts
        
        p1 = parse_version(v1)
        p2 = parse_version(v2)
        
        max_len = max(len(p1), len(p2))
        p1.extend([0] * (max_len - len(p1)))
        p2.extend([0] * (max_len - len(p2)))
        
        if p1 < p2:
            return -1
        elif p1 > p2:
            return 1
        return 0
    
    def download_installer(self, release: ReleaseInfo, dest_dir: Optional[PathLibPath] = None) -> PathLibPath:
        """Download the installer for the latest release.
        
        Args:
            release: ReleaseInfo containing installer info.
            dest_dir: Directory to save installer. Defaults to temp directory.
        
        Returns:
            Path to downloaded installer.
        
        Raises:
            SelfUpdateFailedError: If download fails or no installer found.
        """
        download_url = release.installer_download_url
        filename = release.installer_filename
        
        if not download_url or not filename:
            raise SelfUpdateFailedError("No Windows installer found in release assets")
        
        if dest_dir is None:
            dest_dir = PathLibPath(tempfile.gettempdir()) / "ObtainHub_Updates"
        
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename
        
        logger.info(f"Downloading installer from {download_url}")
        logger.progress(f"Downloading {filename}...")
        
        headers = {"User-Agent": f"ObtainHub/{self.current_version}"}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        req = Request(download_url, headers=headers)
        
        try:
            with urlopen(req, timeout=self.timeout) as response, open(dest_path, "wb") as f:
                if response.status != 200:
                    raise NetworkError(f"Download failed with status {response.status}")
                
                total_size = response.headers.get("Content-Length")
                if total_size:
                    total_size = int(total_size)
                    downloaded = 0
                    chunk_size = 8192
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            logger.progress(f"Downloading {filename}: {percent:.1f}%")
                else:
                    shutil.copyfileobj(response, f)
            
            logger.progress(" " * 60)  # Clear progress line
            logger.success(f"Downloaded installer to {dest_path}")
            return dest_path
            
        except URLError as e:
            raise SelfUpdateFailedError(f"Download failed: {e.reason}")
        except Exception as e:
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            raise SelfUpdateFailedError(f"Download failed: {e}")
    
    def execute_installer(self, installer_path: PathLibPath) -> bool:
        """Execute the downloaded installer in a detached process.
        
        Args:
            installer_path: Path to the installer executable.
        
        Returns:
            True if installer launched successfully, False otherwise.
        """
        if not installer_path.exists():
            logger.error(f"Installer not found: {installer_path}")
            return False
        
        filename = installer_path.name.lower()
        
        if filename.endswith(".msi"):
            # MSI installer - use msiexec
            cmd = [
                "msiexec.exe",
                "/i", str(installer_path),
                "/quiet",           # Quiet mode
                "/norestart",       # Don't restart
            ]
        elif filename.endswith(".exe"):
            # EXE installer - common silent flags
            cmd = [
                str(installer_path),
                "/quiet",           # Inno Setup
                "/silent",          # NSIS
                "/S",               # NSIS alternative
                "/verysilent",      # Inno Setup very silent
                "/norestart",       # Don't restart
            ]
        else:
            logger.error(f"Unsupported installer type: {installer_path.suffix}")
            return False
        
        logger.info(f"Launching installer: {' '.join(cmd)}")
        
        try:
            # Launch detached so we can exit and release file locks
            if os.name == "nt":
                # Windows: use CREATE_NEW_PROCESS_GROUP and DETACHED_PROCESS
                subprocess.Popen(
                    cmd,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                    close_fds=True,
                )
            else:
                # Unix-like (for future cross-platform)
                subprocess.Popen(cmd, start_new_session=True)
            
            logger.success("Installer launched successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to launch installer: {e}")
            return False

    def perform_self_update(self) -> bool:
        """Perform the complete self-update process.
        
        Returns:
            True if update was initiated and process should exit,
            False if no update needed or update failed.
        """
        logger.section("ObtainHub Self-Update")
        
        update_available, release = self.check_for_update()
        
        if not update_available or release is None:
            return False
        
        # Notify user
        logger.warning(f"\n{'=' * 60}")
        logger.warning(f"  A new version of ObtainHub (v{release.version}) is available!")
        logger.warning(f"  Current version: v{CURRENT_VERSION}")
        logger.warning(f"  Release notes: {release.html_url}")
        logger.warning(f"  Updating ObtainHub first...")
        logger.warning(f"{'=' * 60}\n")
        
        try:
            # Download installer
            installer_path = self.download_installer(release)
            
            # Execute installer
            if self.execute_installer(installer_path):
                logger.success("Self-update initiated. Please restart ObtainHub.")
                return True
            else:
                logger.error("Failed to launch installer")
                return False
                
        except SelfUpdateFailedError as e:
            logger.error(f"Self-update failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during self-update: {e}")
            return False


def check_and_update(
    skip_check: bool = False,
    config_manager: Optional[ConfigManager] = None,
    github_token: Optional[str] = None,
) -> bool:
    """Check for updates and perform self-update if available.
    
    This function is called on every CLI invocation before executing the command.
    
    Args:
        skip_check: Whether to skip the update check.
        config_manager: ConfigManager instance for getting settings.
        github_token: Optional GitHub token override.
    
    Returns:
        True if an update was initiated and the process should exit,
        False if no update needed or check was skipped.
    """
    if config_manager is None:
        config_manager = get_config_manager()
        config_manager.load()
    
    # Check config for skip flag
    skip_check = skip_check or config_manager.config.skip_self_update
    
    # Get GitHub token from config if not provided
    if github_token is None:
        github_token = config_manager.config.github_token or None
    
    updater = SelfUpdater(
        current_version=CURRENT_VERSION,
        skip_check=skip_check,
        github_token=github_token,
    )
    
    update_available, release = updater.check_for_update()
    
    if not update_available or release is None:
        return False
    
    # Notify user
    logger.warning(f"\n{'=' * 60}")
    logger.warning(f"  A new version of ObtainHub (v{release.version}) is available!")
    logger.warning(f"  Current version: v{CURRENT_VERSION}")
    logger.warning(f"  Release notes: {release.html_url}")
    logger.warning(f"  Updating ObtainHub first...")
    logger.warning(f"{'=' * 60}\n")
    
    try:
        # Download installer
        installer_path = updater.download_installer(release)
        
        # Execute installer
        if updater.execute_installer(installer_path):
            logger.success("Self-update initiated. Please restart ObtainHub.")
            return True
        else:
            logger.error("Failed to launch installer")
            return False
            
    except SelfUpdateFailedError as e:
        logger.error(f"Self-update failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during self-update: {e}")
        return False


def get_current_version() -> str:
    """Get the current version of ObtainHub."""
    return CURRENT_VERSION