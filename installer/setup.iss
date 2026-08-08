; ObtainHub Inno Setup Script
; Minimal script to verify compilation works

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

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\ohub.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\ObtainHub"; Filename: "{app}\ohub.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\ohub.exe"; Description: "Launch ObtainHub"; Flags: nowait postinstall skipifsilent