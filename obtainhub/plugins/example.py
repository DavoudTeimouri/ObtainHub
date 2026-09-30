"""Example plugin for demonstration purposes."""

from obtainhub.plugins import Plugin, PluginContext


class ExamplePlugin(Plugin):
    """Example plugin that adds a 'hello' command."""

    name = "example"
    version = "1.0.0"
    description = "Example plugin demonstrating the plugin system"

    required_capabilities = ["can_fs_read"]

    def initialize(self) -> None:
        print(f"[ExamplePlugin] Initialized with config_dir: {self.context.config_dir}")

    def shutdown(self) -> None:
        print("[ExamplePlugin] Shutdown")

    def get_commands(self) -> dict:
        return {
            "hello": self.cmd_hello,
        }

    def cmd_hello(self, args, context) -> int:
        print("Hello from ExamplePlugin!")
        return 0

    def get_hooks(self) -> dict:
        return {
            "app_installed": [self.on_app_installed],
        }

    def on_app_installed(self, data: dict) -> None:
        print(f"[ExamplePlugin] App installed: {data.get('name')}")
