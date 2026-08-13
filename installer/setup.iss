; Inno Setup Script for ObtainHub
; Compatible with Inno Setup 6.7+
; Windows x64 installer with PATH management

#define AppName "ObtainHub"
#define AppVersion "0.1.0.9"
#define AppPublisher "DavoudTeimouri"
#define AppURL "https://github.com/DavoudTeimouri/ObtainHub"
#define AppExeName "ohub.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=Output
OutputBaseFilename=ObtainHub-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
DisableProgramGroupPage=yes
DisableDirPage=no
CreateAppDir=yes
UninstallDisplayIcon={app}\{#AppExeName}
MinVersion=6.7

[Files]
Source: "..\dist\ohub.exe"; DestDir: "{app}"; Flags: ignoreversion

[Code]
function AppendToPath(const APath: String): Boolean;
var
  CurrentPath: String;
  NewPath: String;
begin
  Result := False;
  
  // Read current PATH from user registry
  if not RegQueryStringValue(HKCU, 'Environment', 'PATH', CurrentPath) then
    CurrentPath := '';
  
  // Check if already in PATH
  if Pos(APath, CurrentPath) > 0 then begin
    Result := True;
    Exit;
  end;
  
  // Append to PATH
  if Length(CurrentPath) > 0 then
    NewPath := CurrentPath + ';' + APath
  else
    NewPath := APath;
  
  // Write back to user registry (safe, no admin required)
  Result := RegWriteStringValue(HKCU, 'Environment', 'PATH', NewPath);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    // Add to user PATH (safe, no admin required)
    AppendToPath(ExpandConstant('{app}'));
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TSetupUninstallStep);
var
  Msg: String;
begin
  if CurUninstallStep = usUninstall then begin
    // Ask user if they want to remove configuration files
    if MsgBox('Do you want to remove ObtainHub configuration files?', mbConfirmation, MB_YESNO) = IDYES then
    begin
      Msg := 'Removing configuration files...';
      // Delete configuration files
      if DirExists(ExpandConstant('{localappdata}\ObtainHub')) then
      begin
        if not DeleteFile(ExpandConstant('{localappdata}\ObtainHub\state.json')) then
          Msg := Msg + 'Failed to remove state.json' + #13#10;
        if not DeleteFile(ExpandConstant('{localappdata}\ObtainHub\config.json')) then
          Msg := Msg + 'Failed to remove config.json' + #13#10;
        // Try to remove directory if empty
        RemoveDir(ExpandConstant('{localappdata}\ObtainHub'));
      end;
    end
    else
      Msg := 'Configuration files preserved as requested.';
    
    MsgBox(Msg, mbInformation, MB_OK);
  end;
end;