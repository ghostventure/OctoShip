# OctoShip developer notes

This document describes the source snapshot in this repository and the work needed to combine it with a Linux version.

## Platform status

The original 1.5.0 C# application is Windows-only. The native Python/Tk Linux client now lives in `linux/`; see [Linux setup, feature coverage, packaging, and tests](linux/README.md). Its UI-independent backend implements the same GitHub REST workflow, with GitHub CLI credential integration, without requiring the Windows UI assemblies. The following platform notes describe the original C# client. `FileToGitHub.csproj` targets `net6.0-windows` and enables WPF and Windows Forms. Its XAML views and code-behind use WPF windows, controls, dialogs, clipboard, file pickers, Explorer, and PowerShell. Publishing these files with a Linux runtime identifier does not make the application runnable on Linux.

To produce a supported Linux desktop app, keep the existing Windows client working while extracting platform-neutral logic and implementing a cross-platform UI. Avalonia is a reasonable C# UI choice. Then add Linux implementations for file selection, clipboard, URI/file launching, application data paths, single-instance behavior, credential setup, and updates. Build and smoke-test packages on Linux before distributing them. The Windows Inno Setup script is not a Linux installer.

## Source map

| File(s) | Responsibility |
| --- | --- |
| `App.xaml`, `App.xaml.cs`, `SplashWindow.*` | WPF startup, splash screen, and single-instance mutex (`Local\\OctoCat.SingleInstance`). |
| `MainWindow.xaml`, `MainWindow.xaml.cs` | Main search/upload UI, account connection, repository catalog, settings/tools navigation, updater, transfer progress and terminal. Most presentation and application orchestration currently lives in this code-behind. |
| `SearchService.cs` | Local file discovery and content-search behavior. |
| `GitHubRepositoryService.cs` | GitHub repository API models and repository operations. |
| `UploadQueueService.cs`, `BatchUploadWindow.*` | Batch planning, filtering, collision choices, progress, pause/cancel/retry UI. A batch currently creates one commit per file. |
| `FileSafetyRules.cs`, `FileReviewWindow.*` | Sensitive-file checks and local/remote file review. |
| `RepositoryToolsWindow.*` | Repository folder browser and GitHub connection/quota tools. |
| `OctoCatPreferencesService.cs`, `OctoCatSettingsWindow.*` | Preference normalization/import/export, history clearing, publisher verification, and settings UI. |
| `installer/OctoShip.iss` | Per-user Windows installer definition; it packages the separately published `installer/payload` files. |

The WPF event handlers call application logic directly, so the existing classes are not yet a clean cross-platform UI/backend split. A port should move reusable behavior and data models into a UI-independent project before replacing the views.

## Authentication, settings, and privacy

Git for Windows and Git Credential Manager are required by this build. The app asks Credential Manager to list, add, and retrieve GitHub account credentials. Access tokens are held in memory for API requests and are not saved in OctoShip preference files. Linux work should use Git Credential Manager's Linux support or another system credential store; do not put tokens in settings, source, environment files committed to the repository, or logs.

The Windows app stores preferences under `%LOCALAPPDATA%\\OctoShipForGitHub` and can copy preference files from the former `%LOCALAPPDATA%\\OctoCat` directory on first launch. Privacy mode suppresses saved search/repository history. A Linux client needs to use XDG config/data locations and decide explicitly whether to migrate compatible JSON preferences. Windows paths and registry-based publisher checks must not be reused as Linux paths or trust checks.

## Build and package

Requirements for the Windows build are the .NET 6 SDK, the .NET Windows Desktop Runtime to run the framework-dependent app, Git for Windows with Git Credential Manager, and Inno Setup 6 to compile the installer.

```powershell
dotnet build FileToGitHub.csproj -c Release
dotnet publish FileToGitHub.csproj -c Release --no-restore -o dist-OctoShip-v15
Compress-Archive -Path dist-OctoShip-v15\* -DestinationPath OctoShip-for-GitHub-v1.5.0-win-x64.zip -Force
dotnet publish FileToGitHub.csproj -c Release --no-restore -p:DebugType=None -o installer\payload
ISCC.exe installer\OctoShip.iss
```

The setup output is `installers/OctoShip-Setup-v1.5.0-win-x64.exe`. It installs per-user under LocalAppData, creates a Start Menu shortcut, optionally creates a desktop shortcut, and registers an uninstaller. The installer currently requires a compatible .NET Windows Desktop Runtime and Git for Windows; it is not self-contained or Authenticode-signed. Preserve user settings and Credential Manager entries when uninstalling.

This repository snapshot has no automated test project. At minimum, build the app and launch the installed package on Windows. A future Linux release needs Linux CI/build tooling and real package-install/launch checks for each advertised format, such as `.deb` and AppImage.

## Release and update configuration

The source repository is `ghostventure/OctoShip` and its default branch is `main`. The app's updater currently defaults to `ghostventure/OctoCat` in `MainWindow.xaml.cs`. That repository was not found in the signed-in GitHub account when this source snapshot was published. Before publishing releases, point the updater at the actual release repository and publish the exact `OctoShip-win-x64.zip` asset expected by the updater, with GitHub's SHA-256 asset digest. The 1.5.0 source upload did not publish a release or binaries.

## Repository hygiene

`.gitignore` excludes build output, installers, archives, and compiled files. Do not commit local settings, tokens, Credential Manager output, signing keys, or generated packages. The GitHub repository is private. No license file is included in this snapshot; do not assume public redistribution terms until a license is chosen.
