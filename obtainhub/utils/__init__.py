"""Utility functions for ObtainHub."""

import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

from obtainhub.core.logger import get_logger


logger = get_logger()


def get_platform() -> str:
    """Get the current platform identifier."""
    if sys.platform.startswith("win"):
        return "windows"
    elif sys.platform.startswith("darwin"):
        return "macos"
    elif sys.platform.startswith("linux"):
        return "linux"
    return "unknown"


def is_windows() -> bool:
    """Check if running on Windows."""
    return sys.platform.startswith("win")


def is_admin() -> bool:
    """Check if running with administrator privileges."""
    try:
        if is_windows():
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.geteuid() == 0
    except Exception:
        return False


def run_command(
    cmd: list[str],
    capture: bool = True,
    timeout: int = 60,
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    logger.debug(f"Running command: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
            shell=False,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s: {' '.join(cmd)}")
        return -1, "", f"Timeout after {timeout}s"
    except Exception as e:
        logger.error(f"Command failed: {e}")
        return -1, "", str(e)


def run_command_async(
    cmd: list[str],
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
) -> subprocess.Popen:
    """Run a command asynchronously and return the Popen object."""
    logger.debug(f"Running async command: {' '.join(cmd)}")
    creation_flags = 0
    if is_windows():
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creation_flags,
        close_fds=True,
    )


def calculate_hash(filepath: Path, algorithm: str = "sha256") -> str:
    """Calculate hash of a file."""
    hash_obj = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


def verify_hash(filepath: Path, expected_hash: str, algorithm: str = "sha256") -> bool:
    """Verify file hash matches expected value."""
    actual_hash = calculate_hash(filepath, algorithm)
    return actual_hash.lower() == expected_hash.lower()


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename for safe filesystem usage."""
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename)
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(" .")
    # Limit length
    if len(sanitized) > 255:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[: 255 - len(ext)] + ext
    return sanitized or "unnamed"


def parse_owner_repo(repo_string: str) -> tuple[str, str]:
    """Parse 'owner/repo' string into (owner, repo)."""
    parts = repo_string.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid repository format: {repo_string}. Expected 'owner/repo'")
    return parts[0], parts[1]


def format_size(size_bytes: int) -> str:
    """Format bytes into human readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def format_duration(seconds: float) -> str:
    """Format seconds into human readable duration."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, create if needed."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_remove(path: Path) -> bool:
    """Safely remove a file or directory."""
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to remove {path}: {e}")
        return False


def find_executable(name: str) -> Optional[Path]:
    """Find an executable in PATH."""
    path = shutil.which(name)
    return Path(path) if path else None


def get_app_data_dir(app_name: str = "ObtainHub") -> Path:
    """Get application data directory."""
    if is_windows():
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / app_name


def parse_version(version: str) -> list[int]:
    """Parse version string into list of integers."""
    version = version.lstrip("v")
    parts = []
    for part in version.split("."):
        num = "".join(c for c in part if c.isdigit())
        parts.append(int(num) if num else 0)
    return parts


def compare_versions(v1: str, v2: str) -> int:
    """Compare two version strings. Returns -1 if v1 < v2, 0 if equal, 1 if v1 > v2."""
    p1 = parse_version(v1)
    p2 = parse_version(v2)
    
    max_len = max(len(p1), len(p2))
    p1.extend([0] * (max_len - len(p1)))
    p2.extend([0] * (max_len - len(p2)))
    
    if p1 < p2:
        return -1
    elif p1 > p2:
        return 1
    return 0


def is_newer_version(current: str, latest: str) -> bool:
    """Check if latest version is newer than current."""
    return compare_versions(current, latest) < 0


def get_file_size(path: Path) -> int:
    """Get file size in bytes."""
    try:
        return path.stat().st_size
    except Exception:
        return 0


def is_url(string: str) -> bool:
    """Check if a string is a valid URL."""
    try:
        result = urlparse(string)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def get_github_api_headers(token: Optional[str] = None) -> dict[str, str]:
    """Get standard headers for GitHub API requests."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ObtainHub",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    return headers