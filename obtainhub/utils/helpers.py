"""Utility helpers for ObtainHub (Windows x64 focus)."""

import asyncio
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from obtainhub.core.exceptions import DownloadError, DownloadChecksumError


def is_windows() -> bool:
    """Check if running on Windows."""
    return sys.platform == 'win32' or platform.system().lower() == 'windows'


def is_admin() -> bool:
    """Check if running with administrator privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def get_platform() -> str:
    """Get platform identifier."""
    if is_windows():
        return "windows"
    return sys.platform


def get_architecture() -> str:
    """Get system architecture."""
    machine = platform.machine().lower()
    if machine in ('amd64', 'x86_64'):
        return 'x64'
    elif machine in ('i386', 'i686', 'x86'):
        return 'x86'
    elif machine in ('arm64', 'aarch64'):
        return 'arm64'
    return machine


def is_windows_x64() -> bool:
    """Check if running on Windows x64."""
    return is_windows() and get_architecture() == 'x64'


def run_command(
    cmd: list[str],
    cwd: Optional[Path] = None,
    timeout: int = 300,
    capture: bool = True,
) -> Tuple[int, str, str]:
    """Run a command and return (exit_code, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            timeout=timeout,
            capture_output=capture,
            text=True,
            encoding='utf-8',
            errors='replace',
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


async def run_command_async(
    cmd: list[str],
    cwd: Optional[Path] = None,
    timeout: int = 300,
) -> Tuple[int, str, str]:
    """Run a command asynchronously."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, stdout.decode('utf-8', errors='replace'), stderr.decode('utf-8', errors='replace')
    except asyncio.TimeoutError:
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


def calculate_hash(file_path: Path, algorithm: str = 'sha256') -> str:
    """Calculate file hash."""
    hash_obj = hashlib.new(algorithm)
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


def verify_hash(file_path: Path, expected_hash: str, algorithm: str = 'sha256') -> bool:
    """Verify file hash matches expected."""
    actual = calculate_hash(file_path, algorithm)
    return actual.lower() == expected_hash.lower()


def normalize_path(path: str) -> Path:
    """Normalize and expand a path."""
    return Path(path).expanduser().resolve()


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_owner_repo(repo_str: str) -> Tuple[str, str]:
    """Parse 'owner/repo' string into (owner, repo)."""
    parts = repo_str.strip().split('/')
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid repository format: '{repo_str}'. Expected 'owner/repo'")
    return parts[0], parts[1]


def parse_version(version: str) -> tuple:
    """Parse a version string into a comparable tuple of ints.

    Handles optional leading 'v', and dotted/numeric segments plus a trailing
    prerelease tag (e.g. ``1.2.0-beta1`` -> ``(1, 2, 0, 'beta1')``). Non-numeric
    segments sort after numeric ones. Missing segments compare as 0.
    """
    if version is None:
        return (0,)
    v = str(version).lstrip("vV").strip()
    if not v:
        return (0,)
    # Split off prerelease on first '-' or '+'
    main = v.split("-", 1)[0].split("+", 1)[0]
    parts = []
    for seg in main.split("."):
        num = ""
        for ch in seg:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    # Pad short versions (e.g. "1.2" -> (1, 2, 0)); keep all segments so
    # 4-part versions like 0.7.6.4 are not truncated to 0.7.6.
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer(latest: str, current: str) -> bool:
    """Return True if ``latest`` is strictly newer than ``current``."""
    return parse_version(latest) > parse_version(current)


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_temp_dir() -> Path:
    """Get system temp directory."""
    return Path(tempfile.gettempdir()) / "obtainhub"


def clean_temp_dir() -> None:
    """Clean up ObtainHub temp directory."""
    temp_dir = get_temp_dir()
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)


def download_file(
    url: str,
    dest_path: Path,
    headers: Optional[dict] = None,
    timeout: int = 300,
    expected_hash: Optional[str] = None,
    hash_algorithm: str = 'sha256',
    progress_callback: Optional[callable] = None,
) -> Path:
    """Download a file with progress and optional hash verification."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    req_headers = {'User-Agent': 'ObtainHub/1.0'}
    if headers:
        req_headers.update(headers)
    
    req = Request(url, headers=req_headers)
    
    try:
        with urlopen(req, timeout=timeout) as response:
            total = response.headers.get('Content-Length')
            total = int(total) if total else 0
            
            downloaded = 0
            chunk_size = 8192
            
            with open(dest_path, 'wb') as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if progress_callback and total > 0:
                        progress_callback(downloaded, total)
            
            if expected_hash:
                if not verify_hash(dest_path, expected_hash, hash_algorithm):
                    dest_path.unlink(missing_ok=True)
                    raise DownloadChecksumError(
                        f"Checksum mismatch for {dest_path.name}",
                        details={'expected': expected_hash, 'algorithm': hash_algorithm}
                    )
            
            return dest_path
            
    except HTTPError as e:
        if dest_path.exists():
            dest_path.unlink(missing_ok=True)
        raise DownloadError(f"HTTP {e.code}: {e.reason}")
    except URLError as e:
        if dest_path.exists():
            dest_path.unlink(missing_ok=True)
        raise DownloadError(f"Network error: {e.reason}")
    except Exception as e:
        if dest_path.exists():
            dest_path.unlink(missing_ok=True)
        raise DownloadError(f"Download failed: {e}")


def install_msi(msi_path: Path, silent: bool = True, args: Optional[list] = None) -> bool:
    """Install an MSI package."""
    if not msi_path.exists():
        raise FileNotFoundError(f"MSI not found: {msi_path}")
    
    cmd = ['msiexec', '/i', str(msi_path)]
    if silent:
        cmd.extend(['/quiet', '/norestart'])
    if args:
        cmd.extend(args)
    
    exit_code, stdout, stderr = run_command(cmd, timeout=600)
    return exit_code == 0


def install_exe(exe_path: Path, silent: bool = True, args: Optional[list] = None) -> bool:
    """Install an EXE setup."""
    if not exe_path.exists():
        raise FileNotFoundError(f"EXE not found: {exe_path}")
    
    cmd = [str(exe_path)]
    if silent:
        # Common silent install flags
        cmd.extend(['/S', '/quiet', '/silent', '--silent', '-s', '/VERYSILENT', '/SUPPRESSMSGBOXES'])
    if args:
        cmd.extend(args)
    
    exit_code, stdout, stderr = run_command(cmd, timeout=600)
    return exit_code == 0


def uninstall_msi(product_code: str, silent: bool = True) -> bool:
    """Uninstall an MSI package by product code."""
    cmd = ['msiexec', '/x', product_code]
    if silent:
        cmd.extend(['/quiet', '/norestart'])
    
    exit_code, stdout, stderr = run_command(cmd, timeout=300)
    return exit_code == 0


def find_uninstall_string(app_name: str) -> Optional[str]:
    """Find uninstall command from registry."""
    import winreg
    
    uninstall_keys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]
    
    for root_key in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        for subkey in uninstall_keys:
            try:
                with winreg.OpenKey(root_key, subkey) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as app_key:
                                display_name = winreg.QueryValueEx(app_key, "DisplayName")[0]
                                if app_name.lower() in display_name.lower():
                                    return winreg.QueryValueEx(app_key, "UninstallString")[0]
                        except (OSError, WindowsError):
                            continue
            except (OSError, WindowsError):
                continue
    return None


