; ObtainHub Inno Setup Script
; Compiles the EXE installer

#define MyAppName "ObtainHub"
#define MyAppVersion "0.1.0-beta.3"
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
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=.
OutputBaseFilename=ObtainHub-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "path"; Description: "Add Ohub to PATH"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\ohub.exe"; DestDir: "{app}"; Flags: ignoreversion
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\ObtainHub"
Type: filesandordirs; Name: "{commonappdata}\ObtainHub"

[Code]
var
  RemoveDataPage: TWizardPage;
  RemoveDataCheck: TNewCheckBox;

procedure InitializeWizard();
begin
  RemoveDataPage := CreateCustomPage(wpWelcome, 'Remove Data', 'Choose whether to remove application data');
  RemoveDataCheck := TNewCheckBox.Create(RemoveDataPage);
  RemoveDataCheck.Parent := RemoveDataPage.Surface;
  RemoveDataCheck.Top := 0;
  RemoveDataCheck.Left := 0;
  RemoveDataCheck.Width := RemoveDataPage.Surface.Width;
  RemoveDataCheck.Height := 30;
  RemoveDataCheck.Caption := 'Remove all application data (settings, cache, logs) from %LOCALAPPDATA%\ObtainHub and %ALLUSERSPROFILE%\ObtainHub';
  RemoveDataCheck.Checked := False;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataPath: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if RemoveDataCheck.Checked then
    begin
      DataPath := ExpandConstant('{localappdata}\ObtainHub');
      if DirExists(DataPath) then
        DelTree(DataPath, True, True, True);
      
      DataPath := ExpandConstant('{commonappdata}\ObtainHub');
      if DirExists(DataPath) then
        DelTree(DataPath, True, True, True);
    end;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpReady then
  begin
    if IsTaskSelected('path') then
    begin
      // Add to PATH will be handled by the installer
    end;
  end;
end;

procedure RegisterPreviousData(PreviousDataKey: Integer);
begin
  // Store the remove data choice for uninstall
  SetPreviousData(PreviousDataKey, 'RemoveData', RemoveDataCheck.Checked);
end;