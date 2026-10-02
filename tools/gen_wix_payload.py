#!/usr/bin/env python3
"""Generate the onedir payload into installer/setup.wxs.

Three WiX rules force this to be generated rather than hand-written:

1. WiX rejects a directory as a <File Source=...>, and a PyInstaller onedir
   tree is a directory of loose files whose contents depend on the Python
   version and the installed dependencies.
2. The tree has to keep its shape. PyInstaller imports from _internal\\ at
   runtime, so flattening _internal\\keyrings\\alt\\ into _internal\\ would
   produce an MSI that installs but does not run.
3. A Component may not carry @Directory when it sits in a ComponentGroup
   (CNDL0062). So each Component is nested inside its own <Directory> and
   the Feature pulls it in with <ComponentRef>.

Ids are restricted to the characters Windows Installer accepts: letters,
digits, underscore and period only, starting with a letter or underscore.
Package names like keyring-25_7_0.dist-info contain hyphens, so a naive
join produces CNDL0014.

Run after PyInstaller, before candle:

    python tools/gen_wix_payload.py
"""

import sys
import uuid
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "ohub"
WXS = ROOT / "installer" / "setup.wxs"

REFS_MARKER = "    <!-- GENERATED COMPONENT REFS -->"
PAYLOAD_MARKER = "  <!-- GENERATED PAYLOAD -->"

# Deterministic namespace so component GUIDs are stable across rebuilds:
# a changed GUID makes Windows Installer install a second copy instead of
# upgrading the first.
GUID_NS = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")

# CNDL0014: a Windows Installer Id may contain only A-Z, a-z, 0-9, "_" and
# ".", and must start with a letter or underscore. 72 chars is the cap.
LEGAL = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.")
MAX_ID = 60


def sanitise(stem: str, taken: set) -> str:
    cleaned = "".join(c if c in LEGAL else "_" for c in stem)
    if not cleaned or not (cleaned[0].isalpha() or cleaned[0] == "_"):
        cleaned = "_" + cleaned
    base = cleaned[:MAX_ID]
    candidate, n = base, 1
    while candidate in taken:
        suffix = "_%d" % n
        candidate = base[: MAX_ID - len(suffix)] + suffix
        n += 1
    taken.add(candidate)
    return candidate


def component_guid(directory: Path) -> str:
    return str(
        uuid.uuid5(GUID_NS, "obtainhub/onedir/" + str(directory).replace("\\", "/"))
    ).upper()


def group_by_dir(payload):
    """{relative parent dir: [files]}, plus every directory in the tree.

    Parents are added even when they hold no files of their own:
    _internal\\keyrings\\alt\\__init__.py implies _internal and
    _internal\\keyrings.
    """
    tree: dict = {}
    for path in payload:
        relative = path.relative_to(DIST)
        tree.setdefault(relative.parent, []).append(relative)

    all_dirs = {Path(".")}
    for parent in list(tree):
        parts = parent.parts
        for i in range(1, len(parts) + 1):
            all_dirs.add(Path(*parts[:i]))
    return tree, all_dirs


def file_id(relative: Path, taken: set) -> str:
    return sanitise("_".join(relative.with_suffix("").parts), taken)


def component_lines(parent, files, ids_taken, indent="      "):
    """One Component holding `files`, nested under its own Directory."""
    if parent == Path("."):
        cid = "c_root"
    else:
        cid = "c_" + sanitise("_".join(parent.parts), ids_taken)

    out = [
        '%s<Component Id="%s" Guid="%s">'
        % (indent, cid, component_guid(parent))
    ]
    taken = {"ohub.exe"}
    for index, relative in enumerate(sorted(files, key=lambda p: p.name)):
        fid = file_id(relative, taken)
        source = str(Path("dist") / "ohub" / relative).replace("/", "\\")
        keypath = ' KeyPath="yes"' if index == 0 else ""
        out.append(
            '%s  <File Id="%s" Name="%s" Source="%s"%s />'
            % (indent, fid, escape(relative.name), escape(source), keypath)
        )
    out.append("%s</Component>" % indent)
    return cid, out


def render(payload):
    tree, all_dirs = group_by_dir(payload)
    ids_taken: set = set()
    dir_taken: set = set()
    taken_files = {"ohub.exe"}

    nested = sorted(
        (d for d in all_dirs if d != Path(".")),
        key=lambda p: (len(p.parts), str(p)),
    )

    def directory_name(path: Path) -> str:
        return "d_" + sanitise("_".join(path.parts), dir_taken)

    body = []
    refs = []
    open_stack: list = []

    for directory in nested:
        while open_stack and open_stack[-1] not in directory.parents:
            body.append("      " + "  " * (len(open_stack) - 1) + "</Directory>")
            open_stack.pop()

        indent = "      " + "  " * len(open_stack)
        body.append(
            '%s<Directory Id="%s" Name="%s">'
            % (indent, directory_name(directory), escape(directory.name))
        )
        open_stack.append(directory)

        if directory in tree:
            cid, lines = component_lines(
                directory, tree[directory], ids_taken, indent + "  "
            )
            body.extend(lines)
            refs.append(cid)

    while open_stack:
        body.append("      " + "  " * (len(open_stack) - 1) + "</Directory>")
        open_stack.pop()

    # Files sitting at the top of dist\ohub get a plain Component next to the
    # generated ones. A ComponentGroup here would be the CNDL0062 shape and
    # cannot live under a DirectoryRef anyway.
    if Path(".") in tree:
        cid, lines = component_lines(Path("."), tree[Path(".")], ids_taken, "      ")
        body.append("")
        body.extend(lines)
        refs.append(cid)

    refs_block = "\n".join(
        ['      <ComponentRef Id="%s" />' % c for c in sorted(refs)]
    )
    payload_block = "\n".join(
        [
            "  <!-- %d file(s) by tools/gen_wix_payload.py - do not hand-edit. -->"
            % len(payload),
            "",
            "  <Fragment>",
            '    <DirectoryRef Id="INSTALLFOLDER">',
        ]
        + body
        + [
            "    </DirectoryRef>",
            "  </Fragment>",
        ]
    )
    return refs_block, payload_block


def splice(text: str, marker: str, block: str, after: str) -> str:
    """Replace [marker, after) with `block` plus a fresh marker.

    The marker is re-emitted so the generator is idempotent: a second run
    finds it again instead of tripping over a missing substring.
    """
    if marker not in text:
        # Already generated; re-insert the marker just above the closing tag.
        at = text.index(after)
        return text[:at] + block + "\n" + marker + "\n" + text[at:]

    start = text.index(marker)
    end = text.index(after, start)
    return text[:start] + block + "\n" + marker + "\n" + text[end:]


def main() -> int:
    if not DIST.is_dir():
        print("ERROR: %s not found - run the PyInstaller build first" % DIST, file=sys.stderr)
        return 1

    payload = sorted(p for p in DIST.rglob("*") if p.is_file() and p.name != "ohub.exe")
    if not payload:
        print("ERROR: onedir payload is empty (only ohub.exe found)", file=sys.stderr)
        return 1

    refs_block, payload_block = render(payload)
    text = WXS.read_text(encoding="utf-8")
    text = splice(text, REFS_MARKER, refs_block, "</Feature>")
    text = splice(text, PAYLOAD_MARKER, payload_block, "</Wix>")
    WXS.write_text(text, encoding="utf-8")

    tree, _ = group_by_dir(payload)
    print(
        "installer/setup.wxs: %d payload file(s) in %d component(s)"
        % (len(payload), len(tree))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
