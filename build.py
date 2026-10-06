#!/usr/bin/env python3
"""Build a standalone Mind Map Viewer for the current OS (Windows or Linux).

    python build.py              # folder build (fast start-up) + release archive
    python build.py --onefile    # single self-extracting executable
    python build.py --clean      # wipe build/ dist/ release/ first

Steps: create/reuse a build venv -> install PySide6 + PyInstaller -> run unit tests ->
PyInstaller -> run the built app's --selftest -> package into release/:

  Windows: MindMapViewer-<ver>-windows-x64.zip   (+ Setup .exe if Inno Setup is installed)
  Linux:   MindMapViewer-<ver>-linux-x86_64.tar.gz (+ mindmap-viewer_<ver>_amd64.deb if dpkg-deb exists)

PyInstaller does not cross-compile: build on Windows for Windows and on Ubuntu for Linux
(or use the GitHub Actions workflow in .github/workflows/build.yml to get both).
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import textwrap
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
APP = "MindMapViewer"
PKG = "mindmap-viewer"
VENV = os.path.join(ROOT, ".venv-build")
IS_WIN = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")


def log(msg):
    print(f"\n=== {msg}", flush=True)


def run(cmd, **kw):
    print("  $ " + " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd), flush=True)
    subprocess.check_call([str(c) for c in cmd], **kw)


def version() -> str:
    src = open(os.path.join(ROOT, "mindmap", "__init__.py"), encoding="utf-8").read()
    return re.search(r'__version__\s*=\s*"([^"]+)"', src).group(1)


def arch() -> str:
    m = platform.machine().lower()
    return {"amd64": "x64", "x86_64": "x86_64" if IS_LINUX else "x64", "aarch64": "arm64",
            "arm64": "arm64"}.get(m, m)


# ----------------------------------------------------------------------------
# venv bootstrap
# ----------------------------------------------------------------------------
def venv_python() -> str:
    return os.path.join(VENV, "Scripts", "python.exe") if IS_WIN else os.path.join(VENV, "bin", "python")


def ensure_venv():
    """Re-run this script inside .venv-build so the system Python stays clean."""
    if os.path.abspath(sys.prefix) == os.path.abspath(VENV):
        return
    if not os.path.exists(venv_python()):
        log("Creating build virtual environment (.venv-build)")
        try:
            run([sys.executable, "-m", "venv", VENV])
        except subprocess.CalledProcessError:
            sys.exit("Could not create a venv. On Ubuntu run:  sudo apt install python3-venv")
    sys.exit(subprocess.call([venv_python(), os.path.abspath(__file__)] + sys.argv[1:]))


# ----------------------------------------------------------------------------
# Steps
# ----------------------------------------------------------------------------
def install_deps():
    log("Installing build dependencies")
    run([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "-q"])
    run([sys.executable, "-m", "pip", "install", "-q", "-r", os.path.join(ROOT, "requirements.txt"),
         "pyinstaller>=6.0"])


def run_tests():
    log("Running unit tests")
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT)


def write_win_version_file(ver: str) -> str:
    nums = (ver.split(".") + ["0", "0", "0", "0"])[:4]
    nums = [int(re.sub(r"\D", "", n) or 0) for n in nums]
    path = os.path.join(ROOT, "build", "version_info.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    t = tuple(nums)
    with open(path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(f"""\
            VSVersionInfo(
              ffi=FixedFileInfo(filevers={t}, prodvers={t}, mask=0x3f, flags=0x0, OS=0x40004,
                                fileType=0x1, subtype=0x0, date=(0, 0)),
              kids=[
                StringFileInfo([StringTable('040904B0', [
                  StringStruct('CompanyName', 'Mind Map Viewer'),
                  StringStruct('FileDescription', 'Mind Map Viewer'),
                  StringStruct('FileVersion', '{ver}'),
                  StringStruct('InternalName', '{APP}'),
                  StringStruct('OriginalFilename', '{APP}.exe'),
                  StringStruct('ProductName', 'Mind Map Viewer'),
                  StringStruct('ProductVersion', '{ver}')])]),
                VarFileInfo([VarStruct('Translation', [1033, 1200])])
              ]
            )
            """))
    return path


def pyinstaller(ver: str, onefile: bool):
    log("Building with PyInstaller" + (" (one file)" if onefile else ""))
    sep = os.pathsep
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
           "--name", APP,
           "--add-data", f"samples{sep}samples",
           "--add-data", f"assets{sep}assets",
           "--exclude-module", "tkinter",
           "--onefile" if onefile else "--onedir"]
    if IS_WIN:
        cmd += ["--icon", os.path.join("assets", "icon.ico"),
                "--version-file", write_win_version_file(ver)]
    else:
        pass  # Linux uses the .desktop icon; PyInstaller ignores --icon here
    cmd.append("app.py")
    run(cmd, cwd=ROOT)


def built_exe(onefile: bool) -> str:
    name = APP + (".exe" if IS_WIN else "")
    return os.path.join(ROOT, "dist", name) if onefile else os.path.join(ROOT, "dist", APP, name)


def smoke_test(exe: str):
    log("Smoke-testing the built app (--selftest, headless)")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    try:
        rc = subprocess.call([exe, "--selftest"], env=env, timeout=180)
    except subprocess.TimeoutExpired:
        rc = -1
    if rc != 0:
        sys.exit(f"Self-test of the built executable failed (exit code {rc}).")
    print("  self-test passed")


# ----------------------------------------------------------------------------
# Packaging
# ----------------------------------------------------------------------------
def package_windows(ver: str, onefile: bool) -> list:
    out = []
    rel = os.path.join(ROOT, "release")
    zpath = os.path.join(rel, f"{APP}-{ver}-windows-{arch()}{'-onefile' if onefile else ''}.zip")
    log(f"Creating {os.path.basename(zpath)}")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        if onefile:
            z.write(built_exe(True), f"{APP}/{APP}.exe")
            for f in os.listdir(os.path.join(ROOT, "samples")):
                z.write(os.path.join(ROOT, "samples", f), f"{APP}/samples/{f}")
        else:
            base = os.path.join(ROOT, "dist", APP)
            for d, _, files in os.walk(base):
                for f in files:
                    full = os.path.join(d, f)
                    z.write(full, os.path.join(APP, os.path.relpath(full, base)))
        z.write(os.path.join(ROOT, "README.md"), f"{APP}/README.md")
    out.append(zpath)

    iscc = shutil.which("iscc") or next((p for p in (
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", r"C:\Program Files\Inno Setup 6\ISCC.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe")) if os.path.exists(p)), None)
    if iscc and not onefile:
        log("Building Windows installer with Inno Setup")
        iss = os.path.join(ROOT, "build", "installer.iss")
        with open(iss, "w", encoding="utf-8") as f:
            f.write(INNO_TEMPLATE.format(ver=ver, app=APP, root=ROOT, rel=rel))
        run([iscc, "/Q", iss])
        out.append(os.path.join(rel, f"{APP}-{ver}-Setup.exe"))
    elif not onefile:
        print("  (Inno Setup not found - skipping Setup.exe. Install it from jrsoftware.org "
              "or `winget install JRSoftware.InnoSetup` to also get an installer.)")
    return out


INNO_TEMPLATE = r'''
[Setup]
AppId={{{{6B0E8E3C-5A5F-4C55-9C0B-4D1F0A7E2B11}}
AppName=Mind Map Viewer
AppVersion={ver}
AppPublisher=Mind Map Viewer
DefaultDirName={{autopf}}\Mind Map Viewer
DefaultGroupName=Mind Map Viewer
UninstallDisplayIcon={{app}}\{app}.exe
OutputDir={rel}
OutputBaseFilename={app}-{ver}-Setup
SetupIconFile={root}\assets\icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
ChangesAssociations=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked
Name: "assoc"; Description: "Open .mm, .opml and .mmd files with Mind Map Viewer"; Flags: unchecked

[Files]
Source: "{root}\dist\{app}\*"; DestDir: "{{app}}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{{group}}\Mind Map Viewer"; Filename: "{{app}}\{app}.exe"
Name: "{{group}}\Uninstall Mind Map Viewer"; Filename: "{{uninstallexe}}"
Name: "{{autodesktop}}\Mind Map Viewer"; Filename: "{{app}}\{app}.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\MindMapViewer.File"; ValueType: string; ValueData: "Mind map"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\MindMapViewer.File\DefaultIcon"; ValueType: string; ValueData: "{{app}}\{app}.exe,0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\MindMapViewer.File\shell\open\command"; ValueType: string; ValueData: """{{app}}\{app}.exe"" ""%1"""; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.mm\OpenWithProgids"; ValueType: string; ValueName: "MindMapViewer.File"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.opml\OpenWithProgids"; ValueType: string; ValueName: "MindMapViewer.File"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.mmd\OpenWithProgids"; ValueType: string; ValueName: "MindMapViewer.File"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.md\OpenWithProgids"; ValueType: string; ValueName: "MindMapViewer.File"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc

[Run]
Filename: "{{app}}\{app}.exe"; Description: "Launch Mind Map Viewer"; Flags: nowait postinstall skipifsilent
'''

DESKTOP_ENTRY = """[Desktop Entry]
Type=Application
Name=Mind Map Viewer
GenericName=Mind map viewer
Comment=Interactive collapsible mind maps from Markdown, text, OPML, Mermaid or images
Exec={exec} %f
Icon={icon}
Terminal=false
Categories=Office;Viewer;Graphics;
MimeType=text/markdown;text/x-markdown;text/plain;text/x-opml+xml;application/json;
StartupWMClass={app}
"""

LINUX_INSTALL_SH = """#!/usr/bin/env bash
# Adds Mind Map Viewer to your applications menu (current user only).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p ~/.local/share/applications ~/.local/bin
ln -sf "$HERE/{app}" ~/.local/bin/{pkg}
cat > ~/.local/share/applications/{pkg}.desktop <<DESK
{desktop}DESK
update-desktop-database ~/.local/share/applications 2>/dev/null || true
echo "Installed. Launch 'Mind Map Viewer' from the app menu or run: {pkg}"
if ! ldconfig -p 2>/dev/null | grep -q libxcb-cursor.so.0; then
  echo "Note: Qt needs libxcb-cursor0 ->  sudo apt install libxcb-cursor0"
