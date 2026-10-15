# OctoShip developer notes

For exhaustive, end-to-end documentation across all features, architecture, and verification, see [OCTOSHIP-GUIDE.md](OCTOSHIP-GUIDE.md). Account retention, the 30-minute inactivity lock, Windows authentication, and its verification boundaries are documented in [ACCOUNT-SESSION.md](ACCOUNT-SESSION.md). The current Windows development target is `net10.0-windows10.0.19041.0`; older target-path references below describe previous releases. The [P0 handoff](P0-HANDOFF.md) supersedes older Windows runtime, publishing-guard, update, and packaging instructions. Windows publisher signing and signed update manifests are optional distribution assurances outside core scope.

This document describes the source snapshot in this repository and the work needed to combine it with a Linux version.

## Platform status

The C# Windows client currently targets `net10.0-windows10.0.19041.0`; its WPF views and code-behind use Windows-specific windows, dialogs, clipboard, file pickers, Explorer, and PowerShell. The native Python/Tk Linux 1.7.0 client lives separately in `linux/`; see [Linux setup, feature coverage, packaging, and tests](linux/README.md). Its UI-independent backend implements GitHub REST upload, atomic batch, comparison, branch/PR, and release workflows, with GitHub CLI credential integration. The Windows client cannot run on Linux by selecting a Linux runtime identifier.

To produce a supported Linux desktop app, keep the existing Windows client working while extracting platform-neutral logic and implementing a cross-platform UI. Avalonia is a reasonable C# UI choice. Then add Linux implementations for file selection, clipboard, URI/file launching, application data paths, single-instance behavior, credential setup, and updates. Build and smoke-test packages on Linux before distributing them. The Windows Inno Setup script is not a Linux installer.

## Source map

| File(s) | Responsibility |
| --- | --- |
| `App.xaml`, `App.xaml.cs`, `SplashWindow.*` | WPF startup, splash screen, and single-instance mutex (`Local\\OctoCat.SingleInstance`). |
| `MainWindow.xaml`, `MainWindow.xaml.cs` | Main search/upload UI, account connection, repository catalog, settings/tools navigation, updater, transfer progress and terminal. Most presentation and application orchestration currently lives in this code-behind. |
| `SearchService.cs` | Local file discovery and content-search behavior. |
| `GitHubRepositoryService.cs` | GitHub repository API models and repository operations. |
| `UploadQueueService.cs`, `BatchUploadWindow.*`, `PersistentUploadQueueStore.cs`, `GitHubAtomicBatchService.cs` | Batch planning, filtering, collision choices, progress, recovery, per-file or single-commit publication. |
| `ContentSecretScanner.cs` | Bounded content scanning that returns redacted finding metadata. |
| `RepositoryWorkflowService.cs`, `RepositoryWorkflowWindow.cs` | Fixed-commit folder comparison and explicit branch/pull-request creation. |
| `GitHubReleaseService.cs`, `ReleasePublisherWindow.cs` | Draft releases, asset uploads, and explicit publishing. |
| `FileSafetyRules.cs`, `FileReviewWindow.*` | Sensitive-file checks and local/remote file review. |
| `RepositoryToolsWindow.*` | Repository folder browser and GitHub connection/quota tools. |
| `OctoCatPreferencesService.cs`, `OctoCatSettingsWindow.*` | Preference normalization/import/export, history clearing, publisher verification, and settings UI. |
| `installer/OctoShip.iss` | Per-user Windows installer definition; it packages the separately published `installer/payload` files. |

The WPF event handlers call application logic directly, so the existing classes are not yet a clean cross-platform UI/backend split. A port should move reusable behavior and data models into a UI-independent project before replacing the views.

## Visual Studio Code

The repository's `.vscode/` directory recommends C# Dev Kit and provides a Debug build task, a Windows WPF launch configuration, and excludes generated build/package folders from Explorer and search. Open the repository root in VS Code with the .NET 10 SDK installed. Run **Terminal → Run Build Task** to build or **Run and Debug → Launch OctoShip** to start the app under the debugger. These settings target Windows; they do not configure the separate Linux client.

The Windows app can hand a selected file or search-root folder to VS Code from the Files view. `VisualStudioCodeSupport.cs` resolves stable or Insiders `Code.exe` from standard per-user and machine-wide installation locations and starts it with a separate argument list. A missing editor is reported without affecting search or upload. This integration opens files/folders for editing; it does not install extensions, commit changes, or send files to GitHub automatically.

