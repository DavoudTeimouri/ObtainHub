"""Asset matching and filtering for Windows x64 installers."""

import platform
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from pathlib import Path


class InstallerType(Enum):
    """Supported installer types for Windows x64."""
    MSI = "msi"
    EXE_SETUP = "exe_setup"
    ZIP_PORTABLE = "zip_portable"
    UNKNOWN = "unknown"


class Architecture(Enum):
    """Supported architectures."""
    X64 = "x64"
    X86 = "x86"
    ARM64 = "arm64"
    UNKNOWN = "unknown"


@dataclass
class AssetInfo:
    """Information about a release asset."""
    name: str
    url: str
    size: int
    installer_type: InstallerType
    architecture: Architecture
    is_prerelease: bool = False
    version: str = ""
    
    @property
    def is_windows_x64_installer(self) -> bool:
        """Check if this is a Windows x64 installer (MSI or Setup.exe)."""
        return (self.architecture == Architecture.X64 and
                self.installer_type in (InstallerType.MSI, InstallerType.EXE_SETUP))
    
    @property
    def is_zip_portable(self) -> bool:
        """Check if this is a ZIP portable archive."""
        return self.installer_type == InstallerType.ZIP_PORTABLE


def detect_architecture(asset_name: str) -> Architecture:
    """Detect architecture from asset filename."""
    name_lower = asset_name.lower()
    
    # x64 patterns (most specific first)
    x64_patterns = [
        r'(?:^|[-_])x64(?:[-_.]|$)',
        r'(?:^|[-_])amd64(?:[-_.]|$)',
        r'(?:^|[-_])win64(?:[-_.]|$)',
        r'(?:^|[-_])64(?:[-_.]|$)',
        r'x86_64',
    ]
    
    # x86 patterns
    x86_patterns = [
        r'(?:^|[-_])x86(?:[-_.]|$)',
        r'(?:^|[-_])win32(?:[-_.]|$)',
        r'(?:^|[-_])32bit(?:[-_.]|$)',
        r'(?:^|[-_])32-bit(?:[-_.]|$)',
        r'(?:^|[-_])32(?:[-_.]|$)',
    ]
    
    # ARM64 patterns
    arm64_patterns = [
        r'(?:^|[-_])arm64(?:[-_.]|$)',
        r'(?:^|[-_])aarch64(?:[-_.]|$)',
    ]
    
    for pattern in x64_patterns:
        if re.search(pattern, name_lower):
            return Architecture.X64
    
    for pattern in arm64_patterns:
        if re.search(pattern, name_lower):
            return Architecture.ARM64
    
    for pattern in x86_patterns:
        if re.search(pattern, name_lower):
            return Architecture.X86
    
    # Default to x64 for Windows installers without explicit arch
    if any(ext in name_lower for ext in ['.msi', '.exe', '.zip']):
        if 'setup' in name_lower or 'install' in name_lower:
            return Architecture.X64
    
    return Architecture.UNKNOWN


def detect_installer_type(asset_name: str) -> InstallerType:
    """Detect installer type from asset filename."""
    name_lower = asset_name.lower()
    
    if name_lower.endswith('.msi'):
        return InstallerType.MSI
    
    if name_lower.endswith('.exe'):
        # Check for setup/installer patterns
        setup_patterns = [
            r'setup',
            r'install',
            r'-setup\.',
            r'_setup\.',
            r'-install\.',
            r'_install\.',
        ]
        for pattern in setup_patterns:
            if re.search(pattern, name_lower):
                return InstallerType.EXE_SETUP
        # Generic .exe - could be portable, treat as setup
        return InstallerType.EXE_SETUP
    
    if name_lower.endswith('.zip'):
        return InstallerType.ZIP_PORTABLE
    
    return InstallerType.UNKNOWN


def parse_asset(asset_name: str, asset_url: str, asset_size: int, is_prerelease: bool = False, version: str = "") -> AssetInfo:
    """Parse a GitHub release asset into AssetInfo."""
    installer_type = detect_installer_type(asset_name)
    architecture = detect_architecture(asset_name)
    
    return AssetInfo(
        name=asset_name,
        url=asset_url,
        size=asset_size,
        installer_type=installer_type,
        architecture=architecture,
        is_prerelease=is_prerelease,
        version=version,
    )


