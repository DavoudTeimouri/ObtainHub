; Inno Setup Script for ObtainHub - Optimized for Inno Setup 6.8+
; Windows x64 installer with modern PATH management and clean uninstall

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
ShowLanguageDialog=no
CloseAfterInstall=no
AllowNoIcons=no
MinVersion=6.8

[Languages]
Default="English"

[Files]
Source: "..\dist\ohub.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsizeskip

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch ObtainHub"; StatusMsg: "Starting ObtainHub..."

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"

[Registry]

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\ObtainHub"

[Code]
// Modern PATH manipulation for user-level installation only
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

function RemoveFromPath(const APath: String): Boolean;
var
  CurrentPath: String;
  NewPath: String;
begin
  Result := False;
  
  if not RegQueryStringValue(HKCU, 'Environment', 'PATH', CurrentPath) then
    Exit;
  
  // Remove APath from PATH
  NewPath := StringReplace(CurrentPath, APath + ';', '', [rfReplaceAll]);
  NewPath := StringReplace(NewPath, ';' + APath, '', [rfReplaceAll]);
  NewPath := StringReplace(NewPath, APath, '', [rfReplaceAll]);
  
  // Clean up extra semicolons
  while Pos(';;', NewPath) > 0 do
    NewPath := StringReplace(NewPath, ';;', ';', [rfReplaceAll]);
  
  NewPath := Trim(NewPath);
  
  // Remove leading/trailing semicolons
  if (Length(NewPath) > 0) and (NewPath[1] = ';') then
    Delete(NewPath, 1, 1);
  if (Length(NewPath) > 0) and (NewPath[Length(NewPath)] = ';') then
    SetLength(NewPath, Length(NewPath) - 1);
  
  Result := RegWriteStringValue(HKCU, 'Environment', 'PATH', NewPath);
end;

// Custom uninstall page for data folder removal option
procedure Uninstall;
var
  RemoveData: Boolean;
  AppPath: String;
begin
  // Show custom uninstall page
  AddMemo('Do you want to remove your ObtainHub configuration and cache data during uninstall?', '', 0);
  AddCheckBox('Remove configuration and cache data (%LOCALAPPDATA%\ObtainHub)', True, 'RemoveData', '');
  
  // Get user's choice
  RemoveData := Get(RemoveData) = '1';
  
  AppPath := ExpandConstant('{app}');
  
  // Remove data folder if requested
  if RemoveData and DirectoryExists(ExpandConstant('{localappdata}\ObtainHub')) then begin
    // Show progress for data removal
    MsgBox('Removing ObtainHub data folder...', mbInformation, MB_OK);
    DeleteFiles(ExpandConstant('{localappdata}\ObtainHub\*'), False, True, True);
    RemoveDir(ExpandConstant('{localappdata}\ObtainHub'), True);
  end;
  
  // Remove from PATH
  RemoveFromPath(AppPath);
  
  // Clean up installation
  DeleteFile(ExpandConstant('{app}\{#AppExeName}'));
  RemoveDir(ExpandConstant('{app}'), False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Msg: String;
begin
  if CurStep = ssPostInstall then begin
    // Add to user PATH (safe, no admin required)
    AppendToPath(ExpandConstant('{app}'));
    
    // Show completion message
    Msg := 'ObtainHub has been successfully installed.' + #13#10 + #13#10 +
           'The application is now available from the Start menu and in PATH.';
    MsgBox(Msg, mbInformation, MB_OK);
  end;
end;

{ Modern Inno Setup 6.8+ features available:
   
   - Silent installation: Add "Silent:" directive to skip welcome pages
   - Custom license: Add license agreement pages
   - Progress bar customization: Enhanced visual feedback
   - File associations: Set file type handling
   - Registry configuration: Pre-populate registry values
   - Internet connection check: Validate connectivity before install
   - Running as administrator: Check and elevate if needed
   
   These features can be added incrementally based on specific requirements.
}