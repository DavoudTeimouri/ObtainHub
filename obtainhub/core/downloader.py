"""File downloader with progress bar for ObtainHub."""

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Optional, Callable
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from obtainhub.core.config import get_config_manager
from obtainhub.core.exceptions import DownloadError, DownloadChecksumError, DownloadInterruptedError
from obtainhub.core.logger import get_logger


logger = get_logger(__name__)


class Downloader:
    """Download files with progress tracking and checksum verification."""

    CHUNK_SIZE = 8192
    DEFAULT_TIMEOUT = 300

    def __init__(
        self,
        download_dir: Optional[str] = None,
        show_progress: bool = True,
        verify_ssl: bool = True,
        chunk_size: int = CHUNK_SIZE,
    ):
        """
        Initialize downloader.

        Args:
            download_dir: Directory to save downloads (uses config if None)
            show_progress: Show progress bar
            verify_ssl: Verify SSL certificates
            chunk_size: Download chunk size in bytes
        """
        self.show_progress = show_progress
        self.verify_ssl = verify_ssl
        self.chunk_size = chunk_size

        if download_dir:
            self.download_dir = Path(download_dir)
        else:
            config = get_config_manager().load()
            self.download_dir = Path(config.download_dir)

        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy."""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _get_filename_from_url(self, url: str) -> str:
        """Extract filename from URL."""
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        if not filename or filename.endswith("/"):
            filename = "download"
        return filename

    def _get_temp_path(self, filename: str) -> Path:
        """Get temporary file path for download."""
        return self.download_dir / f".{filename}.part"

    def _get_final_path(self, filename: str) -> Path:
        """Get final file path."""
        return self.download_dir / filename

    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(self.chunk_size), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def download(
        self,
        url: str,
        filename: Optional[str] = None,
        expected_sha256: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """
        Download file from URL.

        Args:
            url: Download URL
            filename: Local filename (auto-detected if None)
            expected_sha256: Expected SHA256 checksum
            progress_callback: Optional callback(bytes_downloaded, total_bytes)

        Returns:
            Path to downloaded file

        Raises:
            DownloadError: On download failure
            DownloadChecksumError: On checksum mismatch
            DownloadInterruptedError: On interruption
        """
        if not filename:
            filename = self._get_filename_from_url(url)

        temp_path = self._get_temp_path(filename)
        final_path = self._get_final_path(filename)

        logger.info(f"Downloading {url} -> {final_path}")

        try:
            response = self.session.get(
                url,
                stream=True,
                timeout=self.DEFAULT_TIMEOUT,
                verify=self.verify_ssl,
            )
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback:
                            progress_callback(downloaded, total_size)
                        elif self.show_progress and total_size > 0:
                            self._print_progress(downloaded, total_size)

            if self.show_progress:
                print()  # New line after progress bar

            if expected_sha256:
                actual_sha256 = self._calculate_sha256(temp_path)
                if actual_sha256.lower() != expected_sha256.lower():
                    temp_path.unlink(missing_ok=True)
                    raise DownloadChecksumError(
                        f"Checksum mismatch for {filename}",
                        details={"expected": expected_sha256, "actual": actual_sha256},
                    )

            temp_path.rename(final_path)
            logger.info(f"Download complete: {final_path}")
            return final_path

        except requests.exceptions.RequestException as e:
            temp_path.unlink(missing_ok=True)
            if isinstance(e, requests.exceptions.Timeout):
                raise DownloadError(f"Download timeout: {url}")
            elif isinstance(e, requests.exceptions.ConnectionError):
                raise DownloadError(f"Connection error: {url}")
            else:
                raise DownloadError(f"Download failed: {e}")
        except KeyboardInterrupt:
            temp_path.unlink(missing_ok=True)
            raise DownloadInterruptedError("Download interrupted by user")
        except Exception as e:
            temp_path.unlink(missing_ok=True)
            raise DownloadError(f"Unexpected error: {e}")

    def _print_progress(self, downloaded: int, total: int):
        """Print progress bar to stdout."""
        if total <= 0:
            return
        percent = (downloaded / total) * 100
        bar_width = 40
        filled = int(bar_width * downloaded / total)
        bar = "█" * filled + "░" * (bar_width - filled)
        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        print(f"\r[{bar}] {percent:.1f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB)", end="", flush=True)

    def download_with_resume(
        self,
        url: str,
        filename: Optional[str] = None,
        expected_sha256: Optional[str] = None,
    ) -> Path:
        """
        Download file with resume capability.

        Args:
            url: Download URL
            filename: Local filename (auto-detected if None)
            expected_sha256: Expected SHA256 checksum

        Returns:
            Path to downloaded file
        """
        if not filename:
            filename = self._get_filename_from_url(url)

        temp_path = self._get_temp_path(filename)
        final_path = self._get_final_path(filename)

        resume_from = temp_path.stat().st_size if temp_path.exists() else 0
        headers = {}
        if resume_from > 0:
            headers["Range"] = f"bytes={resume_from}-"

        logger.info(f"Downloading {url} -> {final_path} (resume from {resume_from})")

        try:
            response = self.session.get(
                url,
                stream=True,
                timeout=self.DEFAULT_TIMEOUT,
                verify=self.verify_ssl,
                headers=headers,
            )

            if resume_from > 0:
                if response.status_code != 206:
                    logger.warning("Server doesn't support resume, restarting")
                    resume_from = 0
                    temp_path.unlink(missing_ok=True)
                    response = self.session.get(
                        url,
                        stream=True,
                        timeout=self.DEFAULT_TIMEOUT,
                        verify=self.verify_ssl,
                    )
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0)) + resume_from
            downloaded = resume_from

            mode = "ab" if resume_from > 0 else "wb"
            with open(temp_path, mode) as f:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        if self.show_progress and total_size > 0:
                            self._print_progress(downloaded, total_size)

            if self.show_progress:
                print()

            if expected_sha256:
                actual_sha256 = self._calculate_sha256(temp_path)
                if actual_sha256.lower() != expected_sha256.lower():
                    temp_path.unlink(missing_ok=True)
                    raise DownloadChecksumError(
                        f"Checksum mismatch for {filename}",
                        details={"expected": expected_sha256, "actual": actual_sha256},
                    )

            temp_path.rename(final_path)
            logger.info(f"Download complete: {final_path}")
            return final_path

        except requests.exceptions.RequestException as e:
            if isinstance(e, requests.exceptions.Timeout):
                raise DownloadError(f"Download timeout: {url}")
            elif isinstance(e, requests.exceptions.ConnectionError):
                raise DownloadError(f"Connection error: {url}")
            else:
                raise DownloadError(f"Download failed: {e}")
        except KeyboardInterrupt:
            raise DownloadInterruptedError("Download interrupted by user")
        except Exception as e:
            raise DownloadError(f"Unexpected error: {e}")


def download_file(
    url: str,
    download_dir: Optional[str] = None,
    filename: Optional[str] = None,
    expected_sha256: Optional[str] = None,
    show_progress: bool = True,
) -> Path:
    """
    Convenience function to download a file.

    Args:
        url: Download URL
        download_dir: Directory to save file
        filename: Local filename
        expected_sha256: Expected SHA256 checksum
        show_progress: Show progress bar

    Returns:
        Path to downloaded file
    """
    downloader = Downloader(download_dir=download_dir, show_progress=show_progress)
    return downloader.download(url, filename, expected_sha256)