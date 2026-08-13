"""Asset matching for Windows x64 installers."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from obtainhub.core.exceptions import AssetMatchError


class Architecture(Enum):
    """CPU architecture types."""
    UNKNOWN = "unknown"
    X64 = "x64"
    ARM64 = "arm64"
    X86 = "x86"


class InstallerType(Enum):
    """Supported installer types in priority order (highest first)."""
    EXE_SETUP = "exe_setup"        # Inno Setup EXE installer (highest priority)
    MSI = "msi"                    # WiX MSI installer
    ZIP_INSTALLER = "zip_installer"  # ZIP containing installer (Setup/Install in name)
    ZIP = "zip"                    # Portable ZIP archive
    EXE_STANDALONE = "exe"         # Standalone EXE (lowest priority)
    UNKNOWN = "unknown"


@dataclass
class AssetMatch:
    """Matched asset with metadata."""
    name: str
    url: str
    architecture: Architecture
    installer_type: InstallerType
    is_download_only: bool
    size: int
    sha256: str = ""


class AssetMatcher:
    """Match and filter GitHub release assets for Windows x64."""

    def __init__(
        self,
        prefer_x64: bool = True,
        allow_x86_fallback: bool = False,
        allow_prerelease: bool = False,
        allow_arm64: bool = False,
        require_installer: bool = False,
    ):
        self.prefer_x64 = prefer_x64
        self.allow_x86_fallback = allow_x86_fallback
        self.allow_prerelease = allow_prerelease
        self.allow_arm64 = allow_arm64
        self.require_installer = require_installer

        # Architecture detection patterns
        self.arch_regexes = {
            Architecture.X64: [
                re.compile(r'[_-]?x64[_-]?', re.IGNORECASE),
                re.compile(r'[_-]?amd64[_-]?', re.IGNORECASE),
                re.compile(r'[_-]?x86[_-]?64[_-]?', re.IGNORECASE),
                re.compile(r'[_-]?64bit[_-]?', re.IGNORECASE),
                re.compile(r'[_-]?win64[_-]?', re.IGNORECASE),
                re.compile(r'(?<![a-zA-Z0-9])64(?![a-zA-Z0-9])', re.IGNORECASE),
            ],
            Architecture.ARM64: [
                re.compile(r'[_-]?arm64[_-]?', re.IGNORECASE),
                re.compile(r'[_-]?aarch64[_-]?', re.IGNORECASE),
            ],
            Architecture.X86: [
                re.compile(r'(?<![a-zA-Z0-9])x86(?![_-]?64)', re.IGNORECASE),
                re.compile(r'[_-]?win32[_-]?', re.IGNORECASE),
                re.compile(r'[_-]?32bit[_-]?', re.IGNORECASE),
                re.compile(r'(?<![a-zA-Z0-9])32(?![a-zA-Z0-9])', re.IGNORECASE),
            ],
        }

        # Installer type detection
        self.installer_regexes = {
            InstallerType.EXE_SETUP: re.compile(r'-Setup\.exe$|-setup\.exe$', re.IGNORECASE),
            InstallerType.MSI: re.compile(r'\.msi$', re.IGNORECASE),
            InstallerType.ZIP_INSTALLER: re.compile(r'\.zip$', re.IGNORECASE),  # Will be further filtered
            InstallerType.ZIP: re.compile(r'\.zip$', re.IGNORECASE),
            InstallerType.EXE_STANDALONE: re.compile(r'\.exe$', re.IGNORECASE),
        }

        # Exclusion patterns
        self.exclusion_regexes = [
            re.compile(r'\.sha256$', re.IGNORECASE),
            re.compile(r'\.sha512$', re.IGNORECASE),
            re.compile(r'\.asc$', re.IGNORECASE),
            re.compile(r'\.sig$', re.IGNORECASE),
            re.compile(r'\.txt$', re.IGNORECASE),
            re.compile(r'\.md$', re.IGNORECASE),
            re.compile(r'checksum', re.IGNORECASE),
            re.compile(r'signature', re.IGNORECASE),
            re.compile(r'\.blockmap$', re.IGNORECASE),
            re.compile(r'\.dmg$', re.IGNORECASE),
            re.compile(r'\.AppImage$', re.IGNORECASE),
            re.compile(r'\.deb$', re.IGNORECASE),
            re.compile(r'\.rpm$', re.IGNORECASE),
            re.compile(r'\.tar\.(gz|bz2|xz)$', re.IGNORECASE),
            # Non-Windows platform patterns
            re.compile(r'-darwin-', re.IGNORECASE),
            re.compile(r'-linux-', re.IGNORECASE),
            re.compile(r'-macos-', re.IGNORECASE),
            re.compile(r'-osx-', re.IGNORECASE),
            re.compile(r'-win32-ia32-', re.IGNORECASE),
            re.compile(r'-win32-x86-', re.IGNORECASE),
            # Debug/symbol/source packages
            re.compile(r'-symbols', re.IGNORECASE),
            re.compile(r'-debug', re.IGNORECASE),
            re.compile(r'^source', re.IGNORECASE),
        ]

    def _detect_architecture(self, name: str) -> Architecture:
        """Detect architecture from filename."""
        name_lower = name.lower()

        # Check in order of preference: ARM64, X64, X86
        for arch in [Architecture.ARM64, Architecture.X64, Architecture.X86]:
            patterns = self.arch_regexes.get(arch, [])
            for pattern in patterns:
                if pattern.search(name_lower):
                    # Check if this architecture is allowed
                    if arch == Architecture.ARM64 and not self.allow_arm64:
                        return Architecture.UNKNOWN
                    if arch == Architecture.X86 and not self.allow_x86_fallback:
                        return Architecture.UNKNOWN
                    return arch

        # Default to X64 for Windows installers without explicit architecture
        # (since this tool is Windows x64 only)
        if self._is_windows_installer(name_lower):
            return Architecture.X64

        return Architecture.UNKNOWN

    def _is_windows_installer(self, name_lower: str) -> bool:
        """Check if filename looks like a Windows installer."""
        return name_lower.endswith('.exe') or name_lower.endswith('.msi') or name_lower.endswith('.zip')

    def _detect_installer_type(self, name: str) -> InstallerType:
        """Detect installer type from filename."""
        name_lower = name.lower()
        
        # Check for EXE_SETUP (Inno Setup)
        if self.installer_regexes[InstallerType.EXE_SETUP].search(name):
            return InstallerType.EXE_SETUP
        
        # Check for MSI
        if self.installer_regexes[InstallerType.MSI].search(name):
            return InstallerType.MSI
        
        # Check for ZIP - determine if installer or portable
        if name_lower.endswith('.zip'):
            # Check if ZIP name explicitly suggests it contains an installer
            # Must have explicit installer keywords, not just version numbers
            if re.search(r'(setup|install)', name_lower):
                return InstallerType.ZIP_INSTALLER
            return InstallerType.ZIP
        
        # Check for standalone EXE
        if self.installer_regexes[InstallerType.EXE_STANDALONE].search(name):
            return InstallerType.EXE_STANDALONE
            
        return InstallerType.UNKNOWN

    def _is_excluded(self, name: str) -> bool:
        """Check if asset should be excluded."""
        for regex in self.exclusion_regexes:
            if regex.search(name):
                return True
        return False

    def _sort_key(self, match: AssetMatch) -> tuple:
        """Sort key for asset matching preference."""
        # Architecture priority: X64 > ARM64 > X86
        arch_priority = {
            Architecture.X64: 0,
            Architecture.ARM64: 1,
            Architecture.X86: 2,
            Architecture.UNKNOWN: 3,
        }
        # Installer priority: EXE_SETUP > MSI > ZIP_INSTALLER > ZIP > EXE_STANDALONE
        inst_priority = {
            InstallerType.EXE_SETUP: 0,
            InstallerType.MSI: 1,
            InstallerType.ZIP_INSTALLER: 2,
            InstallerType.ZIP: 3,
            InstallerType.EXE_STANDALONE: 4,
            InstallerType.UNKNOWN: 5,
        }
        return (
            arch_priority.get(match.architecture, 3),
            inst_priority.get(match.installer_type, 4),
            -match.size,  # Larger files first (more likely to be full installer)
        )

    def match_assets(self, assets: List[dict]) -> List[AssetMatch]:
        """
        Match and filter assets for Windows x64.

        Args:
            assets: List of asset dicts from GitHub API with keys:
                    name, browser_download_url, size, sha256 (optional)

        Returns:
            Sorted list of AssetMatch objects
        """
        matches = []

        for asset in assets:
            name = asset.get("name", "")
            url = asset.get("browser_download_url", "")
            size = asset.get("size", 0)
            sha256 = asset.get("sha256", "")

            # Skip excluded files
            if self._is_excluded(name):
                continue

            # Detect architecture
            arch = self._detect_architecture(name)

            # Skip if architecture is unknown or disallowed
            if arch == Architecture.UNKNOWN:
                continue

            # Detect installer type
            inst_type = self._detect_installer_type(name)

            # Skip unknown installer types
            if inst_type == InstallerType.UNKNOWN:
                continue

            # Determine if download-only (ZIP files)
            # But if ZIP looks like it contains an installer, treat as installer not portable
            name_lower = name.lower()
            is_download_only = (inst_type == InstallerType.ZIP)
            if is_download_only:
                # Check if ZIP name suggests it contains an installer
                if re.search(r'(setup|install|-\d+\.\d+\.\d+-)', name_lower):
                    is_download_only = False  # ZIP likely contains an installer
                # Also check if there are MSI/EXE assets in the same release - if so, prefer those
                # This will be handled by get_best_match priority

            matches.append(AssetMatch(
                name=name,
                url=url,
                architecture=arch,
                installer_type=inst_type,
                is_download_only=is_download_only,
                size=size,
                sha256=sha256,
            ))

        # Sort by preference
        matches.sort(key=self._sort_key)
        return matches

    def get_best_match(self, assets: List[dict]) -> Optional[AssetMatch]:
            """Get the single best matching asset.

            Priority order (strict - only installer types):
            1. Inno Setup EXE installer (Setup.exe)
            2. WiX MSI installer
            3. ZIP containing installer (Setup/Install in name) - only if no EXE_SETUP/MSI
            """
            matches = self.match_assets(assets)

            if not matches:
                return None

            # Priority order: EXE_SETUP > MSI > ZIP_INSTALLER
            # ZIP and EXE_STANDALONE are NOT auto-selected
            priority = {
                InstallerType.EXE_SETUP: 0,
                InstallerType.MSI: 1,
                InstallerType.ZIP_INSTALLER: 2,
            }

            installer_matches = [m for m in matches if m.installer_type in priority]
            if installer_matches:
                installer_matches.sort(key=lambda m: priority.get(m.installer_type, 99))
                return installer_matches[0]

            return None

    def get_installer_options(self, assets: List[dict]) -> List[AssetMatch]:
        """Get all installer-type assets (EXE_SETUP, MSI, ZIP_INSTALLER) for user selection.
        
        Returns list sorted by installer priority: EXE_SETUP > MSI > ZIP_INSTALLER
        """
        matches = self.match_assets(assets)
        
        installer_priority = {
            InstallerType.EXE_SETUP: 0,
            InstallerType.MSI: 1,
            InstallerType.ZIP_INSTALLER: 2,
        }
        
        installer_matches = [m for m in matches if m.installer_type in installer_priority]
        installer_matches.sort(key=lambda m: installer_priority.get(m.installer_type, 99))
        return installer_matches


def get_asset_matcher(**kwargs) -> AssetMatcher:
    """Factory function to create AssetMatcher with defaults."""
    return AssetMatcher(**kwargs)