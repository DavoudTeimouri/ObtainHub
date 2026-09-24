#!/usr/bin/env python3
"""Generate a changelog template for the next version."""

import re
import sys
from pathlib import Path
from datetime import datetime

CHANGELOG_PATH = Path("CHANGELOG.md")


def read_changelog():
    return CHANGELOG_PATH.read_text(encoding="utf-8")


def write_changelog(content):
    CHANGELOG_PATH.write_text(content, encoding="utf-8")


def get_latest_version_section(content):
    # Find the first version header (e.g., ## [X.Y.Z] - YYYY-MM-DD)
    pattern = r"^## \[([^\]]+)\](?: - .+)?$"
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if re.match(pattern, line):
            # Return the line index and version
            version = re.match(pattern, line).group(1)
            return i, version
    return None, None


def remove_empty_sections(content):
    """Remove sections that are empty (only contain a dash line)."""
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("### "):
            # Find the end of this section (next ### or ## or end of file)
            j = i + 1
            while j < len(lines) and not (lines[j].startswith("### ") or lines[j].startswith("## ")):
                j += 1
            # Check if the section is empty: only contains a dash line and possibly blank lines
            section_lines = lines[i+1:j]
            # Remove empty lines at start and end
            while section_lines and not section_lines[0].strip():
                section_lines.pop(0)
            while section_lines and not section_lines[-1].strip():
                section_lines.pop()
            # If after stripping we have exactly one line that is just a dash (with optional spaces)
            if len(section_lines) == 1 and re.match(r'^\s*-\s*$', section_lines[0]):
                # Remove the entire section including the header
                del lines[i:j]
                # Do not increment i because we removed elements and the next line is now at i
                continue
            else:
                i = j
        else:
            i += 1
    return "\n".join(lines)


def main():
    content = read_changelog()
    idx, version = get_latest_version_section(content)
    if idx is None:
        print("No version header found in CHANGELOG.md")
        sys.exit(1)
    # Insert a new section after the header
    new_section = f"""## [{version}] - {datetime.now().date().isoformat()}

### Added
- 

### Changed
- 

### Fixed
- 

### Security
- 

### Deprecated

"""
    # Insert after the header line
    lines = content.splitlines()
    lines.insert(idx + 1, new_section)
    new_content = "\n".join(lines)
    # Remove empty sections
    new_content = remove_empty_sections(new_content)
    write_changelog(new_content)
    print(f"Added template for version {version} at {CHANGELOG_PATH}")


if __name__ == "__main__":
    main()