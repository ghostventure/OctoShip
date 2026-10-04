# OctoShip for GitHub

OctoShip for GitHub finds local files and sends them to GitHub. The original Windows desktop client is in the repository root. A native Linux client is now available in [linux/](linux/README.md), with a desktop launcher, Debian package builder, and tested GitHub upload backend.

## Linux 1.6.0

The native [Linux client](linux/README.md) now includes atomic or per-file batch
uploads, opt-in saved queues, redacted content scanning, fixed-commit folder
comparison, branch and pull-request creation, and draft-first release publishing
with reviewed assets. The native interface has Find & upload and Repository tools
tabs. Build packages with `./linux/packaging/build-deb.sh`; see the Linux guide for
installation, checks, and remaining Windows-only features.

## Use OctoShip on Windows

Install Git for Windows and sign in through Git Credential Manager. Launch `OctoShip.exe`, choose an account, and connect. GitHub tokens stay in memory and are never written to OctoShip settings.

Choose a folder and search by filename or file contents. Search options include regular expressions, exact and case-sensitive matches, file types, size and modified-date filters, hidden files, recursion, excluded folders, sorting, result limits, and cancel. Reparse points are skipped and content searches read at most 2 MiB per file. Review a selected file with image or small-text preview, local SHA-256, and optional text comparison against the remote destination.

Single-file uploads check repository permissions, branches, destination conflicts, and sensitive filename rules. The repository browser can list accessible repositories and folders and check GitHub API connectivity and quota. Batch uploads support up to 100 files, editable paths and messages, ordering, ignore and size rules, rename/replace/skip collision handling, progress, pause, cancel, retry, and GitHub links. The development build adds a single-commit batch option alongside per-file commits.

## Component development preview

The layout preview groups search and results in the left workspace and the GitHub destination in the right panel. Selected-file and folder-batch uploads have separate tabs; advanced search filters open in a flyout. Settings and tools are organized into Projects, Repository tools, Preferences, and Updates & diagnostics tabs. Build this preview separately from an already-running development build with `dotnet build FileToGitHub.csproj -c Release --no-restore -o dist-layout-preview`, then run `dist-layout-preview/OctoShip.exe` after closing the previous OctoShip window.

The working source includes the first priority wave from [COMPONENT-ROADMAP.md](COMPONENT-ROADMAP.md). Existing 1.5.0 release archives and installers do not contain these additions.

- **Batch uploads:** select single-commit mode to publish the reviewed files with one branch update. A moved branch stops publication; updates are never forced. Files are checked again before sending. Closing a batch preserves its queue when privacy mode is off; use **Resume saved batch** with the same repository and branch to recover and review it. Recovery never automatically uploads files and does not persist credentials.
- **Content review:** previews and upload paths scan supported text for likely credentials. Findings contain type and line number, never matched values. Scans are heuristic and bounded to 2 MiB; binary files, archives, and unsupported encodings are explicitly reported as unscanned. Uploads require review when findings exist or scanning is incomplete.
- **Repository workflows:** open the repository browser and choose **Compare / Branch / PR** to compare a local folder against a fixed remote commit, create a branch, or prepare a draft pull request. Comparison reads raw bytes, excludes `.git`, and does not apply other ignore rules or normalize line endings. Incomplete remote trees and local links stop comparison.
- **Release publishing:** **Settings & Tools → Prepare a release** creates a draft and uploads selected assets. Publishing is a separate explicit action. Archives and binaries are not inspected for embedded secrets. If an operation fails after starting, inspect GitHub for a partial draft before retrying.

These additions are validated locally using mock HTTP requests; real GitHub write operations require a connected account and remain a separate integration check. No release is published by building or running the verification harnesses.

The **Settings & Tools** page houses preferences, GitHub repository tools, update controls, a compatibility check, and privacy-safe diagnostics. Its **User Profile** is read-only and summarizes the selected account and current app preferences. The existing-project catalog lists repositories visible to the connected account, including visibility, description, default branch, and last update; filter the list, open a project on GitHub, or select it as an upload target. Settings include credential-free import/export, privacy mode, stable or preview update channel, editable sensitive-file patterns, destination preset management, selective history clearing, and publisher-signature inspection. PDF previews open in the Windows default PDF viewer.

OctoShip detects active Wi-Fi or Ethernet adapters. Before uploads it warns when Wi-Fi is active because transfers may take longer. Upload and update-download progress include a remaining-time estimate when the transfer size is known. The expandable terminal at the bottom records recent transfer filenames, destinations, progress, and outcomes; it does not record tokens.

Developer architecture, build prerequisites, security boundaries, and Linux-port notes are in [DEVELOPMENT.md](DEVELOPMENT.md).

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
