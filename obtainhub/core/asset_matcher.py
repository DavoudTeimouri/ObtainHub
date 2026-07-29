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
    ):
        self.prefer_x64 = prefer_x64
        self.allow_x86_fallback = allow_x86_fallback
        self.allow_prerelease = allow_prerelease
        self.allow_arm64 = allow_arm64

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
        return Architecture.UNKNOWN

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
        type_priority = {
            InstallerType.MSI: 0,
            InstallerType.EXE: 1,
            InstallerType.ZIP: 2,
            InstallerType.UNKNOWN: 3,
        }
        # Prefer installers (non-download-only) over download-only assets
        return (
            match.is_download_only,
            arch_priority.get(match.architecture, 3),
            type_priority.get(match.installer_type, 3),
            -match.size,
        )

    def match_assets(self, assets: List[dict]) -> List[AssetMatch]:
        """
        Match and filter assets for Windows x64.

        Args:
            assets: List of asset dicts from GitHub API with 'name', 'browser_download_url', 'size', 'sha256'

        Returns:
            List of AssetMatch sorted by preference (best first)
        """
        matches = []

        for asset in assets:
            name = asset.get("name", "")
            url = asset.get("browser_download_url", "")
            size = asset.get("size", 0)
            sha256 = asset.get("sha256", "")

            if not name or not url:
                continue

            # Skip excluded files
            if self._is_excluded(name):
                continue

            # Detect architecture
            arch = self._detect_architecture(name)

            # Skip if architecture is explicitly disallowed
            name_lower = name.lower()
            if not self.allow_arm64:
                arm64_matched = any(p.search(name_lower) for p in self.arch_regexes.get(Architecture.ARM64, []))
                if arm64_matched:
                    continue

            if not self.allow_x86_fallback:
                x86_matched = any(p.search(name_lower) for p in self.arch_regexes.get(Architecture.X86, []))
                if x86_matched:
                    continue

            # Detect installer type
            installer_type = self._detect_installer_type(name)

            # Determine if download-only (ZIP) vs installer
            is_download_only = installer_type == InstallerType.ZIP

            match = AssetMatch(
                name=name,
                url=url,
                architecture=arch,
                installer_type=installer_type,
                is_download_only=is_download_only,
                size=size,
                sha256=sha256,
            )
            matches.append(match)

        # Sort by preference
        matches.sort(key=self._sort_key)
        return matches

    def get_best_match(self, assets: List[dict]) -> Optional[AssetMatch]:
        """Get the single best matching asset."""
        # Handle case where pre-matched AssetMatch objects are passed
        if assets and isinstance(assets[0], AssetMatch):
            matches = assets
        else:
            matches = self.match_assets(assets)
        return matches[0] if matches else None


def get_system_architecture() -> Architecture:
    """Get the current system architecture."""
    import sys
    import platform

    if sys.platform != "win32":
        return Architecture.UNKNOWN

    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64"):
        return Architecture.X64
    elif machine in ("arm64", "aarch64"):
        return Architecture.ARM64
    elif machine in ("x86", "i386", "i686"):
        return Architecture.X86
    return Architecture.UNKNOWN


def is_windows_x64() -> bool:
    """Check if running on Windows x64."""
    import sys
    return sys.platform == "win32" and get_system_architecture() == Architecture.X64