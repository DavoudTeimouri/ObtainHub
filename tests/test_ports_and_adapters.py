"""Tests for ports and adapters."""

import tempfile
from pathlib import Path

import pytest

from obtainhub.core.event_bus import EventBus as CoreEventBus, get_event_bus
from obtainhub.plugins import ExamplePlugin, PluginContext, PluginManager
from obtainhub.ports import (
    ReleaseInfo,
    SearchResult,
    RateLimitInfo,
)
from obtainhub.adapters.github_adapter import GitHubAdapter
from obtainhub.adapters.json_state_store import JsonStateStore


class TestPorts:
    """Test port interfaces."""

    def test_release_info_creation(self):
        release = ReleaseInfo(
            tag_name="v1.0.0",
            version="1.0.0",
            html_url="https://github.com/test/repo/releases/tag/v1.0.0",
            body="Release notes",
            prerelease=False,
            draft=False,
            assets=[{"name": "app.exe", "url": "https://example.com/app.exe", "size": 1000}],
            published_at="2024-01-01T00:00:00Z",
            checksums={"app.exe": "sha256..."},
        )
        assert release.version == "1.0.0"
        assert release.prerelease is False

    def test_search_result_creation(self):
        result = SearchResult(items=[{"full_name": "test/repo", "stargazers_count": 100}])
        assert len(result.items) == 1
        assert result.error is None

    def test_rate_limit_info_creation(self):
        info = RateLimitInfo(limit=5000, remaining=4999, reset_at=1234567890)
        assert info.limit == 5000
        assert info.remaining == 4999


class TestEventBus:
    """Test EventBus implementation."""

    def test_publish_subscribe(self):
        bus = CoreEventBus()
        received = []

        def handler(data):
            received.append(data)

        bus.subscribe("test_event", handler)
        bus.publish("test_event", {"key": "value"})
        assert len(received) == 1
        assert received[0]["key"] == "value"

    def test_multiple_subscribers(self):
        bus = CoreEventBus()
        received1 = []
        received2 = []

        bus.subscribe("test", lambda d: received1.append(d))
        bus.subscribe("test", lambda d: received2.append(d))
        bus.publish("test", {"x": 1})
        assert len(received1) == 1
        assert len(received2) == 1

    def test_unsubscribe(self):
        bus = CoreEventBus()
        received = []

        def handler(data):
            received.append(data)

        bus.subscribe("test", handler)
        bus.publish("test", {"a": 1})
        assert len(received) == 1

        bus.unsubscribe("test", handler)
        bus.publish("test", {"a": 2})
        assert len(received) == 1  # No new event


class TestCoreEventBus:
    """Test global event bus."""

    def test_get_event_bus_singleton(self):
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2
        # Clean up
        bus1.clear()


class TestJsonStateStore:
    """Test JSON state store adapter."""

    @pytest.fixture
    def temp_state_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            yield Path(f.name)
        # Cleanup
        try:
            Path(f.name).unlink()
        except Exception:
            pass
        # Also cleanup history file
        try:
            Path(f.name).with_name("check_history.json").unlink()
        except Exception:
            pass

    def test_load_empty(self, temp_state_file):
        store = JsonStateStore(temp_state_file)
        apps = store.load()
        assert apps == []

    def test_save_and_load(self, temp_state_file):
        store = JsonStateStore(temp_state_file)
        apps = [{"id": "test/app", "name": "Test", "version": "1.0.0"}]
        store.save(apps)
        loaded = store.load()
        assert loaded == apps

    def test_add_app(self, temp_state_file):
        store = JsonStateStore(temp_state_file)
        store.add_app({"id": "test/app", "name": "Test"})
        apps = store.load()
        assert len(apps) == 1
        assert apps[0]["id"] == "test/app"

    def test_update_app(self, temp_state_file):
        store = JsonStateStore(temp_state_file)
        store.add_app({"id": "test/app", "name": "Test", "version": "1.0.0"})
        store.update_app("test/app", {"version": "2.0.0"})
        app = store.get_app("test/app")
        assert app["version"] == "2.0.0"

    def test_remove_app(self, temp_state_file):
        store = JsonStateStore(temp_state_file)
        store.add_app({"id": "test/app", "name": "Test"})
        store.remove_app("test/app")
        apps = store.load()
        assert len(apps) == 0

    def test_get_app(self, temp_state_file):
        store = JsonStateStore(temp_state_file)
        store.add_app({"id": "test/app", "name": "Test"})
        app = store.get_app("test/app")
        assert app is not None
        assert app["name"] == "Test"

        # Non-existent
        app = store.get_app("nonexistent")
        assert app is None

    def test_check_history(self, temp_state_file):
        store = JsonStateStore(temp_state_file)
        store.add_check_history({"app_name": "test", "user_choice": "managed"})
        history = store.get_check_history()
        assert "test" in history
        assert history["test"]["user_choice"] == "managed"

        store.clear_check_history()
        history = store.get_check_history()
        assert history == {}


class TestGitHubAdapter:
    """Test GitHub adapter (mocked)."""

    def test_adapter_initialization(self):
        adapter = GitHubAdapter(token="test-token")
        assert adapter.token == "test-token"
        assert adapter.headers["Authorization"] == "Bearer test-token"

    def test_adapter_no_token(self):
        adapter = GitHubAdapter()
        assert adapter.token is None
        assert "Authorization" not in adapter.headers


class TestPluginSystem:
    """Test plugin system."""

    def test_plugin_context(self):
        from obtainhub.plugins import PluginContext
        ctx = PluginContext(
            config_dir=Path("/tmp/config"),
            state_dir=Path("/tmp/state"),
            download_dir=Path("/tmp/downloads"),
        )
        assert ctx.config_dir == Path("/tmp/config")
        assert ctx.can_read_config is False

    def test_example_plugin(self):
        from obtainhub.plugins import ExamplePlugin, PluginContext
        ctx = PluginContext(
            config_dir=Path("/tmp/config"),
            state_dir=Path("/tmp/state"),
            download_dir=Path("/tmp/downloads"),
        )
        plugin = ExamplePlugin(ctx)
        assert plugin.name == "example"
        assert plugin.version == "1.0.0"

        plugin.initialize()
        plugin.shutdown()

        commands = plugin.get_commands()
        assert "hello" in commands

        hooks = plugin.get_hooks()
        assert "app_installed" in hooks

    def test_plugin_manager_discover(self):
        from obtainhub.plugins import PluginManager, PluginContext
        ctx = PluginContext(
            config_dir=Path("/tmp/config"),
            state_dir=Path("/tmp/state"),
            download_dir=Path("/tmp/downloads"),
        )
        manager = PluginManager(ctx)
        plugins = manager.discover_plugins()
        # Should not crash, may return empty list
        assert isinstance(plugins, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])