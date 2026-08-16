"""Regression test: 4-part versions must not collapse to equal tuples."""
import obtainhub.main  # noqa: F401  full package init (avoids helpers circular import)


def test_parse_version_keeps_four_segments():
    from obtainhub.utils.helpers import parse_version
    assert parse_version("0.7.6.3") == (0, 7, 6, 3)
    assert parse_version("0.7.6.4") == (0, 7, 6, 4)
    # They must NOT truncate to (0, 7, 6)
    assert parse_version("0.7.6.3") != parse_version("0.7.6.4")


def test_is_newer_distinguishes_patch_versions():
    from obtainhub.utils.helpers import is_newer
    assert is_newer("0.7.6.4", "0.7.6.3") is True
    assert is_newer("0.7.6.3", "0.7.6.4") is False


def test_parse_version_pads_short_versions():
    from obtainhub.utils.helpers import parse_version, is_newer
    assert parse_version("1.2") == (1, 2, 0)
    assert parse_version("1.2.0") == (1, 2, 0)  # 1.2 and 1.2.0 are equal
    assert is_newer("1.2.1", "1.2") is True
