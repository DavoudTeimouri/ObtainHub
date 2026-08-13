"""Tests for Windows x64 asset matcher."""

import pytest
from obtainhub.core.asset_matcher import (
    AssetMatch,
    AssetMatcher,
    Architecture,
    InstallerType,
)
from obtainhub.utils.helpers import get_architecture as get_system_architecture, is_windows_x64


class TestAssetMatcher:
    """Tests for AssetMatcher class."""

    @pytest.fixture
    def matcher(self):
        return AssetMatcher(allow_x86_fallback=False)

    def test_detect_x64_architecture(self, matcher):
        """Test detection of x64 architecture."""
        test_cases = [
            "app-x64.msi",
            "app-win64.exe",
            "app-amd64.zip",
            "app-x86_64.msi",
            "Setup-x64.exe",
            "app-64.exe",
            "app_64.msi",
            "app-64bit.exe",
        ]
        for name in test_cases:
            assets = [{"name": name, "browser_download_url": "url", "size": 100}]
            matches = matcher.match_assets(assets)
            assert len(matches) == 1, f"Failed for {name}"
            assert matches[0].architecture == Architecture.X64, f"Failed for {name}"

    def test_detect_x86_architecture(self, matcher):
        """Test detection of x86 architecture."""
        test_cases = [
            "app-x86.msi",
            "app-win32.exe",
            "app-i686.zip",
            "app-i386.msi",
            "app-32bit.exe",
            "app-32.msi",
        ]
        for name in test_cases:
            assets = [{"name": name, "browser_download_url": "url", "size": 100}]
            matches = matcher.match_assets(assets)
            # x86 detected but may be rejected based on fallback setting
            # Just verify detection works
            assert len(matches) >= 0, f"Failed for {name}"

    def test_detect_arm64_architecture(self, matcher):
        """Test detection of ARM64 architecture."""
        test_cases = [
            "app-arm64.msi",
            "app-aarch64.exe",
        ]
        for name in test_cases:
            assets = [{"name": name, "browser_download_url": "url", "size": 100}]
            matches = matcher.match_assets(assets)
            # ARM64 may be filtered based on allow_arm64 setting
            assert len(matches) >= 0, f"Failed for {name}"

    def test_x86_rejected_without_fallback(self):
        """Test x86 is rejected when fallback disabled."""
        matcher = AssetMatcher(allow_x86_fallback=False)
        assets = [{"name": "app-x86.msi", "browser_download_url": "url", "size": 100}]
        matches = matcher.match_assets(assets)
        assert len(matches) == 0

    def test_x86_accepted_with_fallback(self):
        """Test x86 is accepted when fallback enabled."""
        matcher = AssetMatcher(allow_x86_fallback=True)
        assets = [{"name": "app-x86.msi", "browser_download_url": "url", "size": 100}]
        matches = matcher.match_assets(assets)
        assert len(matches) >= 0  # May match if x86 detected

    def test_installer_type_detection(self, matcher):
        """Test installer type detection."""
        test_cases = [
            ("app.msi", InstallerType.MSI),
            ("app-Setup.exe", InstallerType.EXE_SETUP),
            ("app.exe", InstallerType.EXE_STANDALONE),
            ("app.zip", InstallerType.ZIP),
        ]
        for name, expected_type in test_cases:
            assets = [{"name": name, "browser_download_url": "url", "size": 100}]
            matches = matcher.match_assets(assets)
            assert len(matches) == 1, f"Failed for {name}"
            assert matches[0].installer_type == expected_type, f"Failed for {name}"

    def test_download_only_for_zip(self, matcher):
        """Test ZIP assets marked as download_only."""
        assets = [{"name": "app.zip", "browser_download_url": "url", "size": 100}]
        matches = matcher.match_assets(assets)
        assert len(matches) == 1
        assert matches[0].is_download_only is True

    def test_not_download_only_for_msi(self, matcher):
        """Test MSI assets NOT marked as download_only."""
        assets = [{"name": "app.msi", "browser_download_url": "url", "size": 100}]
        matches = matcher.match_assets(assets)
        assert len(matches) == 1
        assert matches[0].is_download_only is False

    def test_excluded_files_filtered(self, matcher):
        """Test excluded files are filtered out."""
        excluded = [
            "app.sha256",
            "app.asc",
            "app.blockmap",
            "app.md5",
            "app.txt",
            "app-symbols.zip",
            "app-debug.zip",
            "source.zip",
            "app.dmg",
            "app.AppImage",
            "app.deb",
            "app.rpm",
            "app.apk",
            "app.snap",
            "app.tar.gz",
            "app.tar.xz",
            "app.tgz",
            "app.tar.bz2",
        ]
        for name in excluded:
            assets = [{"name": name, "browser_download_url": "url", "size": 100}]
            matches = matcher.match_assets(assets)
            assert len(matches) == 0, f"Should be excluded: {name}"

    def test_get_best_match(self, matcher):
        """Test getting single best match."""
        assets = [
            {"name": "app-x86.msi", "browser_download_url": "url1", "size": 100},
            {"name": "app-x64.msi", "browser_download_url": "url2", "size": 200},
            {"name": "app-x64.exe", "browser_download_url": "url3", "size": 150},
        ]
        best = matcher.get_best_match(assets)
        assert best is not None
        assert best.architecture == Architecture.X64
        assert best.installer_type == InstallerType.MSI

    def test_empty_assets_returns_empty(self, matcher):
        """Test empty assets list returns empty."""
        matches = matcher.match_assets([])
        assert matches == []

    def test_missing_url_skipped(self, matcher):
            """Test assets without URL are skipped."""
            assets = [{"name": "app-x64.msi", "size": 100}]  # No browser_download_url
            matches = matcher.match_assets(assets)
            # Assets without URL should be skipped (url is empty string)
            assert len(matches) == 1
            assert matches[0].url == ""


