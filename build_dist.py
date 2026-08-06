#!/usr/bin/env python3
"""
Build script for ObtainHub - creates Windows x64 executables and installers.
Run on Windows x64 (or GitHub Actions windows-latest).
"""

import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path

ROOT = Path(__file__).parent
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
INSTALLER_DIR = ROOT / "installer"

IS_WINDOWS = platform.system() == "Windows"
IS_64BIT = platform.machine().endswith("64") or platform.machine() in ("x86_64", "AMD64")


def run_cmd(cmd, cwd=None, check=True):
    """Run command and return result."""
    print(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(cmd, cwd=cwd or ROOT, shell=isinstance(cmd, str), capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}")
    return result


def check_platform():
    """Check if we're on the correct platform for Windows builds."""
    if not IS_WINDOWS:
        print("=" * 60)
        print("WARNING: Not running on Windows!")
        print(f"Current platform: {platform.system()} {platform.machine()}")
        print("PyInstaller CANNOT cross-compile to Windows from Linux/macOS.")
        print("Windows binaries MUST be built on Windows x64 (or via GitHub Actions).")
        print("=" * 60)
        return False
    if not IS_64BIT:
        print("WARNING: Not running on 64-bit platform!")
        print(f"Architecture: {platform.machine()}")
        print("Windows x64 builds require 64-bit Python.")
        return False
    print("Platform check passed: Windows x64")
    return True


def build_executable(onefile=True):
    """Build standalone executable with PyInstaller."""
    if not check_platform():
        print("Skipping executable build (wrong platform).")
        return None

    print("Building executable with PyInstaller...")

    mode = "--onefile" if onefile else "--onedir"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        mode,
        "--console",
        "--name", "ohub",
        "--target-arch", "x86_64",
        "--add-data", f"{ROOT / 'obtainhub' / 'core' / 'config.py'};obtainhub/core",
        "--add-data", f"{ROOT / 'obtainhub' / 'core' / 'state.py'};obtainhub/core",
        "--add-data", f"{ROOT / 'obtainhub' / 'core' / 'logger.py'};obtainhub/core",
        "--add-data", f"{ROOT / 'obtainhub' / 'core' / 'exceptions.py'};obtainhub/core",
        "--add-data", f"{ROOT / 'obtainhub' / 'core' / 'github_client.py'};obtainhub/core",
        "--add-data", f"{ROOT / 'obtainhub' / 'core' / 'asset_matcher.py'};obtainhub/core",
        "--add-data", f"{ROOT / 'obtainhub' / 'core' / 'downloader.py'};obtainhub/core",
        "--add-data", f"{ROOT / 'obtainhub' / 'core' / 'installer.py'};obtainhub/core",
        "--add-data", f"{ROOT / 'obtainhub' / 'core' / 'self_updater.py'};obtainhub/core",
        "--add-data", f"{ROOT / 'obtainhub' / 'utils' / 'helpers.py'};obtainhub/utils",
        "--hidden-import", "obtainhub.core.config",
        "--hidden-import", "obtainhub.core.state",
        "--hidden-import", "obtainhub.core.logger",
        "--hidden-import", "obtainhub.core.exceptions",
        "--hidden-import", "obtainhub.core.github_client",
        "--hidden-import", "obtainhub.core.asset_matcher",
        "--hidden-import", "obtainhub.core.downloader",
        "--hidden-import", "obtainhub.core.installer",
        "--hidden-import", "obtainhub.core.self_updater",
        "--hidden-import", "obtainhub.utils.helpers",
        "--hidden-import", "requests",
        "--hidden-import", "urllib3",
        str(ROOT / "obtainhub" / "main.py"),
    ]

    run_cmd(cmd)

    exe_path = DIST_DIR / "ohub.exe"
    if onefile:
        exe_path = DIST_DIR / "ohub.exe"
    else:
        exe_path = DIST_DIR / "ohub" / "ohub.exe"

    if exe_path.exists():
        print(f"Executable built: {exe_path}")
        return exe_path
    else:
        raise RuntimeError(f"Executable not found after build: {exe_path}")