fi
"""


def package_linux(ver: str, onefile: bool) -> list:
    out = []
    rel = os.path.join(ROOT, "release")
    top = f"{APP}-{ver}"
    tpath = os.path.join(rel, f"{APP}-{ver}-linux-{arch()}{'-onefile' if onefile else ''}.tar.gz")
    log(f"Creating {os.path.basename(tpath)}")
    staging = os.path.join(ROOT, "build", "tar", top)
    shutil.rmtree(os.path.dirname(staging), ignore_errors=True)
    if onefile:
        os.makedirs(staging)
        shutil.copy2(built_exe(True), staging)
        shutil.copytree(os.path.join(ROOT, "samples"), os.path.join(staging, "samples"))
        icon_path = '$HERE/icon.png'
        shutil.copy2(os.path.join(ROOT, "assets", "icon.png"), staging)
    else:
        shutil.copytree(os.path.join(ROOT, "dist", APP), staging, symlinks=True)
        icon_path = '$HERE/_internal/assets/icon.png'
    shutil.copy2(os.path.join(ROOT, "README.md"), staging)
    desk = DESKTOP_ENTRY.format(exec=f'"$HERE/{APP}"', icon=icon_path, app=APP)
    inst = os.path.join(staging, "install.sh")
    with open(inst, "w", encoding="utf-8", newline="\n") as f:
        f.write(LINUX_INSTALL_SH.format(app=APP, pkg=PKG, desktop=desk))
    os.chmod(inst, 0o755)
    with tarfile.open(tpath, "w:gz") as t:
        t.add(staging, arcname=top)
    out.append(tpath)

    if shutil.which("dpkg-deb") and not onefile:
        out.append(build_deb(ver))
    elif not onefile:
        print("  (dpkg-deb not found - skipping .deb)")
    return out


def build_deb(ver: str) -> str:
    deb_arch = {"x86_64": "amd64", "aarch64": "arm64"}.get(platform.machine(), platform.machine())
    log(f"Creating {PKG}_{ver}_{deb_arch}.deb")
    root = os.path.join(ROOT, "build", "deb")
    shutil.rmtree(root, ignore_errors=True)
    opt = os.path.join(root, "opt", PKG)
    shutil.copytree(os.path.join(ROOT, "dist", APP), opt, symlinks=True)
    os.makedirs(os.path.join(root, "usr", "bin"))
    os.symlink(f"/opt/{PKG}/{APP}", os.path.join(root, "usr", "bin", PKG))
    icon_dir = os.path.join(root, "usr", "share", "icons", "hicolor", "256x256", "apps")
    os.makedirs(icon_dir)
    shutil.copy2(os.path.join(ROOT, "assets", "icon.png"), os.path.join(icon_dir, f"{PKG}.png"))
    app_dir = os.path.join(root, "usr", "share", "applications")
    os.makedirs(app_dir)
    with open(os.path.join(app_dir, f"{PKG}.desktop"), "w") as f:
        f.write(DESKTOP_ENTRY.format(exec=f"/opt/{PKG}/{APP}", icon=PKG, app=APP))
    size_kb = sum(os.path.getsize(os.path.join(d, x)) for d, _, fs in os.walk(opt) for x in fs
                  if not os.path.islink(os.path.join(d, x))) // 1024
    os.makedirs(os.path.join(root, "DEBIAN"))
    with open(os.path.join(root, "DEBIAN", "control"), "w") as f:
        f.write(textwrap.dedent(f"""\
            Package: {PKG}
            Version: {ver}
            Section: graphics
            Priority: optional
            Architecture: {deb_arch}
            Installed-Size: {size_kb}
            Depends: libxcb-cursor0, libxkbcommon-x11-0, libegl1, libfontconfig1, libdbus-1-3
            Maintainer: Mind Map Viewer <noreply@example.com>
            Description: Interactive collapsible mind map viewer
             Opens Markdown, indented text, Mermaid, OPML, FreeMind, XMind and JSON
             outlines as an interactive mind map; mind map images can be converted
             with Claude's vision API.
            """))
    for d, dirs, files in os.walk(root):
        for x in dirs:
            os.chmod(os.path.join(d, x), 0o755)
    out = os.path.join(ROOT, "release", f"{PKG}_{ver}_{deb_arch}.deb")
    run(["dpkg-deb", "--root-owner-group", "--build", root, out])
    return out


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--onefile", action="store_true", help="single-file executable (slower start-up)")
    ap.add_argument("--clean", action="store_true", help="remove build/, dist/ and release/ first")
    ap.add_argument("--skip-tests", action="store_true", help="skip unit tests and the smoke test")
    ap.add_argument("--no-venv", action="store_true", help="use the current Python instead of .venv-build")
    args = ap.parse_args()

    if not (IS_WIN or IS_LINUX):
        sys.exit("This script builds for Windows or Linux. (macOS works with PyInstaller too, "
                 "but packaging is not set up here.)")
    if sys.version_info < (3, 9):
        sys.exit("Python 3.9 or newer is required.")
    if not args.no_venv:
        ensure_venv()

    os.chdir(ROOT)
    ver = version()
    print(f"Building {APP} {ver} for {platform.system()} {arch()} with Python {platform.python_version()}")
    if args.clean:
        for d in ("build", "dist", "release"):
            shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)
    os.makedirs(os.path.join(ROOT, "release"), exist_ok=True)

    install_deps()
    if not args.skip_tests:
        run_tests()
    pyinstaller(ver, args.onefile)
    exe = built_exe(args.onefile)
    if not os.path.exists(exe):
        sys.exit(f"Build output not found: {exe}")
    if not args.skip_tests:
        smoke_test(exe)
    outputs = package_windows(ver, args.onefile) if IS_WIN else package_linux(ver, args.onefile)

    log("Done")
    print(f"  App:      {exe}")
    for o in outputs:
        print(f"  Release:  {o}  ({os.path.getsize(o) / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
