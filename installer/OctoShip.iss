#define MyAppName "OctoShip for GitHub"
#define MyAppVersion "1.6.1-preview.18"
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
SetupIconFile=..\branding\octoship.ico
CloseApplications=no
RestartApplications=no
Uninstallable=yes
AppComments=Windows desktop uploader for GitHub
AppSupportURL=https://github.com/ghostventure/OctoShip
VersionInfoVersion=1.6.1.18
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=OctoShip for GitHub installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=1.6.1.18
MinVersion=10.0.19041
LicenseFile=..\docs\legal\OCTOSHIP-TERMS-AND-NOTICES.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel2=Installs OctoShip for GitHub for your Windows user. If the .NET 10 desktop runtime is missing, Setup downloads and installs it from Microsoft. An internet connection is required for that step. No GitHub account or credentials are included; add your own account after launch. Git for Windows with Git Credential Manager is required for GitHub sign-in.

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\branding\octoship-primary.svg"; DestDir: "{app}\Branding"; Flags: ignoreversion
Source: "..\branding\octoship-mark.svg"; DestDir: "{app}\Branding"; Flags: ignoreversion
Source: "..\branding\octoship.ico"; DestDir: "{app}\Branding"; Flags: ignoreversion
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

[Code]
const
  DesktopRuntime10Url = 'https://aka.ms/dotnet/10.0/windowsdesktop-runtime-win-x64.exe';
  DesktopRuntimeInstaller = 'dotnet-desktop-runtime-10-win-x64.exe';

function HasDesktopRuntime10At(const RuntimeDirectory: String): Boolean;
var
  FindRec: TFindRec;
  Found: Boolean;
begin
  Result := False;
  if FindFirst(RuntimeDirectory + '\\*', FindRec) then begin
    try
      repeat
        if (CompareText(Copy(FindRec.Name, 1, 3), '10.') = 0) and
           DirExists(RuntimeDirectory + '\\' + FindRec.Name) then begin
          Result := True;
          break;
        end;
        Found := FindNext(FindRec);
      until not Found;
    finally
      FindClose(FindRec);
    end;
  end;
end;

function HasDesktopRuntime10: Boolean;
begin
  Result := HasDesktopRuntime10At(ExpandConstant('{pf}\\dotnet\\shared\\Microsoft.WindowsDesktop.App')) or
    HasDesktopRuntime10At(ExpandConstant('{userprofile}\\.dotnet\\shared\\Microsoft.WindowsDesktop.App')) or
    HasDesktopRuntime10At(ExpandConstant('{userappdata}\\Programs\\dotnet\\shared\\Microsoft.WindowsDesktop.App'));
end;

function InitializeSetup: Boolean;
var
  ExitCode: Integer;
  RuntimeInstallerPath: String;
begin
  Result := True;
  if HasDesktopRuntime10 then
    exit;

  if MsgBox('.NET 10 Desktop Runtime is required. Setup can download and install it from Microsoft now. An internet connection is required. Continue?', mbConfirmation, MB_YESNO) <> IDYES then begin
    Result := False;
    exit;
  end;

  RuntimeInstallerPath := ExpandConstant('{tmp}\\' + DesktopRuntimeInstaller);
  try
    DownloadTemporaryFile(DesktopRuntime10Url, DesktopRuntimeInstaller, '', nil);
  except
    MsgBox('Setup could not download the .NET 10 Desktop Runtime from Microsoft. Check your internet connection and run Setup again.', mbError, MB_OK);
    Result := False;
    exit;
  end;

  if not Exec(RuntimeInstallerPath, '/install /quiet /norestart', '', SW_SHOW, ewWaitUntilTerminated, ExitCode) then begin
    MsgBox('Setup could not start the .NET 10 Desktop Runtime installer.', mbError, MB_OK);
    Result := False;
    exit;
  end;

  if (ExitCode <> 0) and (ExitCode <> 3010) then begin
    MsgBox(Format('The .NET 10 Desktop Runtime installer returned exit code %d. Setup cannot continue.', [ExitCode]), mbError, MB_OK);
    Result := False;
    exit;
  end;

  if not HasDesktopRuntime10 then begin
    MsgBox('The .NET 10 Desktop Runtime was not found after installation. Setup cannot continue.', mbError, MB_OK);
    Result := False;
  end;
end;
