"""Custom exceptions for ObtainHub."""

from typing import Optional


class ObtainHubError(Exception):
    """Base exception for ObtainHub."""
    
    def __init__(self, message: str, *, code: Optional[str] = None, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
    
    def __str__(self) -> str:
        return self.message


class ConfigError(ObtainHubError):
    """Configuration error."""
    pass


class ConfigNotFoundError(ConfigError):
    """Configuration file not found."""
    pass


class ConfigValidationError(ConfigError):
    """Configuration validation failed."""
    pass


class NetworkError(ObtainHubError):
    """Network-related error."""
    pass


class NetworkTimeoutError(NetworkError):
    """Network request timeout."""
    pass


class NetworkConnectionError(NetworkError):
    """Network connection failed."""
    pass


class NetworkRateLimitError(NetworkError):
    """Rate limited by API."""
    
    def __init__(self, message: str, *, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class DownloadError(ObtainHubError):
    """Download failed."""
    pass


class DownloadChecksumError(DownloadError):
    """Downloaded file checksum mismatch."""
    pass


class DownloadInterruptedError(DownloadError):
    """Download was interrupted."""
    pass


class InstallerError(ObtainHubError):
    """Installer-related error."""
    pass


class InstallerNotFoundError(InstallerError):
    """No suitable installer found."""
    pass


class InstallerExecutionError(InstallerError):
    """Installer execution failed."""
    
    def __init__(self, message: str, *, exit_code: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.exit_code = exit_code


class InstallerUnsupportedTypeError(InstallerError):
    """Unsupported installer type."""
    pass


class SelfUpdateError(ObtainHubError):
    """Self-update error."""
    pass


class SelfUpdateNotNeededError(SelfUpdateError):
    """Self-update not needed (already latest)."""
    pass


class StateError(ObtainHubError):
    """State database error."""
    pass


class StateNotFoundError(StateError):
    """State entry not found."""
    pass


class StateValidationError(StateError):
    """State validation failed."""
    pass


class CLIError(ObtainHubError):
    """CLI command error."""
    pass


class CLIArgumentError(CLIError):
    """Invalid command line argument."""
    pass


class ManifestError(ObtainHubError):
    """Manifest-related error."""
    pass


class ManifestNotFoundError(ManifestError):
    """Manifest not found."""
    pass


class ManifestValidationError(ManifestError):
    """Manifest validation failed."""
    pass


class ManualUninstallRequired(ObtainHubError):
    """Manual uninstall required before update."""
    pass


class PrereleaseConfirmationRequired(ObtainHubError):
    """Prerelease confirmation required from user."""
    pass


class AssetNotFoundError(ObtainHubError):
    """No suitable asset found."""
    pass


class AssetMatchError(ObtainHubError):
    """Asset matching failed."""
    pass


class ArchitectureMismatchError(AssetMatchError):
    """Architecture mismatch in asset."""
    pass


class InstallerTypeMismatchError(AssetMatchError):
    """Installer type mismatch in asset."""
    pass