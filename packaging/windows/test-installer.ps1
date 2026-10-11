param([Parameter(Mandatory=$true)][string]$Setup)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Repo = (Resolve-Path "$PSScriptRoot\..\..").Path
$TestRoot = Join-Path $Repo 'build\installer-tests'
$ClientKey = 'Software\TinfoilHat\InstallerRegression\WebView2'
$RegistryPath = "HKCU:\$ClientKey"
$Compiler = "${env:ProgramFiles(x86)}\NSIS\makensis.exe"
$CSharpCompiler = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
New-Item -ItemType Directory -Force "$TestRoot\app" | Out-Null
. "$PSScriptRoot\webview2.ps1"
if (-not (Get-WebView2RuntimeVersion)) { throw 'The Windows GUI test requires a real WebView2 runtime.' }

# This test-only updater reproduces the reported HRESULT without touching Edge.
# The compiled fixture checks a private registry key, never real runtime keys.
$StubSource = @'
using System;
using System.IO;
using Microsoft.Win32;
class UpdaterFixture {
    static int Main() {
        File.WriteAllText(Environment.GetEnvironmentVariable("TINFOILHAT_UPDATER_MARKER"), "called");
        if (Environment.GetEnvironmentVariable("TINFOILHAT_UPDATER_REGISTER") == "1") {
            using (var key = Registry.CurrentUser.CreateSubKey("Software\\TinfoilHat\\InstallerRegression\\WebView2")) {
                key.SetValue("pv", "120.0.0.0", RegistryValueKind.String);
            }
        }
        return unchecked((int)0x80040828);
    }
}
'@
$StubSource | Set-Content "$TestRoot\updater.cs" -Encoding utf8
& $CSharpCompiler /nologo /target:exe "/out:$TestRoot\UpdaterFixture.exe" "$TestRoot\updater.cs"
if ($LASTEXITCODE -ne 0) { throw 'Could not compile the installer regression fixture.' }
Copy-Item "$TestRoot\UpdaterFixture.exe" "$TestRoot\app\TinfoilHat.exe" -Force
$FixtureSetup = "$TestRoot\Regression-Setup.exe"
& $Compiler "/DSETUP_OUTFILE=$FixtureSetup" "/DAPP_PAYLOAD=$TestRoot\app" `
    "/DWEBVIEW2_INSTALLER=$TestRoot\UpdaterFixture.exe" "/DWEBVIEW2_CLIENT_KEY=$ClientKey" `
    "$PSScriptRoot\installer.nsi"
if ($LASTEXITCODE -ne 0) { throw 'Could not compile the installer regression setup.' }

function Invoke-SetupCase {
    param([string]$Executable, [string]$Destination, [bool]$ExpectSuccess)
    $Process = Start-Process $Executable -ArgumentList "/S /D=$Destination" -PassThru
    if (-not $Process.WaitForExit(120000)) {
        Stop-Process -Id $Process.Id -Force
        throw "Installer test timed out: $Destination"
    }
    $Process.Refresh()
    if (($Process.ExitCode -eq 0) -ne $ExpectSuccess) {
        throw "Unexpected installer exit code $($Process.ExitCode): $Destination"
    }
    if ((Test-Path "$Destination\TinfoilHat.exe") -ne $ExpectSuccess) {
        throw "Unexpected installer payload state: $Destination"
    }
}

try {
    $env:TINFOILHAT_UPDATER_MARKER = "$TestRoot\updater-called.txt"
    $env:TINFOILHAT_UPDATER_REGISTER = '0'
    Remove-Item $RegistryPath -Recurse -Force -ErrorAction SilentlyContinue
    New-Item $RegistryPath -Force | Out-Null
    New-ItemProperty $RegistryPath -Name pv -Value '120.0.0.0' -PropertyType String -Force | Out-Null
    Invoke-SetupCase $FixtureSetup "$TestRoot\existing-runtime" $true
    if (Test-Path $env:TINFOILHAT_UPDATER_MARKER) { throw 'Setup unnecessarily launched the runtime updater.' }

    Remove-ItemProperty $RegistryPath -Name pv
    Invoke-SetupCase $FixtureSetup "$TestRoot\missing-runtime" $false
    if (-not (Test-Path $env:TINFOILHAT_UPDATER_MARKER)) { throw 'Setup failed to attempt a missing runtime install.' }

    Remove-Item $env:TINFOILHAT_UPDATER_MARKER
    $env:TINFOILHAT_UPDATER_REGISTER = '1'
    Invoke-SetupCase $FixtureSetup "$TestRoot\runtime-available-after-error" $true
    if (-not (Test-Path $env:TINFOILHAT_UPDATER_MARKER)) { throw 'The updater fallback was not exercised.' }

    # Now exercise the actual release installer and its installed executable.
    $Installed = "$TestRoot\real-installed-app"
    Invoke-SetupCase $Setup $Installed $true
    Invoke-SetupCase $Setup $Installed $true
    foreach ($Mode in @('smoke-test', 'gui-smoke-test')) {
        $Report = "$Repo\build\installed-$Mode.json"
        Remove-Item $Report -Force -ErrorAction SilentlyContinue
        $Process = Start-Process "$Installed\TinfoilHat.exe" `
            -ArgumentList "--$Mode", '--smoke-report', "`"$Report`"" -PassThru
        if (-not $Process.WaitForExit(90000)) {
            Stop-Process -Id $Process.Id -Force
            throw "Installed application $Mode timed out."
        }
        $Process.Refresh()
        if ($Process.ExitCode -ne 0 -or -not (Test-Path $Report)) { throw "Installed application $Mode failed." }
        if ((Get-Content $Report -Raw | ConvertFrom-Json).status -ne 'passed') { throw "Installed $Mode report failed." }
    }
    Write-Host 'Installer regression cases, reinstall, and installed backend/native window checks passed.'
} finally {
    Remove-Item $RegistryPath -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item Env:TINFOILHAT_UPDATER_MARKER -ErrorAction SilentlyContinue
    Remove-Item Env:TINFOILHAT_UPDATER_REGISTER -ErrorAction SilentlyContinue
}
