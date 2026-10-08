; NSIS 3.09+ installer for ObtainHub (Rust version)
; Replaces Inno Setup setup.iss - maintains all current constraints:
; - Machine-wide, admin-only
; - Default C:\Program Files\ObtainHub
; - No shortcuts
; - Exact PATH add/remove semantics
; - Mutual refusal (EXE blocks MSI, MSI blocks EXE)
; - Silent install /S works without dialogs
; - Shared GUID for MSI upgrade detection: A1B2C3D4-E5F6-7890-ABCD-EF1234567890

!include "LogicLib.nsh"
!include "MUI2.nsh"
!include "x64.nsh"
!include "FileFunc.nsh"
!include "StrFunc.nsh"
!include "WinCore.nsh"

; Product GUID (MUST match MSI UpgradeCode in setup.wxs)
!define PRODUCT_GUID "{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}"
!define APP_NAME "ObtainHub"
!define APP_EXE "ohub.exe"
!define PUBLISHER "DavoudTeimouri"
!define URL "https://github.com/DavoudTeimouri/ObtainHub"
!define VERSION "3.0.0"

Name "${APP_NAME} ${VERSION}"
OutFile "ObtainHub-Setup.exe"
InstallDir "$PROGRAMFILES64\${APP_NAME}"
InstallDirRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_GUID}" "InstallLocation"
RequestExecutionLevel admin

; LZMA solid compression (NSIS 3 default)
SetCompressor lzma
SetCompressorDictSize 8

; CRC check for installer integrity
CRCCheck on

; MUI pages
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

; ---------- Mutual refusal: EXE detects MSI (shared GUID) ----------
Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "ObtainHub requires 64-bit Windows.$\n$\nSetup will now abort."
    Abort
  ${EndIf}

  ; Verify binary exists in installer directory
  IfFileExists "$EXEDIR\${APP_EXE}" 0 binary_missing
  StrCpy $0 1
  Goto binary_ok
binary_missing:
  MessageBox MB_ICONSTOP "Installer corrupted: ${APP_EXE} not found in installer directory.$\n$\nPlease re-download the installer."
  Abort
binary_ok:

  ; Check 64-bit view first (MSI on 64-bit)
  ReadRegStr $0 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_GUID}" "DisplayName"
  StrCmp $0 "" check_wow64 msi_found
check_wow64:
  ; Check 32-bit view (MSI on 64-bit in WoW64)
  ReadRegStr $0 HKLM "Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_GUID}" "DisplayName"
  StrCmp $0 "" done_check msi_found
msi_found:
  ; Silent mode: block without UI
  ${RunningX64} $1
  StrCmp $1 1 silent_x64
  StrCmp ${Silent} 1 silent_x64
  MessageBox MB_ICONSTOP|MB_OK "$\n${APP_NAME} is already installed via MSI (ObtainHub.msi).$\n$\nPlease uninstall the MSI version first, then run this installer again.$\n$\nFound: $0" /SD IDOK
  Goto not_silent_x64
silent_x64:
  StrCpy $0 1
not_silent_x64:
  StrCmp $0 1 abort_install
  Abort
abort_install:
  SetErrorLevel 1
  Quit
done_check:
FunctionEnd

; ---------- PATH helper: $R0=entry, returns $R0=1 found / 0 not ----------
Function PathHasEntry
  ; $R0 = entry to find (e.g. $INSTDIR)
  ; Returns $R0 = 1 if found, 0 if not
  Push $R1
  Push $R2
  Push $R3
  Push $R4

  ; Read current user PATH
  ReadRegStr $R1 HKCU "Environment" "PATH"
  StrCmp $R1 "" not_found
  StrCpy $R2 0
loop:
  StrCpy $R3 $R1 "" $R2
  StrCmp $R3 "" not_found
  StrCpy $R4 $R1 $R2
  StrLen $R3 $R4
  IntOp $R4 $R4 + $R2
  StrCpy $R4 $R1 "" $R4
  StrCmp $R4 ";" 0 check_entry
  StrCpy $R4 ""
check_entry:
  StrCmp $R3 $R0 found
  IntOp $R2 $R2 + 1
  StrCmp $R4 "" not_found
  Goto loop
found:
  StrCpy $R0 1
  Goto done
not_found:
  StrCpy $R0 0
done:
  Pop $R4
  Pop $R3
  Pop $R2
  Pop $R1
  Exch $R0
FunctionEnd

