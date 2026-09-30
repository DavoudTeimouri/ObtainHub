"""Tests for plugin sandboxing."""

import tempfile
from pathlib import Path

import pytest

from obtainhub.plugins import PluginContext
from obtainhub.plugins.sandbox import (
    Capability,
    CapabilityEnforcer,
    PluginManifest,
    RestrictedConfigManager,
    RestrictedStateManager,
    RestrictedFilesystem,
    create_sandboxed_context,
)


class TestCapabilities:
    """Test capability definitions."""

    def test_capability_enum(self):
        assert Capability.READ_CONFIG.value == "read_config"
        assert Capability.WRITE_CONFIG.value == "write_config"
        assert Capability.READ_STATE.value == "read_state"
        assert Capability.WRITE_STATE.value == "write_state"
        assert Capability.NETWORK.value == "network"
        assert Capability.EXECUTE.value == "execute"
        assert Capability.FS_READ.value == "fs_read"
        assert Capability.FS_WRITE.value == "fs_write"


class TestPluginManifest:
    """Test plugin manifest."""

    def test_manifest_creation(self):
        manifest = PluginManifest(
            name="test",
            version="1.0.0",
            description="Test plugin",
            entry_point="test:TestPlugin",
            required_capabilities=["read_config", "fs_read"],
        )
        assert manifest.name == "test"
        assert manifest.required_capabilities == ["read_config", "fs_read"]


class TestCapabilityEnforcer:
    """Test capability enforcement."""

    def test_check_granted(self):
        context = PluginContext(
            config_dir=Path("/tmp/config"),
            state_dir=Path("/tmp/state"),
            download_dir=Path("/tmp/downloads"),
        )
        granted = {Capability.READ_CONFIG, Capability.FS_READ}
        enforcer = CapabilityEnforcer(context, granted)

        assert enforcer.check(Capability.READ_CONFIG) is True
        assert enforcer.check(Capability.FS_READ) is True
        assert enforcer.check(Capability.WRITE_CONFIG) is False

    def test_require_granted(self):
        context = PluginContext(
            config_dir=Path("/tmp/config"),
            state_dir=Path("/tmp/state"),
            download_dir=Path("/tmp/downloads"),
        )
        granted = {Capability.READ_CONFIG}
        enforcer = CapabilityEnforcer(context, granted)

        enforcer.require(Capability.READ_CONFIG)  # Should not raise

    def test_require_denied(self):
        context = PluginContext(
            config_dir=Path("/tmp/config"),
            state_dir=Path("/tmp/state"),
            download_dir=Path("/tmp/downloads"),
        )
        granted = {Capability.READ_CONFIG}
        enforcer = CapabilityEnforcer(context, granted)

        with pytest.raises(PermissionError):
            enforcer.require(Capability.WRITE_CONFIG)


class TestRestrictedConfigManager:
    """Test restricted config manager."""

    def test_read_allowed(self):
        from obtainhub.core.config import ConfigManager
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_manager = ConfigManager(config_dir=config_dir)
            context = PluginContext(
                config_dir=config_dir,
                state_dir=Path("/tmp/state"),
                download_dir=Path("/tmp/downloads"),
            )
            granted = {Capability.READ_CONFIG}
            enforcer = CapabilityEnforcer(context, granted)
            restricted = enforcer.wrap_config_manager(config_manager)

            config = restricted.load()
            assert config is not None

    def test_write_denied(self):
        from obtainhub.core.config import ConfigManager
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_manager = ConfigManager(config_dir=config_dir)
            context = PluginContext(
                config_dir=config_dir,
                state_dir=Path("/tmp/state"),
                download_dir=Path("/tmp/downloads"),
            )
            granted = {Capability.READ_CONFIG}  # No WRITE_CONFIG
            enforcer = CapabilityEnforcer(context, granted)
            restricted = enforcer.wrap_config_manager(config_manager)

            with pytest.raises(PermissionError):
                restricted.save()


