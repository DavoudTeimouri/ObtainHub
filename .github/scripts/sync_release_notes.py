#!/usr/bin/env python3
"""Sync CHANGELOG.md sections to GitHub release notes by tag.

Reads CHANGELOG.md, extracts the section for each release tag
(stripping the leading 'v'), and updates the release body via the
GitHub API using the workflow-provided GITHUB_TOKEN.
"""
import re
import os
import sys
import json
import urllib.request
import urllib.error

REPO = os.environ.get("GITHUB_REPOSITORY", "DavoudTeimouri/ObtainHub")
TOKEN = os.environ.get("GITHUB_TOKEN")
API = "https://api.github.com"


def api_request(url, method="GET", data=None):
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "sync-release-notes")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def parse_changelog(path="CHANGELOG.md"):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    sections = {}
    matches = list(re.finditer(r"^##\s+\[([^\]]+)\]", content, re.MULTILINE))
    for i, m in enumerate(matches):
        version = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        # Strip the leading heading line already consumed; keep sub-content
        body = content[start:end].strip()
        sections[version] = f"# Changelog for {version}\n\n{body}"
    return sections


def main():
    if not TOKEN:
        print("GITHUB_TOKEN not set")
        sys.exit(1)

    sections = parse_changelog()
    print(f"Parsed {len(sections)} changelog sections")

    releases = api_request(f"{API}/repos/{REPO}/releases?per_page=100")
    updated = 0
    for rel in releases:
        tag = rel["tag_name"]
        version = tag.lstrip("v")
        if version in sections:
            try:
                api_request(
                    f"{API}/repos/{REPO}/releases/{rel['id']}",
                    method="PATCH",
                    data=json.dumps({"body": sections[version]}).encode(),
                )
                print(f"Updated release {tag}")
                updated += 1
            except urllib.error.HTTPError as e:
                print(f"Failed {tag}: {e.code} {e.read().decode()[:200]}")
        else:
            print(f"No changelog section for {tag}")

    print(f"Done. Updated {updated} release(s).")


if __name__ == "__main__":
    main()
