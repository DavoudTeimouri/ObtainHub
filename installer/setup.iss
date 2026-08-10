; Inno Setup Script for ObtainHub
; Windows x64 installer with per-user/all-users choice, PATH addition, uninstall data removal prompt

#define AppName "ObtainHub"
#define AppVersion "0.1.0.3"
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
; SetupIconFile=..\assets\icon.ico

[Files]
Source: "..\dist\ohub.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Registry]
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "PATH"; ValueData: "{app};%PATH%"; Flags: preservestringtype uninsdeletevalue
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "PATH"; ValueData: "{app};%PATH%"; Flags: preservestringtype uninsdeletevalue

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\ObtainHub"

[Code]
var
  RemoveDataPage: TWizardPage;
  RemoveDataCheckBox: TCheckBox;

procedure CurUninstallStepChange(CurUninstallStep: TUninstallStep);
var
  RemoveData: Boolean;
begin
  if CurUninstallStep = usUninstall then begin
    RemoveDataPage := CreateCustomPage(wpWelcome, 'Remove User Data?', 'Do you want to remove your ObtainHub configuration and cache data?');
    RemoveDataCheckBox := TCheckBox.Create(RemoveDataPage);
    with RemoveDataCheckBox do begin
      Parent := RemoveDataPage.Surface;
      Caption := 'Remove configuration and cache data (%LOCALAPPDATA%\ObtainHub)';
      Top := 10;
      Left := 10;
      Width := RemoveDataPage.SurfaceWidth - 20;
      Checked := True;
      Name := 'RemoveDataCheckBox';
    end;
    RemoveDataPage.Show;
  end;
  if CurUninstallStep = usPostUninstall then begin
    RemoveData := True;
    if Assigned(RemoveDataPage) then begin
      RemoveDataCheckBox := TCheckBox(RemoveDataPage.FindComponent('RemoveDataCheckBox'));
      if Assigned(RemoveDataCheckBox) then
        RemoveData := RemoveDataCheckBox.Checked;
    end;
    if RemoveData then begin
      DeleteFile(ExpandConstant('{localappdata}\ObtainHub\*'), True);
      RemoveDir(ExpandConstant('{localappdata}\ObtainHub'));
    end;
  end;
end;