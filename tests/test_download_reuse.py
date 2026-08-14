"""Download reuse: an existing file with matching size is reused, not re-downloaded."""

import io
from pathlib import Path
from unittest import mock

from obtainhub.core.downloader import Downloader, DownloadError


def test_reuse_existing_file_by_size(tmp_path):
    # Pre-existing file with the expected size -> reuse, network never hit
    dest = tmp_path / "app.zip"
    payload = b"x" * 64
    dest.write_bytes(payload)

    called = {"n": 0}

    def fake_get(*a, **k):
        called["n"] += 1
        raise AssertionError("network must not be called on reuse")

    dl = Downloader(download_dir=tmp_path, show_progress=False)
    with mock.patch.object(dl.session, "get", fake_get):
        out = dl.download("http://example/app.zip", filename="app.zip",
                          expected_size=len(payload), reuse_callback=lambda p, s: True)
    assert out == dest
    assert called["n"] == 0


def test_force_ignores_existing(tmp_path):
    dest = tmp_path / "app.zip"
    dest.write_bytes(b"old")

    buf = io.BytesIO(b"new content")

    class Resp:
        status_code = 200
        headers = {"content-length": str(len(b"new content"))}
        def raise_for_status(self): pass
        def iter_content(self, chunk_size=1):
            yield buf.read()

    dl = Downloader(download_dir=tmp_path, show_progress=False)
    with mock.patch.object(dl.session, "get", return_value=Resp()):
        out = dl.download("http://example/app.zip", filename="app.zip", force=True)
    assert out.read_bytes() == b"new content"
