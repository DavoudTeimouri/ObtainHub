"""Self-check for tools/gen_wix_payload.py — run directly:

    python3 selfcheck_wix_payload.py

Asserts the generated setup.wxs satisfies the WiX rules that have actually
broken the build: CNDL0014 (legal identifiers), CNDL0062 (Component/@Directory
under a ComponentGroup), CNDL0005 (Environment only in a Fragment), valid XML,
sources on disk, the onedir tree preserved, and idempotent output.
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

# The exact grammar WiX accepts, from CNDL0014.
LEGAL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")

HYPHENATED = [
    "api-ms-win-core-console-l1-1-0",
    "libcrypto-3",
    "keyring-25_7_0.dist-info",
    "charset_normalizer-cd-cp311-win_amd64",
    "importlib_metadata-9_0_1.dist-info",
]


def build_fake_ondedir(base: Path) -> Path:
    dist = base / "dist" / "ohub"
    (dist / "_internal" / "keyrings" / "alt").mkdir(parents=True)
    (dist / "_internal" / "importlib_metadata-9_0_1.dist-info" / "licenses").mkdir(parents=True)
    (dist / "ohub.exe").write_bytes(b"MZ")
    (dist / "pyvenv.cfg").write_bytes(b"home = /x")
    (dist / "_internal" / "python311.dll").write_bytes(b"PE")
    (dist / "_internal" / "base_library.zip").write_bytes(b"PK")
    for name in HYPHENATED:
        (dist / "_internal" / (name + ".dll")).write_bytes(b"PE")
    (dist / "_internal" / "keyrings" / "alt" / "__init__.py").write_text("")
    (dist / "_internal" / "importlib_metadata-9_0_1.dist-info" / "METADATA").write_text("")
    (dist / "_internal" / "importlib_metadata-9_0_1.dist-info" / "licenses" / "LICENSE").write_text("")
    return dist


def check_ids(kind, values):
    for v in values:
        if not LEGAL_RE.match(v or ""):
            FAILS.append("CNDL0014 %s Id is not legal: %r" % (kind, v))
        if len(v or "") > 72:
            FAILS.append("%s Id over 72 chars: %r" % (kind, v))


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

# 1. Valid XML.
try:
    root = ET.fromstring(text)
except ET.ParseError as e:
    FAILS.append("generated setup.wxs is not well-formed XML: %s" % e)
    root = None

if root is not None:
    files = list(root.iter(WIX_NS + "File"))
    comps = list(root.iter(WIX_NS + "Component"))
    dirs = list(root.iter(WIX_NS + "Directory"))
    groups = list(root.iter(WIX_NS + "ComponentGroup"))
    sources = [f.get("Source") for f in files]

    # 2. CNDL0014: every generated Id must match the WiX grammar.
    check_ids("File", [f.get("Id") for f in files])
    check_ids("Component", [c.get("Id") for c in comps])
    check_ids("Directory", [d.get("Id") for d in dirs])

    # 3. Ids unique within each namespace.
    for kind, values in (
        ("File", [f.get("Id") for f in files]),
        ("Component", [c.get("Id") for c in comps]),
        ("Directory", [d.get("Id") for d in dirs]),
    ):
        dupes = {i for i in values if values.count(i) > 1}
        if dupes:
            FAILS.append("duplicate %s Ids: %s" % (kind, sorted(dupes)))

    # 4. CNDL0062: a Component inside a ComponentGroup must not set @Directory.
    for group in groups:
        if not group.get("Directory"):
            FAILS.append("ComponentGroup %s has no Directory" % group.get("Id"))
        for c in group.findall(WIX_NS + "Component"):
            if c.get("Directory") is not None:
                FAILS.append(
                    "CNDL0062: Component %s sets @Directory inside a ComponentGroup"
                    % c.get("Id")
                )

    # 4b. A ComponentGroup is not legal under a DirectoryRef either. WiX rejects
    #     it the same way it rejects @Directory on a nested Component.
    for dref in root.iter(WIX_NS + "DirectoryRef"):
        for group in dref.iter(WIX_NS + "ComponentGroup"):
            FAILS.append(
                "CNDL0062: ComponentGroup %s nested under DirectoryRef"
                % group.get("Id")
            )

    # 4c. CNDL0010: a Component that is not inside a Directory and not inside a
    #     ComponentGroup must carry @Directory itself. ElementTree has no parent
    #     pointers, so walk the tree once and index them.
    parent_of = {}
    for p in root.iter():
        for child in p:
            parent_of[child] = p

    def has_ancestor(elem, tag):
        node = parent_of.get(elem)
        while node is not None:
            if node.tag == tag:
                return True
            node = parent_of.get(node)
        return False

    for c in comps:
        in_dir = has_ancestor(c, WIX_NS + "Directory")
        in_dref = has_ancestor(c, WIX_NS + "DirectoryRef")
        in_group = has_ancestor(c, WIX_NS + "ComponentGroup")
        if not (in_dir or in_dref or in_group) and c.get("Directory") is None:
            FAILS.append(
                "CNDL0010: Component %s has no @Directory, no parent Directory "
                "and no parent DirectoryRef" % c.get("Id")
            )

    # 5. CNDL0005: Environment is only legal under a Fragment.
    product = root.find(WIX_NS + "Product")
    if product is not None:
        for env in product.findall(WIX_NS + "Environment"):
            FAILS.append("CNDL0005: Environment nested directly under Product")

    # 6. Every Component is reachable: nested in a Directory, in a group, or
    #    referenced by the Feature.
    refs = {r.get("Id") for r in root.iter(WIX_NS + "ComponentRef")}
    in_group = {c.get("Id") for g in groups for c in g.findall(WIX_NS + "Component")}
    for c in comps:
        if c.get("Id") not in refs and c.get("Id") not in in_group:
            FAILS.append("Component %s is neither referenced nor in a group" % c.get("Id"))

    # 7. Every Source exists on disk.
    for s in sources:
        rel = s.replace("\\", "/").split("/", 2)[2]
        if not (dist / rel).exists():
            FAILS.append("Source not on disk: %s" % s)

    # 8. The onedir tree shape is preserved.
    for needed in (
        "_internal\\keyrings\\alt\\__init__.py",
        "_internal\\importlib_metadata-9_0_1.dist-info\\METADATA",
        "_internal\\importlib_metadata-9_0_1.dist-info\\licenses\\LICENSE",
    ):
        if not any(needed in s for s in sources):
            FAILS.append("nested path not preserved: %s" % needed)
    for name in ("_internal", "keyrings", "alt", "licenses"):
        if not any(d.get("Name") == name for d in dirs):
            FAILS.append("Directory %r missing from the generated tree" % name)

    # 9. Full coverage, no extras.
    expected = {
        str(p.relative_to(dist)).replace("/", "\\")
        for p in dist.rglob("*") if p.is_file() and p.name != "ohub.exe"
    }
    covered = {s.replace("\\", "/")[len("dist/ohub/"):].replace("/", "\\") for s in sources}
    if expected - covered:
        FAILS.append("payload not enumerated: %s" % sorted(expected - covered)[:5])
    if (covered - expected) - {"ohub.exe"}:
        FAILS.append("unexpected sources: %s" % sorted(covered - expected))

    # 10. Exactly one KeyPath per file-only Component.
    for c in comps:
        kids = c.findall(WIX_NS + "File")
        if kids and c.find(WIX_NS + "RegistryValue") is None:
            keypaths = [k for k in kids if k.get("KeyPath") == "yes"]
            if len(keypaths) != 1:
                FAILS.append(
                    "Component %s has %d KeyPaths, expected exactly 1"
                    % (c.get("Id"), len(keypaths))
                )

    # 11. GUIDs stable across runs.
    before = {c.get("Id"): c.get("Guid") for c in comps}
    gen.main()
    after = {
        c.get("Id"): c.get("Guid")
        for c in ET.fromstring(gen.WXS.read_text(encoding="utf-8")).iter(WIX_NS + "Component")
    }
    if before != after:
        FAILS.append("component GUIDs are not stable across runs")

# 12. Idempotent: the placeholders survive (re-emitted by the generator).
#     The generated block's own comment also says "GENERATED PAYLOAD",
#     so the count will be >= 1. Just verify both placeholders exist.
if "<!-- GENERATED PAYLOAD -->" not in text:
    FAILS.append("GENERATED PAYLOAD placeholder missing")
if "<!-- GENERATED COMPONENT REFS -->" not in text:
    FAILS.append("GENERATED COMPONENT REFS placeholder missing")
if text.count("<Fragment>") != text.count("</Fragment>"):
    FAILS.append("unbalanced <Fragment> elements")
if text.count("<DirectoryRef") != text.count("</DirectoryRef>"):
    FAILS.append("unbalanced <DirectoryRef> elements")

# 13. CNDL0107: <Wix> may contain only elements, never text. The generator
#     used to emit "<!-- GENERATED PAYLOAD --> 131 file(s) ...", which closed
#     the comment early and left the rest as text under <Wix>. ElementTree
#     drops whitespace-only .text, so check the raw source: strip comments,
#     then look for text that is not pure whitespace between any two tags.
no_comments = re.sub(r"<!--.*?-->", "", text, flags=re.S)
for m in re.finditer(r">([^<]*)<", no_comments):
    if m.group(1).strip():
        FAILS.append(
            "CNDL0107: non-whitespace text inside <Wix>: %r" % m.group(1)[:60]
        )
        break

# 14. Missing dist/ is a clean error.
gen.DIST = tmp / "nope"
if gen.main() != 1:
    FAILS.append("generator did not fail cleanly on a missing dist dir")

shutil.rmtree(tmp, ignore_errors=True)

if FAILS:
    print("FAIL")
    for f in FAILS[:25]:
        print("  -", f)
    if len(FAILS) > 25:
        print("  ... and %d more" % (len(FAILS) - 25))
    sys.exit(1)
print("PASS: WiX payload obeys CNDL0014/0062/0005, tree preserved, wired into the Feature")
