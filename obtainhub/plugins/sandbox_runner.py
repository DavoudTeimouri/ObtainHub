#!/usr/bin/env python3
"""Sandbox runner for plugins.

This module runs inside a separate subprocess to execute plugin commands
with restricted capabilities. It is invoked by SubprocessSandbox.
"""

import sys
import json
import os
import importlib


def main():
    """Entry point for sandboxed plugin execution."""
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: sandbox_runner <entry_point> <command> [args...]"}))
        return 1

    entry_point = sys.argv[1]  # e.g., "my_plugin:MyPluginClass"
    command = sys.argv[2]      # e.g., "hello"
    
    # Parse manifest from environment
    manifest_json = os.environ.get("OBTAINHUB_PLUGIN_MANIFEST", "{}")
    try:
        manifest = json.loads(manifest_json)
    except json.JSONDecodeError:
        manifest = {}

    # Read input from stdin
    input_data = {}
    try:
        stdin_data = sys.stdin.read()
        if stdin_data:
            input_data = json.loads(stdin_data)
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input"}))
        return 1

    # Load plugin class
    try:
        module_name, class_name = entry_point.split(":", 1)
        module = importlib.import_module(module_name)
        plugin_class = getattr(module, class_name)
    except Exception as e:
        print(json.dumps({"error": f"Failed to load plugin: {e}"}))
        return 1

    # Create a minimal context for the plugin
    from obtainhub.plugins import PluginContext
    from pathlib import Path
    
    context = PluginContext(
        config_dir=Path(os.environ.get("OBTAINHUB_CONFIG_DIR", "/tmp")),
        state_dir=Path(os.environ.get("OBTAINHUB_STATE_DIR", "/tmp")),
        download_dir=Path(os.environ.get("OBTAINHUB_DOWNLOAD_DIR", "/tmp")),
        can_read_config="read_config" in manifest.get("capabilities", []),
        can_write_config="write_config" in manifest.get("capabilities", []),
        can_read_state="read_state" in manifest.get("capabilities", []),
        can_write_state="write_state" in manifest.get("capabilities", []),
        can_network="network" in manifest.get("capabilities", []),
        can_execute="execute" in manifest.get("capabilities", []),
        can_fs_read="fs_read" in manifest.get("capabilities", []),
        can_fs_write="fs_write" in manifest.get("capabilities", []),
    )

    # Instantiate and initialize plugin
    try:
        plugin = plugin_class(context)
        plugin.initialize()
    except Exception as e:
        print(json.dumps({"error": f"Plugin initialization failed: {e}"}))
        return 1

    # Get command handler
    commands = plugin.get_commands()
    if command not in commands:
        print(json.dumps({"error": f"Command '{command}' not found in plugin"}))
        return 1

    handler = commands[command]

    # Execute command
    try:
        # Convert input_data to argparse.Namespace-like object
        from argparse import Namespace
        args = Namespace(**input_data)
        exit_code = handler(args, context)
        
        if exit_code is None:
            exit_code = 0
        
        print(json.dumps({"exit_code": exit_code}))
        return exit_code
    except Exception as e:
        print(json.dumps({"error": f"Command execution failed: {e}", "exit_code": 1}))
        return 1
    finally:
        try:
            plugin.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())