def get_installed_programs() -> list[dict]:
    """Get list of installed programs from registry."""
    import winreg
    
    programs = []
    uninstall_keys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]
    
    for root_key in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        for subkey in uninstall_keys:
            try:
                with winreg.OpenKey(root_key, subkey) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as app_key:
                                try:
                                    display_name = winreg.QueryValueEx(app_key, "DisplayName")[0]
                                    version = winreg.QueryValueEx(app_key, "DisplayVersion")[0] if "DisplayVersion" in [winreg.EnumValue(app_key, j)[0] for j in range(winreg.QueryInfoKey(app_key)[1])] else ""
                                    publisher = winreg.QueryValueEx(app_key, "Publisher")[0] if "Publisher" in [winreg.EnumValue(app_key, j)[0] for j in range(winreg.QueryInfoKey(app_key)[1])] else ""
                                    uninstall_string = winreg.QueryValueEx(app_key, "UninstallString")[0] if "UninstallString" in [winreg.EnumValue(app_key, j)[0] for j in range(winreg.QueryInfoKey(app_key)[1])] else ""
                                    programs.append({
                                        "name": display_name,
                                        "version": version,
                                        "publisher": publisher,
                                        "uninstall_string": uninstall_string,
                                        "registry_key": subkey_name,
                                    })
                                except (OSError, WindowsError):
                                    continue
                        except (OSError, WindowsError):
                            continue
            except (OSError, WindowsError):
                continue
    return programs


def extract_zip(zip_path: Path, dest_dir: Path) -> Path:
    """Extract ZIP archive."""
    import zipfile
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(dest_dir)
    
    return dest_dir


def is_portable_app(path: Path) -> bool:
    """Check if a path looks like a portable app (no installer)."""
    # Check for common portable indicators
    if path.suffix.lower() == '.exe':
        # Single exe in a folder might be portable
        pass
    return False


__all__ = [
    'is_windows',
    'is_admin',
    'get_platform',
    'get_architecture',
    'is_windows_x64',
    'run_command',
    'run_command_async',
    'calculate_hash',
    'verify_hash',
    'normalize_path',
    'ensure_dir',
    'parse_owner_repo',
    'format_size',
    'get_temp_dir',
    'clean_temp_dir',
    'download_file',
    'install_msi',
    'install_exe',
    'uninstall_msi',
    'find_uninstall_string',
    'get_installed_programs',
    'extract_zip',
    'is_portable_app',
]