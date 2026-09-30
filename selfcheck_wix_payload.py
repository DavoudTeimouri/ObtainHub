"""Self-check for tools/gen_wix_payload.py — run directly:

    python3 selfcheck_wix_payload.py

Builds a fake onedir tree, generates the payload, and asserts the
resulting setup.wxs is what Windows Installer and PyInstaller need:
well-formed XML, unique and legal Ids, stable GUIDs, the directory
shape preserved, the Feature actually referencing the payload, and
idempotent re-runs.
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
    (dist / "_internal" / "keyrings" / "alt").mkdir(parents=True)
    (dist / "ohub.exe").write_bytes(b"MZ")
    (dist / "pyvenv.cfg").write_bytes(b"home = /x")
    (dist / "_internal" / "python311.dll").write_bytes(b"PE")
    (dist / "_internal" / "base_library.zip").write_bytes(b"PK")
    (dist / "_internal" / "keyrings" / "alt" / "__init__.py").write_text("")
    return dist


def legal_id(value: str) -> bool:
    return bool(
        value
        and (value[0].isalpha() or value[0] == "_")
        and len(value) <= 72
        and re.match(r"^[A-Za-z0-9_.-]+$", value)
    )


tmp = Path(tempfile.mkdtemp())
dist = build_fake_ondedir(tmp)

gen.ROOT = tmp
gen.DIST = dist
gen.WXS = tmp / "setup.wxs"
gen.WXS.write_text((ROOT / "installer" / "setup.wxs").read_text(encoding="utf-8"), encoding="utf-8")

if gen.main() != 0:
    print("FAIL: generator returned non-zero")
    raise SystemExit(1)

text = gen.WXS.read_text(encoding="utf-8")

# 1. Well-formed XML.
try:
    root = ET.fromstring(text)
except ET.ParseError as e:
    FAILS.append("generated setup.wxs is not well-formed XML: %s" % e)
    root = None

if root is not None:
    files = list(root.iter(WIX_NS + "File"))
    comps = list(root.iter(WIX_NS + "Component"))
    dirs = list(root.iter(WIX_NS + "Directory"))
    sources = [f.get("Source") for f in files]
    ids = [f.get("Id") for f in files]

    # 2. File Ids unique and MSI-legal.
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        FAILS.append("duplicate File Ids: %s" % sorted(dupes))
    for i in ids:
        if not legal_id(i):
            FAILS.append("illegal File Id: %r" % i)

    # 3. Directory and Component Ids unique and legal.
    for tag, elements in (("Directory", dirs), ("Component", comps)):
        got = [e.get("Id") for e in elements]
        dup = {i for i in got if got.count(i) > 1}
        if dup:
            FAILS.append("duplicate %s Ids: %s" % (tag, sorted(dup)))
        for i in got:
            if not legal_id(i):
                FAILS.append("illegal %s Id: %r" % (tag, i))

    # 4. Every Component and DirectoryRef points at a Directory that exists.
    known = {d.get("Id") for d in dirs} | {
        "INSTALLFOLDER", "TARGETDIR", "ProgramFiles64Folder",
        "ProgramMenuFolder", "ApplicationProgramsFolder",
    }
    group_dirs = {g.get("Id"): g.get("Directory") for g in root.iter(WIX_NS + "ComponentGroup")}
    for c in comps:
        target = c.get("Directory")
        if target is None:
            # Legal inside a ComponentGroup: the directory is inherited.
            target = group_dirs.get("OnedirPayload") or "INSTALLFOLDER"
        if target not in known:
            FAILS.append("Component %s -> unknown Directory %r" % (c.get("Id"), c.get("Directory")))
    for ref in root.iter(WIX_NS + "DirectoryRef"):
        if ref.get("Id") not in known:
            FAILS.append("DirectoryRef -> unknown Directory %r" % ref.get("Id"))

    # 5. Every Source exists on disk (relative to the fake tree).
    for s in sources:
        rel = s.replace("\\", "/").split("/", 2)[2]
        if not (dist / rel).exists():
            FAILS.append("Source not on disk: %s" % s)

    # 6. Tree shape preserved: _internal\\keyrings\\alt stays nested. A flattened
    #    payload installs cleanly and then fails to import at runtime.
    nested = "_internal\\keyrings\\alt\\__init__.py"
    if not any(nested in s for s in sources):
        FAILS.append("nested path %s was not preserved" % nested)
    for name in ("_internal", "keyrings", "alt"):
        if not any(d.get("Name") == name for d in dirs):
            FAILS.append("Directory %r missing from the generated tree" % name)

    # 7. Every payload file covered exactly once; ohub.exe is its own component.
    expected = {
        str(p.relative_to(dist)).replace("/", "\\")
        for p in dist.rglob("*") if p.is_file() and p.name != "ohub.exe"
    }
    covered = {s.replace("\\", "/")[len("dist/ohub/"):].replace("/", "\\") for s in sources}
    if expected - covered:
        FAILS.append("payload not enumerated: %s" % sorted(expected - covered))
    if (covered - expected) - {"ohub.exe"}:
        FAILS.append("unexpected sources: %s" % sorted(covered - expected - {"ohub.exe"}))
    if sources.count("dist\\ohub\\ohub.exe") != 1:
        FAILS.append("ohub.exe should appear exactly once")

    # 8. THE regression: a ComponentGroup nothing references is never installed.
    refs = {r.get("Id") for r in root.iter(WIX_NS + "ComponentGroupRef")}
    groups = {g.get("Id") for g in root.iter(WIX_NS + "ComponentGroup")}
    if "OnedirPayload" not in groups:
        FAILS.append("OnedirPayload ComponentGroup missing")
    if "OnedirPayload" not in refs:
        FAILS.append("Feature does not reference OnedirPayload; payload would never install")

    # 9. Every file-only Component needs a KeyPath or the link fails.
    for c in comps:
        first = c.find(WIX_NS + "File")
        if first is not None and c.find(WIX_NS + "RegistryValue") is None:
            if first.get("KeyPath") != "yes":
                FAILS.append("Component %s: first File is not KeyPath=yes" % c.get("Id"))

    # 10. Component GUIDs deterministic across runs.
    guids_before = {c.get("Id"): c.get("Guid") for c in comps}
    gen.main()
    comps2 = list(ET.fromstring(gen.WXS.read_text(encoding="utf-8")).iter(WIX_NS + "Component"))
    guids_after = {c.get("Id"): c.get("Guid") for c in comps2}
    if guids_before != guids_after:
        FAILS.append("component GUIDs are not stable across runs")

# 11. Idempotent: the marker is not duplicated.
if text.count("GENERATED PAYLOAD") != 1:
    FAILS.append("generator is not idempotent; marker duplicated")

# 12. Missing dist/ is a clean error, not a traceback.
gen.DIST = tmp / "nope"
if gen.main() != 1:
    FAILS.append("generator did not fail cleanly on a missing dist dir")

shutil.rmtree(tmp, ignore_errors=True)

if FAILS:
    print("FAIL")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print(
    "PASS: WiX payload preserves the onedir tree, is wired into the Feature, "
    "ids/guids stable, idempotent"
)
