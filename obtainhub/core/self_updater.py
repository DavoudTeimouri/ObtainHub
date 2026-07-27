"""Self-updater module for ObtainHub (Windows x64 only)."""

import json
import os
import sys
import subprocess
import tempfile
import time
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from obtainhub import __version__
from obtainhub.core.config import get_config
from obtainhub.core.logger import get_logger
from obtainhub.core.asset_matcher import (
    AssetInfo,
    Architecture,
    InstallerType,
    parse_asset,
    find_best_installer,
    find_zip_assets,
    decide_download_action,
    DownloadDecision,
    is_windows_x64,
)
from obtainhub.core.exceptions import (
    SelfUpdateError,
    SelfUpdateNotNeededError,
    NetworkError,
    NetworkRateLimitError,
    DownloadError,
    InstallerError,
    InstallerNotFoundError,
    InstallerExecutionError,
)

logger = get_logger()


@dataclass
class ReleaseInfo:
    """Information about a GitHub release."""
    version: str
    name: str
    tag_name: str
    body: str
    prerelease: bool
    draft: bool
    published_at: str
    html_url: str
    assets: list[AssetInfo]
    
    @property
    def is_prerelease(self) -> bool:
        return self.prerelease
    
    @property
    def normalized_version(self) -> str:
        """Normalize version string for comparison."""
        v = self.version.lstrip('vV')
        return v
    
    def get_windows_x64_installer(self) -> Optional[AssetInfo]:
        """Get the best Windows x64 installer (MSI or Setup.exe)."""
        return find_best_installer(self.assets, allow_prerelease=False)
    
    def get_windows_x64_installer_with_prerelease(self) -> Optional[AssetInfo]:
        """Get the best Windows x64 installer including prereleases."""
        return find_best_installer(self.assets, allow_prerelease=True)
    
    def get_zip_assets(self) -> list[AssetInfo]:
        """Get all ZIP portable assets."""
        return find_zip_assets(self.assets, allow_prerelease=False)


