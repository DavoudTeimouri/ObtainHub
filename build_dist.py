import os
import shutil
import subprocess
import sys

def build():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(root_dir, "dist")

    os.makedirs(dist_dir, exist_ok=True)
    print("=== Step 1: Building ohub.exe via PyInstaller ===")
    cmd_pyinstaller = [
        sys.executable, "-m", "PyInstaller",
        "--clean", "--noconfirm", "--onefile",
        "--name", "ohub",
        os.path.join(root_dir, "obtainhub", "main.py")
    ]
    res = subprocess.run(cmd_pyinstaller, cwd=root_dir)
    if res.returncode != 0:
        print("PyInstaller build failed!")
        sys.exit(1)

    print("=== Step 2: Checking Inno Setup for ObtainHub-Setup.exe ===")
    iscc = shutil.which("iscc") or r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    iss_file = os.path.join(root_dir, "installer", "setup.iss")
    if os.path.exists(iscc) and os.path.exists(iss_file):
        subprocess.run([iscc, iss_file], cwd=root_dir)
    else:
        print("ISCC not found or setup.iss missing. Skipping EXE installer compilation.")

    print("=== Step 3: Checking WiX Toolset for ObtainHub.msi ===")
    wix_file = os.path.join(root_dir, "installer", "setup.wxs")
    candle = shutil.which("candle")
    light = shutil.which("light")

    if candle and light and os.path.exists(wix_file):
        subprocess.run([candle, "-out", "dist/setup.wixobj", wix_file], cwd=root_dir)
        subprocess.run([light, "-out", "dist/ObtainHub.msi", "dist/setup.wixobj"], cwd=root_dir)
    else:
        print("WiX toolset (candle/light) not found or setup.wxs missing.")

    print("=== Build Process Complete ===")
    if os.path.exists(os.path.join(dist_dir, "ohub.exe")):
        print(f"Generated assets in: {dist_dir}")
        for f in os.listdir(dist_dir):
            print(f" - {f}")

if __name__ == "__main__":
    build()