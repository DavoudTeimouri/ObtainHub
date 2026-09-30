#!/usr/bin/env python3
"""Build Windows distribution artifacts.

Usage:
    python build_dist.py                 # PyInstaller -> MSI -> EXE (full chain)
    python build_dist.py --exe           # PyInstaller only
    python build_dist.py --installer     # WiX MSI + Inno Setup EXE only
    python build_dist.py --msi           # WiX MSI only
"""

import os
import shutil
import subprocess
import sys

DIST_EXE = os.path.join("dist", "ohub", "ohub.exe")


def run(cmd, cwd=None, shell=False):
    """Run command and check result."""
    print(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=shell)
    if result.returncode != 0:
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        sys.exit(result.returncode)
    return result


def build_exe():
    """Build the onedir PyInstaller distribution and apply PE hardening."""
    run([sys.executable, "-m", "PyInstaller", "--clean", "ObtainHub.spec"])

    if not os.path.exists(DIST_EXE):
        print(f"ERROR: {DIST_EXE} not found")
        sys.exit(1)

    # ASLR/DEP/CFG are PE header bits PyInstaller does not expose. Set them here,
    # after the link, so the shipped binary actually has them.
    from obtainhub.pe_hardening import harden_tree

    modified = harden_tree(os.path.join("dist", "ohub"))
    print(f"PE hardening: {modified} file(s) updated in dist/ohub")
    print(f"Built: {DIST_EXE}")


def build_msi():
    candle = shutil.which("candle")
    light = shutil.which("light")
    if not candle or not light:
        print("ERROR: WiX tools (candle/light) not found in PATH")
        sys.exit(1)
    run([candle, "-out", "dist/ObtainHub.wixobj", "installer/setup.wxs"])
    run([light, "-out", "dist/ObtainHub.msi", "dist/ObtainHub.wixobj"])
    print("Built: dist/ObtainHub.msi")


def build_setup_exe():
    iscc = shutil.which("iscc")
    if not iscc:
        print("ERROR: Inno Setup compiler (iscc) not found in PATH")
        sys.exit(1)
    run([iscc, "installer/setup.iss"])
    # Inno writes to installer/Output/ObtainHub-Setup.exe; the workflow stages it.
    print("Built: installer/Output/ObtainHub-Setup.exe")


def main():
    args = set(sys.argv[1:])
    unknown = args - {"--exe", "--installer", "--msi"}
    if unknown:
        print(f"ERROR: unknown argument(s): {' '.join(sorted(unknown))}")
        print(__doc__)
        sys.exit(2)

    only_exe = "--exe" in args
    only_installer = "--installer" in args
    only_msi = "--msi" in args

    if not args or only_exe:
        build_exe()
    if only_msi or only_installer:
        build_msi()
    if not only_msi and not only_exe:
        build_setup_exe()

    print("\nBuild complete:")
    for path in (DIST_EXE, "dist/ObtainHub.msi", "installer/Output/ObtainHub-Setup.exe"):
        if os.path.exists(path):
            print(f"  {path}")


if __name__ == "__main__":
    main()
