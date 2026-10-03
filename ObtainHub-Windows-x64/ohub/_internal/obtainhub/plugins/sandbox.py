"""Plugin sandboxing and capability enforcement for ObtainHub.

This module provides a restricted execution environment for plugins
with capability-based access control.
"""

import os
import sys
import subprocess
import json
import tempfile
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from obtainhub.plugins import PluginContext


class Capability(Enum):
    """Plugin capabilities - granular permissions."""
    READ_CONFIG = "read_config"
    WRITE_CONFIG = "write_config"
    READ_STATE = "read_state"
    WRITE_STATE = "write_state"
    NETWORK = "network"
    EXECUTE = "execute"
    FS_READ = "fs_read"
    FS_WRITE = "fs_write"
    REGISTRY_READ = "registry_read"
    REGISTRY_WRITE = "registry_write"


@dataclass
class PluginManifest:
    """Plugin manifest (from plugin.yaml or embedded metadata)."""
    name: str
    version: str
    description: str
    entry_point: str  # module:ClassName
    required_capabilities: list[str] = field(default_factory=list)
    optional_capabilities: list[str] = field(default_factory=list)
    author: str = ""
    license: str = ""
    homepage: str = ""
    min_obtainhub_version: str = "1.0.0"
    max_obtainhub_version: str = ""
    signature: str = ""  # Base64 encoded signature for verification


class CapabilityEnforcer:
    """Enforces plugin capabilities at runtime."""

    def __init__(self, context: PluginContext, granted_capabilities: set[Capability]):
        self.context = context
        self.granted = granted_capabilities

    def check(self, capability: Capability) -> bool:
        """Check if a capability is granted."""
        return capability in self.granted

    def require(self, capability: Capability) -> None:
        """Raise if capability not granted."""
        if not self.check(capability):
            raise PermissionError(f"Plugin requires capability: {capability.value}")

    def wrap_config_manager(self, config_manager) -> "RestrictedConfigManager":
        """Return a restricted config manager."""
        return RestrictedConfigManager(config_manager, self)

    def wrap_state_manager(self, state_manager) -> "RestrictedStateManager":
        """Return a restricted state manager."""
        return RestrictedStateManager(state_manager, self)

    def wrap_filesystem(self) -> "RestrictedFilesystem":
        """Return a restricted filesystem accessor."""
        return RestrictedFilesystem(self.context, self)


class RestrictedConfigManager:
    """Config manager with capability enforcement."""

    def __init__(self, config_manager, enforcer: CapabilityEnforcer):
        self._config_manager = config_manager
        self._enforcer = enforcer

    def load(self):
        self._enforcer.require(Capability.READ_CONFIG)
        return self._config_manager.load()

    def save(self, config=None):
        self._enforcer.require(Capability.WRITE_CONFIG)
        return self._config_manager.save(config)

    def get(self, key, default=None):
        self._enforcer.require(Capability.READ_CONFIG)
        return self._config_manager.get(key, default)

    def set(self, key, value):
        self._enforcer.require(Capability.WRITE_CONFIG)
        return self._config_manager.set(key, value)

    def add_manifest_source(self, *args, **kwargs):
        self._enforcer.require(Capability.WRITE_CONFIG)
        return self._config_manager.add_manifest_source(*args, **kwargs)

    def remove_manifest_source(self, *args, **kwargs):
        self._enforcer.require(Capability.WRITE_CONFIG)
        return self._config_manager.remove_manifest_source(*args, **kwargs)


class RestrictedStateManager:
    """State manager with capability enforcement."""

    def __init__(self, state_manager, enforcer: CapabilityEnforcer):
        self._state_manager = state_manager
        self._enforcer = enforcer

    def get_app(self, app_id):
        self._enforcer.require(Capability.READ_STATE)
        return self._state_manager.get_app(app_id)

    def get_all_apps(self):
        self._enforcer.require(Capability.READ_STATE)
        return self._state_manager.get_all_apps()

    def add_installed_app(self, app):
        self._enforcer.require(Capability.WRITE_STATE)
        return self._state_manager.add_installed_app(app)

    def update_app(self, app_id, updates):
        self._enforcer.require(Capability.WRITE_STATE)
        return self._state_manager.update_app(app_id, updates)

    def remove_app(self, app_id):
        self._enforcer.require(Capability.WRITE_STATE)
        return self._state_manager.remove_app(app_id)

    def add_check_history(self, entry):
        self._enforcer.require(Capability.WRITE_STATE)
        return self._state_manager.add_check_history(entry)

    def get_check_history(self):
        self._enforcer.require(Capability.READ_STATE)
        return self._state_manager.get_check_history()


