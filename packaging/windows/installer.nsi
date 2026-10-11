Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"

Name "Tinfoil Hat Competition"
OutFile "..\..\dist\TinfoilHat-Setup-x64.exe"
InstallDir "$LOCALAPPDATA\Programs\TinfoilHat"
InstallDirRegKey HKCU "Software\TinfoilHat" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma

!define MUI_ABORTWARNING
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
        MessageBox MB_ICONSTOP "This release requires 64-bit Windows 10 (22H2) or Windows 11."
        Abort
    ${EndIf}
FunctionEnd

Section "Tinfoil Hat Competition" SEC_APP
    InitPluginsDir
    File /oname=$PLUGINSDIR\WebView2Setup.exe "..\..\build\windows-deps\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
    DetailPrint "Installing Microsoft WebView2 Runtime..."
    ExecWait '"$PLUGINSDIR\WebView2Setup.exe" /silent /install' $0
    ; 0=success, 3010=reboot required, 0x80040902=already installed.
    ${If} $0 != 0
    ${AndIf} $0 != 3010
    ${AndIf} $0 != -2147219198
        MessageBox MB_ICONSTOP "WebView2 installation failed (code $0). Setup cannot continue."
        SetErrorLevel 1
        Abort
    ${EndIf}
    ${If} $0 == 3010
        SetRebootFlag true
    ${EndIf}
    SetOutPath "$INSTDIR"
    File /r "..\..\dist\TinfoilHat\*"
    File /oname=Windows-Readme.md "..\..\docs\windows-desktop.md"
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    CreateDirectory "$SMPROGRAMS\Tinfoil Hat Competition"
    CreateShortcut "$SMPROGRAMS\Tinfoil Hat Competition\Tinfoil Hat Competition.lnk" "$INSTDIR\TinfoilHat.exe"
    CreateShortcut "$SMPROGRAMS\Tinfoil Hat Competition\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKCU "Software\TinfoilHat" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TinfoilHat" "DisplayName" "Tinfoil Hat Competition"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TinfoilHat" "DisplayVersion" "0.1.0"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TinfoilHat" "Publisher" "Tinfoil Hat Competition"
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