class SelfUpdater:
    """Handles self-update checks and installation for ObtainHub (Windows x64)."""
    
    REPO_OWNER = "ObtainHub"
    REPO_NAME = "ObtainHub"
    GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
    
    def __init__(self, current_version: str = None):
        self.current_version = current_version or __version__
        self.config = get_config()
        self.github_token = self.config.github_token
    
    def _get_headers(self) -> dict:
        """Get HTTP headers for GitHub API requests."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"ObtainHub/{self.current_version}",
        }
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        return headers
    
    def _make_request(self, url: str) -> dict:
        """Make HTTP request to GitHub API."""
        headers = self._get_headers()
        req = Request(url, headers=headers)
        
        try:
            with urlopen(req, timeout=30) as response:
                data = response.read().decode('utf-8')
                return json.loads(data)
        except HTTPError as e:
            if e.code == 403:
                # Check for rate limit
                retry_after = e.headers.get('Retry-After')
                reset_time = e.headers.get('X-RateLimit-Reset')
                raise NetworkRateLimitError(
                    "GitHub API rate limit exceeded",
                    retry_after=int(retry_after) if retry_after else None,
                )
            elif e.code == 404:
                raise SelfUpdateError(f"Repository not found: {url}")
            else:
                raise NetworkError(f"HTTP {e.code}: {e.reason}")
        except URLError as e:
            raise NetworkError(f"Network error: {e.reason}")
        except json.JSONDecodeError as e:
            raise NetworkError(f"Invalid JSON response: {e}")
        except Exception as e:
            raise NetworkError(f"Request failed: {e}")
    
    def fetch_latest_release(self, allow_prerelease: bool = False) -> ReleaseInfo:
        """Fetch the latest release from GitHub."""
        url = f"{self.GITHUB_API_URL}/releases"
        if not allow_prerelease:
            url += "/latest"
        else:
            url += "?per_page=10"
        
        data = self._make_request(url)
        
        if allow_prerelease:
            # Find first non-draft release
            for release in data:
                if not release.get('draft', False):
                    data = release
                    break
            else:
                raise SelfUpdateError("No releases found")
        elif isinstance(data, list):
            data = data[0] if data else {}
        
        assets = []
        for asset in data.get('assets', []):
            asset_info = parse_asset(
                asset_name=asset['name'],
                asset_url=asset['browser_download_url'],
                asset_size=asset['size'],
                is_prerelease=data.get('prerelease', False),
                version=data.get('tag_name', '').lstrip('vV'),
            )
            assets.append(asset_info)
        
        return ReleaseInfo(
            version=data.get('tag_name', '').lstrip('vV'),
            name=data.get('name', ''),
            tag_name=data.get('tag_name', ''),
            body=data.get('body', ''),
            prerelease=data.get('prerelease', False),
            draft=data.get('draft', False),
            published_at=data.get('published_at', ''),
            html_url=data.get('html_url', ''),
            assets=assets,
        )
    
    def check_for_update(self, allow_prerelease: bool = False) -> Optional[ReleaseInfo]:
        """Check if an update is available.
        
        Args:
            allow_prerelease: If True, include prereleases in check
            
        Returns:
            ReleaseInfo if update available, None if current is latest
            
        Raises:
            SelfUpdateNotNeededError: If already on latest version
        """
        if not is_windows_x64():
            logger.warning("Self-update only supported on Windows x64")
            return None
        
        release = self.fetch_latest_release(allow_prerelease=allow_prerelease)
        
        # Skip prereleases unless explicitly allowed
        if release.is_prerelease and not allow_prerelease:
            logger.info(f"Latest release {release.version} is a prerelease, skipping")
            return None
        
        # Check if we have a Windows x64 installer
        installer = release.get_windows_x64_installer_with_prerelease() if allow_prerelease else release.get_windows_x64_installer()
        if not installer:
            logger.warning(f"No Windows x64 installer found in release {release.version}")
            return None
        
        current = self._normalize_version(self.current_version)
        latest = self._normalize_version(release.version)
        
        if self._compare_versions(current, latest) >= 0:
            raise SelfUpdateNotNeededError(f"Already on latest version ({self.current_version})")
        
        logger.info(f"Update available: {self.current_version} -> {release.version}")
        return release
    
    def _normalize_version(self, version: str) -> tuple:
        """Normalize version string to tuple for comparison."""
        # Remove 'v' prefix
        v = version.lstrip('vV')
        # Split by dots and convert to ints where possible
        parts = []
        for part in v.split('.'):
            # Handle pre-release suffixes
            if '-' in part:
                num_part, pre_part = part.split('-', 1)
                parts.append(int(num_part) if num_part.isdigit() else 0)
                parts.append(pre_part)
            else:
                parts.append(int(part) if part.isdigit() else 0)
        return tuple(parts)
    
    def _compare_versions(self, v1: tuple, v2: tuple) -> int:
        """Compare two version tuples. Returns -1, 0, or 1."""
        # Pad shorter tuple with zeros
        max_len = max(len(v1), len(v2))
        v1 = list(v1) + [0] * (max_len - len(v1))
        v2 = list(v2) + [0] * (max_len - len(v2))
        
        for a, b in zip(v1, v2):
            if isinstance(a, str) or isinstance(b, str):
                # Handle prerelease comparison: stable (int 0) > prerelease (str)
                if isinstance(a, int) and a == 0 and isinstance(b, str):
                    return 1  # stable > prerelease
                if isinstance(b, int) and b == 0 and isinstance(a, str):
                    return -1  # prerelease < stable
                # Both are strings or mixed non-zero
                a_str = str(a)
                b_str = str(b)
                if a_str < b_str:
                    return -1
                elif a_str > b_str:
                    return 1
            else:
                if a < b:
                    return -1
                elif a > b:
                    return 1
        return 0
    
    def download_installer(self, asset: AssetInfo, dest_dir: Optional[Path] = None) -> Path:
        """Download an installer asset.
        
        Args:
            asset: AssetInfo to download
            dest_dir: Destination directory (defaults to config download_dir)
            
        Returns:
            Path to downloaded file
        """
        dest_dir = dest_dir or self.config.get_download_dir()
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        dest_path = dest_dir / asset.name
        logger.info(f"Downloading {asset.name} ({asset.size} bytes)...")
        
        headers = self._get_headers()
        req = Request(asset.url, headers=headers)
        
        try:
            with urlopen(req, timeout=300) as response, open(dest_path, 'wb') as f:
                total = asset.size
                downloaded = 0
                chunk_size = 8192
                
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total > 0:
                        percent = (downloaded / total) * 100
                        if downloaded % (chunk_size * 100) == 0:
                            logger.debug(f"Download progress: {percent:.1f}%")
            
            # Verify file size
            actual_size = dest_path.stat().st_size
            if actual_size != asset.size:
                raise DownloadError(f"Size mismatch: expected {asset.size}, got {actual_size}")
            
            logger.info(f"Downloaded to {dest_path}")
            return dest_path
            
        except HTTPError as e:
            if dest_path.exists():
                dest_path.unlink()
            raise DownloadError(f"Download failed: HTTP {e.code}")
        except URLError as e:
            if dest_path.exists():
                dest_path.unlink()
            raise DownloadError(f"Download failed: {e.reason}")
        except Exception as e:
            if dest_path.exists():
                dest_path.unlink()
            raise DownloadError(f"Download failed: {e}")
    
    def execute_installer(self, installer_path: Path, silent: bool = True) -> bool:
        """Execute the downloaded installer in a detached process.
        
        Args:
            installer_path: Path to installer
            silent: Run silently (no UI)
            
        Returns:
            True if installer launched successfully
        """
        if not installer_path.exists():
            raise InstallerError(f"Installer not found: {installer_path}")
        
        suffix = installer_path.suffix.lower()
        
        if suffix == '.msi':
            return self._execute_msi(installer_path, silent)
        elif suffix == '.exe':
            return self._execute_exe(installer_path, silent)
        else:
            raise InstallerUnsupportedTypeError(f"Unsupported installer type: {suffix}")
    
    def _execute_msi(self, installer_path: Path, silent: bool) -> bool:
        """Execute MSI installer."""
        args = ['msiexec', '/i', str(installer_path)]
        if silent:
            args.extend(['/quiet', '/norestart'])
        
        logger.info(f"Launching MSI installer: {' '.join(args)}")
        
        try:
            # Use CREATE_NEW_PROCESS_GROUP and DETACHED_PROCESS for true detachment
            creation_flags = 0
            if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP'):
                creation_flags |= subprocess.CREATE_NEW_PROCESS_GROUP
            if hasattr(subprocess, 'DETACHED_PROCESS'):
                creation_flags |= subprocess.DETACHED_PROCESS
            
            proc = subprocess.Popen(
                args,
                creationflags=creation_flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
            
            # Give it a moment to start
            time.sleep(1)
            
            if proc.poll() is not None:
                # Process exited immediately
                return False
            
            logger.info("MSI installer launched successfully (detached)")
            return True
            
        except Exception as e:
            raise InstallerExecutionError(f"Failed to launch MSI: {e}")
    
    def _execute_exe(self, installer_path: Path, silent: bool) -> bool:
        """Execute EXE installer."""
        args = [str(installer_path)]
        if silent:
            # Common silent install flags
            silent_flags = ['/S', '/quiet', '/silent', '--silent', '-s', '/VERYSILENT', '/SUPPRESSMSGBOXES']
            args.extend(silent_flags)
        
        logger.info(f"Launching EXE installer: {' '.join(args)}")
        
        try:
            creation_flags = 0
            if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP'):
                creation_flags |= subprocess.CREATE_NEW_PROCESS_GROUP
            if hasattr(subprocess, 'DETACHED_PROCESS'):
                creation_flags |= subprocess.DETACHED_PROCESS
            
            proc = subprocess.Popen(
                args,
                creationflags=creation_flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
            
            time.sleep(1)
            
            if proc.poll() is not None:
                return False
            
            logger.info("EXE installer launched successfully (detached)")
            return True
            
        except Exception as e:
            raise InstallerExecutionError(f"Failed to launch EXE: {e}")
    
    def perform_self_update(self, allow_prerelease: bool = False, skip_confirmation: bool = False) -> bool:
        """Perform complete self-update check and installation.
        
        Args:
            allow_prerelease: Include prereleases
            skip_confirmation: Skip confirmation prompts
            
        Returns:
            True if update was performed, False if not needed
            
        Raises:
            SelfUpdateError: If update fails
        """
        if not is_windows_x64():
            raise SelfUpdateError("Self-update only supported on Windows x64")
        
        # Check config for auto-update
        if not allow_prerelease and not self.config.auto_update:
            logger.info("Auto-update disabled in config")
            return False
        
        # Check for update
        try:
            release = self.check_for_update(allow_prerelease=allow_prerelease)
        except SelfUpdateNotNeededError:
            logger.info("No update needed")
            return False
        except SelfUpdateError:
            raise
        except Exception as e:
            raise SelfUpdateError(f"Update check failed: {e}")
        
        if not release:
            return False
        
        # Prerelease confirmation
        if release.is_prerelease and not skip_confirmation and not self.config.auto_confirm_prerelease:
            if not self._confirm_prerelease(release.version):
                logger.info("Prerelease update cancelled by user")
                return False
        
        # Find installer
        installer = release.get_windows_x64_installer_with_prerelease() if allow_prerelease else release.get_windows_x64_installer()
        if not installer:
            raise InstallerNotFoundError(f"No Windows x64 installer in release {release.version}")
        
        logger.info(f"Downloading installer: {installer.name}")
        installer_path = self.download_installer(installer)
        
        # Execute installer
        logger.info("Launching installer...")
        success = self.execute_installer(installer_path)
        
        if not success:
            raise InstallerExecutionError("Installer failed to launch")
        
        logger.info(f"ObtainHub {release.version} installer launched. Please complete installation.")
        logger.info("Exiting current instance to allow file replacement...")
        
        # Exit gracefully so files can be replaced
        sys.exit(0)
    
    def _confirm_prerelease(self, version: str) -> bool:
        """Prompt user for prerelease confirmation."""
        print(f"\nWarning: Version {version} is a Prerelease.")
        print("Are you sure you want to proceed? [y/N] ", end='', flush=True)
        
        try:
            response = input().strip().lower()
            return response == 'y'
        except (EOFError, KeyboardInterrupt):
            return False


def check_and_update(
    current_version: str = None,
    allow_prerelease: bool = False,
    skip_self_update: bool = False,
) -> bool:
    """Convenience function to check and perform self-update.
    
    Args:
        current_version: Current version (defaults to package version)
        allow_prerelease: Check prereleases
        skip_self_update: Skip self-update entirely
        
    Returns:
        True if update was performed, False otherwise
    """
    if skip_self_update:
        logger.info("Self-update skipped (--skip-self-update)")
        return False
    
    config = get_config()
    if config.skip_self_update:
        logger.info("Self-update skipped (config setting)")
        return False
    
    updater = SelfUpdater(current_version)
    
    try:
        return updater.perform_self_update(allow_prerelease=allow_prerelease)
    except SelfUpdateNotNeededError:
        return False
    except SelfUpdateError as e:
        logger.error(f"Self-update failed: {e}")
        # Don't crash on self-update failure, just log and continue
        return False


__all__ = [
    'ReleaseInfo',
    'SelfUpdater',
    'check_and_update',
]