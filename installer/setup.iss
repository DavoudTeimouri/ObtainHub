; ObtainHub Inno Setup Script 6.7+
; Inno Setup 6.7+ required (Unicode, modern wizard)
#define AppName "ObtainHub"
#define AppVersion "2.1.0"
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
  I: Integer;
  StartPos: Integer;
  Entry: string;
begin
  Result := False;
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', CurrentPath) then
    CurrentPath := '';
  { Compare whole PATH entries. A substring test would match unrelated
    directories such as C:\Tools\ObtainHubBackup and skip the real one. }
  StartPos := 1;
  while StartPos <= Length(CurrentPath) + 1 do
  begin
    I := Pos(';', Copy(CurrentPath, StartPos, MaxInt));
    if I = 0 then
    begin
      Entry := Copy(CurrentPath, StartPos, MaxInt);
      StartPos := Length(CurrentPath) + 2;
    end
    else
    begin
      Entry := Copy(CurrentPath, StartPos, I - 1);
      StartPos := StartPos + I;
    end;
    if CompareText(Trim(Entry), APath) = 0 then
      Exit;
  end;
  if Length(CurrentPath) > 0 then
    NewPath := CurrentPath + ';' + APath
  else
    NewPath := APath;
  if RegWriteStringValue(HKCU, 'Environment', 'Path', NewPath) then
  begin
    Result := True;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  CurrentPath: string;
  NewPath: string;
  I: Integer;
  StartPos: Integer;
  Entry: string;
  AppDir: string;
begin
  { Drop {app} from PATH, otherwise uninstalling leaves a dead directory
    entry that every later process has to scan. }
  if CurUninstallStep <> usUninstall then
    Exit;
  AppDir := ExpandConstant('{app}');
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', CurrentPath) then
    Exit;
  StartPos := 1;
  NewPath := '';
  while StartPos <= Length(CurrentPath) + 1 do
  begin
    I := Pos(';', Copy(CurrentPath, StartPos, MaxInt));
    if I = 0 then
    begin
      Entry := Copy(CurrentPath, StartPos, MaxInt);
      StartPos := Length(CurrentPath) + 2;
    end
    else
    begin
      Entry := Copy(CurrentPath, StartPos, I - 1);
      StartPos := StartPos + I;
    end;
    if (Trim(Entry) <> '') and (CompareText(Trim(Entry), AppDir) <> 0) then
    begin
      if NewPath = '' then
        NewPath := Trim(Entry)
      else
        NewPath := NewPath + ';' + Trim(Entry);
    end;
  end;
  if NewPath <> CurrentPath then
    RegWriteStringValue(HKCU, 'Environment', 'Path', NewPath);
end;