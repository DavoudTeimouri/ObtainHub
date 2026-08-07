#!/usr/bin/env python3
"""Build Windows distribution artifacts."""

import os
import shutil
import subprocess
import sys

def run(cmd, cwd=None, shell=False):
    """Run command and check result."""
    print(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=shell)
    if result.returncode != 0:
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        sys.exit(result.returncode)
    return result

def main():
    # Build with PyInstaller
    run([
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "ohub",
        "--clean",
        "obtainhub/main.py"
    ])
    
    # Copy to dist root
    dist_exe = "dist/ohub.exe"
    if os.path.exists(dist_exe):
        print(f"Built: {dist_exe}")
    else:
        print("ERROR: ohub.exe not found in dist/")
        sys.exit(1)
    
    # Build WiX MSI - locate tools via PATH
    print("Building WiX MSI...")
    candle = shutil.which("candle")
    light = shutil.which("light")
    if not candle or not light:
        print("ERROR: WiX tools (candle/light) not found in PATH")
        sys.exit(1)
    run([candle, "-out", "dist/ObtainHub.wixobj", "installer/setup.wxs"])
    run([light, "-out", "dist/ObtainHub.msi", "dist/ObtainHub.wixobj"])
    
    # Build Inno Setup EXE installer
    print("Building Inno Setup EXE...")
    iscc = shutil.which("iscc")
    if not iscc:
        print("ERROR: Inno Setup compiler (iscc) not found in PATH")
        sys.exit(1)
    run([iscc, "installer/setup.iss"])
    
    print("\nBuild complete!")
    print(f"  {dist_exe}")
    print(f"  dist/ObtainHub.msi")
    print(f"  dist/ObtainHub-Setup.exe")

if __name__ == "__main__":
    main()