Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "WordFunc.nsh"
!insertmacro VersionCompare

Var WebView2Ready
Var WebView2Version
Var WebView2Candidate
Var WebView2ExitCode

!ifndef WEBVIEW2_CLIENT_KEY
!define WEBVIEW2_CLIENT_KEY "Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
!endif
!define WEBVIEW2_MIN_VERSION "86.0.622.0"
!ifndef WEBVIEW2_INSTALLER
!define WEBVIEW2_INSTALLER "..\..\build\windows-deps\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
!endif
!ifndef APP_PAYLOAD
!define APP_PAYLOAD "..\..\dist\TinfoilHat"
!endif
!ifndef SETUP_OUTFILE
!define SETUP_OUTFILE "..\..\dist\TinfoilHat-Setup-x64.exe"
!endif

Name "Tinfoil Hat Competition"
OutFile "${SETUP_OUTFILE}"
InstallDir "$LOCALAPPDATA\Programs\TinfoilHat"
InstallDirRegKey HKCU "Software\TinfoilHat" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma

!define MUI_ABORTWARNING
!define MUI_ICON "..\..\tinfoilhat\static\img\tinfoil-wizard-hat.ico"
!define MUI_UNICON "..\..\tinfoilhat\static\img\tinfoil-wizard-hat.ico"
!define MUI_FINISHPAGE_RUN "$INSTDIR\TinfoilHat.exe"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
    ${IfNot} ${RunningX64}
        MessageBox MB_ICONSTOP "This release requires 64-bit Windows 10 (22H2) or Windows 11." /SD IDOK
        Abort
    ${EndIf}
FunctionEnd

Function CheckWebView2Candidate
    ${If} $WebView2Candidate != ""
        ${VersionCompare} "$WebView2Candidate" "${WEBVIEW2_MIN_VERSION}" $1
        ${If} $1 == 0
        ${OrIf} $1 == 1
            StrCpy $WebView2Ready 1
            StrCpy $WebView2Version $WebView2Candidate
        ${EndIf}
    ${EndIf}
FunctionEnd

Function CheckWebView2
    ; Microsoft documents pv for per-user and per-machine Evergreen runtimes.
    ; A 32-bit NSIS process must explicitly inspect the correct registry views.
    StrCpy $WebView2Ready 0
    StrCpy $WebView2Version ""
    SetRegView 32
    ReadRegStr $WebView2Candidate HKCU "${WEBVIEW2_CLIENT_KEY}" "pv"
    Call CheckWebView2Candidate
    ReadRegStr $WebView2Candidate HKLM "${WEBVIEW2_CLIENT_KEY}" "pv"
    Call CheckWebView2Candidate
    SetRegView 64
    ReadRegStr $WebView2Candidate HKCU "${WEBVIEW2_CLIENT_KEY}" "pv"
    Call CheckWebView2Candidate
    ReadRegStr $WebView2Candidate HKLM "${WEBVIEW2_CLIENT_KEY}" "pv"
    Call CheckWebView2Candidate
    SetRegView 32
FunctionEnd

Section "Tinfoil Hat Competition" SEC_APP
    Call CheckWebView2
    ${If} $WebView2Ready == 1
        DetailPrint "Using installed Microsoft WebView2 Runtime $WebView2Version."
    ${Else}
        InitPluginsDir
        File /oname=$PLUGINSDIR\WebView2Setup.exe "${WEBVIEW2_INSTALLER}"
        DetailPrint "Installing Microsoft WebView2 Runtime..."
        StrCpy $WebView2ExitCode "could not launch"
        ExecWait '"$PLUGINSDIR\WebView2Setup.exe" /silent /install' $WebView2ExitCode
        ; Check the resulting runtime rather than guessing what an HRESULT means.
        Call CheckWebView2
        ${If} $WebView2Ready != 1
            MessageBox MB_ICONSTOP "Microsoft WebView2 is still unavailable (setup code $WebView2ExitCode). Install or repair the runtime from https://developer.microsoft.com/microsoft-edge/webview2/ and run setup again." /SD IDOK
            SetErrorLevel 1
            Abort
        ${EndIf}
        DetailPrint "Microsoft WebView2 Runtime $WebView2Version is available."
        ${If} $WebView2ExitCode == 3010
            SetRebootFlag true
        ${EndIf}
    ${EndIf}
    SetOutPath "$INSTDIR"
    File /r "${APP_PAYLOAD}\*"
    File /oname=Windows-Readme.md "..\..\docs\windows-desktop.md"
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    CreateDirectory "$SMPROGRAMS\Tinfoil Hat Competition"
    CreateShortcut "$SMPROGRAMS\Tinfoil Hat Competition\Tinfoil Hat Competition.lnk" "$INSTDIR\TinfoilHat.exe" "" "$INSTDIR\_internal\tinfoilhat\static\img\tinfoil-wizard-hat.ico" 0
    CreateShortcut "$SMPROGRAMS\Tinfoil Hat Competition\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKCU "Software\TinfoilHat" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TinfoilHat" "DisplayName" "Tinfoil Hat Competition"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TinfoilHat" "DisplayVersion" "0.1.0"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TinfoilHat" "Publisher" "Tinfoil Hat Competition"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TinfoilHat" "DisplayIcon" '"$INSTDIR\TinfoilHat.exe",0'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TinfoilHat" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TinfoilHat" "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TinfoilHat" "NoRepair" 1
SectionEnd

Section "Uninstall"
    ; Application data and shared WebView2 runtime survive uninstall and upgrades.
    RMDir /r "$INSTDIR\_internal"
    Delete "$INSTDIR\TinfoilHat.exe"
    Delete "$INSTDIR\Windows-Readme.md"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir "$INSTDIR"
    RMDir /r "$SMPROGRAMS\Tinfoil Hat Competition"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TinfoilHat"
    DeleteRegKey HKCU "Software\TinfoilHat"
SectionEnd