class RestrictedFilesystem:
    """Filesystem accessor with capability enforcement and path restrictions."""

    def __init__(self, context: PluginContext, enforcer: CapabilityEnforcer):
        self.context = context
        self.enforcer = enforcer
        # Allowed base directories
        self._allowed_read = [
            context.config_dir,
            context.state_dir,
            context.download_dir,
            Path.home() / ".config" / "obtainhub",
            Path.home() / ".local" / "share" / "obtainhub",
        ]
        self._allowed_write = [
            context.download_dir,
        ]

    def _is_allowed(self, path: Path, write: bool = False) -> bool:
        """Check if path is within allowed directories."""
        path = Path(path).resolve()
        allowed = self._allowed_write if write else self._allowed_read
        for base in allowed:
            try:
                path.relative_to(base.resolve())
                return True
            except ValueError:
                continue
        return False

    def read_text(self, path: Path, encoding: str = "utf-8") -> str:
        self.enforcer.require(Capability.FS_READ)
        if not self._is_allowed(path, write=False):
            raise PermissionError(f"Read access denied: {path}")
        return Path(path).read_text(encoding=encoding)

    def write_text(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        self.enforcer.require(Capability.FS_WRITE)
        if not self._is_allowed(path, write=True):
            raise PermissionError(f"Write access denied: {path}")
        Path(path).write_text(content, encoding=encoding)

    def read_json(self, path: Path) -> dict:
        return json.loads(self.read_text(path))

    def write_json(self, path: Path, data: dict, indent: int = 2) -> None:
        self.write_text(path, json.dumps(data, indent=indent))

    def list_dir(self, path: Path) -> list[Path]:
        self.enforcer.require(Capability.FS_READ)
        if not self._is_allowed(path, write=False):
            raise PermissionError(f"List access denied: {path}")
        return list(Path(path).iterdir())

    def exists(self, path: Path) -> bool:
        self.enforcer.require(Capability.FS_READ)
        if not self._is_allowed(path, write=False):
            raise PermissionError(f"Exists check denied: {path}")
        return Path(path).exists()

    def mkdir(self, path: Path, parents: bool = True, exist_ok: bool = True) -> None:
        self.enforcer.require(Capability.FS_WRITE)
        if not self._is_allowed(path, write=True):
            raise PermissionError(f"Mkdir denied: {path}")
        Path(path).mkdir(parents=parents, exist_ok=exist_ok)


class SubprocessSandbox:
    """Runs plugin code in a separate subprocess with restricted environment."""

    def __init__(self, plugin_name: str, context: PluginContext, manifest: PluginManifest):
        self.plugin_name = plugin_name
        self.context = context
        self.manifest = manifest
        self._granted = {Capability(c) for c in manifest.required_capabilities}
        self._enforcer = CapabilityEnforcer(context, self._granted)

    def run_command(self, command_name: str, args: list, input_data: dict = None) -> tuple[int, dict]:
        """Run a plugin command in the sandbox."""
        # Serialize input
        input_json = json.dumps(input_data or {})
        
        # Build restricted environment
        env = os.environ.copy()
        env["OBTAINHUB_PLUGIN_MODE"] = "1"
        env["OBTAINHUB_PLUGIN_NAME"] = self.plugin_name
        env["OBTAINHUB_PLUGIN_MANIFEST"] = json.dumps({
            "name": self.manifest.name,
            "version": self.manifest.version,
            "capabilities": [c.value for c in self._granted],
        })
        
        # Run in subprocess
        cmd = [
            sys.executable, "-m", "obtainhub.plugins.sandbox_runner",
            self.manifest.entry_point, command_name,
        ]
        
        try:
            result = subprocess.run(
                cmd,
                input=input_json,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
            
            # Parse output
            try:
                output = json.loads(result.stdout) if result.stdout else {}
            except json.JSONDecodeError:
                output = {"error": "Invalid JSON from plugin", "raw": result.stdout}
            
            return result.returncode, output
            
        except subprocess.TimeoutExpired:
            return 1, {"error": "Plugin command timed out"}
        except Exception as e:
            return 1, {"error": str(e)}

    def get_enforcer(self) -> CapabilityEnforcer:
        """Get the capability enforcer for in-process use."""
        return self._enforcer


def create_sandboxed_context(context: PluginContext, manifest: PluginManifest) -> PluginContext:
    """Create a PluginContext with only granted capabilities."""
    granted = {Capability(c) for c in manifest.required_capabilities}
    new_ctx = PluginContext(
        config_dir=context.config_dir,
        state_dir=context.state_dir,
        download_dir=context.download_dir,
        can_read_config=Capability.READ_CONFIG in granted,
        can_write_config=Capability.WRITE_CONFIG in granted,
        can_read_state=Capability.READ_STATE in granted,
        can_write_state=Capability.WRITE_STATE in granted,
        can_network=Capability.NETWORK in granted,
        can_execute=Capability.EXECUTE in granted,
        can_fs_read=Capability.FS_READ in granted,
        can_fs_write=Capability.FS_WRITE in granted,
    )
    return new_ctx