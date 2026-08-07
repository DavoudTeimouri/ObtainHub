; ObtainHub Inno Setup Script - Minimal test
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
DefaultDirName={autopf}\{#MyAppName}
OutputDir=.
OutputBaseFilename=ObtainHub-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\ohub.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"