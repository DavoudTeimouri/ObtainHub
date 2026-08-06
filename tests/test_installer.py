"""Tests for SilentInstaller."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from obtainhub.core.asset_matcher import InstallerType
from obtainhub.core.installer import (
    SilentInstaller,
    InstallResult,
    install_app,
)
from obtainhub.core.state import StateManager, InstalledApp


class TestSilentInstaller:
    """Test SilentInstaller class."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def state_manager(self, temp_dir):
        """Create StateManager instance."""
        return StateManager(state_dir=temp_dir)

    @pytest.fixture
    def installer(self, temp_dir, state_manager):
        """Create SilentInstaller instance."""
        with patch("obtainhub.core.installer.get_state_manager", return_value=state_manager):
            return SilentInstaller(download_dir=str(temp_dir), dry_run=True)

    def test_install_msi_dry_run(self, installer, temp_dir):
        """Test MSI install in dry run mode."""
        msi_file = temp_dir / "app.msi"
        msi_file.write_bytes(b"fake msi")

        result, message = installer.install(
            msi_file, InstallerType.MSI, "owner/repo"
        )

        assert result == InstallResult.SUCCESS
        assert "DRY RUN" in message

    def test_install_exe_dry_run(self, installer, temp_dir):
        """Test EXE install in dry run mode."""
        exe_file = temp_dir / "app.exe"
        exe_file.write_bytes(b"fake exe")

        result, message = installer.install(
            exe_file, InstallerType.EXE, "owner/repo"
        )

        assert result == InstallResult.SUCCESS
        assert "DRY RUN" in message

    def test_install_zip_download_only(self, installer, temp_dir):
        """Test ZIP file is download-only."""
        zip_file = temp_dir / "app.zip"
        zip_file.write_bytes(b"fake zip")

        result, message = installer.install(
            zip_file, InstallerType.ZIP, "owner/repo"
        )

        assert result == InstallResult.DOWNLOAD_ONLY
        assert "download-only" in message.lower()

    def test_install_download_only_flag(self, installer, temp_dir):
        """Test download-only flag overrides installer type."""
        msi_file = temp_dir / "app.msi"
        msi_file.write_bytes(b"fake msi")

        result, message = installer.install(
            msi_file, InstallerType.MSI, "owner/repo", download_only=True
        )

        assert result == InstallResult.DOWNLOAD_ONLY

    def test_install_manual_uninstall_required(self, installer, temp_dir, state_manager):
        """Test manual uninstall required detection."""
        # Add app with manual uninstall required
        app = InstalledApp(
            name="owner/repo",
            version="1.0.0",
            installer_type="msi",
            install_path=str(temp_dir / "old.msi"),
            source_url="https://github.com/owner/repo/releases/tag/v1.0.0",
            tag="v1.0.0",
            install_date="2024-01-01T00:00:00",
            requires_manual_uninstall=True,
        )
        state_manager.add_installed_app(app)

        msi_file = temp_dir / "app.msi"
        msi_file.write_bytes(b"fake msi")

        result, message = installer.install(
            msi_file, InstallerType.MSI, "owner/repo"
        )

        assert result == InstallResult.MANUAL_UNINSTALL_REQUIRED
        assert "manual uninstallation" in message.lower()

    def test_install_force_overrides_manual_uninstall(self, installer, temp_dir, state_manager):
        """Test force flag overrides manual uninstall."""
        # Add app with manual uninstall required
        app = InstalledApp(
            name="owner/repo",
            version="1.0.0",
            installer_type="msi",
            install_path=str(temp_dir / "old.msi"),
            source_url="https://github.com/owner/repo/releases/tag/v1.0.0",
            tag="v1.0.0",
            install_date="2024-01-01T00:00:00",
            requires_manual_uninstall=True,
        )
        state_manager.add_installed_app(app)

        msi_file = temp_dir / "app.msi"
        msi_file.write_bytes(b"fake msi")

        result, message = installer.install(
            msi_file, InstallerType.MSI, "owner/repo", force=True
        )

        # Should proceed with installation (dry run succeeds)
        assert result == InstallResult.SUCCESS

    def test_install_nonexistent_file(self, installer):
        """Test install with nonexistent file."""
        result, message = installer.install(
            Path("/nonexistent/app.msi"), InstallerType.MSI, "owner/repo"
        )

        assert result == InstallResult.FAILED
        assert "not found" in message.lower()

    def test_record_installation(self, installer, temp_dir, state_manager):
        """Test recording installation in state."""
        app = installer.record_installation(
            app_id="owner/repo",
            name="repo",
            version="1.0.0",
            installer_type=InstallerType.MSI,
            installer_path=str(temp_dir / "app.msi"),
            source_url="https://github.com/owner/repo/releases/tag/v1.0.0",
            tag="v1.0.0",
        )

        assert app.name == "owner/repo"
        assert app.version == "1.0.0"
        assert app.installer_type == "msi"

        # Verify in state
        stored = state_manager.get_installed_app("owner/repo")
        assert stored is not None
        assert stored.version == "1.0.0"

    def test_record_update(self, installer, temp_dir, state_manager):
        """Test recording update in state."""
        # Add initial app
        initial = InstalledApp(
            name="owner/repo",
            version="1.0.0",
            installer_type="msi",
            install_path=str(temp_dir / "old.msi"),
            source_url="https://github.com/owner/repo/releases/tag/v1.0.0",
            tag="v1.0.0",
            install_date="2024-01-01T00:00:00",
        )
        state_manager.add_installed_app(initial)

        # Record update
        app = installer.record_update(
            app_id="owner/repo",
            version="2.0.0",
            installer_type=InstallerType.MSI,
            installer_path=str(temp_dir / "new.msi"),
            source_url="https://github.com/owner/repo/releases/tag/v2.0.0",
            tag="v2.0.0",
        )

        assert app.version == "2.0.0"
        assert app.install_path == str(temp_dir / "new.msi")

        # Verify in state
        stored = state_manager.get_installed_app("owner/repo")
        assert stored.version == "2.0.0"


class TestInstallApp:
    """Test install_app convenience function."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @patch("obtainhub.core.installer.SilentInstaller.install")
    def test_install_app(self, mock_install, temp_dir):
        """Test install_app function."""
        mock_install.return_value = (InstallResult.SUCCESS, "Success")

        msi_file = temp_dir / "app.msi"
        msi_file.write_bytes(b"fake")

        result, message = install_app(
            msi_file, InstallerType.MSI, "owner/repo", dry_run=True
        )

        assert result == InstallResult.SUCCESS
        mock_install.assert_called_once()