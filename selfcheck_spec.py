"""Static check of ObtainHub.spec: every referenced input must exist, and the
onedir wiring (EXE exclude_binaries + COLLECT) must be correct.

Run: python3 selfcheck_spec.py
"""

import os
import re
import sys

SPEC = "/workspace/project/github/public-repository/ObtainHub/ObtainHub.spec"
ROOT = os.path.dirname(SPEC)
FAILS = []

src = open(SPEC, encoding="utf-8").read()

# 1. Every ('path', 'dest') tuple in datas must point at a real file.
datas = re.findall(r"\('([^']+)',\s*'([^']+)'\)", src)
for src_path, _dest in datas:
    if not os.path.exists(os.path.join(ROOT, src_path)):
        FAILS.append("datas references a missing file: %s" % src_path)
print("datas entries: %d" % len(datas))

# 2. Every hiddenimport that names a module inside this repo must exist on disk.
# Third-party and stdlib packages are installed by pip, not vendored here.
STDLIB = {"json", "pathlib", "dataclasses", "typing", "datetime", "threading",
          "tempfile", "subprocess", "argparse", "signal", "shutil", "logging",
          "re", "hashlib", "base64", "stat", "platform", "ctypes",
          "importlib.metadata"}
THIRD_PARTY = {"requests", "urllib3", "textual", "rich", "keyring", "keyrings.alt"}

mods = re.search(r"hiddenimports=\[(.*?)\n    \],", src, re.S)
mods = re.findall(r"'([\w.]+)'", mods.group(1)) if mods else []
for mod in mods:
    if mod in STDLIB or mod in THIRD_PARTY:
        continue
    rel = mod.replace(".", os.sep)
    if not (os.path.exists(os.path.join(ROOT, rel + ".py")) or
            os.path.isdir(os.path.join(ROOT, rel))):
        FAILS.append("hiddenimport has no source on disk: %s" % mod)
print("hiddenimports: %d (%d repo, %d third-party/stdlib)" % (
    len(mods), len(mods) - len(STDLIB) - len(THIRD_PARTY), len(STDLIB) + len(THIRD_PARTY)))

# 3. onedir wiring: EXE must exclude binaries and a COLLECT must consume them.
exe_block = re.search(r"exe = EXE\((.*?)\n\)", src, re.S)
if not exe_block:
    FAILS.append("no EXE(...) block found")
else:
    body = exe_block.group(1)
    if "exclude_binaries=True" not in body:
        FAILS.append("EXE is missing exclude_binaries=True (onedir requires it)")
    if re.search(r"^\s*a\.binaries,", body, re.M):
        FAILS.append("EXE still consumes a.binaries; that belongs in COLLECT")

if not re.search(r"coll = COLLECT\(", src):
    FAILS.append("no COLLECT(...) block; EXE alone produces no dist/ohub/ directory")
else:
    coll = re.search(r"coll = COLLECT\((.*?)\n\)", src, re.S).group(1)
    for required in ("a.binaries", "a.datas", "exe"):
        if required not in coll:
            FAILS.append("COLLECT is missing %s" % required)

# 4. onefile must be absent.
if re.search(r"onefile\s*=", src):
    FAILS.append("spec still passes onefile=; onedir must use EXE+COLLECT")

# 5. UPX must be gated on the signing env var.
if not re.search(r"upx=not IS_SIGNED_BUILD", src):
    FAILS.append("UPX is not gated behind OBTAINHUB_SIGNED_BUILD")

if FAILS:
    print("FAIL")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("PASS: spec inputs exist, hiddenimports resolve, onedir wiring is EXE+COLLECT")
