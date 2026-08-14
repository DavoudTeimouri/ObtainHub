"""Tests for the GitHub search-query cleaning used by `ohub check`."""
from obtainhub.main import _clean_app_query, _progressive_queries


def test_clean_app_query_strips_versions():
    assert _clean_app_query("OnionHop V3 version 3.7.10") == "OnionHop"
    assert _clean_app_query("v2rayN 6.0") == "v2rayN"
    assert _clean_app_query("App 1.2.3") == "App"
    assert _clean_app_query("Notepad++") == "Notepad++"


def test_clean_app_query_fallback_to_original():
    # If everything looks like a version, keep the original name
    assert _clean_app_query("3.7.10") == "3.7.10"


def test_progressive_queries_onionhop():
    out = _progressive_queries("OnionHop V3 version 3.7.10")
    assert out[0] == "OnionHop"
    assert "OnionHop V3 version 3.7.10" in out  # raw name is the final fallback
    # cleanest first, then progressively shorter, no duplicates
    assert out == ["OnionHop", "OnionHop V3 version 3.7.10"]
