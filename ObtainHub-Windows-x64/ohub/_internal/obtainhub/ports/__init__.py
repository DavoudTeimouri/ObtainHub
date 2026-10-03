"""Core ports (interfaces) for ObtainHub.

Defines the abstract contracts that adapters must implement.
This enables dependency inversion and plugin extensibility.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class ReleaseInfo:
    """Normalized release information from any source."""
    tag_name: str
    version: str
    html_url: str
    body: str
    prerelease: bool
    draft: bool
    assets: list[dict]  # List of asset dicts with name, url, size, sha256
    published_at: str
    checksums: dict  # filename -> sha256


@dataclass
class SearchResult:
    """Normalized search result."""
    items: list[dict]  # List of repo dicts with full_name, name, stargazers_count, etc.
    error: Optional[str] = None


@dataclass
class RateLimitInfo:
    """GitHub API rate limit info."""
    limit: int
    remaining: int
    reset_at: int


class RepositorySource(ABC):
    """Abstract interface for fetching releases from any source (GitHub, custom, etc.)."""

    @abstractmethod
    def get_latest_release(self, owner: str, repo: str, include_prerelease: bool = False) -> Optional[ReleaseInfo]:
        """Get the latest release for a repository."""
        pass

    @abstractmethod
    def get_release_by_tag(self, owner: str, repo: str, tag: str) -> Optional[ReleaseInfo]:
        """Get a specific release by tag."""
        pass

    @abstractmethod
    def get_releases(self, owner: str, repo: str, per_page: int = 30) -> list[ReleaseInfo]:
        """Get recent releases for a repository."""
        pass

    @abstractmethod
    def search_repositories(
        self,
        query: str,
        min_stars: int = 0,
        ignore_case: bool = False,
        active_only: bool = True,
        per_page: int = 30,
    ) -> SearchResult:
        """Search for repositories."""
        pass

    @abstractmethod
    def get_repo_status(self, owner: str, repo: str) -> Optional[dict]:
        """Check if repo is archived/inactive."""
        pass

    @abstractmethod
    def get_rate_limit(self) -> RateLimitInfo:
        """Get API rate limit status."""
        pass


class StateStore(ABC):
    """Abstract interface for persisting installed app state."""

    @abstractmethod
    def load(self) -> list[dict]:
        """Load all installed apps as dicts."""
        pass

    @abstractmethod
    def save(self, apps: list[dict]) -> None:
        """Save all installed apps."""
        pass

    @abstractmethod
    def add_app(self, app: dict) -> None:
        """Add a single app."""
        pass

    @abstractmethod
    def update_app(self, app_id: str, updates: dict) -> None:
        """Update a single app."""
        pass

    @abstractmethod
    def remove_app(self, app_id: str) -> None:
        """Remove an app."""
        pass

    @abstractmethod
    def get_app(self, app_id: str) -> Optional[dict]:
        """Get a single app by ID."""
        pass

    @abstractmethod
    def get_all_apps(self) -> list[dict]:
        """Get all apps."""
        pass

    @abstractmethod
    def add_check_history(self, entry: dict) -> None:
        """Add a check history entry."""
        pass

    @abstractmethod
    def get_check_history(self) -> dict:
        """Get all check history entries."""
        pass

    @abstractmethod
    def clear_check_history(self) -> None:
        """Clear check history."""
        pass


class Downloader(ABC):
    """Abstract interface for downloading files."""

    @abstractmethod
    def download(
        self,
        url: str,
        dest: Path,
        expected_sha256: Optional[str] = None,
        expected_size: Optional[int] = None,
        progress_callback: Optional[callable] = None,
    ) -> Path:
        """Download a file to destination."""
        pass


class Installer(ABC):
    """Abstract interface for installing applications."""

    @abstractmethod
    def install(
        self,
        file_path: Path,
        installer_type: str,
        app_id: str,
        force: bool = False,
        interactive: bool = False,
        hooks: Optional[dict] = None,
    ) -> tuple[bool, str]:
        """Install an application. Returns (success, message)."""
        pass

    @abstractmethod
    def uninstall(
        self,
        app: dict,
        interactive: bool = False,
    ) -> tuple[bool, str]:
        """Uninstall an application. Returns (success, message)."""
        pass


class SystemScanner(ABC):
    """Abstract interface for scanning system-installed applications."""

    @abstractmethod
    def get_installed_apps(self) -> list[dict]:
        """Get all system-installed applications."""
        pass

    @abstractmethod
    def is_app_installed(self, name: str) -> bool:
        """Check if an app is installed by name."""
        pass


class AssetMatcherPort(ABC):
    """Abstract interface for matching assets to platform/architecture."""

    @abstractmethod
    def get_best_match(self, assets: list[dict]) -> Optional[dict]:
        """Get the best matching asset for the current platform."""
        pass

    @abstractmethod
    def get_installable_candidates(self, assets: list[dict]) -> list[dict]:
        """Get all installable candidate assets."""
        pass

    @abstractmethod
    def get_installer_options(self, assets: list[dict]) -> list[dict]:
        """Get installer options (MSI, EXE_SETUP, etc.)."""
        pass

    @abstractmethod
    def match_by_pattern(self, assets: list[dict], pattern: str) -> Optional[dict]:
        """Match asset by saved pattern."""
        pass

    @abstractmethod
    def derive_asset_pattern(self, asset: dict) -> str:
        """Derive a pattern from an asset for future matching."""
        pass


class EventBus(ABC):
    """Abstract interface for event publishing."""

    @abstractmethod
    def publish(self, event: str, data: dict) -> None:
        """Publish an event."""
        pass

    @abstractmethod
    def subscribe(self, event: str, handler: callable) -> None:
        """Subscribe to an event."""
        pass