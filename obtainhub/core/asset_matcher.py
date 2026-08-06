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
    """Installer file types."""
    UNKNOWN = "unknown"
    MSI = "msi"
    EXE = "exe"
    ZIP = "zip"


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
            InstallerType.MSI: re.compile(r'\.msi$', re.IGNORECASE),
            InstallerType.EXE: re.compile(r'-Setup\.exe$|\.exe$', re.IGNORECASE),
            InstallerType.ZIP: re.compile(r'\.zip$', re.IGNORECASE),
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
        for installer_type, regex in self.installer_regexes.items():
            if regex.search(name):
                return installer_type
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
        # Installer priority: MSI > EXE > ZIP
        inst_priority = {
            InstallerType.MSI: 0,
            InstallerType.EXE: 1,
            InstallerType.ZIP: 2,
            InstallerType.UNKNOWN: 3,
        }
        return (
            arch_priority.get(match.architecture, 3),
            inst_priority.get(match.installer_type, 3),
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
            is_download_only = (inst_type == InstallerType.ZIP)

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
        """Get the single best matching asset."""
        matches = self.match_assets(assets)
        return matches[0] if matches else None


def get_asset_matcher(**kwargs) -> AssetMatcher:
    """Factory function to create AssetMatcher with defaults."""
    return AssetMatcher(**kwargs)