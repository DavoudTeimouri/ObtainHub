r"""Self-check for tools/extract_release_notes.py.

The v2.0.0 release body originally contained every past version because the
workflow used '$notes -replace "(?s)^## \[.*?\n"' without (?m): ^ anchored to
the start of the whole string, which is the "# Changelog" preamble, so no
replace matched and the entire file was published.

These checks pin the extraction behaviour, including that regression.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOL = ROOT / "tools" / "extract_release_notes.py"
CHANGELOG = ROOT / "CHANGELOG.md"

FAILS = []


def run(*args):
    return subprocess.run(
        [sys.executable, str(TOOL), *args], capture_output=True, text=True
    )


tmp = Path(tempfile.mkdtemp())

# 1. Real changelog: default version must be the newest one.
out = str(tmp / "auto.md")
r = run(str(CHANGELOG), out)
if r.returncode != 0:
    FAILS.append("default extraction failed: %s" % r.stderr.strip())
else:
    body = (tmp / "auto.md").read_text(encoding="utf-8")
    headings = re.findall(r"(?m)^## \[([^\]]+)\]", body)
    if headings != ["2.0.0"]:
        FAILS.append("expected exactly one heading [2.0.0], got %s" % headings)
    if len(body) > 6000:
        FAILS.append("body is %d bytes - past versions leaked in" % len(body))

# 2. Explicit version, with and without the leading 'v'.
a, b = str(tmp / "a.md"), str(tmp / "b.md")
ra, rb = run(str(CHANGELOG), a, "2.0.0"), run(str(CHANGELOG), b, "v2.0.0")
if ra.returncode or rb.returncode:
    FAILS.append("explicit version lookup failed")
elif (tmp / "a.md").read_bytes() != (tmp / "b.md").read_bytes():
    FAILS.append("'2.0.0' and 'v2.0.0' produced different bodies")

# 3. A middle version must extract cleanly too, not just the newest.
c = str(tmp / "c.md")
r = run(str(CHANGELOG), c, "1.0.5")
if r.returncode != 0:
    FAILS.append("mid-history version failed: %s" % r.stderr.strip())
else:
    body = (tmp / "c.md").read_text(encoding="utf-8")
    headings = re.findall(r"(?m)^## \[([^\]]+)\]", body)
    if headings != ["1.0.5"]:
        FAILS.append("1.0.5 extraction produced headings %s" % headings)

# 4. Missing version fails loudly instead of publishing everything.
d = str(tmp / "d.md")
r = run(str(CHANGELOG), d, "9.9.9")
if r.returncode == 0:
    FAILS.append("a missing version must exit non-zero, not publish the whole file")

# 5. A file with no version headings fails loudly.
nc = tmp / "noheadings.md"
nc.write_text("# Notes\n\nno version headings here\n", encoding="utf-8")
e = str(tmp / "e.md")
r = run(str(nc), e)
if r.returncode == 0:
    FAILS.append("a file without version headings must exit non-zero")

# 6. Regression: a two-section changelog must not leak the second section.
two = tmp / "two.md"
two.write_text(
    "# Changelog\n\n## [2.0.0] - 2026-01-01\n\n### Added\n- new thing\n\n"
    "## [1.0.0] - 2025-01-01\n\n### Added\n- old thing\n",
    encoding="utf-8",
)
f = str(tmp / "f.md")
r = run(str(two), f)
if r.returncode != 0:
    FAILS.append("synthetic changelog extraction failed: %s" % r.stderr.strip())
else:
    body = (tmp / "f.md").read_text(encoding="utf-8")
    if "old thing" in body:
        FAILS.append("1.0.0 content leaked into the 2.0.0 section")
    if "new thing" not in body:
        FAILS.append("2.0.0 content missing from its own section")

# 7. The changelog preamble must not reach the release body. It belongs to the
#    repository file, not to a release page:
#      "# Changelog", "All notable changes...",
#      "The format is based on [Keep a Changelog]...",
#      "...adheres to [Semantic Versioning]..."
PREAMBLE = (
    "# Changelog",
    "All notable changes",
    "Keep a Changelog",
    "Semantic Versioning",
)
g = str(tmp / "g.md")
r = run(str(CHANGELOG), g)
if r.returncode == 0:
    body = (tmp / "g.md").read_text(encoding="utf-8")
    leaked = [p for p in PREAMBLE if p in body]
    if leaked:
        FAILS.append("changelog preamble leaked into the release body: %s" % leaked)
    if not body.startswith("## ["):
        FAILS.append("body must start with the version heading, got %r"
                     % body[:40])

if FAILS:
    print("FAIL")
    for x in FAILS:
        print("  -", x)
    raise SystemExit(1)
print(
    "PASS: release notes extract one version only, reject bad input, "
    "handle a leading 'v'"
)