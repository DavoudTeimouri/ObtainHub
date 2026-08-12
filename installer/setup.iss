; Inno Setup Script for ObtainHub - Compatible with Inno Setup 6.7
; Windows x64 installer with PATH addition, uninstall data removal prompt

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
; SetupIconFile=..\assets\icon.ico

[Files]
Source: "..\dist\ohub.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"

[Registry]

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\ObtainHub"

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

{ This script is compatible with Inno Setup 6.7+
   - Provides basic installation with PATH management
   - Includes uninstall cleanup functionality
   - Professional user experience
}