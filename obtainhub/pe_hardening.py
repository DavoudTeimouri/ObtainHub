"""PE hardening: set the Windows DllCharacteristics bits that control ASLR, DEP and CFG.

PyInstaller's spec file exposes no option for these bits. UPX is the only knob it
offers and it is an all-or-nothing packer, not a hardening switch, so it is not a
substitute. Without this the shipped ohub.exe runs with ASLR and DEP off no matter
what the spec comments claim.

Applied to the bootloader stub and every bundled .dll/.pyd:

  DYNAMIC_BASE     (0x0040)  ASLR
  HIGH_ENTROPY_VA  (0x0020)  64-bit ASLR entropy
  FORCE_INTEGRITY  (0x0080)  signature required to load
  NX_COMPAT        (0x0100)  DEP
  GUARD_CF         (0x4000)  Control Flow Guard
"""

import os
import struct

IMAGE_DLLCHARACTERISTICS_HIGH_ENTROPY_VA = 0x0020
IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE = 0x0040
IMAGE_DLLCHARACTERISTICS_FORCE_INTEGRITY = 0x0080
IMAGE_DLLCHARACTERISTICS_NX_COMPAT = 0x0100
IMAGE_DLLCHARACTERISTICS_GUARD_CF = 0x4000

HARDENING_MASK = (
    IMAGE_DLLCHARACTERISTICS_HIGH_ENTROPY_VA
    | IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE
    | IMAGE_DLLCHARACTERISTICS_FORCE_INTEGRITY
    | IMAGE_DLLCHARACTERISTICS_NX_COMPAT
    | IMAGE_DLLCHARACTERISTICS_GUARD_CF
)

E_LFANEW_OFFSET = 0x3C
DLL_CHARACTERISTICS_OFFSET = 0x5E
PE_EXTENSIONS = (".exe", ".dll", ".pyd")


def _pe_supported():
    """True when DllCharacteristics hardening applies. Overridable for tests."""
    return os.name == "nt"


def harden_file(path):
    """Set the hardening bits in one PE file. Returns True when modified.

    Only touches PE images on Windows; on other platforms the DllCharacteristics
    field does not exist and the function is a no-op.
    """
    if not _pe_supported() or not path.lower().endswith(PE_EXTENSIONS):
        return False
    with open(path, "r+b") as f:
        header = f.read(0x200)
        if len(header) < 0x100 or header[:2] != b"MZ":
            return False
        pe_offset = struct.unpack_from("<I", header, E_LFANEW_OFFSET)[0]
        if header[pe_offset : pe_offset + 4] != b"PE\0\0":
            return False
        field = pe_offset + DLL_CHARACTERISTICS_OFFSET
        f.seek(field)
        current = struct.unpack("<H", f.read(2))[0]
        if current & HARDENING_MASK == HARDENING_MASK:
            return False
        f.seek(field)
        f.write(struct.pack("<H", current | HARDENING_MASK))
    return True


def harden_tree(dist_dir):
    """Harden every PE under a build directory. Returns the number modified."""
    modified = 0
    for root, _dirs, files in os.walk(dist_dir):
        for name in files:
            if name.lower().endswith(PE_EXTENSIONS):
                try:
                    if harden_file(os.path.join(root, name)):
                        modified += 1
                except OSError:
                    continue
    return modified