Function un.PathHasEntry
  ; $R0 = entry to find (e.g. $INSTDIR)
  ; Returns $R0 = 1 if found, 0 if not
  Push $R1
  Push $R2
  Push $R3
  Push $R4

  ; Read current user PATH
  ReadRegStr $R1 HKCU "Environment" "PATH"
  StrCmp $R1 "" not_found
  StrCpy $R2 0
loop:
  StrCpy $R3 $R1 "" $R2
  StrCmp $R3 "" not_found
  StrCpy $R4 $R1 $R2
  StrLen $R3 $R4
  IntOp $R4 $R4 + $R2
  StrCpy $R4 $R1 "" $R4
  StrCmp $R4 ";" 0 check_entry
  StrCpy $R4 ""
check_entry:
  StrCmp $R3 $R0 found
  IntOp $R2 $R2 + 1
  StrCmp $R4 "" not_found
  Goto loop
found:
  StrCpy $R0 1
  Goto done
not_found:
  StrCpy $R0 0
done:
  Pop $R4
  Pop $R3
  Pop $R2
  Pop $R1
  Exch $R0
FunctionEnd

Function AddToUserPath
  ; $R0 = entry to add ($INSTDIR)
  StrCpy $R0 "$INSTDIR"
  Call PathHasEntry
  Pop $R0
  StrCmp $R0 1 done

  ; Not found, append to PATH
  ReadRegStr $R0 HKCU "Environment" "PATH"
  StrCmp $R0 "" write_path
  StrCpy $R0 "$R0;$INSTDIR"
write_path:
  WriteRegStr HKCU "Environment" "PATH" "$R0"
  System::Call 'user32::SendMessageTimeout(i 0xFFFF, i 0x1A, i 0, t "Environment", i 0x2, i 5000, i .r0)'
done:
FunctionEnd

Function un.RemoveFromUserPath
  ; $R0 = entry to remove ($INSTDIR)
  StrCpy $R0 "$INSTDIR"
  Call un.PathHasEntry
  Pop $R0
  StrCmp $R0 0 done

  ; Found, rebuild PATH without it
  ReadRegStr $R0 HKCU "Environment" "PATH"
  StrCmp $R0 "" done

  StrCpy $R1 ""
  StrCpy $R2 0
rebuild_loop:
  StrCpy $R3 $R0 "" $R2
  StrCmp $R3 "" write_rebuilt
  StrCpy $R4 $R0 $R2
  StrLen $R3 $R4
  IntOp $R4 $R4 + $R2
  StrCpy $R4 $R0 "" $R4
  StrCmp $R4 ";" 0 check_entry2
  StrCpy $R4 ""
check_entry2:
  StrCmp $R3 "$INSTDIR" skip_entry
  StrCmp $R1 "" first_entry
  StrCpy $R1 "$R1;$R3"
  Goto next_entry
first_entry:
  StrCpy $R1 "$R3"
next_entry:
skip_entry:
  IntOp $R2 $R2 + 1
  StrCmp $R4 "" write_rebuilt
  Goto rebuild_loop
write_rebuilt:
  WriteRegStr HKCU "Environment" "PATH" "$R1"
  System::Call 'user32::SendMessageTimeout(i 0xFFFF, i 0x1A, i 0, t "Environment", i 0x2, i 5000, i .r0)'
done:
FunctionEnd

; ---------- Install section ----------
Section "MainSection" SEC01
  SetOutPath "$INSTDIR"
  File "/oname=$INSTDIR\\${APP_EXE}" "${APP_EXE}"
  WriteUninstaller "$INSTDIR\\uninstall.exe"

  ; Registry under shared GUID (same as MSI)
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_GUID}" "DisplayName" "${APP_NAME} ${VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_GUID}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_GUID}" "QuietUninstallString" '"$INSTDIR\uninstall.exe" /S'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_GUID}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_GUID}" "Publisher" "${PUBLISHER}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_GUID}" "URLInfoAbout" "${URL}"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_GUID}" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_GUID}" "NoRepair" 1
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_GUID}" "DisplayVersion" "${VERSION}"

  ; PATH management (user scope for exact add/remove)
  Call AddToUserPath
SectionEnd

; ---------- Uninstall ----------
Section "Uninstall"
  Call un.RemoveFromUserPath

  RMDir /r "$INSTDIR"

  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_GUID}"
SectionEnd

; ---------- Silent uninstall mutual refusal ----------
Function un.onInit
FunctionEnd