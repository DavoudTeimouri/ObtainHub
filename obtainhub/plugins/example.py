"""Example plugin that logs update events."""
from obtainhub.plugins.base import Plugin


class ExamplePlugin(Plugin):
    def on_load(self):
        print(f"[Plugin] {self.name} loaded")

    def on_update(self, app_id: str, current_version: str, latest_version: str):
        print(f"[Plugin] {self.name}: {app_id} updated {current_version} -> {latest_version}")

    def on_install(self, app_id: str, version: str):
        print(f"[Plugin] {self.name}: {app_id} installed version {version}")

    def on_uninstall(self, app_id: str):
        print(f"[Plugin] {self.name}: {app_id} uninstalled")