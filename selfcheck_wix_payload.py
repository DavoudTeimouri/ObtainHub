"""Self-check for tools/gen_wix_payload.py — run directly:

    python3 selfcheck_wix_payload.py

Builds a fake onedir tree, generates the payload block, and asserts the
resulting setup.wxs is well-formed XML, has unique MSI-legal File Ids, and
references only files that exist.
"""

import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import tools.gen_wix_payload as gen

FAILS = []
WIX_NS = "{http://schemas.microsoft.com/wix/2006/wi}"


def build_fake_ondedir(base: Path) -> Path:
    dist = base / "dist" / "ohub"
    (dist / "_internal").mkdir(parents=True)
    (dist / "ohub.exe").write_bytes(b"MZ")
    (dist / "_internal" / "python311.dll").write_bytes(b"PE")
    (dist / "_internal" / "base_library.zip").write_bytes(b"PK")
    nested = dist / "_internal" / "keyrings" / "alt"
    nested.mkdir(parents=True)
    (nested / "__init__.py").write_text("")
    return dist


tmp = Path(tempfile.mkdtemp())
dist = build_fake_ondedir(tmp)

# Point the generator at the fake tree and a copy of the real setup.wxs.
gen.ROOT = tmp
gen.DIST = dist
gen.WXS = tmp / "setup.wxs"
gen.WXS.write_text(
    (ROOT / "installer" / "setup.wxs").read_text(encoding="utf-8"), encoding="utf-8"
)

rc = gen.main()
if rc != 0:
    print("FAIL: generator returned %d" % rc)
    raise SystemExit(1)

text = gen.WXS.read_text(encoding="utf-8")

# 1. Well-formed XML (a malformed Ids block fails candle, not this script).
try:
    root = ET.fromstring(text)
except ET.ParseError as e:
    FAILS.append("generated setup.wxs is not well-formed XML: %s" % e)
    root = None

if root is not None:
    files = root.iter(WIX_NS + "File")
    ids = []
    sources = []
    for f in files:
        ids.append(f.get("Id"))
        sources.append(f.get("Source"))

    # 2. Ids unique and MSI-legal.
    if len(ids) != len(set(ids)):
        dupes = [i for i in set(ids) if ids.count(i) > 1]
        FAILS.append("duplicate File Ids: %s" % dupes)
    for i in ids:
        if not i or not (i[0].isalpha() or i[0] == "_"):
            FAILS.append("File Id %r does not start with a letter or underscore" % i)
        if len(i) > 72:
            FAILS.append("File Id %r exceeds 72 characters" % i)
        if not re.match(r"^[A-Za-z0-9_.-]+$", i):
            FAILS.append("File Id %r has characters MSI forbids" % i)

    # 3. Every source file must exist under the repo root.
    for s in sources:
        if not (ROOT / s.replace("\\", "/")).exists() and not (tmp / s.replace("\\", "/")).exists():
            FAILS.append("Source does not exist: %s" % s)

    # 4. All onedir files are covered, and ohub.exe is not duplicated.
    expected = {
        str(p.relative_to(dist)).replace("/", "\\")
        for p in dist.rglob("*") if p.is_file() and p.name != "ohub.exe"
    }
    covered = {s.replace("\\", "/")[len("dist/ohub/"):] for s in sources}
    covered = {p.replace("/", "\\") for p in covered}
    missing = expected - covered
    if missing:
        FAILS.append("payload files not enumerated: %s" % sorted(missing))

    if sources.count("dist\\ohub\\ohub.exe") != 1:
        FAILS.append("ohub.exe should appear exactly once (its own Component)")

# 5. Running twice is stable (no duplicate blocks).
gen.main()
second = gen.WXS.read_text(encoding="utf-8")
if second.count("GENERATED PAYLOAD") != 1:
    FAILS.append("generator is not idempotent; marker duplicated")
if text.replace("\r\n", "\n") != second.replace("\r\n", "\n"):
    FAILS.append("second run changed the generated block")

# 6. Missing dist/ must be a clean error, not a traceback.
gen.DIST = tmp / "nope"
if gen.main() != 1:
    FAILS.append("generator did not fail cleanly on a missing dist dir")

shutil.rmtree(tmp, ignore_errors=True)

if FAILS:
    print("FAIL")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("PASS: WiX payload block is well-formed, ids unique/legal, all files covered, idempotent")
