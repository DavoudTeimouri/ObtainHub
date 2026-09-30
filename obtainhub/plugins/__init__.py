"""Plugin system for ObtainHub.

Defines the plugin interface and discovery mechanism.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from importlib.metadata import entry_points


@dataclass
class PluginContext:
    """Context provided to plugins at initialization."""
    config_dir: Path
    state_dir: Path
    download_dir: Path
    # Capability flags - plugins declare what they need
    can_read_config: bool = False
    can_write_config: bool = False
    can_read_state: bool = False
    can_write_state: bool = False
    can_network: bool = False
    can_execute: bool = False
    can_fs_read: bool = False
    can_fs_write: bool = False


class Plugin(ABC):
    """Base class for ObtainHub plugins."""

    name: str = ""
    version: str = "0.0.0"
    description: str = ""
    # Required capabilities - plugin declares what it needs
    required_capabilities: list[str] = []

    def __init__(self, context: PluginContext):
        self.context = context

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the plugin. Called once at startup."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Cleanup on shutdown."""
        pass

    def get_commands(self) -> dict:
        """Return command handlers this plugin provides.
        
        Returns dict of command_name -> handler_function
        Handler signature: (args, context) -> int (exit code)
        """
        return {}

    def get_hooks(self) -> dict[str, list]:
        """Return event hooks this plugin provides.
        
        Returns dict of event_name -> list of handler functions
        """
        return {}


class PluginManager:
    """Manages plugin discovery, loading, and lifecycle."""

    def __init__(self, context: PluginContext):
        self.context = context
        self.plugins: dict[str, Plugin] = {}
        self._command_map: dict[str, tuple[str, callable]] = {}  # cmd -> (plugin_name, handler)

    def discover_plugins(self) -> list[Plugin]:
        """Discover plugins via entry points."""
        plugins = []
        try:
            eps = entry_points(group="obtainhub.plugins")
            for ep in eps:
                try:
                    plugin_class = ep.load()
                    if isinstance(plugin_class, type) and issubclass(plugin_class, Plugin):
                        plugins.append(plugin_class)
                except Exception:
                    pass  # Skip broken plugins
        except Exception:
            pass
        return plugins

    def load_plugins(self, plugin_classes: list[type[Plugin]] = None) -> None:
        """Load and initialize plugins."""
        if plugin_classes is None:
            plugin_classes = self.discover_plugins()

        for plugin_class in plugin_classes:
            try:
                plugin = plugin_class(self.context)
                plugin.initialize()
                self.plugins[plugin_class.name] = plugin

                # Register commands
                for cmd_name, handler in plugin.get_commands().items():
                    self._command_map[cmd_name] = (plugin_class.name, handler)

                # Register hooks
                for event_name, handlers in plugin.get_hooks().items():
                    for handler in handlers:
                        from obtainhub.core.event_bus import get_event_bus
                        get_event_bus().subscribe(event_name, handler)

            except Exception as e:
                # Log but don't fail - other plugins should still load
                print(f"Warning: Failed to load plugin {plugin_class.__name__}: {e}")

    def get_command_handler(self, command: str) -> Optional[tuple[str, callable]]:
        """Get handler for a command."""
        return self._command_map.get(command)

    def shutdown(self) -> None:
        """Shutdown all plugins."""
        for plugin in self.plugins.values():
            try:
                plugin.shutdown()
            except Exception:
                pass
        self.plugins.clear()
        self._command_map.clear()


def get_plugin_manager(context: PluginContext) -> PluginManager:
    """Get a plugin manager instance."""
    return PluginManager(context)


# Export example plugin for testing
from obtainhub.plugins.example import ExamplePlugin

# Export sandbox components
from obtainhub.plugins.sandbox import (
    Capability,
    CapabilityEnforcer,
    PluginManifest,
    RestrictedConfigManager,
    RestrictedStateManager,
    RestrictedFilesystem,
    SubprocessSandbox,
    create_sandboxed_context,
)

__all__ = [
    "Plugin",
    "PluginContext",
    "PluginManager",
    "get_plugin_manager",
    "ExamplePlugin",
    "Capability",
    "CapabilityEnforcer",
    "PluginManifest",
    "RestrictedConfigManager",
    "RestrictedStateManager",
    "RestrictedFilesystem",
    "SubprocessSandbox",
    "create_sandboxed_context",
]