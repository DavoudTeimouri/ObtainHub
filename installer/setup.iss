; ObtainHub Inno Setup Script
; Full featured installer with per-user/all-users choice, PATH addition, uninstall data removal prompt

#define MyAppName "ObtainHub"
#define MyAppVersion "0.1.0-beta.3"
#define MyAppPublisher "ObtainHub"
#define MyAppURL "https://github.com/DavoudTeimouri/ObtainHub"
#define MyAppExeName "ohub.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\ObtainHub
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=Output
OutputBaseFilename=ObtainHub-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=auto
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
DisableDirPage=no
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "addpath"; Description: "Add ObtainHub to system PATH"; GroupDescription: "Additional tasks:"; Flags: unchecked

[Files]
Source: "..\dist\ohub.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\ObtainHub"; Filename: "{app}\ohub.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\ohub.exe"; Description: "Launch ObtainHub"; Flags: nowait postinstall skipifsilent

[Registry]
; Add to PATH if task selected
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{app}"; Flags: preservestringtype; Tasks: addpath; Check: IsPathAlreadyAdded('{app}')
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{app}"; Flags: preservestringtype; Tasks: addpath; Check: IsPathAlreadyAddedCU('{app}')

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\ObtainHub"; Tasks: removedata

[Code]
var
  RemoveDataPage: TInputOptionWizardPage;
  RemoveDataRadio: TNewCheckBox;

function IsPathAlreadyAdded(PathToCheck: string): Boolean;
var
  CurrentPath: string;
begin
  if not RegQueryStringValue(HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'Path', CurrentPath) then
    Result := False
  else
    Result := Pos(';' + PathToCheck + ';', ';' + CurrentPath + ';') > 0;
end;

function IsPathAlreadyAddedCU(PathToCheck: string): Boolean;
var
  CurrentPath: string;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', CurrentPath) then
    Result := False
  else
    Result := Pos(';' + PathToCheck + ';', ';' + CurrentPath + ';') > 0;
end;

procedure CreateRemoveDataPage;
begin
  RemoveDataPage := CreateInputOptionPage(wpWelcome, 
    'Remove User Data', 'Should user data be removed?',
    'Choose whether to remove ObtainHub user data (settings, cache, logs) during uninstallation.',
    True, False);
  RemoveDataRadio := TNewCheckBox.Create(RemoveDataPage);
  RemoveDataRadio.Parent := RemoveDataPage.Surface;
  RemoveDataRadio.Caption := 'Remove all user data (settings, cache, logs in %LOCALAPPDATA%\ObtainHub)';
  RemoveDataRadio.Checked := False;
  RemoveDataRadio.Width := RemoveDataPage.SurfaceWidth - 10;
  RemoveDataRadio.Top := 10;
  RemoveDataRadio.Left := 10;
end;

procedure InitializeWizard;
begin
  CreateRemoveDataPage;
end;

function ShouldRemoveData: Boolean;
begin
  Result := RemoveDataRadio.Checked;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  if CurPageID = RemoveDataPage.ID then
    WizardForm.NextButton.Enabled := True;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    SetUninstallData('removedata', RemoveDataRadio.Checked);
end;

function InitializeUninstall: Boolean;
begin
  Result := True;
  CreateRemoveDataPage;
  RemoveDataPage.Show;
end;