def create_inno_setup_script():
    """Create Inno Setup script for Windows installer."""
    INSTALLER_DIR.mkdir(exist_ok=True)

    icon_path = ""
    icon_file = ROOT / "assets" / "icon.ico"
    if icon_file.exists():
        icon_path = icon_file.as_posix()

    iss_content = """ ; ObtainHub Inno Setup Script
 ; Compiles ObtainHub-Setup.exe for Windows x64
 ; Pure CLI tool - no desktop shortcuts, no launch prompts

 #define AppName "ObtainHub"
 #define AppVersion "0.1.0"
 #define AppPublisher "Davoud Teimouri"
 #define AppURL "https://github.com/DavoudTeimouri/ObtainHub"
 #define AppExeName "ohub.exe"

 [Setup]
 AppName={{#AppName}}
 AppVersion={{#AppVersion}}
 AppPublisher={{#AppPublisher}}
 AppPublisherURL={{#AppURL}}
 AppSupportURL={{#AppURL}}
 AppUpdatesURL={{#AppURL}}
 DefaultDirName={{autopf}}\\\\{#AppName}
 DefaultGroupName={{#AppName}}
 OutputDir={installer_dir}
 OutputBaseFilename=ObtainHub-Setup
 SetupIconFile={icon_path}
 Compression=lzma/ultra
 SolidCompression=yes
 WizardStyle=modern
 ArchitecturesInstallIn64BitMode=x64
 ArchitecturesAllowed=x64
 PrivilegesRequired=admin
 DisableProgramGroupPage=yes
 UninstallDisplayIcon={{app}}\\\\{#AppExeName}

 [Files]
 Source: "{dist_dir}\\\\ohub.exe"; DestDir: "{{app}}"; Flags: ignoreversion

 ; No Icons section - pure CLI tool, no shortcuts
 ; No Tasks section - no desktop icon option
 ; No Run section - no "Launch Application" checkbox

 [UninstallDelete]
 Type: filesandordirs; Name: "{{app}}"

 [Registry]
 Root: HKLM; Subkey: "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Uninstall\\\\{{#AppName}}"; ValueType: string; ValueName: "DisplayVersion"; ValueData: "{{#AppVersion}}"
 Root: HKLM; Subkey: "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Uninstall\\\\{{#AppName}}"; ValueType: string; ValueName: "Publisher"; ValueData: "{{#AppPublisher}}"
 Root: HKLM; Subkey: "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Uninstall\\\\{{#AppName}}"; ValueType: string; ValueName: "URLInfoAbout"; ValueData: "{{#AppURL}}"
 """.format(
        installer_dir=INSTALLER_DIR.as_posix(),
        dist_dir=DIST_DIR.as_posix(),
        icon_path=icon_path
    )

    iss_path = INSTALLER_DIR / "setup.iss"
    with open(iss_path, 'w') as f:
        f.write(iss_content)
    print(f"Created Inno Setup script: {iss_path}")
    return iss_path


def build_inno_setup(iss_path):
    """Build installer with Inno Setup (ISCC)."""
    if not check_platform():
        print("Skipping Inno Setup build (wrong platform).")
        return None

    print("Building installer with Inno Setup...")

    iscc_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        "ISCC.exe",
    ]

    iscc = None
    for path in iscc_paths:
        if shutil.which(path) or Path(path).exists():
            iscc = path
            break

    if not iscc:
        print("ERROR: Inno Setup (ISCC) not found.")
        print("Install Inno Setup 6 from https://jrsoftware.org/isinfo.php")
        print("Skipping installer build.")
        return None

    cmd = [iscc, str(iss_path)]
    run_cmd(cmd, check=False)

    setup_exe = INSTALLER_DIR / "ObtainHub-Setup.exe"
    if setup_exe.exists():
        print(f"Installer built: {setup_exe}")
        return setup_exe
    else:
        print("ERROR: Installer not found after build")
        return None


