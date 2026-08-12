; Inno Setup Script for ObtainHub
; Windows x64 installer with PATH addition, uninstall data removal prompt, no desktop shortcut, no run after install

#define AppName "ObtainHub"
#define AppVersion "0.1.0.7"
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

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\ObtainHub"

[Code]
function AppendToPath(const APath: String; HKey: Integer; const SubKey: String; const ValueName: String): Boolean;
var
  CurrentPath: String;
  NewPath: String;
begin
  Result := False;
  if not RegKeyExists(HKey, SubKey) then Exit;
  if not RegQueryStringValue(HKey, SubKey, ValueName, CurrentPath) then Exit;
  if Pos(APath, CurrentPath) > 0 then begin
    Result := True;
    Exit;
  end;
  if Length(CurrentPath) > 0 then
    NewPath := CurrentPath + ';' + APath
  else
    NewPath := APath;
  Result := RegWriteStringValue(HKey, SubKey, ValueName, NewPath);
end;

function RemoveFromPath(const APath: String; HKey: Integer; const SubKey: String; const ValueName: String): Boolean;
var
  CurrentPath: String;
  NewPath: String;
begin
  Result := False;
  if not RegKeyExists(HKey, SubKey) then Exit;
  if not RegQueryStringValue(HKey, SubKey, ValueName, CurrentPath) then Exit;
  NewPath := StringReplace(CurrentPath, APath + ';', '', [rfReplaceAll]);
  NewPath := StringReplace(NewPath, ';' + APath, '', [rfReplaceAll]);
  NewPath := StringReplace(NewPath, APath, '', [rfReplaceAll]);
  while Pos(';;', NewPath) > 0 do
    NewPath := StringReplace(NewPath, ';;', ';', [rfReplaceAll]);
  NewPath := Trim(NewPath);
  if (Length(NewPath) > 0) and (NewPath[1] = ';') then
    Delete(NewPath, 1, 1);
  if (Length(NewPath) > 0) and (NewPath[Length(NewPath)] = ';') then
    SetLength(NewPath, Length(NewPath) - 1);
  Result := RegWriteStringValue(HKey, SubKey, ValueName, NewPath);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppPath: String;
begin
  if CurStep = ssPostInstall then begin
    AppPath := ExpandConstant('{app}');
    // Add to user PATH (HKCU)
    AppendToPath(AppPath, HKCU, 'Environment', 'PATH');
    // Add to system PATH (HKLM) - requires admin
    if IsAdminLoggedOn() then
      AppendToPath(AppPath, HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'PATH');
  end;
end;

procedure CurUninstallStepChange(CurUninstallStep: TUninstallStep);
var
  AppPath: String;
  RemoveDataPage: TWizardPage;
  RemoveDataCheckBox: TCheckBox;
  RemoveData: Boolean;
begin
  AppPath := ExpandConstant('{app}');
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
    // Remove from PATH
    RemoveFromPath(AppPath, HKCU, 'Environment', 'PATH');
    if IsAdminLoggedOn() then
      RemoveFromPath(AppPath, HKLM, 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'PATH');
  end;
end;