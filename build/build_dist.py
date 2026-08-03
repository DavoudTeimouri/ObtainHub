#!/usr/bin/env python3
"""
Build script for ObtainHub - creates Windows x64 executables and installers.
IMPORTANT: PyInstaller CANNOT cross-compile. This script MUST be run on Windows x64
to produce valid Windows binaries. On Linux/macOS it will only validate the setup.
Uses PyInstaller for standalone executable and Inno Setup for installer.
"""

import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path


ROOT = Path(__file__).parent.parent
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
INSTALLER_DIR = ROOT / "installer"
SPEC_FILE = ROOT / "ObtainHub.spec"

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


def clean_build():
    """Clean build artifacts."""
    print("Cleaning build directories...")
    for d in [BUILD_DIR, DIST_DIR]:
        if d.exists():
            shutil.rmtree(d)
    print("Clean done.")


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


def build_executable(onedir=False, onefile=True):
    """Build standalone executable with PyInstaller."""
    if not check_platform():
        print("Skipping executable build (wrong platform).")
        return None

    print("Building executable with PyInstaller...")

    mode = "--onedir" if onedir else "--onefile"
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        mode,
        "--console",
        "--name", "ohub",
        "--target-arch", "x86_64",
        "--icon", str(ROOT / "assets" / "icon.ico") if (ROOT / "assets" / "icon.ico").exists() else "NONE",
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

    # Verify executable
    exe_name = "ohub.exe" if onedir else "ohub.exe"
    exe_path = DIST_DIR / exe_name
    if onedir:
        exe_path = DIST_DIR / "ohub" / "ohub.exe"
    
    if exe_path.exists():
        print(f"Executable built: {exe_path}")
        return exe_path
    else:
        raise RuntimeError(f"Executable not found after build: {exe_path}")


def create_spec_file(onedir=False):
    """Create PyInstaller spec file for more control."""
    mode = 'ONEDIR' if onedir else 'ONEFILE'
    
    # Use as_posix() for cross-platform path handling in spec file
    main_py = (ROOT / "obtainhub" / "main.py").as_posix()
    root_posix = ROOT.as_posix()
    config_py = (ROOT / "obtainhub" / "core" / "config.py").as_posix()
    state_py = (ROOT / "obtainhub" / "core" / "state.py").as_posix()
    logger_py = (ROOT / "obtainhub" / "core" / "logger.py").as_posix()
    exceptions_py = (ROOT / "obtainhub" / "core" / "exceptions.py").as_posix()
    github_client_py = (ROOT / "obtainhub" / "core" / "github_client.py").as_posix()
    asset_matcher_py = (ROOT / "obtainhub" / "core" / "asset_matcher.py").as_posix()
    downloader_py = (ROOT / "obtainhub" / "core" / "downloader.py").as_posix()
    installer_py = (ROOT / "obtainhub" / "core" / "installer.py").as_posix()
    self_updater_py = (ROOT / "obtainhub" / "core" / "self_updater.py").as_posix()
    helpers_py = (ROOT / "obtainhub" / "utils" / "helpers.py").as_posix()
    icon_path = (ROOT / "assets" / "icon.ico").as_posix() if (ROOT / "assets" / "icon.ico").exists() else ""
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['{main_py}'],
    pathex=['{root_posix}'],
    binaries=[],
    datas=[
        ('{config_py}', 'obtainhub/core'),
        ('{state_py}', 'obtainhub/core'),
        ('{logger_py}', 'obtainhub/core'),
        ('{exceptions_py}', 'obtainhub/core'),
        ('{github_client_py}', 'obtainhub/core'),
        ('{asset_matcher_py}', 'obtainhub/core'),
        ('{downloader_py}', 'obtainhub/core'),
        ('{installer_py}', 'obtainhub/core'),
        ('{self_updater_py}', 'obtainhub/core'),
        ('{helpers_py}', 'obtainhub/utils'),
    ],
    hiddenimports=[
        'obtainhub.core.config',
        'obtainhub.core.state',
        'obtainhub.core.logger',
        'obtainhub.core.exceptions',
        'obtainhub.core.github_client',
        'obtainhub.core.asset_matcher',
        'obtainhub.core.downloader',
        'obtainhub.core.installer',
        'obtainhub.core.self_updater',
        'obtainhub.utils.helpers',
        'requests',
        'urllib3',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ohub',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='x86_64',
    codesign_identity=None,
    entitlements_file=None,
    icon='{icon_path}',
    onefile={str(not onedir).capitalize()},
)
'''

    with open(SPEC_FILE, 'w') as f:
        f.write(spec_content)
    print(f"Created spec file: {SPEC_FILE}")


def build_with_spec(onedir=False):
    """Build using spec file."""
    if not check_platform():
        print("Skipping spec build (wrong platform).")
        return None

    print("Building with spec file...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        str(SPEC_FILE),
    ]
    run_cmd(cmd)

    # Check both possible output locations
    exe_path_onedir = DIST_DIR / "ohub" / "ohub.exe"
    exe_path_onefile = DIST_DIR / "ohub.exe"
    
    if exe_path_onedir.exists():
        print(f"Executable built (onedir): {exe_path_onedir}")
        return exe_path_onedir
    elif exe_path_onefile.exists():
        print(f"Executable built (onefile): {exe_path_onefile}")
        return exe_path_onefile
    else:
        raise RuntimeError("Executable not found after build")


def create_inno_setup_script():
    """Create Inno Setup script for Windows installer."""
    INSTALLER_DIR.mkdir(exist_ok=True)

    iss_content = f'''; ObtainHub Inno Setup Script
