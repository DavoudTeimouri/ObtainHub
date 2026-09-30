#!/usr/bin/env python3
"""Generate the onedir payload block in installer/setup.wxs.

A PyInstaller onedir build is a directory of loose files whose exact contents
depend on the Python version and the installed dependencies, so the WiX MSI
cannot reference them from a static list. WiX also rejects a directory as a
<File Source=...>, so the payload has to be enumerated at build time.

Run after PyInstaller, before candle:

    python tools/gen_wix_payload.py

Rewrites everything between the GENERATED PAYLOAD marker and the closing
</Fragment> in installer/setup.wxs.
"""

import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "ohub"
WXS = ROOT / "installer" / "setup.wxs"
MARKER = "<!-- GENERATED PAYLOAD:"

# A Windows Installer File Id must start with a letter or underscore and stay
# within 72 characters; short|long names must also be unique package-wide.
MAX_ID = 60


def sanitise_id(relative: Path, taken: set) -> str:
    """Deterministic, unique, MSI-legal File Id for one payload path."""
    stem = "_".join(relative.with_suffix("").parts)
    cleaned = "".join(c if (c.isalnum() or c in "_-") else "_" for c in stem)
    if not cleaned or not (cleaned[0].isalpha() or cleaned[0] == "_"):
        cleaned = "f_" + cleaned
    base = cleaned[:MAX_ID]
    candidate = base
    n = 1
    while candidate in taken:
        suffix = "_%d" % n
        candidate = base[: MAX_ID - len(suffix)] + suffix
        n += 1
    taken.add(candidate)
    return candidate


def render_block(payload) -> str:
    taken = {"ohub.exe"}
    lines = []
    for path in payload:
        relative = path.relative_to(DIST)
        file_id = sanitise_id(relative, taken)
        source = str(Path("dist") / "ohub" / relative).replace("/", "\\")
        lines.append(
            '        <File Id="%s" Name="%s" Source="%s" />'
            % (file_id, escape(relative.name), escape(source))
        )

    return "\n".join(
        [
            MARKER + " %d file(s) by tools/gen_wix_payload.py - do not hand-edit."
            % len(payload),
            "    -->",
            '    <DirectoryRef Id="INTERNALFOLDER">',
            '      <Component Id="OnedirPayload" Guid="A1B2C3D4-E5F6-7890-ABCD-EF1234567892">',
        ]
        + lines
        + [
            "      </Component>",
            "    </DirectoryRef>",
        ]
    )


def main() -> int:
    if not DIST.is_dir():
        print("ERROR: %s not found - run the PyInstaller build first" % DIST, file=sys.stderr)
        return 1

    payload = sorted(
        p for p in DIST.rglob("*")
        if p.is_file() and p.name != "ohub.exe"
    )
    if not payload:
        print("ERROR: onedir payload is empty (only ohub.exe found)", file=sys.stderr)
        return 1

    text = WXS.read_text(encoding="utf-8")
    start = text.index(MARKER)
    end = text.index("</Fragment>", start)
    # The tail already carries the closing </Fragment>, so replace the previous
    # block only. Re-appending text[end:] here would duplicate that close.
    WXS.write_text(text[:start] + render_block(payload) + "\n  " + text[end:], encoding="utf-8")

    print("installer/setup.wxs: %d payload file(s) enumerated" % len(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
