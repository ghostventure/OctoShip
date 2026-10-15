#define MyAppName "OctoShip for GitHub"
#define MyAppVersion "1.6.1-preview.15"
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
VersionInfoVersion=1.6.1.15
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=OctoShip for GitHub installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=1.6.1.15
MinVersion=10.0.19041
LicenseFile=..\docs\legal\OCTOSHIP-TERMS-AND-NOTICES.txt
LicenseForceAccept=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel2=Installs OctoShip for GitHub for your Windows user. No GitHub account or credentials are included; add your own account after launch. This package includes the .NET 10 desktop runtime. Git for Windows with Git Credential Manager is required for GitHub sign-in.

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\branding\octoship-primary.svg"; DestDir: "{app}\Branding"; Flags: ignoreversion
Source: "..\branding\octoship-mark.svg"; DestDir: "{app}\Branding"; Flags: ignoreversion
Source: "..\SECURITY-OPERATIONS.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\OCTOSHIP-GUIDE.md"; DestDir: "{app}\Docs"; Flags: ignoreversion
Source: "..\docs\legal\OCTOSHIP-USER-GUIDE.md"; DestDir: "{app}\Docs"; Flags: ignoreversion
Source: "..\docs\legal\OCTOSHIP-PRIVACY-NOTICE.txt"; DestDir: "{app}\Docs"; Flags: ignoreversion
Source: "..\docs\legal\THIRD-PARTY-NOTICES.txt"; DestDir: "{app}\Docs"; Flags: ignoreversion
Source: "..\docs\legal\OCTOSHIP-TERMS-AND-NOTICES.txt"; DestDir: "{app}\Docs"; Flags: ignoreversion
Source: "..\docs\legal\OCTOSHIP-COPYRIGHT-AND-DMCA-NOTICE.txt"; DestDir: "{app}\Docs"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{autoprograms}\{#MyAppName}\Security and account guide"; Filename: "{app}\SECURITY-OPERATIONS.md"
Name: "{autoprograms}\{#MyAppName}\User Guide"; Filename: "{app}\Docs\OCTOSHIP-USER-GUIDE.md"
Name: "{autoprograms}\{#MyAppName}\Privacy Notice"; Filename: "{app}\Docs\OCTOSHIP-PRIVACY-NOTICE.txt"
Name: "{autoprograms}\{#MyAppName}\Third-Party Notices"; Filename: "{app}\Docs\THIRD-PARTY-NOTICES.txt"
Name: "{autoprograms}\{#MyAppName}\Terms and Notices"; Filename: "{app}\Docs\OCTOSHIP-TERMS-AND-NOTICES.txt"
Name: "{autoprograms}\{#MyAppName}\Copyright and DMCA Information"; Filename: "{app}\Docs\OCTOSHIP-COPYRIGHT-AND-DMCA-NOTICE.txt"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: postinstall nowait skipifsilent
