"""Notifier plugin that shows desktop notifications on update."""
import sys
from obtainhub.plugins.base import Plugin

try:
    from plyer import notification
    HAS_PLyer = True
except Exception:
    HAS_PLyer = False


class NotifierPlugin(Plugin):
    def on_load(self):
        if not HAS_PLyer:
            print(f"[Notifier] plyer not installed, notifications disabled")

    def on_update(self, app_id: str, current_version: str, latest_version: str):
        if not HAS_PLyer:
            return
        title = f"ObtainHub Update: {app_id}"
        message = f"{current_version or '-'} -> {latest_version}"
        notification.notify(title=title, message=message, timeout=10)

    # other hooks can be implemented similarly