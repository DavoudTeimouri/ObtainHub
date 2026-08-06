"""Tests for Downloader."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from obtainhub.core.downloader import Downloader, download_file


class TestDownloader:
    """Test Downloader class."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def downloader(self, temp_dir):
        """Create Downloader instance."""
        return Downloader(download_dir=str(temp_dir), show_progress=False)

    @patch("obtainhub.core.downloader.requests.Session.get")
    def test_download_success(self, mock_get, downloader, temp_dir):
        """Test successful download."""
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "100"}
        mock_response.iter_content.return_value = [b"x" * 50, b"y" * 50]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = downloader.download("https://example.com/file.zip", filename="file.zip")

        assert result.exists()
        assert result.name == "file.zip"
        assert result.stat().st_size == 100

    @patch("obtainhub.core.downloader.requests.Session.get")
    def test_download_with_sha256(self, mock_get, downloader, temp_dir):
        """Test download with SHA256 verification."""
        content = b"hello world"
        expected_sha256 = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

        mock_response = MagicMock()
        mock_response.headers = {"content-length": str(len(content))}
        mock_response.iter_content.return_value = [content]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = downloader.download(
            "https://example.com/file.zip",
            filename="file.zip",
            expected_sha256=expected_sha256,
        )

        assert result.exists()

    @patch("obtainhub.core.downloader.requests.Session.get")
    def test_download_sha256_mismatch(self, mock_get, downloader, temp_dir):
        """Test download with SHA256 mismatch."""
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "11"}
        mock_response.iter_content.return_value = [b"hello world"]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with pytest.raises(Exception) as exc_info:
            downloader.download(
                "https://example.com/file.zip",
                filename="file.zip",
                expected_sha256="wrong_hash",
            )

        assert "Checksum mismatch" in str(exc_info.value)

    @patch("obtainhub.core.downloader.requests.Session.get")
    def test_download_network_error(self, mock_get, downloader):
        """Test download network error."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

        with pytest.raises(Exception) as exc_info:
            downloader.download("https://example.com/file.zip")

        assert "Connection error" in str(exc_info.value)

    @patch("obtainhub.core.downloader.requests.Session.get")
    def test_download_timeout(self, mock_get, downloader):
        """Test download timeout."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")

        with pytest.raises(Exception) as exc_info:
            downloader.download("https://example.com/file.zip")

        assert "timeout" in str(exc_info.value).lower()

    @patch("obtainhub.core.downloader.requests.Session.get")
    def test_download_resume(self, mock_get, downloader, temp_dir):
        """Test download with resume."""
        content = b"hello world"
        partial_content = b"hello "

        # First call returns 206 Partial Content
        mock_response1 = MagicMock()
        mock_response1.status_code = 206
        mock_response1.headers = {"content-length": str(len(content) - len(partial_content))}
        mock_response1.iter_content.return_value = [content[len(partial_content):]]
        mock_response1.raise_for_status.return_value = None

        # Second call (if needed) returns full content
        mock_response2 = MagicMock()
        mock_response2.headers = {"content-length": str(len(content))}
        mock_response2.iter_content.return_value = [content]
        mock_response2.raise_for_status.return_value = None

        mock_get.side_effect = [mock_response1, mock_response2]

        # Create partial file
        temp_path = temp_dir / ".file.zip.part"
        temp_path.write_bytes(partial_content)

        result = downloader.download_with_resume("https://example.com/file.zip", filename="file.zip")

        assert result.exists()

    @patch("obtainhub.core.downloader.requests.Session.get")
    def test_download_filename_from_url(self, mock_get, downloader, temp_dir):
        """Test auto filename from URL."""
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "10"}
        mock_response.iter_content.return_value = [b"x" * 10]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = downloader.download("https://example.com/path/to/app-v1.0.0.msi")

        assert result.name == "app-v1.0.0.msi"

    def test_calculate_sha256(self, downloader, temp_dir):
        """Test SHA256 calculation."""
        file_path = temp_dir / "test.txt"
        file_path.write_bytes(b"hello world")

        sha256 = downloader._calculate_sha256(file_path)
        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert sha256 == expected


class TestDownloadFile:
    """Test download_file convenience function."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @patch("obtainhub.core.downloader.Downloader.download")
    def test_download_file(self, mock_download, temp_dir):
        """Test download_file function."""
        mock_download.return_value = temp_dir / "file.zip"

        result = download_file("https://example.com/file.zip", download_dir=str(temp_dir))

        assert result == temp_dir / "file.zip"
        mock_download.assert_called_once()