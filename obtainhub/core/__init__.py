"""Core module exports for ObtainHub."""

from obtainhub.core.config import (
    Config,
    ConfigManager,
    ManifestSource,
    get_config,
    get_config_manager,
)
from obtainhub.core.state import (
    InstalledApp,
    ManifestEntry,
    StateManager,
    get_state_manager,
)
from obtainhub.core.logger import (
    LogLevel,
    LogRecord,
    JSONFormatter,
    ConsoleFormatter,
    StructuredLogger,
    setup_logging,
    get_logger,
    get_default_logger,
)
from obtainhub.core.self_updater import (
    ReleaseInfo,
    SelfUpdater,
    check_and_update,
)
from obtainhub.core.exceptions import (
    ObtainHubError,
    ConfigError,
    ConfigNotFoundError,
    ConfigValidationError,
    NetworkError,
    DownloadError,
    InstallerError,
    InstallerNotFoundError,
    InstallerExecutionError,
    SelfUpdateError,
    SelfUpdateNotNeededError,
    StateError,
    StateNotFoundError,
    StateValidationError,
    CLIError,
    CLIArgumentError,
    ManualUninstallRequired,
    PrereleaseConfirmationRequired,
    AssetNotFoundError,
    AssetMatchError,
    ArchitectureMismatchError,
    InstallerTypeMismatchError,
)
from obtainhub.core.github_client import (
    GitHubClient,
    ReleaseInfo,
)
from obtainhub.core.asset_matcher import (
    InstallerType,
    Architecture,
    AssetMatch,
    AssetMatcher,
)
from obtainhub.core.downloader import (
    Downloader,
    download_file,
)
from obtainhub.core.installer import (
    SilentInstaller,
    InstallResult,
    install_app,
)
from obtainhub.utils.helpers import get_architecture as get_system_architecture, is_windows_x64

__all__ = [
    # Config
    "Config",
    "ConfigManager",
    "ManifestSource",
    "get_config",
    "get_config_manager",
    # State
    "InstalledApp",
    "ManifestEntry",
    "StateManager",
    "get_state_manager",
    # Logger
    "LogLevel",
    "LogRecord",
    "JSONFormatter",
    "ConsoleFormatter",
    "StructuredLogger",
    "setup_logging",
    "get_logger",
    "get_default_logger",
    # Self Updater
    "SelfUpdater",
    "check_and_update",
    # Exceptions
    "ObtainHubError",
    "ConfigError",
    "ConfigNotFoundError",
    "ConfigValidationError",
    "NetworkError",
    "DownloadError",
    "InstallerError",
    "InstallerNotFoundError",
    "InstallerExecutionError",
    "SelfUpdateError",
    "SelfUpdateNotNeededError",
    "StateError",
    "StateNotFoundError",
    "StateValidationError",
    "CLIError",
    "CLIArgumentError",
    "ManualUninstallRequired",
    "PrereleaseConfirmationRequired",
    "AssetNotFoundError",
    "AssetMatchError",
    "ArchitectureMismatchError",
    "InstallerTypeMismatchError",
    # Downloader
    "Downloader",
    "download_file",
    # Installer
    "SilentInstaller",
    "InstallResult",
    "install_app",
    # GitHub Client
    "GitHubClient",
    # Asset Matcher
    "InstallerType",
    "Architecture",
    "AssetMatch",
    "AssetMatcher",
    "get_system_architecture",
    "is_windows_x64",
]