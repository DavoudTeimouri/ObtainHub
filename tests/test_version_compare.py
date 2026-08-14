"""Semantic version comparison used by check/update 'up to date' detection."""

from obtainhub.utils.helpers import is_newer, parse_version


def test_parse_version_strips_v():
    assert parse_version("v1.2.3") == (1, 2, 3)


def test_is_newer_dotted():
    assert is_newer("1.10.0", "1.2.0")
    assert not is_newer("1.2.0", "1.10.0")
    assert not is_newer("1.2.0", "1.2.0")


def test_is_newer_missing_segments():
    assert not is_newer("1.2", "1.2.0")  # equal
    assert is_newer("2.0", "1.9.9")