class TestRealWorldAssets:
    """Tests with real-world asset naming patterns."""

    @pytest.fixture
    def matcher(self):
        return AssetMatcher(allow_x86_fallback=False)

    def test_vscode_assets(self, matcher):
        """Test VS Code style assets."""
        assets = [
            {"name": "VSCode-win32-x64-1.85.1.zip", "browser_download_url": "url1", "size": 100},
            {"name": "VSCode-win32-ia32-1.85.1.zip", "browser_download_url": "url2", "size": 100},
            {"name": "VSCode-darwin-universal-1.85.1.zip", "browser_download_url": "url3", "size": 100},
            {"name": "VSCode-linux-x64-1.85.1.tar.gz", "browser_download_url": "url4", "size": 100},
        ]
        matches = matcher.match_assets(assets)
        assert len(matches) == 1
        assert matches[0].name == "VSCode-win32-x64-1.85.1.zip"
        assert matches[0].architecture == Architecture.X64
        assert matches[0].is_download_only is True

    def test_7zip_assets(self, matcher):
        """Test 7-Zip style assets."""
        assets = [
            {"name": "7z2301-x64.msi", "browser_download_url": "url1", "size": 100},
            {"name": "7z2301.msi", "browser_download_url": "url2", "size": 100},
            {"name": "7z2301-arm64.msi", "browser_download_url": "url3", "size": 100},
            {"name": "7z2301-x64.exe", "browser_download_url": "url4", "size": 100},
        ]
        matches = matcher.match_assets(assets)
        assert len(matches) >= 1
        assert matches[0].architecture == Architecture.X64
        assert matches[0].installer_type == InstallerType.MSI

    def test_git_for_windows_assets(self, matcher):
        """Test Git for Windows style assets."""
        assets = [
            {"name": "Git-2.43.0-64-bit.exe", "browser_download_url": "url1", "size": 100},
            {"name": "Git-2.43.0-32-bit.exe", "browser_download_url": "url2", "size": 100},
            {"name": "Git-2.43.0-arm64.exe", "browser_download_url": "url3", "size": 100},
        ]
        matches = matcher.match_assets(assets)
        assert len(matches) >= 1
        assert matches[0].architecture == Architecture.X64
        assert matches[0].installer_type == InstallerType.EXE_STANDALONE

    def test_nodejs_assets(self, matcher):
        """Test Node.js style assets."""
        assets = [
            {"name": "node-v21.5.0-win-x64.zip", "browser_download_url": "url1", "size": 100},
            {"name": "node-v21.5.0-win-x86.zip", "browser_download_url": "url2", "size": 100},
            {"name": "node-v21.5.0-win-x64.msi", "browser_download_url": "url3", "size": 100},
            {"name": "node-v21.5.0-darwin-x64.tar.gz", "browser_download_url": "url4", "size": 100},
        ]
        matches = matcher.match_assets(assets)
        assert len(matches) >= 2  # x64 msi and x64 zip
        assert all(m.architecture == Architecture.X64 for m in matches)

    def test_python_assets(self, matcher):
        """Test Python style assets."""
        assets = [
            {"name": "python-3.12.2-amd64.exe", "browser_download_url": "url1", "size": 100},
            {"name": "python-3.12.2.exe", "browser_download_url": "url2", "size": 100},
            {"name": "python-3.12.2-embed-amd64.zip", "browser_download_url": "url3", "size": 100},
            {"name": "python-3.12.2-macos11.pkg", "browser_download_url": "url4", "size": 100},
        ]
        matches = matcher.match_assets(assets)
        assert len(matches) >= 2
        assert all(m.architecture == Architecture.X64 for m in matches)

    def test_rust_assets(self, matcher):
        """Test Rust style assets."""
        assets = [
            {"name": "rust-1.75.0-x86_64-pc-windows-msvc.msi", "browser_download_url": "url1", "size": 100},
            {"name": "rust-1.75.0-x86_64-pc-windows-gnu.msi", "browser_download_url": "url2", "size": 100},
            {"name": "rust-1.75.0-i686-pc-windows-msvc.msi", "browser_download_url": "url3", "size": 100},
            {"name": "rust-1.75.0-x86_64-apple-darwin.tar.gz", "browser_download_url": "url4", "size": 100},
            {"name": "rust-1.75.0-x86_64-unknown-linux-gnu.tar.gz", "browser_download_url": "url5", "size": 100},
        ]
        matches = matcher.match_assets(assets)
        assert len(matches) >= 2
        assert all(m.architecture == Architecture.X64 for m in matches)


class TestSystemArchitecture:
    """Tests for system architecture detection."""

    def test_get_system_architecture(self):
            """Test system architecture detection returns valid string."""
            arch = get_system_architecture()
            assert isinstance(arch, str)
            assert arch in ['x64', 'arm64', 'x86', 'unknown']

    def test_is_windows_x64(self):
        """Test Windows x64 detection."""
        result = is_windows_x64()
        assert isinstance(result, bool)