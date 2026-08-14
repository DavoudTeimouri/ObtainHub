"""Custom source resolution: classify + manifest/github normalization."""

from unittest import mock

from obtainhub.core.sources import (
    SourceAppEntry, _classify, fetch_source_entries, find_in_sources,
    _fetch_manifest, _fetch_github,
)
from obtainhub.core.config import Config, ManifestSource


def test_classify():
    assert _classify("App-Setup.exe") == "exe_setup"
    assert _classify("App.msi") == "msi"
    assert _classify("app.zip") == "zip"
    assert _classify("app.exe") == "exe_standalone"
    assert _classify("notes.txt") == "unknown"


def test_manifest_parsing():
    src = ManifestSource(name="m", url="https://x/manifest.json", type="manifest")
    data = [
        {"name": "Foo", "version": "1.0.0", "url": "https://x/foo.zip", "installer_type": "zip"},
        {"name": "Bar", "version": "2.0.0", "url": "https://x/bar-setup.exe"},
    ]
    with mock.patch("obtainhub.core.sources.requests.get") as g:
        g.return_value.json.return_value = data
        g.return_value.raise_for_status.return_value = None
        entries = _fetch_manifest(src)
    assert len(entries) == 2
    assert entries[0].installer_type == "zip"
    assert entries[1].installer_type == "exe_setup"  # auto-detected
    assert entries[0].source_name == "m"


def test_github_releases_normalization():
    src = ManifestSource(name="gh", url="https://github.com/owner/repo", type="github")
    rel = [{"tag_name": "v1.2.3", "assets": [
        {"name": "repo-Setup.exe", "browser_download_url": "https://x/s.exe", "size": 10},
    ]}]
    with mock.patch("obtainhub.core.sources.requests.get") as g:
        g.return_value.json.return_value = rel
        g.return_value.raise_for_status.return_value = None
        entries = _fetch_github(src)
    assert entries[0].version == "1.2.3"
    assert entries[0].installer_type == "exe_setup"
    assert entries[0].repo_id == "owner/repo"


def test_find_in_sources_by_name():
    entries = [
        SourceAppEntry(name="Foo", version="1", url="u", installer_type="zip", source_name="a"),
        SourceAppEntry(name="Bar", version="1", url="u", installer_type="msi", source_name="b"),
    ]
    found, src = find_in_sources(entries, "Bar")
    assert found is not None and src == "b"
    assert find_in_sources(entries, "nonexistent") is None


def test_fetch_source_entries_aggregates():
    cfg = Config()
    cfg.manifest_sources = [
        ManifestSource(name="a", url="https://x/a.json", type="manifest"),
        ManifestSource(name="b", url="https://github.com/o/r", type="github", enabled=False),
    ]
    data = [{"name": "Foo", "version": "1", "url": "https://x/f.zip"}]
    with mock.patch("obtainhub.core.sources.requests.get") as g:
        g.return_value.json.return_value = data
        g.return_value.raise_for_status.return_value = None
        entries = fetch_source_entries(cfg)
    # disabled source 'b' is skipped
    assert [e.source_name for e in entries] == ["a"]
