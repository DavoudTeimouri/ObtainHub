"""Self-check for .github/scripts/sync_release_notes.py.

Two regressions it caused:
  1. It wrote "# Changelog for <version>" as the release body, which is repo
     file formatting, not release-page formatting.
  2. It rewrote the body of every release, including the retired ones, so it
     silently deleted the "superseded" notice from all 31 old releases.
"""
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "sync_release_notes", ROOT / ".github" / "scripts" / "sync_release_notes.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

FAILS = []

sections = mod.parse_changelog(str(ROOT / "CHANGELOG.md"))

if not sections:
    FAILS.append("no changelog sections parsed")
else:
    for version, body in sections.items():
        if body.startswith("# Changelog for"):
            FAILS.append(
                "release body for %s starts with '# Changelog for' - release "
                "pages use the '## [version]' form" % version
            )
        if not body.startswith("## ["):
            FAILS.append("release body for %s does not start with '## ['" % version)
        leaked = [v for v in re.findall(r"(?m)^## \[([^\]]+)\]", body) if v != version]
        if leaked:
            FAILS.append("%s body leaks other versions: %s" % (version, leaked))

    two = sections.get("2.0.0", "")
    for p in ("Keep a Changelog", "Semantic Versioning", "All notable changes"):
        if p in two:
            FAILS.append("changelog preamble present in the 2.0.0 body: %r" % p)

# The skip guard must exist, since main() rewrites bodies in place.
src = (ROOT / ".github" / "scripts" / "sync_release_notes.py").read_text(
    encoding="utf-8"
)
if "SUPERSEDED_MARKER" not in src:
    FAILS.append("no superseded-release guard: retired notices get overwritten")
elif src.count("SUPERSEDED_MARKER") < 2:
    FAILS.append(
        "SUPERSEDED_MARKER is declared but never used to skip a release"
    )

if FAILS:
    print("FAIL")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print(
    "PASS: release bodies use the '## [version]' form, carry no preamble, "
    "and retired releases are skipped"
)