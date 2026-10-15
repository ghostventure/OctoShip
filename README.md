# OctoShip for GitHub

**Current Windows build: 1.6.1-preview.10 (2026-10-15).** The self-contained x64 installer includes the .NET 10 desktop runtime. GitHub auto-connect, an option to skip OctoShip's own Windows-authentication inactivity prompt, startup readiness checks, bounded file traversal, busy-file recovery, safer content previews, a CycloneDX release SBOM, and additional security/performance fixes are included. See the [P1 implementation and installation handoff](P1-HANDOFF.md) for feature and verification details. This locally built preview has not been published as a GitHub release. The installer/app are unsigned. The updater is active and verifies GitHub release downloads over HTTPS against GitHub's SHA-256 asset digest. Linux is unchanged by this Windows pass.

The Windows 1.6.0-preview.2 build now retains account/workspace preferences and locks after 30 minutes of inactivity, with Windows Hello or Windows account password unlocking. See [account retention and session protection](ACCOUNT-SESSION.md) for behavior and verification boundaries.

OctoShip for GitHub finds local files and sends them to GitHub. The original Windows desktop client is in the repository root. A native Linux client is now available in [linux/](linux/README.md), with a desktop launcher, Debian package builder, and tested GitHub upload backend.

## Linux 1.8.0 GUI preview

The current Linux source includes a modern charcoal/violet interface, responsive
sidebar navigation, rounded controls, smoother system fonts, and expandable upload
settings. The installed preview passed 86 backend and 15 GUI workflow tests, plus
offline installer verification. See the [GUI refresh documentation](docs/linux-1.8.0-gui-refresh.md)
for build instructions, runtime selection, checksums, and rollback details.
The packaged stable download remains Linux 1.7.0 below.

## Linux 1.7.0

