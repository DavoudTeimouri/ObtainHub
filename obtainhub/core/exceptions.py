"""Custom exceptions for ObtainHub."""

from typing import Optional


class ObtainHubError(Exception):
    """Base exception for ObtainHub."""
    
    def __init__(self, message: str, *, code: Optional[str] = None, details: Optional[dict] = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class ConfigError(ObtainHubError):
    """Configuration related errors."""
    pass


class ConfigNotFoundError(ConfigError):
    """Configuration file not found."""
    pass


class ConfigValidationError(ConfigError):
    """Configuration validation failed."""
    pass


class StateError(ObtainHubError):
    """State management related errors."""
    pass


class StateNotFoundError(StateError):
    """State file not found."""
    pass


class StateCorruptedError(StateError):
    """State file is corrupted or invalid."""
    pass


class SelfUpdateError(ObtainHubError):
    """Self-update related errors."""
    pass


class SelfUpdateCheckFailedError(SelfUpdateError):
    """Failed to check for updates."""
    pass


class SelfUpdateFailedError(SelfUpdateError):
    """Self-update failed."""
    pass


class SelfUpdateSkippedError(SelfUpdateError):
    """Self-update was skipped by user."""
    pass


class NetworkError(ObtainHubError):
    """Network related errors."""
    
    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        details: Optional[dict] = None,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message, code=code, details=details)
        self.status_code = status_code


class DownloadError(ObtainHubError):
    """Download related errors."""
    
    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        details: Optional[dict] = None,
        url: Optional[str] = None,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message, code=code, details=details)
        self.url = url
        self.status_code = status_code


class InstallerError(ObtainHubError):
    """Installer execution errors."""
    pass


class InstallerNotFoundError(InstallerError):
    """Installer file not found."""
    pass


class InstallerExecutionError(InstallerError):
    """Failed to execute installer."""
    pass


class GitHubAPIError(ObtainHubError):
    """GitHub API related errors."""
    
    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        details: Optional[dict] = None,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ) -> None:
        super().__init__(message, code=code, details=details)
        self.status_code = status_code
        self.response_body = response_body


class RateLimitError(GitHubAPIError):
    """GitHub API rate limit exceeded."""
    pass


class NotFoundError(GitHubAPIError):
    """Resource not found on GitHub."""
    pass


class AuthenticationError(GitHubAPIError):
    """Authentication failed with GitHub API."""
    pass


class ValidationError(ObtainHubError):
    """Input validation error."""
    pass


class ManifestError(ObtainHubError):
    """Manifest related errors."""
    pass


class ManifestNotFoundError(ManifestError):
    """Manifest not found for repository."""
    pass


class ManifestParseError(ManifestError):
    """Failed to parse manifest."""
    pass


class CLIError(ObtainHubError):
    """CLI related errors."""
    pass


class CLIArgumentError(CLIError):
    """Invalid CLI argument."""
    pass


class CLICommandError(CLIError):
    """Command execution failed."""
    pass