class TestRestrictedStateManager:
    """Test restricted state manager."""

    def test_read_allowed(self):
        from obtainhub.core.state import StateManager
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state" / "state.json"
            state_manager = StateManager(state_file=state_file)
            context = PluginContext(
                config_dir=Path("/tmp/config"),
                state_dir=state_file.parent,
                download_dir=Path("/tmp/downloads"),
            )
            granted = {Capability.READ_STATE}
            enforcer = CapabilityEnforcer(context, granted)
            restricted = enforcer.wrap_state_manager(state_manager)

            apps = restricted.get_all_apps()
            assert isinstance(apps, list)

    def test_write_denied(self):
        from obtainhub.core.state import StateManager
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state" / "state.json"
            state_manager = StateManager(state_file=state_file)
            context = PluginContext(
                config_dir=Path("/tmp/config"),
                state_dir=state_file.parent,
                download_dir=Path("/tmp/downloads"),
            )
            granted = {Capability.READ_STATE}  # No WRITE_STATE
            enforcer = CapabilityEnforcer(context, granted)
            restricted = enforcer.wrap_state_manager(state_manager)

            with pytest.raises(PermissionError):
                restricted.add_installed_app({"id": "test/app", "name": "Test"})


class TestRestrictedFilesystem:
    """Test restricted filesystem access."""

    def test_read_allowed_in_config_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            test_file = config_dir / "test.txt"
            test_file.write_text("hello")

            context = PluginContext(
                config_dir=config_dir,
                state_dir=Path("/tmp/state"),
                download_dir=Path("/tmp/downloads"),
            )
            granted = {Capability.FS_READ}
            enforcer = CapabilityEnforcer(context, granted)
            fs = enforcer.wrap_filesystem()

            content = fs.read_text(test_file)
            assert content == "hello"

    def test_read_denied_outside_allowed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            outside_file = Path(tmpdir) / "secret.txt"
            outside_file.write_text("secret")

            context = PluginContext(
                config_dir=config_dir,
                state_dir=Path("/tmp/state"),
                download_dir=Path("/tmp/downloads"),
            )
            granted = {Capability.FS_READ}
            enforcer = CapabilityEnforcer(context, granted)
            fs = enforcer.wrap_filesystem()

            with pytest.raises(PermissionError):
                fs.read_text(outside_file)

    def test_write_allowed_in_download_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            download_dir = Path(tmpdir) / "downloads"
            download_dir.mkdir()
            context = PluginContext(
                config_dir=Path("/tmp/config"),
                state_dir=Path("/tmp/state"),
                download_dir=download_dir,
            )
            granted = {Capability.FS_WRITE}
            enforcer = CapabilityEnforcer(context, granted)
            fs = enforcer.wrap_filesystem()

            test_file = download_dir / "output.txt"
            fs.write_text(test_file, "written")
            assert test_file.read_text() == "written"

    def test_write_denied_outside_allowed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            context = PluginContext(
                config_dir=config_dir,
                state_dir=Path("/tmp/state"),
                download_dir=Path("/tmp/downloads"),
            )
            granted = {Capability.FS_WRITE}
            enforcer = CapabilityEnforcer(context, granted)
            fs = enforcer.wrap_filesystem()

            with pytest.raises(PermissionError):
                fs.write_text(config_dir / "not_allowed.txt", "data")


class TestCreateSandboxedContext:
    """Test sandboxed context creation."""

    def test_context_has_correct_flags(self):
        context = PluginContext(
            config_dir=Path("/tmp/config"),
            state_dir=Path("/tmp/state"),
            download_dir=Path("/tmp/downloads"),
        )
        manifest = PluginManifest(
            name="test",
            version="1.0.0",
            description="Test",
            entry_point="test:Test",
            required_capabilities=["read_config", "fs_read", "network"],
        )

        sandboxed = create_sandboxed_context(context, manifest)

        assert sandboxed.can_read_config is True
        assert sandboxed.can_write_config is False
        assert sandboxed.can_read_state is False
        assert sandboxed.can_write_state is False
        assert sandboxed.can_network is True
        assert sandboxed.can_execute is False
        assert sandboxed.can_fs_read is True
        assert sandboxed.can_fs_write is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])