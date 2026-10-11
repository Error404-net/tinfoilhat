"""Build on the target OS. Windows builds include the staged HackRF distribution."""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).parent
datas = [
    (str(root / "tinfoilhat" / "templates"), "tinfoilhat/templates"),
    (str(root / "tinfoilhat" / "schema.sql"), "tinfoilhat"),
    (str(root / "LICENSE"), "licenses/tinfoilhat"),
    (str(root / "packaging" / "windows" / "THIRD_PARTY_NOTICES.txt"), "licenses"),
]
# Never package competition uploads or a development database.
static_root = root / "tinfoilhat" / "static"
for path in static_root.rglob("*"):
    if path.is_file() and "uploads" not in path.relative_to(static_root).parts:
        datas.append((str(path), str(Path("tinfoilhat/static") / path.relative_to(static_root).parent)))
datas += collect_data_files("webview")
for distribution in ("pywebview", "Flask", "numpy", "waitress", "platformdirs"):
    datas += copy_metadata(distribution, recursive=True)
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.is_file():
    datas.append((str(python_license), "licenses/python"))
hiddenimports = []
if os.name == "nt":
    hackrf = root / "build" / "windows-deps" / "hackrf"
    if not (hackrf / "hackrf_info.exe").is_file() or not (hackrf / "hackrf_transfer.exe").is_file():
        raise RuntimeError("Stage the HackRF dependencies using packaging/windows/build.ps1 first.")
    datas.append((str(hackrf), "hackrf"))
    datas.append((str(root / "build" / "windows-deps" / "licenses"), "licenses/hackrf"))
    hiddenimports += ["webview.platforms.winforms", "webview.platforms.edgechromium", "clr", "pythonnet"]

a = Analysis(
    [str(root / "desktop_launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "rtlsdr", "pytest", "tox", "black", "ruff", "isort"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="TinfoilHat",
    debug=False, strip=False, upx=False, console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="TinfoilHat")