def filter_windows_x64_installers(assets: list[AssetInfo], allow_prerelease: bool = False) -> list[AssetInfo]:
    """Filter assets to only Windows x64 installers (MSI and Setup.exe)."""
    filtered = []
    for asset in assets:
        if not asset.is_windows_x64_installer:
            continue
        if asset.is_prerelease and not allow_prerelease:
            continue
        filtered.append(asset)
    return filtered


def find_best_installer(assets: list[AssetInfo], allow_prerelease: bool = False) -> Optional[AssetInfo]:
    """Find the best Windows x64 installer from assets.
    
    Priority:
    1. MSI (preferred for system installs)
    2. Setup.exe
    """
    filtered = filter_windows_x64_installers(assets, allow_prerelease)
    
    if not filtered:
        return None
    
    # Sort: MSI first, then by version (newest first)
    def sort_key(asset: AssetInfo):
        type_priority = 0 if asset.installer_type == InstallerType.MSI else 1
        return (type_priority, asset.version)
    
    filtered.sort(key=sort_key)
    return filtered[0]


def find_zip_assets(assets: list[AssetInfo], allow_prerelease: bool = False) -> list[AssetInfo]:
    """Find all ZIP portable assets."""
    filtered = []
    for asset in assets:
        if not asset.is_zip_portable:
            continue
        if asset.is_prerelease and not allow_prerelease:
            continue
        filtered.append(asset)
    return filtered


def get_system_architecture() -> Architecture:
    """Get the current system architecture."""
    machine = platform.machine().lower()
    if machine in ('amd64', 'x86_64'):
        return Architecture.X64
    elif machine in ('i386', 'i686', 'x86'):
        return Architecture.X86
    elif machine in ('arm64', 'aarch64'):
        return Architecture.ARM64
    return Architecture.UNKNOWN


def is_windows_x64() -> bool:
    """Check if running on Windows x64."""
    return platform.system().lower() == 'windows' and get_system_architecture() == Architecture.X64


@dataclass
class DownloadDecision:
    """Decision on how to handle a download."""
    action: str  # 'install', 'download_only', 'manual_uninstall', 'skip'
    asset: Optional[AssetInfo] = None
    message: str = ""
    requires_confirmation: bool = False
    confirmation_prompt: str = ""


def decide_download_action(
    assets: list[AssetInfo],
    allow_prerelease: bool = False,
    requires_manual_uninstall: bool = False,
) -> DownloadDecision:
    """Decide what action to take based on available assets."""
    
    # First, look for Windows x64 installers
    installer = find_best_installer(assets, allow_prerelease)
    
    if installer:
        if requires_manual_uninstall:
            return DownloadDecision(
                action='manual_uninstall',
                asset=installer,
                message=f"Notice: This application requires manual uninstallation of the previous version.",
                requires_confirmation=True,
                confirmation_prompt=(
                    "Installer downloaded. Do you want ohub to attempt auto-uninstalling "
                    "the previous version, or will you perform it manually? "
                    "[1: Attempt Auto-Uninstall / 2: Manual / Abort]"
                ),
            )
        return DownloadDecision(
            action='install',
            asset=installer,
            message=f"Found Windows x64 installer: {installer.name}",
        )
    
    # No installer found, check for ZIP
    zip_assets = find_zip_assets(assets, allow_prerelease)
    if zip_assets:
        # Prefer x64 ZIP if available
        x64_zips = [a for a in zip_assets if a.architecture == Architecture.X64]
        chosen = x64_zips[0] if x64_zips else zip_assets[0]
        
        return DownloadDecision(
            action='download_only',
            asset=chosen,
            message=(
                f"No Windows x64 installer (.msi/.exe) found. "
                f"Downloading portable archive: {chosen.name}"
            ),
        )
    
    return DownloadDecision(
        action='skip',
        message="No suitable Windows x64 assets found in release.",
    )


__all__ = [
    'InstallerType',
    'Architecture',
    'AssetInfo',
    'DownloadDecision',
    'detect_architecture',
    'detect_installer_type',
    'parse_asset',
    'filter_windows_x64_installers',
    'find_best_installer',
    'find_zip_assets',
    'get_system_architecture',
    'is_windows_x64',
    'decide_download_action',
]