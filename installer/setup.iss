; ObtainHub Inno Setup Script 6.7+
; Inno Setup 6.7+ required (Unicode, modern wizard)
#define AppName "ObtainHub"
#define AppVersion "2.1.2"
#define AppPublisher "DavoudTeimouri"
#define AppURL "https://github.com/DavoudTeimouri/ObtainHub"
#define AppExeName "ohub.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
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

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "Path"; ValueData: "{olddata};{app}"; Flags: preservestringtype; Check: AppendToPath('{app}')

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
{ The MSI and the EXE install to the same folder with no shared installer
  identity, so installing one after the other left both registered and
  double-installed. Detect the other installer's uninstall entry and stop
  before writing anything.

  The MSI is perMachine, so it registers its uninstall entry under
  HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\{UpgradeCode}.

  Inno now has an AppId equal to the same GUID, so its own entry is
  written as {UpgradeCode}_is1 and Inno handles its own upgrade path.
  Only the MSI case has to be blocked here. }

const
  MsiUninstallKey = 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\' +
    '{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}';

function MsiInstalled(): Boolean;
begin
  Result := RegKeyExists(HKLM, MsiUninstallKey);
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if MsiInstalled then
  begin
    MsgBox('ObtainHub is already installed by ObtainHub.msi.' + #13#10 +
      'Uninstall it first, then run this installer.' + #13#10 + #13#10 +
      'Both installers write to the same folder. Installing both leaves two ' +
      'uninstall entries fighting over the same files.',
      mbError, MB_OK);
    Result := False;
  end;
end;

function PathHasEntry(const APath: String): Boolean;
var
  CurrentPath: String;
  Start: Integer;
  Stop: Integer;
  Entry: String;
begin
  { Exact entry match only. A substring test would treat C:\Tools\ObtainHubBackup
    as already present and silently skip the real PATH entry. Split on ';' and
    compare whole entries. }
  Result := False;
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', CurrentPath) then
    Exit;

  Start := 1;
  while Start <= Length(CurrentPath) do
  begin
    if CurrentPath[Start] = ';' then
    begin
      Inc(Start);
      Continue;
    end;

    Stop := Start;
    while (Stop <= Length(CurrentPath)) and (CurrentPath[Stop] <> ';') do
      Inc(Stop);
    Entry := Copy(CurrentPath, Start, Stop - Start);

    if CompareText(Trim(Entry), APath) = 0 then
    begin
      Result := True;
      Exit;
    end;

    Start := Stop;
  end;
end;

function AppendToPath(const APath: String): Boolean;
var
  CurrentPath: String;
  NewPath: String;
begin
  Result := False;
  if PathHasEntry(APath) then
    Exit;

  if not RegQueryStringValue(HKCU, 'Environment', 'Path', CurrentPath) then
    CurrentPath := '';
  if Length(CurrentPath) > 0 then
    NewPath := CurrentPath + ';' + APath
  else
    NewPath := APath;

  if RegWriteStringValue(HKCU, 'Environment', 'Path', NewPath) then
    Result := True;
end;

function CurUninstallStepChanged(CurUninstallStep: TUninstallStep): Boolean;
var
  CurrentPath: String;
  NewPath: String;
  Start: Integer;
  Stop: Integer;
  Entry: String;
begin
  { Remove our exact PATH entry so a later install starts clean. Split on ';'
    and rebuild without the matching entry, for the same reason
    PathHasEntry compares whole entries. }
  Result := True;
  if CurUninstallStep <> usPostUninstall then
    Exit;

  if not RegQueryStringValue(HKCU, 'Environment', 'Path', CurrentPath) then
    Exit;
  if not PathHasEntry(CurrentPath, ExpandConstant('{app}')) then
    Exit;

  NewPath := '';
  Start := 1;
  while Start <= Length(CurrentPath) do
  begin
    if CurrentPath[Start] = ';' then
    begin
      Inc(Start);
      Continue;
    end;

    Stop := Start;
    while (Stop <= Length(CurrentPath)) and (CurrentPath[Stop] <> ';') do
      Inc(Stop);
    Entry := Copy(CurrentPath, Start, Stop - Start);

    if CompareText(Trim(Entry), ExpandConstant('{app}')) <> 0 then
    begin
      if NewPath <> '' then
        NewPath := NewPath + ';';
      NewPath := NewPath + Trim(Entry);
    end;

    Start := Stop;
  end;

  if RegWriteStringValue(HKCU, 'Environment', 'Path', NewPath) then
    Result := True;
end;