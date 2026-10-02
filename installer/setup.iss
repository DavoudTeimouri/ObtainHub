; ObtainHub Inno Setup Script 6.7+
; Inno Setup 6.7+ required (Unicode, modern wizard)
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
CloseApplications=yes
CloseApplicationsFilter={#AppExeName}
RestartApplications=yes

[Files]
Source: "..\dist\ohub\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "Path"; ValueData: "{olddata};{app}"; Flags: preservestringtype; Check: AppendToPath('{app}')

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

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
    Result := True;
  end;
end;