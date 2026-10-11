param(
    [Parameter(Mandatory=$true)][string]$HackRfPrefix,
    [string]$PackageCache = "$env:MAMBA_ROOT_PREFIX\pkgs"
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$Repo = (Resolve-Path "$PSScriptRoot\..\..").Path
Push-Location $Repo
try {
    if (-not [Environment]::Is64BitProcess) { throw "Build using 64-bit Python and PowerShell." }
    python -m pip install -e ".[desktop,dev]" -r packaging/windows/requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
    python packaging/fetch_assets.py
    if ($LASTEXITCODE -ne 0) { throw "Asset verification failed." }
    $Stage = "$Repo\build\windows-deps"
    if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }
    New-Item -ItemType Directory -Force "$Stage\hackrf", "$Stage\licenses" | Out-Null
    # Keep each native dependency beside the command-line tools, including VC runtimes.
    Get-ChildItem "$HackRfPrefix\Library\bin\*.dll" | Copy-Item -Destination "$Stage\hackrf" -Force
    Get-ChildItem "$HackRfPrefix\Library\bin\hackrf*.exe" | Copy-Item -Destination "$Stage\hackrf" -Force
    foreach ($Name in @("hackrf_info.exe", "hackrf_transfer.exe")) {
        if (-not (Test-Path "$Stage\hackrf\$Name")) { throw "Missing $Name in $HackRfPrefix" }
    }
    Copy-Item "$HackRfPrefix\conda-meta" "$Stage\licenses\package-records" -Recurse -Force
    $LicenseCount = 0
    Get-ChildItem "$HackRfPrefix\conda-meta\*.json" | ForEach-Object {
        $Record = Get-Content $_.FullName -Raw | ConvertFrom-Json
        $Package = "$($Record.name)-$($Record.version)-$($Record.build)"
        $Info = Join-Path $PackageCache "$Package\info"
        if (Test-Path "$Info\licenses") {
            Copy-Item $Info "$Stage\licenses\$Package" -Recurse -Force
            $LicenseCount++
        }
    }
    if ($LicenseCount -eq 0) { throw "Conda license cache was not found; refusing an incomplete distribution." }
    python packaging/windows/collect_sources.py "$Stage\licenses"
    if ($LASTEXITCODE -ne 0) { throw "Native dependency source collection failed." }
    # Validate that the bundled tools load their DLLs even with the build environment off PATH.
    $OriginalPath = $env:PATH
    try {
        $env:PATH = "$Stage\hackrf;$env:SystemRoot\System32;$env:SystemRoot"
        & "$Stage\hackrf\hackrf_info.exe"
        # hackrf_info exits 1 when no physical device is attached, but still loads the libraries.
        if ($LASTEXITCODE -notin @(0, 1)) { throw "The bundled HackRF tools cannot load their dependencies." }
    } finally { $env:PATH = $OriginalPath }
    python -m pytest tests
    if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
    python -m PyInstaller --noconfirm --clean packaging/desktop.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
    $Runtime = "$Stage\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
    Invoke-WebRequest "https://go.microsoft.com/fwlink/p/?LinkId=2124701" -OutFile $Runtime
    $Signature = Get-AuthenticodeSignature $Runtime
    if ($Signature.Status -ne "Valid" -or $Signature.SignerCertificate.Subject -notmatch "O=Microsoft Corporation") {
        throw "The WebView2 installer does not have a valid Microsoft signature."
    }
    # Exercise the runtime and native window on the build machine before shipping.
    $RuntimeProcess = Start-Process $Runtime -ArgumentList "/silent", "/install" -Wait -PassThru
    if ($RuntimeProcess.ExitCode -notin @(0, 3010, -2147219198)) {
        throw "WebView2 setup failed with exit code $($RuntimeProcess.ExitCode)."
    }
    foreach ($Mode in @("smoke-test", "gui-smoke-test")) {
        $Report = "$Repo\build\$Mode.json"
        Remove-Item $Report -Force -ErrorAction SilentlyContinue
        $Process = Start-Process "$Repo\dist\TinfoilHat\TinfoilHat.exe" `
            -ArgumentList "--$Mode", "--smoke-report", "`"$Report`"" -PassThru
        if (-not $Process.WaitForExit(90000)) {
            Stop-Process -Id $Process.Id -Force
            throw "$Mode timed out."
        }
        $Process.Refresh()
        if ($Process.ExitCode -ne 0 -or -not (Test-Path $Report)) { throw "$Mode failed." }
        if ((Get-Content $Report -Raw | ConvertFrom-Json).status -ne "passed") { throw "$Mode report failed." }
    }
    $Makensis = Get-Command makensis.exe -ErrorAction SilentlyContinue
    $CompilerPath = if ($Makensis) { $Makensis.Source } else { "${env:ProgramFiles(x86)}\NSIS\makensis.exe" }
    & $CompilerPath packaging/windows/installer.nsi
    if ($LASTEXITCODE -ne 0) { throw "Installer packaging failed." }
    Get-FileHash "dist\TinfoilHat-Setup-x64.exe" -Algorithm SHA256 | Format-List
} finally { Pop-Location }
