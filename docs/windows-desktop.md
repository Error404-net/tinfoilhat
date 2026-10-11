# Windows desktop application

The Windows build produces **TinfoilHat-Setup-x64.exe**. Run the installer, then
open **Tinfoil Hat Competition** from the Start menu. The application opens in
its own native window. Python, pip, a terminal, and a separately started web
server are not required on the user's computer.

Supported target: Windows 10 22H2 / Windows 11, x64, with .NET Framework 4.8 or
later (included with these Windows versions). Windows on ARM and 32-bit Windows
are not supported by this installer.

## Included dependencies

- Embedded Python and the application's runtime Python libraries.
- pywebview and a local Waitress server that listens only on loopback.
- jQuery, Select2, and Chart.js for offline application functionality.
- HackRF command-line tools and their DLL dependencies, from conda-forge.
- Microsoft's signed WebView2 Evergreen **offline** runtime installer.

The installer does not need to download dependencies on the user's machine.
Setup reuses an existing compatible WebView2 runtime. If it must install the
runtime, setup checks that it is available afterward rather than rejecting an
updater return code when the required runtime is already present.
Google Fonts remain optional online resources; system fonts work offline.
Windows and WebView2 may subsequently check for their own updates.

## HackRF hardware

The application opens without connected hardware; registration, leaderboards,
voting, flyers, and saved results remain usable. RF measurements require a
connected **HackRF One**. Install the device's **WinUSB** driver if Windows does
not already have a compatible driver. The official HackRF Windows instructions
describe using Zadig: https://hackrf.readthedocs.io/en/latest/installing_hackrf_software.html

USB driver changes require selecting the correct physical device and may need
administrator access. The installer cannot safely choose a USB device for you.
No RF readings are simulated. Hardware measurements must be tested on a real
Windows machine with the HackRF connected.

## Data, updates, and troubleshooting

Competition data, contestant uploads, session key, WebView storage, and
`desktop.log` live in `%LOCALAPPDATA%\TinfoilHat`. The executable uses a random
available local port; it does not expose the application to other computers.
Closing the desktop window shuts down its server. Billboard and voting URLs
are therefore local to this computer; use the existing web deployment for
audience access from other devices.

Close the application before installing an update. Updates and uninstallation
retain competition data. Back up the data directory while the app is closed.
Existing web-instance data is not automatically copied into this directory.
The installer is unsigned unless your release process adds a signing step, so
Windows may display a SmartScreen notice.

## Build the EXE

Windows executables must be built on Windows; PyInstaller does not cross-compile
from Linux. The repository's **Windows desktop release** GitHub Actions workflow
builds the installer and runs tests against both its packaged backend and native
window. Run it manually to download the `TinfoilHat-Windows-x64` artifact.
Pushing a `v*` tag also creates a **draft** GitHub Release after successful checks.
Review that draft before publishing it.

For a local build, install x64 Python 3.13, NSIS, and micromamba, then run:

```powershell
micromamba create -y -n hackrf-tools -c conda-forge --strict-channel-priority hackrf=2026.01.3
python -m venv .venv
.venv\Scripts\Activate.ps1
.\packaging\windows\build.ps1 -HackRfPrefix "$env:MAMBA_ROOT_PREFIX\envs\hackrf-tools"
```

The build verifies downloads, stages native tools and license files, bundles the
app with PyInstaller, validates the signed WebView2 installer, runs backend and
GUI smoke checks, and builds the NSIS installer. It fails if required checks fail.
CI also tests the actual installer, reinstallation, and launching the installed
application. Regression fixtures cover a preinstalled runtime and updater error
`0x80040828`, including refusing to continue if the runtime remains unavailable.
The result is `dist\TinfoilHat-Setup-x64.exe` with a printed SHA-256 checksum.

## Develop without packaging

```shell
python -m pip install -e ".[desktop,dev]"
python packaging/fetch_assets.py
python desktop_launcher.py
```

On Linux and macOS, pywebview also requires that platform's GUI backend. This
release workflow currently targets Windows only. The existing Flask entry points
continue to work; run `packaging/fetch_assets.py` once to prepare the local UI
dependencies for those entry points too.