## Authentication, settings, and privacy

Git for Windows and Git Credential Manager are required by this build. The app asks Credential Manager to list, add, and retrieve GitHub account credentials. Access tokens are held in memory for API requests and are not saved in OctoShip preference files. Linux work should use Git Credential Manager's Linux support or another system credential store; do not put tokens in settings, source, environment files committed to the repository, or logs.

The Windows app stores preferences under `%LOCALAPPDATA%\\OctoShipForGitHub` and can copy preference files from the former `%LOCALAPPDATA%\\OctoCat` directory on first launch. Privacy mode suppresses saved search/repository history. A Linux client needs to use XDG config/data locations and decide explicitly whether to migrate compatible JSON preferences. Windows paths and registry-based publisher checks must not be reused as Linux paths or trust checks.

## Windows build and package

Requirements to build and package the Windows client are the .NET 10 SDK, Git for Windows with Git Credential Manager, and Inno Setup 6. The current Windows installer is self-contained and bundles the .NET 10 runtime; a separate runtime installation is not required to run it.

```powershell
dotnet build FileToGitHub.csproj -c Release
dotnet publish FileToGitHub.csproj -c Release -r win-x64 --self-contained true -o dist-OctoShip
Compress-Archive -Path dist-OctoShip\* -DestinationPath OctoShip-for-GitHub-win-x64.zip -Force
dotnet publish FileToGitHub.csproj -c Release -r win-x64 --self-contained true -p:DebugType=None -o installer\payload
ISCC.exe installer\OctoShip.iss
```

The setup output name/version is configured in `installer/OctoShip.iss`. It installs per-user under LocalAppData, creates a Start Menu shortcut, optionally creates a desktop shortcut, and registers an uninstaller. The current package is self-contained and bundles .NET 10; it is not Authenticode-signed. Git for Windows with Git Credential Manager is required for GitHub sign-in. Preserve user settings and Credential Manager entries when uninstalling.

The component preview includes focused offline harnesses under `verification/`. Their source templates avoid the application project's default C# compilation glob. Build the app and run these harnesses before packaging. Mock HTTP verification does not establish live GitHub integration or installer behavior. The Linux package builder and offline/GUI harnesses are documented in `linux/README.md`; verification evidence is in `verification/linux-port-1.6.0.md`. Linux 1.7.0 also has a self-contained runtime installer and bundled Debian package; see `linux/packaging/README.md`. Linux CI and AppImage packaging remain future work.

## Release and update configuration

The source repository and updater feed are `ghostventure/OctoShip`. See [the current guide](OCTOSHIP-GUIDE.md#github-automatic-updates) for automatic installation, authentication, release asset naming, hash verification and package-version checks. The original 1.5.0 source upload did not publish a release or binaries.

## Repository hygiene

`.gitignore` excludes build output, installers, archives, and compiled files. Do not commit local settings, tokens, Credential Manager output, signing keys, or generated packages. The GitHub repository is public (verified 2026-10-11); review source, history, documentation and release assets accordingly. No license file is included in this snapshot; do not assume public redistribution terms until a license is chosen.

## Shipping workflow extensions

[SHIPPING-PREPARATION.md](SHIPPING-PREPARATION.md) records architecture, storage, safety limits and verification for feature additions 13–28. [SHIPPING-WORKBENCH.md](SHIPPING-WORKBENCH.md) covers features 1–12. The preparation module uses ShippingPreparationWindow, ShippingInspectionService and SelectiveTextChanges; shared atomic timeout reconciliation lives in GitHubAtomicBatchService and move annotations in RepositoryWorkflowService.

## Linux October 11 port (1.7.0)

`workbench.py` handles reviewed shipment/delivery; `preparation.py` handles offline
plans and pinned selective publication; `inspection.py` contains bounded local
checks. `workbench_ui.py` exposes them as native tabs. `session.py` owns the
persistent shield, PAM authentication and optional logind monitor; `storage.py`
provides private atomic JSON saves. Shared API transport enforces the lock and
strips authorization when following signed asset-download redirects. The atomic
uploader reconciles uncertain ref updates without retrying PATCH.

Run the commands in [linux/README.md](linux/README.md). Shipping and lock
regressions are in `linux/tests/test_shipping.py` and `gui_shipping.py`.
See [port verification](verification/linux-port-1.7.0.md) for evidence and limits,
and the [release handoff](docs/linux-1.7.0-handoff.md) for published artifacts,
architecture/storage, recovery, reproduction commands and future release procedures.