**Published:** [Download Linux 1.7.0](https://github.com/ghostventure/OctoShip/releases/tag/linux-v1.7.0)
(marked Latest on 2026-10-11). [Complete release and maintainer handoff](docs/linux-1.7.0-handoff.md).

The native [Linux client](linux/README.md) now ports the latest Windows shipping
workbench, offline preparation and selective publishing, inspection and delivery
checks, display/privacy settings, and a persistent inactivity lock using Linux PAM.
See the Linux guide for platform differences and authentication limits. It includes atomic or per-file batch
uploads, opt-in saved queues, redacted content scanning, fixed-commit folder
comparison, branch and pull-request creation, and draft-first release publishing
with reviewed assets. The native interface has Find & upload, Repository tools,
and Shipping workbench tabs. Build a self-contained installer with `python3 linux/packaging/build-standalone.py`.
It bundles Python, Tcl/Tk, GitHub CLI, and certificates, including a dark installer
window and offline installation. See the Linux guide for installation, checks, and
remaining Windows-only features.

## Use OctoShip on Windows

Install Git for Windows with Git Credential Manager and sign in. The Windows installer includes the .NET 10 desktop runtime; no separate .NET runtime install is needed. Launch OctoShip, choose an account, and connect. GitHub tokens stay in memory and are never written to OctoShip settings.

Choose a folder and search by filename or file contents. Search options include regular expressions, exact and case-sensitive matches, file types, size and modified-date filters, hidden files, recursion, excluded folders, sorting, result limits, and cancel. Reparse points are skipped and content searches read at most 2 MiB per file. Review a selected file with image or small-text preview, local SHA-256, and optional text comparison against the remote destination.

Single-file uploads check repository permissions, branches, destination conflicts, and sensitive filename rules. The repository browser can list accessible repositories and folders and check GitHub API connectivity and quota. Batch uploads support up to 100 files, editable paths and messages, ordering, ignore and size rules, rename/replace/skip collision handling, progress, pause, cancel, retry, and GitHub links. The development build adds a single-commit batch option alongside per-file commits.

## Component development preview

The layout preview groups search and results in the left workspace and the GitHub destination in the right panel. Selected-file and folder-batch uploads have separate tabs; advanced search filters open in a flyout. Settings and tools are organized into Projects, Repository tools, Preferences, and Updates & diagnostics tabs. Build this preview separately from an already-running development build with `dotnet build FileToGitHub.csproj -c Release --no-restore -o dist-layout-preview`, then run `dist-layout-preview/OctoShip.exe` after closing the previous OctoShip window.

The working Windows source includes the implemented priority waves documented in [P1-HANDOFF.md](P1-HANDOFF.md). The local preview.10 package includes the current Windows additions; older 1.5.0 and 1.6.0 packages do not. The improvement backlog remains partially open.

- **Batch uploads:** select single-commit mode to publish the reviewed files with one branch update. A moved branch stops publication; updates are never forced. Files are checked again before sending. Closing a batch preserves its queue when privacy mode is off; use **Resume saved batch** with the same repository and branch to recover and review it. Recovery never automatically uploads files and does not persist credentials.
- **Content review:** previews and upload paths scan supported text for likely credentials. Findings contain type and line number, never matched values. Scans are heuristic and bounded to 2 MiB; binary files, archives, and unsupported encodings are explicitly reported as unscanned. Uploads require review when findings exist or scanning is incomplete.
- **Repository workflows:** open the repository browser and choose **Compare / Branch / PR** to compare a local folder against a fixed remote commit, create a branch, or prepare a draft pull request. Comparison reads raw bytes, excludes `.git`, and does not apply other ignore rules or normalize line endings. Incomplete remote trees and local links stop comparison.
- **Release publishing:** **Settings & Tools → Prepare a release** creates a draft and uploads selected assets. Publishing is a separate explicit action. Archives and binaries are not inspected for embedded secrets. If an operation fails after starting, inspect GitHub for a partial draft before retrying.

These additions are validated locally using mock HTTP requests; real GitHub write operations require a connected account and remain a separate integration check. No release is published by building or running the verification harnesses.

The **Settings & Tools** page houses preferences, GitHub repository tools, update controls, a compatibility check, and privacy-safe diagnostics. Its **User Profile** is read-only and summarizes the selected account and current app preferences. The existing-project catalog lists repositories visible to the connected account, including visibility, description, default branch, and last update; filter the list, open a project on GitHub, or select it as an upload target. Settings include credential-free import/export, privacy mode, stable or preview update channel, editable sensitive-file patterns, destination preset management, selective history clearing, and publisher-signature inspection. Display preferences include 15 color themes that apply across windows and persist locally; see the [theme guide](OCTOSHIP-GUIDE.md#uniform-gui-and-extension-rules) for names and selection steps. PDF previews open in the Windows default PDF viewer.

OctoShip detects active Wi-Fi or Ethernet adapters. Before uploads it warns when Wi-Fi is active because transfers may take longer. Upload and update-download progress include a remaining-time estimate when the transfer size is known. The expandable terminal at the bottom records recent transfer filenames, destinations, progress, and outcomes; it does not record tokens.

Developer architecture, build prerequisites, security boundaries, and Linux-port notes are in [DEVELOPMENT.md](DEVELOPMENT.md). For comprehensive end-to-end technical documentation covering all features, design systems, and security mechanisms, see [OCTOSHIP-GUIDE.md](OCTOSHIP-GUIDE.md).

The updater checks the public GitHub release feed at startup and every two minutes while enabled and idle. It downloads the release package over HTTPS and verifies GitHub's SHA-256 asset digest before staging an update. Code signing and signed update manifests are not required. See the [update protocol and limitations](OCTOSHIP-GUIDE.md#github-automatic-updates).

Settings are stored under `%LOCALAPPDATA%\OctoShipForGitHub`. On first launch, the app copies existing preference files from `%LOCALAPPDATA%\OctoCat` when present; the old files are left intact. Privacy mode suppresses saved search and repository history. Portable settings exports exclude credentials and machine-local paths.

## Build

Build with `dotnet build FileToGitHub.csproj -c Release`. Publish the self-contained Windows app with:

```powershell
dotnet publish FileToGitHub.csproj -c Release -r win-x64 --self-contained true -p:DebugType=None -o installer\payload
ISCC.exe /DPayloadDir=payload installer\OctoShip.iss
```

Build the per-user Windows installer with Inno Setup 6 using the commands above; the output name/version comes from `installer/OctoShip.iss`. Setup installs under the current user's LocalAppData, creates Start Menu shortcuts, offers an optional desktop shortcut, and registers an uninstaller. It does not automatically close running applications. User settings and Git credentials are preserved on uninstall. Windows 10 build 19041 or later and Git for Windows with Git Credential Manager are required to use GitHub sign-in. The self-contained package bundles .NET 10. Developers need the .NET 10 SDK and Inno Setup 6. Publisher verification reports unsigned builds until an Authenticode certificate is configured.

## Additional development workflows

Use **Prepare & inspect** for offline mapping, selective changes, account/visibility bindings and project/release inspection. See [SHIPPING-PREPARATION.md](SHIPPING-PREPARATION.md) for features 13–28 and boundaries. **Ship project & delivery checks** covers the first twelve additions; see [SHIPPING-WORKBENCH.md](SHIPPING-WORKBENCH.md). These are development-source additions, not a statement that an updated public installer has been released.
