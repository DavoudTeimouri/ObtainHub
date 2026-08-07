#!/usr/bin/env python3
"""Build Windows distribution artifacts."""

import os
import shutil
import subprocess
import sys

def run(cmd, cwd=None):
    """Run command and check result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
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
    
    # Build WiX MSI
    print("Building WiX MSI...")
    run([
        "candle",
        "-out", "dist/ObtainHub.wixobj",
        "installer/setup.wxs"
    ])
    run([
        "light",
        "-out", "dist/ObtainHub.msi",
        "dist/ObtainHub.wixobj"
    ])
    
    # Build Inno Setup EXE installer
    print("Building Inno Setup EXE...")
    run([
        "iscc",
        "installer/setup.iss"
    ])
    
    print("\nBuild complete!")
    print(f"  {dist_exe}")
    print(f"  dist/ObtainHub.msi")
    print(f"  dist/ObtainHub-Setup.exe")

if __name__ == "__main__":
    main()