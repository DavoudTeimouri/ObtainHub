"""Tests for self_updater module."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from obtainhub.core.asset_matcher import (
    AssetMatch,
    InstallerType,
    Architecture,
    AssetMatcher,
)
from obtainhub.utils.helpers import get_architecture as get_system_architecture, is_windows_x64
from obtainhub.core.self_updater import (
    ReleaseInfo,
    SelfUpdater,
    check_and_update,
    SelfUpdateNotNeededError,
    SelfUpdateError,
    InstallerNotFoundError,
)


class TestAssetMatcher:
    """Tests for asset matching functionality."""

    @pytest.fixture
    def matcher(self):
        """Create a matcher instance."""
        return AssetMatcher(allow_x86_fallback=False)

    @pytest.fixture
    def matcher_with_fallback(self):
        """Create a matcher with x86 fallback."""
        return AssetMatcher(allow_x86_fallback=True)

    def test_detect_architecture_x64(self, matcher):
        """Test x64 architecture detection."""
        test_cases = [
            "app-x64.msi", "app-amd64.msi", "app-x86_64.msi",
            "app-win64.msi", "app-64bit.msi", "app-64.exe",
            "app_64.msi", "Setup-x64.exe",
        ]
        for name in test_cases:
            assets = [{"name": name, "browser_download_url": "url", "size": 100}]
            matches = matcher.match_assets(assets)
            assert len(matches) == 1, f"Failed for {name}"
            assert matches[0].architecture == Architecture.X64, f"Failed for {name}"

    def test_detect_architecture_x86(self, matcher_with_fallback):
        """Test x86 architecture detection with fallback."""
        test_cases = [
            "app-x86.msi", "app-win32.msi", "app-32bit.msi",
            "app-32-bit.msi", "app-32.exe", "app_32.msi",
        ]
        for name in test_cases:
            assets = [{"name": name, "browser_download_url": "url", "size": 100}]
            matches = matcher_with_fallback.match_assets(assets)
            assert len(matches) == 1, f"Failed for {name}"
            assert matches[0].architecture == Architecture.X86, f"Failed for {name}"

    def test_x86_rejected_without_fallback(self, matcher):
        """Test that x86 is rejected without fallback."""
        assets = [{"name": "app-x86.msi", "browser_download_url": "url", "size": 100}]
        matches = matcher.match_assets(assets)
        assert len(matches) == 0

    def test_arm64_rejected(self, matcher):
        """Test that ARM64 is rejected."""
        assets = [{"name": "app-arm64.msi", "browser_download_url": "url", "size": 100}]
        matches = matcher.match_assets(assets)
        assert len(matches) == 0

    def test_installer_type_msi(self, matcher):
        """Test MSI installer type detection."""
        assets = [{"name": "app-x64.msi", "browser_download_url": "url", "size": 100}]
        matches = matcher.match_assets(assets)
        assert len(matches) == 1
        assert matches[0].installer_type == InstallerType.MSI
        assert matches[0].is_download_only is False

    def test_installer_type_exe_setup(self, matcher):
        """Test EXE setup installer type detection."""
        test_cases = [
            "app-Setup.exe", "app-Install.exe", "Setup.exe",
            "Install.exe", "app-setup.exe", "app_setup.exe",
            "app-install.exe", "app_install.exe", "app.exe",
        ]
        for name in test_cases:
            assets = [{"name": name, "browser_download_url": "url", "size": 100}]
            matches = matcher.match_assets(assets)
            assert len(matches) == 1, f"Failed for {name}"
            assert matches[0].installer_type == InstallerType.EXE, f"Failed for {name}"
            assert matches[0].is_download_only is False, f"Failed for {name}"

    def test_installer_type_zip(self, matcher):
        """Test ZIP installer type detection (download only)."""
        assets = [{"name": "app-x64.zip", "browser_download_url": "url", "size": 100}]
        matches = matcher.match_assets(assets)
        assert len(matches) == 1
        assert matches[0].installer_type == InstallerType.ZIP
        assert matches[0].is_download_only is True

    def test_priority_msi_over_exe(self, matcher):
        """Test that MSI is preferred over EXE."""
        assets = [
            {"name": "app-Setup.exe", "browser_download_url": "url1", "size": 100},
            {"name": "app-x64.msi", "browser_download_url": "url2", "size": 100},
        ]
        matches = matcher.match_assets(assets)
        assert len(matches) == 2
        assert matches[0].installer_type == InstallerType.MSI
        assert matches[1].installer_type == InstallerType.EXE

    def test_priority_exe_over_zip(self, matcher):
        """Test that EXE is preferred over ZIP."""
        assets = [
            {"name": "app-x64.zip", "browser_download_url": "url1", "size": 100},
            {"name": "app-Setup.exe", "browser_download_url": "url2", "size": 100},
        ]
        matches = matcher.match_assets(assets)
        assert len(matches) == 2
        assert matches[0].installer_type == InstallerType.EXE
        assert matches[1].installer_type == InstallerType.ZIP

    def test_get_best_match(self, matcher):
        """Test getting best match from assets."""
        assets = [
            {"name": "app-Setup.exe", "browser_download_url": "url1", "size": 100},
            {"name": "app-x64.msi", "browser_download_url": "url2", "size": 100},
        ]
        matches = matcher.match_assets(assets)
        best = matcher.get_best_match(assets)
        assert best is not None
        assert best.installer_type == InstallerType.MSI

    def test_exclude_checksum_files(self, matcher):
        """Test that checksum files are excluded."""
        assets = [
            {"name": "app-x64.msi", "browser_download_url": "url1", "size": 100},
            {"name": "app-x64.msi.sha256", "browser_download_url": "url2", "size": 100},
            {"name": "app-x64.msi.asc", "browser_download_url": "url3", "size": 100},
            {"name": "app-x64.msi.sig", "browser_download_url": "url4", "size": 100},
            {"name": "app-x64.msi.blockmap", "browser_download_url": "url5", "size": 100},
        ]
        matches = matcher.match_assets(assets)
        assert len(matches) == 1
        assert matches[0].name == "app-x64.msi"


class TestRealWorldAssets:
    """Tests with realistic asset names."""

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
        assert matches[0].architecture == Architecture.X64

    def test_7zip_assets(self, matcher):
        """Test 7-Zip style assets."""
        assets = [
            {"name": "7z2301-x64.msi", "browser_download_url": "url1", "size": 100},
            {"name": "7z2301-arm64.msi", "browser_download_url": "url2", "size": 100},
        ]
        matches = matcher.match_assets(assets)
        assert len(matches) == 1
        assert matches[0].installer_type == InstallerType.MSI
        assert matches[0].architecture == Architecture.X64

    def test_git_for_windows_assets(self, matcher):
        """Test Git for Windows style assets."""
        assets = [
            {"name": "Git-2.43.0-64-bit.exe", "browser_download_url": "url1", "size": 100},
            {"name": "Git-2.43.0-32-bit.exe", "browser_download_url": "url2", "size": 100},
            {"name": "Git-2.43.0-64-bit.exe.sha256", "browser_download_url": "url3", "size": 100},
        ]
        matches = matcher.match_assets(assets)
        assert len(matches) == 1
        assert matches[0].architecture == Architecture.X64

    def test_obsidian_assets(self, matcher):
        """Test Obsidian style assets."""
        assets = [
            {"name": "Obsidian-1.5.3.exe", "browser_download_url": "url1", "size": 100},
            {"name": "Obsidian-1.5.3-arm64.exe", "browser_download_url": "url2", "size": 100},
            {"name": "Obsidian-1.5.3.dmg", "browser_download_url": "url3", "size": 100},
            {"name": "Obsidian-1.5.3.AppImage", "browser_download_url": "url4", "size": 100},
        ]
        matches = matcher.match_assets(assets)
        assert len(matches) == 1
        assert matches[0].architecture == Architecture.X64

    def test_firefox_assets(self, matcher):
        """Test Firefox style assets."""
        assets = [
            {"name": "Firefox Setup 122.0.exe", "browser_download_url": "url1", "size": 100},
            {"name": "Firefox Setup 122.0.msi", "browser_download_url": "url2", "size": 100},
            {"name": "firefox-122.0.tar.bz2", "browser_download_url": "url3", "size": 100},
        ]
        matches = matcher.match_assets(assets)
        assert len(matches) >= 2
        msi_matches = [m for m in matches if m.installer_type == InstallerType.MSI]
        assert len(msi_matches) >= 1

    def test_nodejs_assets(self, matcher):
        """Test Node.js style assets."""
        assets = [
            {"name": "node-v21.5.0-win-x64.zip", "browser_download_url": "url1", "size": 100},
            {"name": "node-v21.5.0-win-x86.zip", "browser_download_url": "url2", "size": 100},
            {"name": "node-v21.5.0-win-x64.msi", "browser_download_url": "url3", "size": 100},
            {"name": "node-v21.5.0-darwin-x64.tar.gz", "browser_download_url": "url4", "size": 100},
        ]
        matches = matcher.match_assets(assets)
        assert len(matches) >= 2
        assert all(m.architecture == Architecture.X64 for m in matches)

    def test_python_assets(self, matcher):
        """Test Python style assets."""
        assets = [
            {"name": "python-3.12.1-amd64.exe", "browser_download_url": "url1", "size": 100},
            {"name": "python-3.12.1-arm64.exe", "browser_download_url": "url2", "size": 100},
        ]
        matches = matcher.match_assets(assets)
        assert len(matches) == 1
        assert matches[0].architecture == Architecture.X64

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
        """Test system architecture detection."""
        arch = get_system_architecture()
        assert arch in ['x64', 'arm64', 'x86', 'unknown']

    def test_is_windows_x64(self):
        """Test Windows x64 check."""
        result = is_windows_x64()
        assert isinstance(result, bool)


class TestSelfUpdater:
    """Tests for SelfUpdater class."""

    @pytest.fixture
    def mock_config(self):
        """Mock config."""
        config = Mock()
        config.github_token = "test_token"
        config.prerelease_allowed = False
        config.update_check_interval_hours = 24
        config.allow_x86_fallback = False
        config.allow_arm64 = False
        config.prefer_x64 = True
        config.manual_uninstall_fallback = True
        config.downloads_dir = "/tmp/downloads"
        return config

    def test_compare_versions(self):
        """Test version comparison."""
        updater = SelfUpdater("1.0.0")
        
        # Semantic versions
        assert updater._compare_versions("2.0.0", "1.0.0") == 1
        assert updater._compare_versions("1.0.0", "1.0.0") == 0
        assert updater._compare_versions("1.0.0", "2.0.0") == -1
        
        # With v prefix
        assert updater._compare_versions("v2.0.0", "v1.0.0") == 1
        assert updater._compare_versions("v1.0.0", "v1.0.0") == 0
        
        # Prerelease handling
        assert updater._compare_versions("1.0.0", "1.0.0-beta") == 1
        assert updater._compare_versions("1.0.0-beta", "1.0.0") == -1

    def test_is_newer(self):
        """Test newer version check."""
        updater = SelfUpdater("1.0.0")
        assert updater._is_newer("2.0.0") is True
        assert updater._is_newer("1.0.0") is False
        assert updater._is_newer("0.9.0") is False

    def test_compare_versions_prerelease(self):
        """Test prerelease version comparison."""
        updater = SelfUpdater("1.0.0")
        assert updater._compare_versions("1.0.1", "1.0.0") == 1
        assert updater._compare_versions("1.0.0-beta", "1.0.0") == -1
        assert updater._compare_versions("1.0.0", "1.0.0-beta") == 1
        assert updater._compare_versions("1.0.0-beta.1", "1.0.0-beta") == 1
        assert updater._compare_versions("1.0.0-beta", "1.0.0-beta.1") == -1

    @patch('obtainhub.core.self_updater.is_windows_x64', return_value=True)
    def test_check_for_update_prerelease_skipped(self, mock_is_windows, mock_config):
        """Test prerelease skipped when not allowed."""
        # Create release with proper fields
        release = ReleaseInfo(
            version="2.0.0-beta",
            name="Release 2.0.0-beta",
            tag_name="v2.0.0-beta",
            body="Beta release",
            prerelease=True,
            draft=False,
            published_at="",
            html_url="",
            assets=[
                AssetMatch(
                    name="app-x64.msi",
                    url="https://example.com/app-x64.msi",
                    architecture=Architecture.X64,
                    installer_type=InstallerType.MSI,
                    is_download_only=False,
                    size=100,
                    sha256="",
                ),
            ],
        )
        
        with patch('obtainhub.core.self_updater.get_config', return_value=mock_config):
            updater = SelfUpdater("1.0.0")
            with patch.object(updater, 'fetch_latest_release', return_value=release):
                with pytest.raises(SelfUpdateNotNeededError, match="Prerelease skipped"):
                    updater.check_for_update(allow_prerelease=False)

    def test_check_for_update_prerelease_allowed(self, mock_config):
        """Test prerelease allowed when flag set."""
        mock_config.prerelease_allowed = True
        
        release = ReleaseInfo(
            version="2.0.0-beta",
            name="Release 2.0.0-beta",
            tag_name="v2.0.0-beta",
            body="Beta release",
            prerelease=True,
            draft=False,
            published_at="",
            html_url="",
            assets=[
                AssetMatch(
                    name="app-x64.msi",
                    url="https://example.com/app-x64.msi",
                    architecture=Architecture.X64,
                    installer_type=InstallerType.MSI,
                    is_download_only=False,
                    size=100,
                    sha256="",
                ),
            ],
        )
        
        with patch('obtainhub.core.self_updater.get_config', return_value=mock_config):
            with patch('obtainhub.core.self_updater.is_windows_x64', return_value=True):
                updater = SelfUpdater("1.0.0")
                with patch.object(updater, 'fetch_latest_release', return_value=release):
                    result = updater.check_for_update(allow_prerelease=True)
                    assert result is not None
                    assert result.version == "2.0.0-beta"

    @patch('obtainhub.core.self_updater.get_config')
    @patch('obtainhub.core.self_updater.is_windows_x64', return_value=True)
    def test_find_windows_x64_installer(self, mock_is_windows, mock_get_config, mock_config):
        """Test finding Windows x64 installer."""
        mock_get_config.return_value = mock_config
        
        release = ReleaseInfo(
            version="2.0.0",
            name="Release 2.0.0",
            tag_name="v2.0.0",
            body="Release notes",
            prerelease=False,
            draft=False,
            published_at="",
            html_url="",
            assets=[
                AssetMatch(
                    name="app-Setup.exe",
                    url="url1",
                    architecture=Architecture.X64,
                    installer_type=InstallerType.EXE,
                    is_download_only=False,
                    size=100,
                    sha256="",
                ),
                AssetMatch(
                    name="app-x64.msi",
                    url="url2",
                    architecture=Architecture.X64,
                    installer_type=InstallerType.MSI,
                    is_download_only=False,
                    size=100,
                    sha256="",
                ),
                AssetMatch(
                    name="app-arm64.msi",
                    url="url3",
                    architecture=Architecture.ARM64,
                    installer_type=InstallerType.MSI,
                    is_download_only=False,
                    size=100,
                    sha256="",
                ),
            ],
        )
        
        updater = SelfUpdater("1.0.0")
        installer = updater.find_windows_x64_installer(release, allow_prerelease=False)
        assert installer is not None
        assert installer.installer_type == InstallerType.MSI


class TestCheckAndUpdate:
    """Tests for check_and_update function."""

    @patch('obtainhub.core.self_updater.is_windows_x64', return_value=True)
    @patch('obtainhub.core.self_updater.get_config')
    def test_check_and_update_skip_flag(self, mock_get_config, mock_is_windows):
        """Test skip self-update flag."""
        mock_config = Mock()
        mock_config.skip_self_update = False
        mock_get_config.return_value = mock_config
        
        with patch('obtainhub.core.self_updater.SelfUpdater') as mock_updater_class:
            mock_updater = Mock()
            mock_updater_class.return_value = mock_updater
            mock_updater.perform_self_update.return_value = True
            result = check_and_update("1.0.0", skip_self_update=True)
            assert result is None  # Should skip and return None
            mock_updater.perform_self_update.assert_not_called()

    @patch('obtainhub.core.self_updater.is_windows_x64', return_value=True)
    @patch('obtainhub.core.self_updater.get_config')
    def test_check_and_update_config_skip(self, mock_get_config, mock_is_windows):
        """Test config-based skip."""
        mock_config = Mock()
        mock_config.skip_self_update = True
        mock_get_config.return_value = mock_config
        
        with patch('obtainhub.core.self_updater.SelfUpdater') as mock_updater_class:
            mock_updater = Mock()
            mock_updater_class.return_value = mock_updater
            mock_updater.perform_self_update.return_value = True
            result = check_and_update("1.0.0")
            assert result is None
            mock_updater.perform_self_update.assert_not_called()

    @patch('obtainhub.core.self_updater.is_windows_x64', return_value=True)
    @patch('obtainhub.core.self_updater.get_config')
    def test_check_and_update_not_needed(self, mock_get_config, mock_is_windows):
        """Test when update not needed."""
        mock_config = Mock()
        mock_config.skip_self_update = False
        mock_get_config.return_value = mock_config
        
        with patch('obtainhub.core.self_updater.SelfUpdater') as mock_updater_class:
            mock_updater = Mock()
            mock_updater_class.return_value = mock_updater
            mock_updater.check_for_update.side_effect = SelfUpdateNotNeededError("Already latest")
            result = check_and_update("2.0.0")
            assert result is False

    @patch('obtainhub.core.self_updater.is_windows_x64', return_value=True)
    @patch('obtainhub.core.self_updater.get_config')
    def test_check_and_update_error(self, mock_get_config, mock_is_windows):
        """Test error handling."""
        mock_config = Mock()
        mock_config.skip_self_update = False
        mock_get_config.return_value = mock_config
        
        with patch('obtainhub.core.self_updater.SelfUpdater') as mock_updater_class:
            mock_updater = Mock()
            mock_updater_class.return_value = mock_updater
            mock_updater.check_for_update.side_effect = SelfUpdateError("Network error")
            result = check_and_update("1.0.0")
            assert result is False

    @patch('obtainhub.core.self_updater.is_windows_x64', return_value=True)
    @patch('obtainhub.core.self_updater.get_config')
    def test_check_and_update_success(self, mock_get_config, mock_is_windows):
        """Test successful update."""
        mock_config = Mock()
        mock_config.skip_self_update = False
        mock_get_config.return_value = mock_config
        
        with patch('obtainhub.core.self_updater.SelfUpdater') as mock_updater_class:
            mock_updater = Mock()
            mock_updater_class.return_value = mock_updater
            mock_updater.check_for_update.return_value = Mock()  # ReleaseInfo mock
            mock_updater.perform_self_update.return_value = True
            result = check_and_update("1.0.0")
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])