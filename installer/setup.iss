; ObtainHub Inno Setup script
; Requires Inno Setup 6.7+
; PATH management

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
; CloseApplications and them
CloseApplications=yes
CloseApplicationsFilter={#AppExeName}
RestartApplications=yes

[Files]
Source: "..\dist\ohub\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Code]
function AppendToPath(const APath: string): Boolean;
var
  CurrentPath: string;
  NewPath: string;
begin
  Result := False;
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', CurrentPath) then
    CurrentPath := '';
  if Pos(APath, CurrentPath) > 0 then
    Exit;
  if Length(CurrentPath) > 0 then
    NewPath := CurrentPath + ';' + APath
  else
    NewPath := APath;
  if RegWriteStringValue(HKCU, 'Environment', 'Path', NewPath) then
  begin
    SendMessageTimeout(HWND_BROADCAST, WM_SETTINGCHANGE, 0, PChar('Environment'), SMTO_ABORTIFHUNG, 5000, @Result);
    Result := True;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Only add to PATH if the CLI wasn't already in it
    AppendToPath(ExpandConstant('{app}'));
  end;
end;
