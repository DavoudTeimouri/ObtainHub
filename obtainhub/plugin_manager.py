"""Plugin manager for ObtainHub."""
import importlib
import os
from pathlib import Path
from typing import List

from obtainhub.plugins.base import Plugin


def load_plugins(plugin_dir: str = "obtainhub/plugins") -> List[Plugin]:
    """Load all plugins from the plugin directory.

    Args:
        plugin_dir: Directory containing plugin modules.

    Returns:
        List of instantiated Plugin objects.
    """
    plugins: List[Plugin] = []
    base_path = Path(__file__).parent / plugin_dir
    if not base_path.is_dir():
        return plugins

    for file in base_path.glob("*.py"):
        if file.name.startswith("_"):
            continue
        module_name = f"{plugin_dir}.{file.stem}"
        try:
            module = importlib.import_module(module_name)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Plugin) and attr is not Plugin:
                    # Instantiate with class name as plugin name
                    plugin = attr(name=attr_name)
                    plugin.on_load()
                    plugins.append(plugin)
        except Exception as e:
            print(f"[Plugin] Failed to load {module_name}: {e}")
    return plugins