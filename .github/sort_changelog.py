#!/usr/bin/env python3
"""Reorder CHANGELOG.md sections newest-first by semver tag.

Sections are blocks starting with '## [<tag>]'. The preamble before the first
section is preserved. Blocks are sorted by parsed tag, so the file order always
matches version order regardless of how edits were appended.
"""
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "CHANGELOG.md"
text = open(path).read()

parts = re.split(r"(?m)^(?=## \[)", text)
preamble = parts[0].rstrip("\n")
sections = parts[1:]

if not sections:
    print("no sections found; nothing to do")
    sys.exit(0)


def key(block):
    tag = re.match(r"## \[([^\]]+)\]", block).group(1)
    # strip any -rc / -beta suffix so v3.0.6-rc1 sorts with v3.0.6
    core = re.sub(r"-(?:rc|beta|alpha)\d*$", "", tag).lstrip("v")
    nums = [int(n) for n in re.findall(r"\d+", core)] or [0]
    return (nums, tag)


before = [re.match(r"## \[([^\]]+)\]", b).group(1) for b in sections]
sections.sort(key=key, reverse=True)
after = [re.match(r"## \[([^\]]+)\]", b).group(1) for b in sections]

if before != after:
    print("reordered:")
    print("  before:", before)
    print("  after: ", after)
else:
    print("already in version order")

open(path, "w").write(preamble + "\n\n" + "\n".join(s.rstrip("\n") + "\n" for s in sections))
print(f"{len(sections)} sections written")