; Compiles ObtainHub-Setup.exe for Windows x64

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
DefaultDirName={{autopf}}\\{{#AppName}}
DefaultGroupName={{#AppName}}
OutputDir={INSTALLER_DIR}
OutputBaseFilename=ObtainHub-Setup
SetupIconFile={ROOT / "assets" / "icon.ico" if (ROOT / "assets" / "icon.ico").exists() else ""}
Compression=lzma/ultra
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
PrivilegesRequired=admin
DisableProgramGroupPage=yes
UninstallDisplayIcon={{app}}\\{{#AppExeName}}

[Files]
Source: "{DIST_DIR}\\ohub.exe"; DestDir: "{{app}}"; Flags: ignoreversion

[Icons]
Name: "{{autoprograms}}\\{{#AppName}}"; Filename: "{{app}}\\{{#AppExeName}}"
Name: "{{autodesktop}}\\{{#AppName}}"; Filename: "{{app}}\\{{#AppExeName}}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"; Flags: unchecked

[Run]
Filename: "{{app}}\\{{#AppExeName}}"; Description: "{{cm:LaunchProgram,{{#AppName}}}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{{app}}"

[Registry]
Root: HKLM; Subkey: "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{{#AppName}}"; ValueType: string; ValueName: "DisplayVersion"; ValueData: "{{#AppVersion}}"
Root: HKLM; Subkey: "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{{#AppName}}"; ValueType: string; ValueName: "Publisher"; ValueData: "{{#AppPublisher}}"
Root: HKLM; Subkey: "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{{#AppName}}"; ValueType: string; ValueName: "URLInfoAbout"; ValueData: "{{#AppURL}}"
'''

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

    # Check if ISCC is available
    iscc_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        "ISCC.exe",  # In PATH
    ]

    iscc = None
    for path in iscc_paths:
        if shutil.which(path) or Path(path).exists():
            iscc = path
            break

    if not iscc:
        print("ERROR: Inno Setup (ISCC) not found.")
        print("Install Inno Setup 6 from https://jrsoftware.org/isinfo.php")
        print("Skipping installer build - no dummy file created.")
        return None

    cmd = [iscc, str(iss_path)]
    run_cmd(cmd, check=False)

    # Check output
    setup_exe = INSTALLER_DIR / "ObtainHub-Setup.exe"
    if setup_exe.exists():
        print(f"Installer built: {setup_exe}")
        return setup_exe
    else:
        print("ERROR: Installer not found after build")
        return None


def create_wix_msi():
    """Create WiX project for MSI installer."""
    wix_dir = ROOT / "installer" / "wix"
    wix_dir.mkdir(parents=True, exist_ok=True)

    wxs_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">
    <Product Id="*" Name="ObtainHub" Language="1033" Version="0.1.0" Manufacturer="Davoud Teimouri" UpgradeCode="PUT-GUID-HERE">
        <Package InstallerVersion="500" Compressed="yes" InstallScope="perMachine" Platform="x64" />
        <MajorUpgrade DowngradeErrorMessage="A newer version of ObtainHub is already installed." />
        <MediaTemplate EmbedCab="yes" />

        <Feature Id="ProductFeature" Title="ObtainHub" Level="1">
            <ComponentGroupRef Id="ProductComponents" />
        </Feature>
    </Product>

    <Fragment>
        <Directory Id="TARGETDIR" Name="SourceDir">
            <Directory Id="ProgramFiles64Folder">
                <Directory Id="INSTALLFOLDER" Name="ObtainHub" />
            </Directory>
        </Directory>
    </Fragment>

    <Fragment>
        <ComponentGroup Id="ProductComponents" Directory="INSTALLFOLDER">
            <Component Id="MainExecutable" Guid="PUT-GUID-HERE">
                <File Id="ohub.exe" Source="{DIST_DIR}/ohub.exe" KeyPath="yes" />
            </Component>
        </ComponentGroup>
    </Fragment>
</Wix>
'''

    wxs_path = wix_dir / "obtainhub.wxs"
    with open(wxs_path, 'w') as f:
        f.write(wxs_content)
    print(f"Created WiX project: {wxs_path}")
    print("Note: Requires WiX Toolset v4+ to compile MSI")
    return wxs_path


def build_msi(wxs_path):
    """Build MSI with WiX (if available)."""
    if not check_platform():
        print("Skipping MSI build (wrong platform).")
        return None

    print("Building MSI with WiX...")

    # Check for WiX
    if not shutil.which("wix") and not shutil.which("candle.exe"):
        print("ERROR: WiX Toolset not found.")
        print("Install WiX v4+ from https://wixtoolset.org/")
        print("Skipping MSI build - no dummy file created.")
        return None

    # WiX v4 uses 'wix build' command
    cmd = ["wix", "build", str(wxs_path), "-o", str(INSTALLER_DIR / "ObtainHub.msi")]
    result = run_cmd(cmd, check=False)

    msi_path = INSTALLER_DIR / "ObtainHub.msi"
    if msi_path.exists():
        print(f"MSI built: {msi_path}")
        return msi_path
    else:
        print("ERROR: MSI not found after build")
        return None


def create_github_workflow():
    """Create GitHub Actions workflow for automated builds."""
    workflow_dir = ROOT / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)

    workflow_content = '''name: Build Windows x64

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:
    inputs:
      prerelease:
        description: 'Create prerelease'
        type: boolean
        default: false

permissions:
  contents: write

jobs:
  build:
    runs-on: windows-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          architecture: 'x64'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pyinstaller

      - name: Build executable (onefile)
        run: |
          python build/build_dist.py --onefile

      - name: Build executable (onedir)
        run: |
          python build/build_dist.py --onedir

      - name: Install Inno Setup
        run: |
          choco install innosetup --version=6.2.2

      - name: Build installer
        run: |
          python build/build_dist.py --installer

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: ObtainHub-Windows-x64
          path: |
            dist/ohub.exe
            dist/ohub/
            installer/ObtainHub-Setup.exe

      - name: Create Release
        uses: softprops/action-gh-release@v1
        if: startsWith(github.ref, 'refs/tags/')
        with:
          files: |
            dist/ohub.exe
            installer/ObtainHub-Setup.exe
          prerelease: ${{ github.event.inputs.prerelease || false }}
          draft: false
          generate_release_notes: true
'''

    workflow_path = workflow_dir / "build.yml"
    with open(workflow_path, 'w') as f:
        f.write(workflow_content)
    print(f"Created GitHub Actions workflow: {workflow_path}")
    return workflow_path


def verify_executable(exe_path):
    """Verify the executable runs correctly."""
    if not exe_path or not exe_path.exists():
        return False
    
    if not check_platform():
        print("Cannot verify executable on non-Windows platform.")
        return False

    print(f"Verifying executable: {exe_path}")
    result = run_cmd([str(exe_path), "--help"], check=False)
    if result.returncode == 0:
        print("✓ Executable verified successfully!")
        return True
    else:
        print("✗ Executable verification failed!")
        print(f"Return code: {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        return False


def main():
    """Main build function."""
    import argparse

    parser = argparse.ArgumentParser(description="Build ObtainHub Windows x64 binaries")
    parser.add_argument("--clean", action="store_true", help="Clean build directories")
    parser.add_argument("--onefile", action="store_true", help="Build onefile executable (default)")
    parser.add_argument("--onedir", action="store_true", help="Build onedir executable")
    parser.add_argument("--installer", action="store_true", help="Build Inno Setup installer (requires exe)")
    parser.add_argument("--msi", action="store_true", help="Build MSI with WiX (requires WiX toolset)")
    parser.add_argument("--workflow", action="store_true", help="Generate GitHub Actions workflow")
    parser.add_argument("--verify", action="store_true", help="Verify built executable")
    parser.add_argument("--all", action="store_true", help="Build everything (onefile + installer)")

    args = parser.parse_args()

    if args.clean:
        clean_build()
        return 0

    if args.workflow:
        create_github_workflow()
        return 0

    # Default behavior
    if not (args.onefile or args.onedir or args.installer or args.msi or args.verify):
        args.onefile = True

    try:
        exe_path = None
        
        if args.onefile or args.all:
            create_spec_file(onedir=False)
            exe_path = build_with_spec(onedir=False)
        
        if args.onedir:
            create_spec_file(onedir=True)
            exe_path = build_with_spec(onedir=True)
        
        if args.installer or args.all:
            if not exe_path:
                exe_path = DIST_DIR / "ohub.exe"
            if not exe_path.exists():
                print("ERROR: Executable not found. Build executable first.")
                return 1
            iss_path = create_inno_setup_script()
            build_inno_setup(iss_path)

        if args.msi:
            wxs_path = create_wix_msi()
            build_msi(wxs_path)

        if args.workflow or args.all:
            create_github_workflow()

        if args.verify and exe_path:
            verify_executable(exe_path)

        print("\nBuild complete!")
        if (DIST_DIR / "ohub.exe").exists():
            print(f"OneFile exe:  {DIST_DIR / 'ohub.exe'}")
        if (DIST_DIR / "ohub" / "ohub.exe").exists():
            print(f"OneDir exe:   {DIST_DIR / 'ohub' / 'ohub.exe'}")
        if (INSTALLER_DIR / "ObtainHub-Setup.exe").exists():
            print(f"Installer:    {INSTALLER_DIR / 'ObtainHub-Setup.exe'}")
        if (INSTALLER_DIR / "ObtainHub.msi").exists():
            print(f"MSI:          {INSTALLER_DIR / 'ObtainHub.msi'}")
        print(f"Workflow:     {ROOT / '.github' / 'workflows' / 'build.yml'}")

        return 0

    except Exception as e:
        print(f"Build failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())