def create_msi_with_msilib():
    """Create MSI installer using Python's msilib (stdlib). Windows only."""
    if not IS_WINDOWS:
        raise RuntimeError(
            "MSI build with msilib requires Windows platform. "
            "Run on Windows x64 or use GitHub Actions (windows-latest)."
        )

    print("Building MSI with Python msilib...")

    import warnings
    import msilib
    import uuid
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="msilib")

    msi_path = INSTALLER_DIR / "ObtainHub.msi"
    INSTALLER_DIR.mkdir(exist_ok=True)

    exe_path = DIST_DIR / "ohub.exe"
    if not exe_path.exists():
        print(f"ERROR: Executable not found: {exe_path}")
        return None

    try:
        db = msilib.init_database(
            str(msi_path),
            "ObtainHub",
            "ObtainHub",
            "0.1.0",
            "Davoud Teimouri",
            "{" + str(uuid.uuid4()).upper() + "}"
        )

        db.Properties.AddProperty("ProductName", "ObtainHub")
        db.Properties.AddProperty("ProductVersion", "0.1.0")
        db.Properties.AddProperty("Manufacturer", "Davoud Teimouri")
        db.Properties.AddProperty("ProductCode", "{" + str(uuid.uuid4()).upper() + "}")
        db.Properties.AddProperty("UpgradeCode", "{" + str(uuid.uuid4()).upper() + "}")

        db.Directories.AddDirectory("TARGETDIR", "SourceDir", None)
        db.Directories.AddDirectory("TARGETDIR", "ProgramFiles64Folder", None)
        db.Directories.AddDirectory("ProgramFiles64Folder", "INSTALLFOLDER", "ObtainHub")

        comp = db.Components.AddComponent("MainExecutable", "INSTALLFOLDER")
        db.Components.AddFile(
            comp,
            "ohub.exe",
            str(exe_path),
            "ohub.exe",
            None,
            0
        )

        feature = db.Features.AddFeature("ProductFeature", "ObtainHub", 1, "ObtainHub")
        feature.Components.AddComponent("MainExecutable")

        db.Shortcuts.AddShortcut(
            "ProgramMenuShortcut",
            "ProgramMenuFolder",
            "ObtainHub",
            "INSTALLFOLDER",
            "ohub.exe",
            None, None, None, 0, None, "ObtainHub"
        )

        db.Commit()
        db.Close()

        print(f"MSI built: {msi_path}")
        return msi_path

    except Exception as e:
        print(f"ERROR building MSI: {e}")
        if msi_path.exists():
            msi_path.unlink()
        return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build ObtainHub Windows x64 binaries")
    parser.add_argument("--clean", action="store_true", help="Clean build directories")
    parser.add_argument("--onefile", action="store_true", help="Build onefile executable (default)")
    parser.add_argument("--onedir", action="store_true", help="Build onedir executable")
    parser.add_argument("--installer", action="store_true", help="Build Inno Setup installer (requires exe)")
    parser.add_argument("--msi", action="store_true", help="Build MSI with Python msilib (stdlib)")

    args = parser.parse_args()

    if args.clean:
        for d in [BUILD_DIR, DIST_DIR]:
            if d.exists():
                shutil.rmtree(d)
        print("Clean done.")
        return 0

    if not (args.onefile or args.onedir or args.installer or args.msi):
        args.onefile = True

    try:
        exe_path = None

        if args.onefile or args.onedir:
            exe_path = build_executable(onefile=args.onefile)

        if args.installer:
            if not exe_path:
                exe_path = DIST_DIR / "ohub.exe"
            if not exe_path.exists():
                print("ERROR: Executable not found. Build executable first.")
                return 1
            iss_path = create_inno_setup_script()
            build_inno_setup(iss_path)

        if args.msi:
            msi_result = create_msi_with_msilib()
            if not msi_result:
                print("ERROR: MSI build failed", file=sys.stderr)
                return 1

        print("\nBuild complete!")
        if (DIST_DIR / "ohub.exe").exists():
            print(f"OneFile exe:  {DIST_DIR / 'ohub.exe'}")
        if (DIST_DIR / "ohub" / "ohub.exe").exists():
            print(f"OneDir exe:   {DIST_DIR / 'ohub' / 'ohub.exe'}")
        if (INSTALLER_DIR / "ObtainHub-Setup.exe").exists():
            print(f"Installer:    {INSTALLER_DIR / 'ObtainHub-Setup.exe'}")
        if (INSTALLER_DIR / "ObtainHub.msi").exists():
            print(f"MSI:          {INSTALLER_DIR / 'ObtainHub.msi'}")

        return 0

    except Exception as e:
        print(f"Build failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())