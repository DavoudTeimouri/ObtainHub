#!/usr/bin/env python3
"""Generate the onedir payload into installer/setup.wxs.

Two facts force this to be generated rather than hand-written:

1. WiX rejects a directory as a <File Source=...>, and a PyInstaller onedir
   tree is a directory of loose files whose contents depend on the Python
   version and the installed dependencies.
2. The tree has to keep its shape. PyInstaller imports from _internal\\ at
   runtime, so flattening _internal\\keyrings\\alt\\ into _internal\\ would
   produce an MSI that installs but does not run.

So this emits the real directory tree, one Component per directory (each
carrying a stable GUID so upgrades replace files correctly), and wires the
result into a Feature. Run after PyInstaller, before candle:

    python tools/gen_wix_payload.py
"""

import sys
import uuid
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "ohub"
WXS = ROOT / "installer" / "setup.wxs"
MARKER = "  <!-- GENERATED PAYLOAD:"

# Deterministic namespace so component GUIDs are stable across rebuilds:
# a changed GUID makes Windows Installer install a second copy instead of
# upgrading the first.
GUID_NS = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")

# A Windows Installer Id must start with a letter or underscore, stay within
# 72 characters, and be unique across the package.
MAX_ID = 60


def sanitise(stem: str, taken: set) -> str:
    cleaned = "".join(c if (c.isalnum() or c in "_-") else "_" for c in stem)
    if not cleaned or not (cleaned[0].isalpha() or cleaned[0] == "_"):
        cleaned = "f_" + cleaned
    base = cleaned[:MAX_ID]
    candidate, n = base, 1
    while candidate in taken:
        suffix = "_%d" % n
        candidate = base[: MAX_ID - len(suffix)] + suffix
        n += 1
    taken.add(candidate)
    return candidate


def group_by_dir(payload):
    """{relative parent dir: [files]} plus the set of every dir in the tree.

    Parents are added even when they hold no files of their own:
    _internal\\keyrings\\alt\\__init__.py implies _internal and _internal\\keyrings.
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


def directory_id(directory: Path, taken: set) -> str:
    return "d_" + sanitise("_".join(directory.parts), taken)


def component_id(directory: Path, taken: set) -> str:
    return "c_" + sanitise("_".join(directory.parts), taken)


class Ids:
    """One id per directory, memoised so the DirectoryRef and the Component
    that targets it always name the same Directory."""

    def __init__(self):
        self._dirs: dict = {}
        self._comps: dict = {}
        self._taken_dirs: set = set()
        self._taken_comps: set = set()

    def directory(self, path: Path) -> str:
        if path not in self._dirs:
            self._dirs[path] = directory_id(path, self._taken_dirs)
        return self._dirs[path]

    def component(self, path: Path) -> str:
        if path not in self._comps:
            self._comps[path] = component_id(path, self._taken_comps)
        return self._comps[path]


def component_guid(directory: Path) -> str:
    return str(
        uuid.uuid5(GUID_NS, "obtainhub/onedir/" + str(directory).replace("\\", "/"))
    ).upper()


def render(payload) -> str:
    ids = Ids()
    taken_files = {"ohub.exe"}
    tree, all_dirs = group_by_dir(payload)

    # Every directory except the root, shallowest first so nesting is legal.
    nested = sorted(
        (d for d in all_dirs if d != Path(".")),
        key=lambda p: (len(p.parts), str(p)),
    )

    out = [
        MARKER + " %d file(s) by tools/gen_wix_payload.py - do not hand-edit."
        % len(payload),
        "  -->",
        "",
        "  <Fragment>",
        '    <DirectoryRef Id="INSTALLFOLDER">',
    ]

    open_stack: list = []
    for directory in nested:
        # Close anything that is not an ancestor of this directory.
        while open_stack and open_stack[-1] not in directory.parents:
            out.append("      " + "  " * (len(open_stack) - 1) + "</Directory>")
            open_stack.pop()

        indent = "      " + "  " * len(open_stack)
        out.append(
            '%s<Directory Id="%s" Name="%s">'
            % (indent, ids.directory(directory), escape(directory.name))
        )
        open_stack.append(directory)

    while open_stack:
        out.append("      " + "  " * (len(open_stack) - 1) + "</Directory>")
        open_stack.pop()

    out.append("    </DirectoryRef>")
    out.append("")
    out.append('    <ComponentGroup Id="OnedirPayload" Directory="INSTALLFOLDER">')

    # One component per directory holding files, KeyPath on its first file.
    for parent in sorted(tree, key=lambda p: (len(p.parts), str(p))):
        cid = "c_root" if parent == Path(".") else ids.component(parent)
        did = "INSTALLFOLDER" if parent == Path(".") else ids.directory(parent)
        out.append(
            '      <Component Id="%s" Guid="%s" Directory="%s">'
            % (cid, component_guid(parent), did)
        )
        files = sorted(tree[parent], key=lambda p: p.name)
        for index, relative in enumerate(files):
            fid = sanitise("_".join(relative.with_suffix("").parts), taken_files)
            source = str(Path("dist") / "ohub" / relative).replace("/", "\\")
            # Windows Installer needs exactly one KeyPath per component.
            keypath = ' KeyPath="yes"' if index == 0 else ""
            out.append(
                '        <File Id="%s" Name="%s" Source="%s"%s />'
                % (fid, escape(relative.name), escape(source), keypath)
            )
        out.append("      </Component>")

    out.append("    </ComponentGroup>")
    out.append("  </Fragment>")
    return "\n".join(out)


def main() -> int:
    if not DIST.is_dir():
        print("ERROR: %s not found - run the PyInstaller build first" % DIST, file=sys.stderr)
        return 1

    payload = sorted(p for p in DIST.rglob("*") if p.is_file() and p.name != "ohub.exe")
    if not payload:
        print("ERROR: onedir payload is empty (only ohub.exe found)", file=sys.stderr)
        return 1

    text = WXS.read_text(encoding="utf-8")
    start = text.index(MARKER)
    end = text.index("</Wix>", start)
    WXS.write_text(text[:start] + render(payload) + "\n" + text[end:], encoding="utf-8")

    tree, _ = group_by_dir(payload)
    print(
        "installer/setup.wxs: %d payload file(s) in %d component(s)"
        % (len(payload), len(tree))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
