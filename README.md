# OctoShip for GitHub 1.5.0

OctoShip for GitHub is a Windows desktop app for finding local files and sending them to GitHub.

## Use OctoShip

Install Git for Windows and sign in through Git Credential Manager. Launch `OctoShip.exe`, choose an account, and connect. GitHub tokens stay in memory and are never written to OctoShip settings.

Choose a folder and search by filename or file contents. Search options include regular expressions, exact and case-sensitive matches, file types, size and modified-date filters, hidden files, recursion, excluded folders, sorting, result limits, and cancel. Reparse points are skipped and content searches read at most 2 MiB per file. Review a selected file with image or small-text preview, local SHA-256, and optional text comparison against the remote destination.

Single-file uploads check repository permissions, branches, destination conflicts, and sensitive filename rules. The repository browser can list accessible repositories and folders and check GitHub API connectivity and quota. Batch uploads support up to 100 files, editable paths and messages, ordering, ignore and size rules, rename/replace/skip collision handling, progress, pause, cancel, retry, and GitHub links. Batches currently create one commit per file.

The **Settings & Tools** page houses preferences, GitHub repository tools, update controls, a compatibility check, and privacy-safe diagnostics. Its **User Profile** is read-only and summarizes the selected account and current app preferences. The existing-project catalog lists repositories visible to the connected account, including visibility, description, default branch, and last update; filter the list, open a project on GitHub, or select it as an upload target. Settings include credential-free import/export, privacy mode, stable or preview update channel, editable sensitive-file patterns, destination preset management, selective history clearing, and publisher-signature inspection. PDF previews open in the Windows default PDF viewer.

OctoShip detects active Wi-Fi or Ethernet adapters. Before uploads it warns when Wi-Fi is active because transfers may take longer. Upload and update-download progress include a remaining-time estimate when the transfer size is known. The expandable terminal at the bottom records recent transfer filenames, destinations, progress, and outcomes; it does not record tokens.

OctoShip checks the existing `ghostventure/OctoCat` release repository at startup. Stable releases use GitHub's latest release; Preview uses the latest published prerelease. The updater verifies GitHub's SHA-256 digest before staging an update and asks before installing it. New releases must attach `OctoShip-win-x64.zip` containing `OctoShip.exe` and `OctoShip.dll`. The release source and renamed update asset have not been verified as published. Internet access and a writable install folder are required.

Settings are stored under `%LOCALAPPDATA%\OctoShipForGitHub`. On first launch, the app copies existing preference files from `%LOCALAPPDATA%\OctoCat` when present; the old files are left intact. Privacy mode suppresses saved search and repository history. Portable settings exports exclude credentials and machine-local paths.

## Build

Build with `dotnet build FileToGitHub.csproj -c Release`. Publish the framework-dependent Windows app with:

```powershell
dotnet publish FileToGitHub.csproj -c Release --no-restore -o dist-OctoShip-v15
Compress-Archive -Path dist-OctoShip-v15\* -DestinationPath OctoShip-for-GitHub-v1.5.0-win-x64.zip -Force
dotnet publish FileToGitHub.csproj -c Release --no-restore -p:DebugType=None -o installer\payload
ISCC.exe installer\OctoShip.iss
```

Build the per-user Windows installer with Inno Setup 6 using the commands above. The setup executable is written to `installers\OctoShip-Setup-v1.5.0-win-x64.exe`. Setup installs under the current user's LocalAppData, creates Start Menu shortcuts, offers an optional desktop shortcut, and registers an uninstaller. User settings and Git credentials are preserved on uninstall. The installer contains the framework-dependent build; Git for Windows and a compatible .NET Windows Desktop Runtime (6 or later) remain runtime requirements. Publisher verification will report unsigned builds until an Authenticode certificate is configured.
