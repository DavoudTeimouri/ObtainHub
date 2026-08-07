; ObtainHub Inno Setup Script
; Compiles the EXE installer

#define MyAppName "ObtainHub"
#define MyAppVersion "0.1.0-beta.2"
#define MyAppPublisher "ObtainHub"
#define MyAppURL "https://github.com/DavoudTeimouri/ObtainHub"
#define MyAppExeName "ohub.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=ObtainHub-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Types]
Name: "currentuser"; Description: "Install for current user only"
Name: "allusers"; Description: "Install for all users (requires administrator)"

[Components]
Name: "main"; Description: "Main program"; Types: currentuser allusers

[Tasks]
Name: "addpath"; Description: "Add ObtainHub to PATH"; GroupDescription: "Additional tasks:"

[Files]
Source: "..\dist\ohub.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{commonprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: addpath
Name: "{userprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: addpath

[Registry]
; Add to PATH for current user (always)
Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "PATH"; ValueData: "{app};"; Flags: preservestringtype uninsdeletevalue; Tasks: addpath

; Add to PATH for all users (only if allusers type selected)
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "PATH"; ValueData: "{app};"; Flags: preservestringtype uninsdeletevalue; Tasks: addpath; Permissions: admins-full; Check: IsAdminInstallMode

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
; Data directory cleanup (conditional)
Type: filesandordirs; Name: "{localappdata}\ObtainHub"
Type: filesandordirs; Name: "{commonappdata}\ObtainHub"

[Code]
var
  RemoveData: Boolean;

function IsAdminInstallMode(): Boolean;
begin
  Result := (WizardSetupType(False) = 'allusers');
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;

function NeedRestart(): Boolean;
begin
  Result := False;
end;

procedure InitializeUninstall();
begin
  // Ask user about data removal
  RemoveData := False;
  if MsgBox('Do you want to remove all ObtainHub data (settings, cache, logs)?'#13#10#13#10'This includes:'#13#10'  - %LOCALAPPDATA%\ObtainHub'#13#10'  - %PROGRAMDATA%\ObtainHub'#13#10#13#10'Click "Yes" to remove all data, "No" to keep data.', mbConfirmation, MB_YESNO) = IDYES then
    RemoveData := True;
end;

function ShouldRemoveData(Param: String): Boolean;
begin
  Result := RemoveData;
end;

[UninstallRun]
; Only run data cleanup if user chose to remove data
Filename: "{app}\{#MyAppExeName}"; Parameters: "--uninstall-cleanup"; Flags: runascurrentuser; Check: ShouldRemoveData('')