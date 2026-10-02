"""Extract the section for one version out of a Keep a Changelog file.

Used by the release workflow to build the GitHub Release body from
CHANGELOG.md without dragging in every previous version.

Usage:
    python tools/extract_release_notes.py CHANGELOG.md OUT.md [VERSION]

VERSION defaults to the highest version present, which is what a tagged
release wants.
"""

import os
import re
import sys

HEADING = re.compile(r"(?m)^## \[(?P<ver>[^\]]+)\][^\n]*\n")


def sections(text):
    """{version: body} for every '## [x.y.z] - date' heading."""
    parts = HEADING.split(text)
    # split() yields [preamble, ver1, body1, ver2, body2, ...]
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def render(version, body):
    out = "## [%s]\n\n%s\n" % (version, body.strip())
    # Only our own heading may appear, or the next version leaked in.
    leaked = [v for v in HEADING.findall(out) if v != version]
    if leaked:
        raise SystemExit("BUG: other version heading(s) leaked into body: %s" % leaked)
    return out


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    src, dst = argv[1], argv[2]
    want = argv[3] if len(argv) > 3 else None

    with open(src, encoding="utf-8") as f:
        found = sections(f.read())

    if not found:
        raise SystemExit("no '## [x.y.z]' headings in %s" % src)

    if want is None:
        # Highest version wins: compare numerically per dotted component.
        want = max(found, key=lambda v: [int(p) for p in v.split(".") if p.isdigit()])

    want = want.lstrip("v")
    if want not in found:
        raise SystemExit(
            "version %r not in %s; have: %s" % (want, src, sorted(found, reverse=True))
        )

    text = render(want, found[want])
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(text)

    print("%s: %d bytes for %s" % (dst, len(text), want))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))