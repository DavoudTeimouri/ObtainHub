import os
import struct
import tempfile

import obtainhub.pe_hardening as pe
from obtainhub.pe_hardening import (
    HARDENING_MASK,
    DLL_CHARACTERISTICS_OFFSET,
    E_LFANEW_OFFSET,
    harden_file,
    harden_tree,
)

# The hardening is a Windows-only PE edit, so force the platform gate on to make
# the check runnable (and meaningful) on any host.
pe._pe_supported = lambda: True

FAILS = []


def make_pe(path, characteristics=0x0000):
    """Write a minimal PE-shaped file with the given DllCharacteristics."""
    data = bytearray(b"\0" * 0x200)
    data[0:2] = b"MZ"
    pe = 0x80
    struct.pack_into("<I", data, E_LFANEW_OFFSET, pe)
    data[pe : pe + 4] = b"PE\0\0"
    struct.pack_into("<H", data, pe + DLL_CHARACTERISTICS_OFFSET, characteristics)
    with open(path, "wb") as f:
        f.write(data)
    return path


def read_characteristics(path):
    with open(path, "rb") as f:
        header = f.read(0x200)
    pe = struct.unpack_from("<I", header, E_LFANEW_OFFSET)[0]
    return struct.unpack_from("<H", header, pe + DLL_CHARACTERISTICS_OFFSET)[0]


tmp = tempfile.mkdtemp()

# 1. Hardening bit check: all five bits get set on a PE32+ image.
p = make_pe(os.path.join(tmp, "a.exe"), 0x0000)
if not harden_file(p):
    FAILS.append("harden_file reported no change on an unhardened PE")
got = read_characteristics(p)
if got & HARDENING_MASK != HARDENING_MASK:
    FAILS.append("missing bits after harden: 0x%04X, want mask 0x%04X" % (got, HARDENING_MASK))
# FORCE_INTEGRITY (0x0080) is not a hardening flag: it makes Windows require a
# valid Authenticode signature before loading the image. CI builds are unsigned
# (sign.ps1 exits early with no secrets), so setting it makes ohub.exe refuse to
# start with "Windows cannot verify the digital signature for this file" - which
# is how the v2.0.0 smoke test failed.
FORCE_INTEGRITY = 0x0080
if HARDENING_MASK & FORCE_INTEGRITY:
    FAILS.append("FORCE_INTEGRITY (0x0080) is in HARDENING_MASK; unsigned builds cannot start")
if got & FORCE_INTEGRITY:
    FAILS.append("harden_file set FORCE_INTEGRITY on the output; Windows will refuse to load it")
print("after harden:      0x%04X" % got)

# 2. Idempotence: a second pass is a no-op, not a double-set.
if harden_file(p):
    FAILS.append("harden_file was not idempotent")
again = read_characteristics(p)
if again != got:
    FAILS.append("characteristics changed on the second pass")

# 3. Existing bits are preserved, not clobbered.
p2 = make_pe(os.path.join(tmp, "b.dll"), 0x0022)  # other flags already set
harden_file(p2)
if read_characteristics(p2) & 0x0022 != 0x0022:
    FAILS.append("pre-existing DllCharacteristics bits were clobbered")

# 4. Non-PE files are left alone.
junk = os.path.join(tmp, "notes.txt")
open(junk, "w").write("not a PE")
before = open(junk, "rb").read()
if harden_file(junk):
    FAILS.append("harden_file modified a non-PE file")
if open(junk, "rb").read() != before:
    FAILS.append("non-PE file contents changed")

# 5. A truncated MZ header is rejected rather than crashing.
short = os.path.join(tmp, "short.exe")
open(short, "wb").write(b"MZ")
if harden_file(short):
    FAILS.append("harden_file accepted a truncated header")

# 6. harden_tree walks the directory and counts what it changed.
tree = os.path.join(tmp, "dist")
os.makedirs(os.path.join(tree, "base_library.zip"))
for name in ("bootloader.dll", "pydsub.dll", "readme.txt"):
    make_pe(os.path.join(tree, name), 0x0000)
changed = harden_tree(tree)
if changed != 2:
    FAILS.append("harden_tree changed %d files, expected 2 PE files" % changed)
# Second walk must find nothing left to do.
if harden_tree(tree) != 0:
    FAILS.append("harden_tree was not idempotent")

# 7. With the platform gate off the function is a no-op, not a crash.
pe._pe_supported = lambda: False
if harden_file(make_pe(os.path.join(tmp, "c.exe"))) or harden_tree(tree):
    FAILS.append("hardening ran with the platform gate disabled")
pe._pe_supported = lambda: True

if FAILS:
    print("FAIL")
    for f in FAILS:
        print("  -", f)
    raise SystemExit(1)
print("PASS: PE hardening sets ASLR/DEP/CFG, is idempotent, preserves existing bits, skips non-PE")
