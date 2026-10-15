#define MyAppName "OctoShip for GitHub"
#define MyAppVersion "1.6.1-preview.14"
#ifndef PayloadDir
#define PayloadDir "payload"
#endif
#define MyAppPublisher "OctoShip"
#define MyAppExeName "OctoShip.exe"

[Setup]
AppId={{D20A79DA-2867-4D72-90CC-2C0CD8F55B2E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\OctoShip for GitHub
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
AppMutex=Local\OctoCat.SingleInstance
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=..\installers
OutputBaseFilename=OctoShip-Setup-v{#MyAppVersion}-win-x64
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no
Uninstallable=yes
AppComments=Windows desktop uploader for GitHub
AppSupportURL=https://github.com/ghostventure/OctoShip
VersionInfoVersion=1.6.1.14
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=OctoShip for GitHub installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=1.6.1.14
MinVersion=10.0.19041

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel2=Installs OctoShip for GitHub for your Windows user. No GitHub account or credentials are included; add your own account after launch. This package includes the .NET 10 desktop runtime. Git for Windows with Git Credential Manager is required for GitHub sign-in.

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\SECURITY-OPERATIONS.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{autoprograms}\{#MyAppName}\Security and account guide"; Filename: "{app}\SECURITY-OPERATIONS.md"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: postinstall nowait skipifsilent
