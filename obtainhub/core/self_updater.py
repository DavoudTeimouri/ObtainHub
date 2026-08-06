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
from typing import Optional, List
from urllib import request, error

from obtainhub.core.asset_matcher import (
    AssetMatch,
    InstallerType,
    Architecture,
    AssetMatcher,
)
from obtainhub.utils.helpers import is_windows_x64, get_architecture as get_system_architecture
from obtainhub.core.config import get_config
from obtainhub.core.logger import get_logger
from obtainhub.core.exceptions import (
    SelfUpdateError,
    SelfUpdateNotNeededError,
    NetworkError,
    DownloadError,
    InstallerError,
    InstallerNotFoundError,
)
from obtainhub.utils.helpers import (
    calculate_hash,
    verify_hash,
    run_command,
    install_msi,
    install_exe,
    get_temp_dir,
    clean_temp_dir,
)

logger = get_logger(__name__)

# ObtainHub GitHub repository
OBTAINHUB_REPO_OWNER = "DavoudTeimouri"
OBTAINHUB_REPO_NAME = "ObtainHub"
GITHUB_API_URL = f"https://api.github.com/repos/{OBTAINHUB_REPO_OWNER}/{OBTAINHUB_REPO_NAME}"


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
    assets: List[AssetMatch]


class SelfUpdater:
    """Handles self-updating of ObtainHub (Windows x64 only)."""

    def __init__(self, config_manager=None, state_manager=None, current_version: str = "0.1.0"):
        # Handle backward compatibility - if first arg is a version string
        if isinstance(config_manager, str) and config_manager.count('.') >= 1:
            current_version = config_manager
            config_manager = None
        
        self.current_version = current_version.lstrip('vV')
        self.config_manager = config_manager
        self.state_manager = state_manager
        if config_manager:
            self.config = config_manager.load()
        else:
            self.config = get_config()
        self.session = request.build_opener()
        self.asset_matcher = AssetMatcher(allow_x86_fallback=False)

        # Add GitHub token if configured
        if self.config.github_token:
            self.session.addheaders = [('Authorization', f'token {self.config.github_token}')]

    def _normalize_version(self, version: str) -> str:
        """Normalize version string."""
        return version.lstrip('vV')

    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings. Returns -1, 0, or 1."""
        def parse(v: str):
            v = self._normalize_version(v)
            parts = []
            for part in v.split('.'):
                if '-' in part:
                    num, pre = part.split('-', 1)
                    parts.append(int(num) if num.isdigit() else 0)
                    parts.append(pre)
                else:
                    parts.append(int(part) if part.isdigit() else 0)
            return parts

        p1 = parse(v1)
        p2 = parse(v2)

        for a, b in zip(p1, p2):
            # Handle prerelease vs release comparison
            if isinstance(a, str) and isinstance(b, int):
                return -1  # prerelease < release
            if isinstance(a, int) and isinstance(b, str):
                return 1   # release > prerelease
            if a != b:
                if isinstance(a, int) and isinstance(b, int):
                    return 1 if a > b else -1
                return 1 if str(a) > str(b) else -1

        if len(p1) != len(p2):
            # Handle cases like 1.0 vs 1.0.0
            remaining = p1[len(p2):] if len(p1) > len(p2) else p2[len(p1):]
            for r in remaining:
                if isinstance(r, int) and r > 0:
                    return 1 if len(p1) > len(p2) else -1
                if isinstance(r, str):
                    return -1 if len(p1) > len(p2) else 1
        return 0

    def _is_newer(self, version: str) -> bool:
        """Check if version is newer than current."""
        return self._compare_versions(version, self.current_version) > 0

    def fetch_latest_release(self, allow_prerelease: bool = False) -> Optional[ReleaseInfo]:
        """Fetch latest release from GitHub API."""
        try:
            url = f"{GITHUB_API_URL}/releases"
            if not allow_prerelease:
                url += "/latest"

            req = request.Request(url)
            if self.config.github_token:
                req.add_header('Authorization', f'token {self.config.github_token}')

            with self.session.open(req, timeout=30) as response:
                if response.status == 404:
                    return None
                data = json.load(response)

                # Handle paginated list vs single release
                if isinstance(data, list):
                    releases = data
                else:
                    releases = [data]

                for rel in releases:
                    if rel.get('draft'):
                        continue
                    if not allow_prerelease and rel.get('prerelease'):
                        continue

                    assets = []
                    for asset_data in rel.get('assets', []):
                        match = AssetMatch(
                            name=asset_data.get('name', ''),
                            url=asset_data.get('browser_download_url', ''),
                            architecture=Architecture.UNKNOWN,
                            installer_type=InstallerType.UNKNOWN,
                            is_download_only=False,
                            size=asset_data.get('size', 0),
                            sha256=asset_data.get('sha256', ''),
                        )
                        # Detect architecture and installer type
                        match.architecture = self.asset_matcher._detect_architecture(match.name)
                        match.installer_type = self.asset_matcher._detect_installer_type(match.name)
                        match.is_download_only = match.installer_type == InstallerType.ZIP
                        assets.append(match)

                    return ReleaseInfo(
                        version=rel.get('tag_name', '').lstrip('vV'),
                        name=rel.get('name', ''),
                        tag_name=rel.get('tag_name', ''),
                        body=rel.get('body', ''),
                        prerelease=rel.get('prerelease', False),
                        draft=rel.get('draft', False),
                        published_at=rel.get('published_at', ''),
                        html_url=rel.get('html_url', ''),
                        assets=assets,
                    )
        except error.HTTPError as e:
            raise NetworkError(f"GitHub API error: {e.code} {e.reason}")
        except error.URLError as e:
            raise NetworkError(f"Network error: {e.reason}")
        except Exception as e:
            raise SelfUpdateError(f"Failed to fetch release: {e}")
        return None

    def check_for_update(self, allow_prerelease: bool = False) -> Optional[ReleaseInfo]:
        """Check for available updates."""
        if not is_windows_x64():
            raise SelfUpdateError("Self-update only supported on Windows x64")

        release = self.fetch_latest_release(allow_prerelease=allow_prerelease)
        if not release:
            raise SelfUpdateNotNeededError("No releases found")

        if release.prerelease and not allow_prerelease:
            raise SelfUpdateNotNeededError("Prerelease skipped (use --prerelease to include)")

        if not self._is_newer(release.version):
            raise SelfUpdateNotNeededError(f"Already at latest version ({self.current_version})")

        return release

    def find_windows_x64_installer(self, release: ReleaseInfo, allow_prerelease: bool = False) -> Optional[AssetMatch]:
        """Find the best Windows x64 installer asset."""
        # Filter prereleases if not allowed
        assets = release.assets
        if not allow_prerelease:
            assets = [a for a in assets if not a.name.endswith(('.sha256', '.asc', '.sig', '.blockmap'))]

        # Filter for x64 architecture
        x64_assets = [a for a in assets if a.architecture == Architecture.X64]
        if not x64_assets:
            return None

        # Sort by installer preference (MSI > EXE > ZIP)
        type_priority = {InstallerType.MSI: 0, InstallerType.EXE: 1, InstallerType.ZIP: 2, InstallerType.UNKNOWN: 3}
        x64_assets.sort(key=lambda a: type_priority.get(a.installer_type, 99))

        return x64_assets[0] if x64_assets else None

    def download_installer(self, asset: AssetMatch, dest_dir: Optional[Path] = None) -> Path:
        """Download installer asset."""
        if dest_dir is None:
            dest_dir = Path(get_temp_dir()) / "obtainhub_update"
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / asset.name
        logger.info(f"Downloading {asset.name} from {asset.url}")

        try:
            req = request.Request(asset.url)
            if self.config.github_token:
                req.add_header('Authorization', f'token {self.config.github_token}')

            with self.session.open(req, timeout=300) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0

                with open(dest_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            logger.debug(f"Download progress: {progress:.1f}%")

                logger.info(f"Downloaded {dest_path} ({downloaded} bytes)")

                # Verify checksum if available
                if asset.sha256:
                    if not verify_hash(dest_path, asset.sha256, 'sha256'):
                        raise DownloadChecksumError(f"Checksum mismatch for {asset.name}")

                return dest_path
        except error.URLError as e:
            raise DownloadError(f"Download failed: {e.reason}")
        except Exception as e:
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            raise DownloadError(f"Download failed: {e}")

    def install_msi(self, msi_path: Path, quiet: bool = True) -> bool:
        """Install MSI package."""
        return install_msi(msi_path, quiet=quiet)

    def install_exe(self, exe_path: Path, silent_args: Optional[List[str]] = None) -> bool:
        """Install EXE package."""
        return install_exe(exe_path, silent_args=silent_args)

    def perform_self_update(self, release: ReleaseInfo, allow_prerelease: bool = False) -> bool:
        """Perform self-update using the release."""
        installer = self.find_windows_x64_installer(release, allow_prerelease)
        if not installer:
            raise InstallerNotFoundError("No suitable Windows x64 installer found")

        logger.info(f"Found installer: {installer.name} ({installer.installer_type.value})")

        # Download installer
        installer_path = self.download_installer(installer)

        try:
            # Install based on type
            if installer.installer_type == InstallerType.MSI:
                success = self.install_msi(installer_path)
            elif installer.installer_type == InstallerType.EXE:
                success = self.install_exe(installer_path)
            else:
                raise InstallerUnsupportedTypeError(f"Unsupported installer type: {installer.installer_type}")

            if success:
                logger.info("Self-update completed successfully")
                return True
            else:
                raise InstallerExecutionError("Installer returned non-zero exit code")
        finally:
            # Cleanup downloaded installer
            if installer_path.exists():
                installer_path.unlink(missing_ok=True)

    def check_and_update(self, allow_prerelease: bool = False, force: bool = False) -> Optional[str]:
            """Check for updates and perform self-update if available."""
            release = None
            try:
                release = self.check_for_update(allow_prerelease=allow_prerelease)
            except SelfUpdateNotNeededError as e:
                if force:
                    logger.info(f"Force update requested, continuing despite: {e}")
                else:
                    logger.info(f"No update needed: {e}")
                    return None
            except SelfUpdateError as e:
                logger.error(f"Self-update check failed: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error during self-update check: {e}")
                return None

            # Update is available - perform it
            if release:
                try:
                    success = self.perform_self_update(release, allow_prerelease=allow_prerelease)
                    if success:
                        return release.version
                except Exception as e:
                    logger.error(f"Self-update failed: {e}")
            return None


def check_and_update(current_version: str, skip_self_update: bool = False, allow_prerelease: bool = False) -> Optional[bool]:
    """Check for updates and perform self-update if available."""
    if skip_self_update:
        return None

    config = get_config()
    if config.skip_self_update:
        return None

    updater = SelfUpdater(current_version=current_version)
    try:
        release = updater.check_for_update(allow_prerelease=allow_prerelease)
    except SelfUpdateNotNeededError:
        return False
    except SelfUpdateError as e:
        logger.error(f"Self-update check failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during self-update check: {e}")
        return False

    # Update is available - perform it
    try:
        success = updater.perform_self_update(release, allow_prerelease=allow_prerelease)
        return success
    except Exception as e:
        logger.error(f"Self-update failed: {e}")
        return False