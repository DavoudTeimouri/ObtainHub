; Inno Setup Script for ObtainHub
; Compatible with Inno Setup 6.7+
; Windows x64 installer with PATH management

#define AppName "ObtainHub"
#define AppVersion "2.0.0"
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
; CloseApplications tells Inno Setup to detect running instances and prompt to close them
CloseApplications=yes
CloseApplicationsFilter={#AppExeName}
RestartApplications=yes

[Files]
Source: "..\dist\ohub\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

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

  // Check if already present
  if Pos(';' + APath + ';', ';' + CurrentPath + ';') > 0 then
  begin
    Result := True;
    Exit;
  end;

  // Build new PATH
  if Length(CurrentPath) = 0 then
    NewPath := APath
  else
    NewPath := CurrentPath + ';' + APath;

  // Write back
  if RegWriteStringValue(HKCU, 'Environment', 'PATH', NewPath) then
  begin
    Result := True;
    // Broadcast environment change
    SendMessageTimeout(HWND_BROADCAST, WM_SETTINGCHANGE, 0, PChar('Environment'), SMTO_ABORTIFHUNG, 5000, @Result);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Only add to PATH if the user didn't disable it (no checkbox, always add for CLI tools)
    AppendToPath(ExpandConstant('{app}'));
  end;
end;
