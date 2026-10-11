# Detect the Evergreen Runtime using Microsoft's documented pv registry values.
# https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution
function Get-WebView2RuntimeVersion {
    $ClientKey = 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
    foreach ($Hive in @([Microsoft.Win32.RegistryHive]::CurrentUser, [Microsoft.Win32.RegistryHive]::LocalMachine)) {
        foreach ($View in @([Microsoft.Win32.RegistryView]::Registry32, [Microsoft.Win32.RegistryView]::Registry64)) {
            $Base = $null
            $Key = $null
            try {
                $Base = [Microsoft.Win32.RegistryKey]::OpenBaseKey($Hive, $View)
                $Key = $Base.OpenSubKey($ClientKey)
                if ($Key) {
                    $Version = $null
                    if ([Version]::TryParse([string]$Key.GetValue('pv'), [ref]$Version) -and $Version -ge [Version]'86.0.622.0') {
                        return $Version
                    }
                }
            } catch [System.Security.SecurityException] {
                continue
            } catch [System.UnauthorizedAccessException] {
                continue
            } finally {
                if ($Key) { $Key.Dispose() }
                if ($Base) { $Base.Dispose() }
            }
        }
    }
}

function Install-WebView2Runtime {
    param([Parameter(Mandatory=$true)][string]$Installer)
    $Version = Get-WebView2RuntimeVersion
    if ($Version) {
        Write-Host "Using installed Microsoft WebView2 Runtime $Version."
        return
    }
    $RuntimeProcess = Start-Process $Installer -ArgumentList '/silent', '/install' -Wait -PassThru
    $Version = Get-WebView2RuntimeVersion
    if (-not $Version) {
        throw "Microsoft WebView2 is unavailable after setup (code $($RuntimeProcess.ExitCode))."
    }
    Write-Host "Microsoft WebView2 Runtime $Version is available (setup code $($RuntimeProcess.ExitCode))."
}
