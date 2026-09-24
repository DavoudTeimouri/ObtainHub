"""Base class for ObtainHub plugins."""
from abc import ABC, abstractmethod


class Plugin(ABC):
    """Base plugin class for ObtainHub."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def on_load(self):
        """Called when the plugin is loaded."""
        pass

    @abstractmethod
    def on_update(self, app_id: str, current_version: str, latest_version: str):
        """Called when an app is updated.

        Args:
            app_id: The app identifier (owner/repo).
            current_version: The current version of the app.
            latest_version: The latest version available.
        """
        pass

    @abstractmethod
    def on_install(self, app_id: str, version: str):
        """Called when an app is installed.

        Args:
            app_id: The app identifier (owner/repo).
            version: The version installed.
        """
        pass

    @abstractmethod
    def on_uninstall(self, app_id: str):
        """Called when an app is uninstalled.

        Args:
            app_id: The app identifier (owner/repo).
        """
        pass