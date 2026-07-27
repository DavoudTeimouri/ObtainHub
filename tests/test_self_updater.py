"""Tests for self_updater module."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from obtainhub.core.asset_matcher import (
    AssetInfo,
    Architecture,
    InstallerType,
    parse_asset,
    detect_architecture,
    detect_installer_type,
    filter_windows_x64_installers,
    find_best_installer,
    find_zip_assets,
    get_system_architecture,
    is_windows_x64,
    decide_download_action,
    DownloadDecision,
)
from obtainhub.core.self_updater import (
    ReleaseInfo,
    SelfUpdater,
    check_and_update,
)
from obtainhub.core.exceptions import SelfUpdateNotNeededError


class TestAssetMatcher:
    """Tests for asset matching and filtering."""
    
    def test_detect_architecture_x64(self):
        """Test x64 architecture detection."""
        assert detect_architecture("app-x64.msi") == Architecture.X64
        assert detect_architecture("app_amd64.exe") == Architecture.X64
        assert detect_architecture("app-win64.zip") == Architecture.X64
        assert detect_architecture("app-64.msi") == Architecture.X64
        assert detect_architecture("app_x64_setup.exe") == Architecture.X64
    
    def test_detect_architecture_x86(self):
        """Test x86 architecture detection."""
        assert detect_architecture("app-x86.msi") == Architecture.X86
        assert detect_architecture("app_win32.exe") == Architecture.X86
        assert detect_architecture("app-32bit.zip") == Architecture.X86
        assert detect_architecture("app-32.msi") == Architecture.X86
    
    def test_detect_architecture_arm64(self):
        """Test ARM64 architecture detection."""
        assert detect_architecture("app-arm64.msi") == Architecture.ARM64
        assert detect_architecture("app_aarch64.exe") == Architecture.ARM64
    
    def test_detect_architecture_unknown(self):
        """Test unknown architecture."""
        assert detect_architecture("app.msi") == Architecture.UNKNOWN
        assert detect_architecture("random_file.txt") == Architecture.UNKNOWN
    
    def test_detect_installer_type_msi(self):
        """Test MSI detection."""
        assert detect_installer_type("app.msi") == InstallerType.MSI
        assert detect_installer_type("APP.MSI") == InstallerType.MSI
    
    def test_detect_installer_type_exe_setup(self):
        """Test Setup.exe detection."""
        assert detect_installer_type("app-setup.exe") == InstallerType.EXE_SETUP
        assert detect_installer_type("app_setup.exe") == InstallerType.EXE_SETUP
        assert detect_installer_type("app-install.exe") == InstallerType.EXE_SETUP
        assert detect_installer_type("app_install.exe") == InstallerType.EXE_SETUP
        assert detect_installer_type("setup.exe") == InstallerType.EXE_SETUP
        assert detect_installer_type("install.exe") == InstallerType.EXE_SETUP
    
    def test_detect_installer_type_zip(self):
        """Test ZIP detection."""
        assert detect_installer_type("app.zip") == InstallerType.ZIP_PORTABLE
        assert detect_installer_type("app-portable.zip") == InstallerType.ZIP_PORTABLE
        assert detect_installer_type("app.ZIP") == InstallerType.ZIP_PORTABLE
    
    def test_detect_installer_type_unknown(self):
        """Test unknown type."""
        assert detect_installer_type("app.tar.gz") == InstallerType.UNKNOWN
        assert detect_installer_type("app.dmg") == InstallerType.UNKNOWN
    
    def test_parse_asset(self):
        """Test parsing asset into AssetInfo."""
        asset = parse_asset(
            asset_name="MyApp-x64-setup.exe",
            asset_url="https://github.com/owner/repo/releases/download/v1.0.0/MyApp-x64-setup.exe",
            asset_size=1024000,
            is_prerelease=False,
            version="1.0.0"
        )
        
        assert asset.name == "MyApp-x64-setup.exe"
        assert asset.installer_type == InstallerType.EXE_SETUP
        assert asset.architecture == Architecture.X64
        assert asset.is_prerelease is False
        assert asset.version == "1.0.0"
        assert asset.is_windows_x64_installer is True
    
    def test_parse_asset_msi(self):
        """Test parsing MSI asset."""
        asset = parse_asset(
            asset_name="MyApp-x64.msi",
            asset_url="https://example.com/MyApp-x64.msi",
            asset_size=5000000,
            is_prerelease=True,
            version="2.0.0-beta"
        )
        
        assert asset.installer_type == InstallerType.MSI
        assert asset.architecture == Architecture.X64
        assert asset.is_prerelease is True
        assert asset.is_windows_x64_installer is True
    
    def test_parse_asset_zip(self):
        """Test parsing ZIP asset."""
        asset = parse_asset(
            asset_name="MyApp-portable.zip",
            asset_url="https://example.com/MyApp-portable.zip",
            asset_size=2000000,
            is_prerelease=False,
            version="1.0.0"
        )
        
        assert asset.installer_type == InstallerType.ZIP_PORTABLE
        assert asset.is_zip_portable is True
        assert asset.is_windows_x64_installer is False
    
    def test_filter_windows_x64_installers(self):
        """Test filtering for Windows x64 installers."""
        assets = [
            AssetInfo("a", "u", 1, InstallerType.MSI, Architecture.X64, False, "1.0"),
            AssetInfo("b", "u", 1, InstallerType.EXE_SETUP, Architecture.X64, False, "1.0"),
            AssetInfo("c", "u", 1, InstallerType.ZIP_PORTABLE, Architecture.X64, False, "1.0"),
            AssetInfo("d", "u", 1, InstallerType.MSI, Architecture.X86, False, "1.0"),
            AssetInfo("e", "u", 1, InstallerType.MSI, Architecture.X64, True, "1.0"),  # prerelease
        ]
        
        # Without prerelease
        filtered = filter_windows_x64_installers(assets, allow_prerelease=False)
        assert len(filtered) == 2
        assert all(a.architecture == Architecture.X64 for a in filtered)
        assert all(a.installer_type in (InstallerType.MSI, InstallerType.EXE_SETUP) for a in filtered)
        
        # With prerelease
        filtered = filter_windows_x64_installers(assets, allow_prerelease=True)
        assert len(filtered) == 3
    
    def test_find_best_installer_prefers_msi(self):
        """Test that MSI is preferred over EXE."""
        assets = [
            AssetInfo("app-setup.exe", "u", 1, InstallerType.EXE_SETUP, Architecture.X64, False, "1.0"),
            AssetInfo("app.msi", "u", 1, InstallerType.MSI, Architecture.X64, False, "1.0"),
        ]
        
        best = find_best_installer(assets)
        assert best is not None
        assert best.installer_type == InstallerType.MSI
        assert best.name == "app.msi"
    
    def test_find_best_installer_returns_none_when_no_match(self):
        """Test returning None when no Windows x64 installer."""
        assets = [
            AssetInfo("app.zip", "u", 1, InstallerType.ZIP_PORTABLE, Architecture.X64, False, "1.0"),
            AssetInfo("app.msi", "u", 1, InstallerType.MSI, Architecture.X86, False, "1.0"),
        ]
        
        best = find_best_installer(assets)
        assert best is None
    
    def test_find_zip_assets(self):
        """Test finding ZIP assets."""
        assets = [
            AssetInfo("app.zip", "u", 1, InstallerType.ZIP_PORTABLE, Architecture.X64, False, "1.0"),
            AssetInfo("app-portable.zip", "u", 1, InstallerType.ZIP_PORTABLE, Architecture.X86, False, "1.0"),
            AssetInfo("app.msi", "u", 1, InstallerType.MSI, Architecture.X64, False, "1.0"),
        ]
        
        zips = find_zip_assets(assets)
        assert len(zips) == 2
        assert all(z.installer_type == InstallerType.ZIP_PORTABLE for z in zips)
    
    def test_decide_download_action_installer_found(self):
        """Test decision when installer found."""
        assets = [
            AssetInfo("app.msi", "u", 1, InstallerType.MSI, Architecture.X64, False, "1.0"),
        ]
        
        decision = decide_download_action(assets, allow_prerelease=False, requires_manual_uninstall=False)
        
        assert decision.action == 'install'
        assert decision.asset is not None
        assert decision.asset.name == "app.msi"
        assert decision.requires_confirmation is False
    
    def test_decide_download_action_manual_uninstall(self):
        """Test decision when manual uninstall required."""
        assets = [
            AssetInfo("app.msi", "u", 1, InstallerType.MSI, Architecture.X64, False, "1.0"),
        ]
        
        decision = decide_download_action(assets, allow_prerelease=False, requires_manual_uninstall=True)
        
        assert decision.action == 'manual_uninstall'
        assert decision.requires_confirmation is True
        assert "manual uninstallation" in decision.message
        assert "Auto-Uninstall" in decision.confirmation_prompt
    
    def test_decide_download_action_zip_fallback(self):
        """Test ZIP download-only fallback."""
        assets = [
            AssetInfo("app-portable.zip", "u", 1, InstallerType.ZIP_PORTABLE, Architecture.X64, False, "1.0"),
        ]
        
        decision = decide_download_action(assets, allow_prerelease=False)
        
        assert decision.action == 'download_only'
        assert decision.asset is not None
        assert decision.asset.installer_type == InstallerType.ZIP_PORTABLE
        assert "No Windows x64 installer" in decision.message
    
    def test_decide_download_action_skip(self):
        """Test skip when no suitable assets."""
        assets = [
            AssetInfo("app.dmg", "u", 1, InstallerType.UNKNOWN, Architecture.UNKNOWN, False, "1.0"),
        ]
        
        decision = decide_download_action(assets)
        
        assert decision.action == 'skip'
        assert decision.asset is None
    
    def test_is_windows_x64(self):
        """Test platform detection."""
        # This will depend on actual platform, just verify it runs
        result = is_windows_x64()
        assert isinstance(result, bool)


class TestSelfUpdater:
    """Tests for SelfUpdater."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock config."""
        with patch('obtainhub.core.self_updater.get_config') as mock:
            config = Mock()
            config.github_token = ""
            config.auto_update = True
            config.skip_self_update = False
            config.auto_confirm_prerelease = False
            config.get_download_dir.return_value = Path("/tmp/downloads")
            mock.return_value = config
            yield config
    
    def test_normalize_version(self, mock_config):
        """Test version normalization."""
        updater = SelfUpdater("1.0.0")
        v1 = updater._normalize_version("1.0.0")
        v2 = updater._normalize_version("v1.0.0")
        v3 = updater._normalize_version("V2.5.3")
        
        assert v1 == v2
        assert v3 == (2, 5, 3)
    
    def test_compare_versions(self, mock_config):
        """Test version comparison."""
        updater = SelfUpdater("1.0.0")
        
        assert updater._compare_versions((1, 0, 0), (1, 0, 0)) == 0
        assert updater._compare_versions((1, 0, 0), (2, 0, 0)) == -1
        assert updater._compare_versions((2, 0, 0), (1, 0, 0)) == 1
        assert updater._compare_versions((1, 1, 0), (1, 0, 0)) == 1
        assert updater._compare_versions((1, 0, 1), (1, 0, 0)) == 1
    
    def test_compare_versions_prerelease(self, mock_config):
        """Test version comparison with prerelease."""
        updater = SelfUpdater("1.0.0")
        
        v1 = updater._normalize_version("1.0.0")
        v2 = updater._normalize_version("1.0.0-alpha")
        
        # 1.0.0 > 1.0.0-alpha
        assert updater._compare_versions(v1, v2) == 1
        assert updater._compare_versions(v2, v1) == -1
    
    @patch('obtainhub.core.self_updater.SelfUpdater._make_request')
    def test_fetch_latest_release(self, mock_request, mock_config):
        """Test fetching latest release."""
        mock_request.return_value = {
            "tag_name": "v1.0.0",
            "name": "Release 1.0.0",
            "body": "Release notes",
            "prerelease": False,
            "draft": False,
            "published_at": "2024-01-01T00:00:00Z",
            "html_url": "https://github.com/ObtainHub/ObtainHub/releases/tag/v1.0.0",
            "assets": [
                {
                    "name": "ObtainHub-x64.msi",
                    "browser_download_url": "https://example.com/ObtainHub-x64.msi",
                    "size": 1000000,
                }
            ],
        }
        
        updater = SelfUpdater("0.9.0")
        release = updater.fetch_latest_release()
        
        assert release.version == "1.0.0"
        assert release.prerelease is False
        assert len(release.assets) == 1
        assert release.assets[0].name == "ObtainHub-x64.msi"
        assert release.assets[0].is_windows_x64_installer is True
    
    @patch('obtainhub.core.self_updater.SelfUpdater.fetch_latest_release')
    @patch('obtainhub.core.self_updater.is_windows_x64')
    def test_check_for_update_no_update_needed(self, mock_is_windows, mock_fetch, mock_config):
        """Test check_for_update when already on latest."""
        mock_is_windows.return_value = True
        mock_fetch.return_value = ReleaseInfo(
            version="1.0.0",
            name="Release 1.0.0",
            tag_name="v1.0.0",
            body="",
            prerelease=False,
            draft=False,
            published_at="",
            html_url="",
            assets=[
                AssetInfo("ObtainHub-x64.msi", "u", 1, InstallerType.MSI, Architecture.X64, False, "1.0.0"),
            ],
        )
        
        updater = SelfUpdater("1.0.0")
        
        with pytest.raises(SelfUpdateNotNeededError):
            updater.check_for_update()
    
    @patch('obtainhub.core.self_updater.SelfUpdater.fetch_latest_release')
    def test_check_for_update_prerelease_skipped(self, mock_fetch, mock_config):
        """Test prerelease is skipped by default."""
        mock_fetch.return_value = ReleaseInfo(
            version="2.0.0-beta",
            name="Release 2.0.0-beta",
            tag_name="v2.0.0-beta",
            body="",
            prerelease=True,
            draft=False,
            published_at="",
            html_url="",
            assets=[],
        )
        
        updater = SelfUpdater("1.0.0")
        result = updater.check_for_update(allow_prerelease=False)
        
        assert result is None
    
    @patch('obtainhub.core.self_updater.SelfUpdater.fetch_latest_release')
    @patch('obtainhub.core.self_updater.is_windows_x64')
    def test_check_for_update_prerelease_allowed(self, mock_is_windows, mock_fetch, mock_config):
        """Test prerelease is allowed when flag set."""
        mock_is_windows.return_value = True
        mock_fetch.return_value = ReleaseInfo(
            version="2.0.0-beta",
            name="Release 2.0.0-beta",
            tag_name="v2.0.0-beta",
            body="",
            prerelease=True,
            draft=False,
            published_at="",
            html_url="",
            assets=[
                AssetInfo("ObtainHub-x64.msi", "u", 1, InstallerType.MSI, Architecture.X64, True, "2.0.0-beta"),
            ],
        )
        
        updater = SelfUpdater("1.0.0")
        result = updater.check_for_update(allow_prerelease=True)
        
        assert result is not None
        assert result.version == "2.0.0-beta"
        assert result.prerelease is True
    
    @patch('obtainhub.core.self_updater.SelfUpdater.fetch_latest_release')
    def test_check_for_update_no_installer(self, mock_fetch, mock_config):
        """Test when no Windows x64 installer in release."""
        mock_fetch.return_value = ReleaseInfo(
            version="1.0.0",
            name="Release 1.0.0",
            tag_name="v1.0.0",
            body="",
            prerelease=False,
            draft=False,
            published_at="",
            html_url="",
            assets=[
                AssetInfo("ObtainHub.dmg", "u", 1, InstallerType.UNKNOWN, Architecture.UNKNOWN, False, "1.0.0"),
            ],
        )
        
        updater = SelfUpdater("0.9.0")
        result = updater.check_for_update()
        
        assert result is None