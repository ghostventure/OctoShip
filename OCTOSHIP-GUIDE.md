# Complete OctoShip Guide & Technical Documentation

This document provides comprehensive, end-to-end documentation for **OctoShip for GitHub**, detailing its architecture, feature inventory, security boundaries, user session protection, uniform design system, Linux client, packaging pipeline, and verification suites.

---

## Table of Contents

1. [Executive Overview](#1-executive-overview)
2. [Source Architecture & Code Map](#2-source-architecture--code-map)
3. [Core Windows Client Features](#3-core-windows-client-features)
4. [Shipping Workbench (Features 1–12)](#4-shipping-workbench-features-112)
5. [Shipping Preparation & Inspection (Features 13–28)](#5-shipping-preparation--inspection-features-1328)
6. [Account Retention & Session Security](#6-account-retention--session-security)
7. [Uniform UI Design System](#7-uniform-ui-design-system)
8. [Cross-Platform Linux Client](#8-cross-platform-linux-client)
9. [Build, Packaging & Distribution Pipeline](#9-build-packaging--distribution-pipeline)
10. [Automated Verification Suites](#10-automated-verification-suites)
11. [Security Boundaries & Operational Constraints](#11-security-boundaries--operational-constraints)

---

## 1. Executive Overview

**OctoShip for GitHub** is a dual-platform developer tool designed for local file discovery, pre-commit inspection, and safe, atomic transfers to GitHub repositories. It bridges the gap between raw Git CLI commands and complex browser interfaces by offering:

- **Local Discovery:** Multithreaded file search by name and content with regex support and reparse-point protection.
- **Pre-Flight Safety:** Deep file inspection, selective hunk/line staging, heuristic secret scanning, and sensitive-file rules.
- **Atomic Operations:** Single-commit batch uploads, fixed-commit directory comparisons, branch generation, and draft release publishing.
- **Session Protection:** Account preference retention and an automatic 30-minute inactivity lock backed by Windows Hello / password verification on Windows and system PAM on Linux.
- **Consistent UX:** A uniform, dark-themed interface across all 10 desktop windows and dialogs.
- **Cross-Platform Delivery:** A framework-dependent Windows desktop client (.NET 6 WPF) alongside a native Linux desktop client (Python 3.10+ / Tkinter) with standalone packaging.

---

## 2. Source Architecture & Code Map

### Windows C# / WPF Application

The Windows application targets `net6.0-windows10.0.19041.0` and utilizes WPF and Windows Forms.

| Component / File | Primary Responsibility |
|---|---|
| `App.xaml`, `App.xaml.cs` | Application lifecycle, global theme injection, and single-instance mutex (`Local\OctoCat.SingleInstance`). |
| `SplashWindow.xaml`, `SplashWindow.xaml.cs` | Startup splash window with uniform styling and initialization telemetry. |
| `MainWindow.xaml`, `MainWindow.xaml.cs` | Primary interface: file search, review panels, GitHub repository catalog, single-file/batch upload controls, live terminal, and tool navigation. |
| `SearchService.cs` | Multithreaded file system search engine supporting regex, date, size filters, and content search up to 2 MiB. |
| `GitHubRepositoryService.cs` | GitHub REST API client for repository metadata, branch heads, tree queries, and push permission verification. |
| `GitHubAtomicBatchService.cs` | Executes atomic single-commit batch uploads via GitHub Git Database API (blobs, trees, commits, refs). |
| `UploadQueueService.cs` | In-memory upload queue planning, progress tracking, cancellation, and retry management. |
| `PersistentUploadQueueStore.cs` | Disk-persisted queue journal excluding credentials for restart recovery. |
| `ContentSecretScanner.cs` | Bounded scanner detecting API keys, private keys, tokens, and credentials with redacted finding metadata. |
| `FileSafetyRules.cs` | Rule evaluator flagging sensitive files (e.g., `.env`, keys, credentials, binary files). |
| `FileReviewWindow.xaml.cs` | Modal for file inspection, syntax preview, SHA-256 computation, and side-by-side remote diff. |
| `BatchUploadWindow.xaml.cs` | Dedicated modal for configuring, reviewing, and executing multi-file batch transfers. |
| `RepositoryWorkflowService.cs`, `RepositoryWorkflowWindow.cs` | Directory comparison against remote trees, branch creation, and draft pull-request authoring. |
| `GitHubReleaseService.cs`, `ReleasePublisherWindow.cs` | GitHub draft release creation, asset attachment with SHA-256 verification, and publishing. |
| `RepositoryToolsWindow.xaml.cs` | Repository folder hierarchy browser, GitHub API quota monitoring, and connectivity checks. |
| `OctoCatPreferencesService.cs`, `OctoCatSettingsWindow.xaml.cs` | Configuration management, credential-free import/export, history wiping, and publisher validation. |
| `ShippingWorkbenchService.cs`, `ShippingWorkbenchWindow.cs` | Shipping workbench covering pre-commit review, hash locking, and recipe execution (Features 1–12). |
| `ShippingInspectionService.cs`, `ShippingPreparationWindow.cs` | Deep inspection, PE parsing, link linting, and archive auditing (Features 13–28). |
| `SelectiveTextChanges.cs` | Line/hunk-level text diff selector for atomic partial staging. |
| `AccountSessionLock.cs`, `AccountSessionState.cs` | 30-minute inactivity timer, state management, and window masking. |
| `SessionNativeWindows.cs`, `WindowsAccountPasswordVerifier.cs` | P/Invoke integration with Windows Hello and Windows authentication APIs. |
| `SessionLockHttpHandler.cs` | Delegating HTTP handler gating network requests while the application is locked. |
| `UniformUi.cs`, `Theme.xaml`, `AppearanceControls.cs`, `OctoShipDialog.cs` | Central design system, shared resources, consistent controls, and modal dialogs. |

### Linux Python / Tkinter Client

Located in `linux/`:
- `linux/octoship/app.py`: Tkinter-based desktop interface.
- `linux/octoship/core.py`: GitHub CLI and REST backend.
- `linux/octoship/queue_store.py`: Local queue persistence.
- `linux/octoship/scanner.py`: Secret scanning engine.
- `linux/octoship/workflows.py`: Comparison, branch, and PR workflows.
- `linux/octoship/theme.py`: Dark theme styling matching the Windows aesthetic.
- `linux/packaging/`: Scripts for standalone bundle creation (`build-standalone.py`) and Debian packages (`build-deb.sh`).

---

## 3. Core Windows Client Features

### 3.1 Local Search Engine (`SearchService.cs`)
- **Filters:** Filename globbing, regular expressions, exact matching, case sensitivity, minimum/maximum file size, and modification date windows.
- **Content Inspection:** Fast text search reading up to 2 MiB per file with binary heuristic bypass.
- **Safety:** Skips symbolic links and NTFS reparse points to avoid infinite directory traversal. Supports cancellation tokens for instant cancellation.

### 3.2 Single-File & Batch Uploads
- **Pre-flight Checks:** Confirms repository write permissions, branch existence, and destination conflict states before initiating transfers.
- **Batch Modes:**
  - *Per-File Mode:* Successive Git commits for incremental progress.
  - *Atomic Mode:* All staged files are committed as a single git commit using GitHub's Git Data API (`blobs -> tree -> commit -> ref update`).
- **Conflict Handling:** Skip, Replace, or Rename collision resolution per file.
- **Queue Persistence:** Unfinished queues survive application restart via `PersistentUploadQueueStore.cs`, strictly omitting authentication credentials.

### 3.3 Content Secret Scanner (`ContentSecretScanner.cs`)
- Scans files up to 2 MiB for token patterns (GitHub PATs, AWS access keys, private keys, JWTs).
- Findings report only rule type and line number; sensitive token strings are never recorded or logged.
- Files exceeding 2 MiB, binary payloads, and unsupported encodings are explicitly marked as `unscanned`.

### 3.4 Repository Workflows & Release Publisher
- **Folder Comparison:** Byte-by-byte comparison between local directory and remote commit tree.
- **Branch & PR Generation:** Branch creation from verified heads and draft pull request submission.
- **Release Publisher:** Draft-first release generation with asset attachment, SHA-256 verification, and explicit publish gating.

---

## 4. Shipping Workbench (Features 1–12)

The Shipping Workbench (`ShippingWorkbenchWindow.cs` & `ShippingWorkbenchService.cs`) provides pre-flight staging and batch execution:

1. **Pre-commit Staging Review:** File-by-file visual approval interface before queuing.
2. **Unchanged-Content Detection:** Computes local SHA-256 and compares with remote blob hashes to skip unnecessary uploads.
3. **Immutable Verification & Hash Locking:** Locks payload hashes prior to batch upload to guarantee byte-for-byte integrity.
4. **Local Modification Alerts:** Detects and flags files modified on disk after staging.
5. **Diagnostic Preflight Checks:** Verifies branch heads, API connectivity, and permissions before execution.
6. **Draft Upload Recovery:** Restores interrupted upload plans from crash-safe disk state.
7. **Branch Recipe Execution:** Configurable branch naming rules (e.g., `feature/{date}-{name}`).
8. **PR Recipe Integration:** Automatically populates PR descriptions with staged commit summaries and checklists.
9. **Target Repo Permissions Validation:** Explicitly checks write permissions before scheduling jobs.
10. **Batch Pause, Resume & Retry:** Fine-grained control over batch execution pipelines.
11. **Commit Message Templating:** Supports variable interpolation (`{branch}`, `{count}`, `{timestamp}`).
12. **Post-Shipping Receipt Generation:** Generates downloadable JSON/text audit receipts containing file paths, blob SHAs, and commit IDs.

---

## 5. Shipping Preparation & Inspection (Features 13–28)

The Shipping Preparation tool (`ShippingPreparationWindow.cs`, `ShippingInspectionService.cs`, `SelectiveTextChanges.cs`) provides deep code and asset inspection across 5 tabs:

13. **Selective Hunk/Line Text Diff Staging:** Allows partial staging of individual lines and diff blocks (`SelectiveTextChanges.cs`).
14. **Markdown Link & Reference Linting:** Verifies intra-document markdown anchors, image links, and relative file paths without sending external web requests.
15. **Version Mismatch & Tag Auditor:** Detects discrepancies between project files (`FileToGitHub.csproj`), installer scripts (`OctoShip.iss`), and Git tags.
16. **Git LFS Attribute & Pointer Auditor:** Inspects `.gitattributes` and flags tracked files matching LFS rules.
17. **Archive / ZIP Traversal Inspection:** Audits ZIP archives for path traversal vulnerabilities (`../`), sensitive filenames, and embedded secrets without extracting files to disk.
18. **Secret & Token Redaction Engine:** Redacts tokens, passwords, and connection strings from user-facing logs and previews.
19. **PE Header & Architecture Reader:** Parses Windows Portable Executable headers to report architecture (`x64`, `x86`, `ARM64`) and subsystem without executing code.
20. **Unsigned Managed Assembly Validator:** Inspects .NET assemblies and Authenticode signatures, flagging unsigned or untrusted binaries.
21. **Atomic Upload Timeout Reconciliation:** Detects dropped HTTP connections, validates remote ref updates, and prevents duplicate commit creation.
22. **Move & Rename Tracking:** Detects content matches across renamed files and emits Git move annotations.
23. **Five-Tab Preparation Interface:** Dedicated views for Diffs, Code Review, Assets, Manifests, and Preflight.
24. **Multi-Profile Account Switcher:** Switches between authorized GitHub profiles with strict token isolation.
25. **Repository Visibility Binding:** Guards against accidental pushes to public repositories when private visibility is expected.
26. **Local Ignore Rule Enforcement:** Parses and enforces `.gitignore` rules in real time.
27. **File Size & Chunking Advisor:** Warns when individual files exceed GitHub's 50 MiB or 100 MiB limits.
28. **Encoding & Line Ending Normalization:** Audits UTF-8 BOM, UTF-8 without BOM, CRLF, and LF formatting.

---

## 6. Account Retention & Session Security

Documented in detail in [`ACCOUNT-SESSION.md`](ACCOUNT-SESSION.md):

### 6.1 Credential Architecture
- OctoShip never saves GitHub Personal Access Tokens or passwords in plain text or settings files.
- Credentials are delegated entirely to **Git Credential Manager (GCM)**. Tokens retrieved in-flight reside in memory only.
- User profile selections (username, active repository, upload presets) are persisted under `%LOCALAPPDATA%\OctoShipForGitHub\preferences.json`.

### 6.2 30-Minute Inactivity Lock
- **Timer:** Monitored by `AccountSessionLock.cs` via user input hooks (`SessionNativeWindows.cs`). After 30 minutes of inactivity, the session locks automatically.
- **Window Masking:** The UI renders an opaque security overlay across all active application windows.
- **Network Gating:** `SessionLockHttpHandler.cs` intercepts all outgoing API calls, immediately throwing exceptions while locked to block unauthorized remote operations.
- **Authentication:** Unlocking requires native Windows authentication via Windows Hello (PIN, facial recognition, fingerprint) or the local Windows account password (`WindowsAccountPasswordVerifier.cs`). Passwords are never captured or retained by OctoShip.

---

## 7. Uniform UI Design System

OctoShip provides a consistent, cohesive design system across all 10 application windows and dialogs via `UniformUi.cs`, `Theme.xaml`, and `AppearanceControls.cs`.

### 7.1 Visual Palette
- **Background Deep:** `#0d1117` (Dark ink black/navy)
- **Panel Surface:** `#161b22` (Secondary container surface)
- **Border & Dividers:** `#30363d` (Subtle boundary borders)
- **Primary Accent:** `#58a6ff` (Electric cyan for primary actions and active tabs)
- **Secondary Accent:** `#bc8cff` (Electric magenta for highlights and tags)
- **Primary Foreground:** `#c9d1d9` (High-contrast readable body text)
- **Muted Foreground:** `#8b949e` (Secondary labels and hint text)

### 7.2 Shared Component Controls
- **Buttons:** Standardized primary (cyan), secondary (dark panel), and danger (red outline) button templates with hover states.
- **Input Fields:** Dark TextBoxes and ComboBoxes with cyan focus rings.
- **TabControl Template:** Custom accessible TabControl with keyboard navigation support and explicit content host exposure.
- **DataGrids & Lists:** Dark rows with alternating subtle tints and cyan selection highlights.
- **Dialog System:** Native-styled modal dialogs (`OctoShipDialog.Show`) replace default Win32 message boxes.

### 7.3 Uniformly Styled Windows
1. `MainWindow` (Primary search and upload workspace)
2. `BatchUploadWindow` (Multi-file batch configuration)
3. `FileReviewWindow` (Single-file review and diff)
4. `RepositoryToolsWindow` (Repository browser and API quota)
5. `OctoCatSettingsWindow` (Preferences and account profile)
6. `SplashWindow` (Application startup splash)
7. `ReleasePublisherWindow` (Release drafts and assets)
8. `RepositoryWorkflowWindow` (Compare, branch, and PR tools)
9. `ShippingPreparationWindow` (Deep inspection and preparation)
10. `ShippingWorkbenchWindow` (Workbench staging and shipping)

---

## 8. Cross-Platform Linux Client

The Linux implementation (`linux/`) offers a native Python/Tk experience without Mono or Wine. **Linux 1.7.0 is published** as [linux-v1.7.0](https://github.com/ghostventure/OctoShip/releases/tag/linux-v1.7.0), marked Latest on 2026-10-11.

- **Technology stack:** source execution uses Python 3.10+, Tkinter and GitHub CLI; the self-contained distribution bundles its runtime.
- **Workflows:** atomic/per-file uploads, saved queues, scanning, folder comparison, branches, PRs and releases, plus the shipping workbench, offline preparation plans, selective text edits, account bindings, local inspection and delivery checks.
- **Session protection:** a persistent 30-minute/manual privacy lock authenticates the current Linux account with system PAM. Windows Hello is not used on Linux.
- **Credential storage:** GitHub CLI owns its credential storage; OctoShip does not write tokens or passwords to its settings. CLI storage protection depends on the host configuration.
- **Distribution:** `linux/packaging/build-standalone.py` builds a `.run` installer, bundled `.deb`, portable `.tar.gz` and SHA-256 file. The target is x86_64/glibc Linux with X11/XWayland and compatible host PAM policy.
- **Verification:** 86 backend tests, 15 GUI tests, loopback HTTP upload checks, isolated installer checks and a real current-user PAM GUI unlock passed. In-app production mutations and real attestation trust remain separate verification boundaries.

The [Linux user guide](linux/README.md) records behavior and limits. The [complete release handoff](docs/linux-1.7.0-handoff.md) records downloads, checksums, architecture, storage, installation/rollback, verification commands and publication procedure. Windows-only features and platform differences are listed there; full feature parity is not claimed.

---

## 9. Build, Packaging & Distribution Pipeline

### 9.1 Windows Build Prerequisites
- .NET 6 SDK (`net6.0-windows10.0.19041.0`)
- .NET Windows Desktop Runtime 6.0+
- Git for Windows with Git Credential Manager
- Inno Setup 6 (installed at `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`)

### 9.2 Build & Packaging Commands
```powershell
# 1. Compile Release binary
dotnet build FileToGitHub.csproj -c Release --no-restore

# 2. Publish framework-dependent payload
dotnet publish FileToGitHub.csproj -c Release --no-restore -p:DebugType=None -o installer\payload-1.6.0-preview.1

# 3. Create portable ZIP archive
Compress-Archive -Path installer\payload-1.6.0-preview.1\* -DestinationPath installers\OctoShip-v1.6.0-preview.1-win-x64.zip -Force

# 4. Compile Inno Setup installer
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" /Q "/DPayloadDir=payload-1.6.0-preview.1" installer\OctoShip.iss
```

### 9.3 Installation Verification
The installer compiles to `installers/OctoShip-Setup-v1.6.0-preview.1-win-x64.exe`:
- Installs per-user under `%LOCALAPPDATA%\Programs\OctoShip for GitHub\`.
- Preserves existing user preferences and Git credentials.
- Silent installation flags:
  ```powershell
  Start-Process -FilePath "installers\OctoShip-Setup-v1.6.0-preview.1-win-x64.exe" -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOCLOSEAPPLICATIONS','/SP-') -Wait
  ```

---

## 10. Automated Verification Suites

OctoShip includes 7 offline test suites located under `verification/`. None of the test suites perform live network writes; all remote operations use mock HTTP handlers.

| Suite | Project / Script | Checks | Scope |
|---|---|:---:|---|
| **Atomic Uploads** | `AtomicUploadChecks.csproj` | 15 | Single-commit batches, branch head validation, conflict aborts, queue isolation, journal recovery. |
| **Workflows** | `WorkflowTests.csproj` | 18 | Commit tree comparisons, branch creation payloads, draft PR formatting, tab accessibility. |
| **Secrets & Release** | `verification/secrets-release/run.ps1` | 33 | Secret scanner heuristics, redaction, draft release asset hashing, WPF render smoke checks. |
| **Session & Lock** | `SessionLockChecks.csproj` | 25 | Inactivity timer, HTTP gating, window masking, persistence, password verifier contract. |
| **Preparation** | `PreparationChecks.csproj` | 28 | Selective diff staging, markdown linter, PE header reader, ZIP traversal checks, timeout recovery. |
| **Workbench** | `ShippingWorkbenchChecks.csproj` | Integration | File approval state, hash locking, recipe expansion, small-window responsiveness. |
| **Uniform UI** | `UniformUiChecks.csproj` | 49 | Shared styling, control brushes, dialog templates, layout rendering across all 10 windows. |

### Running the Entire Verification Suite
```powershell
dotnet run --project verification/uploads/AtomicUploadChecks.csproj -c Release
dotnet run --project verification/repository-workflows/WorkflowTests.csproj -c Release
powershell -NoProfile -ExecutionPolicy Bypass -File verification/secrets-release/run.ps1
dotnet run --project verification/session-lock/SessionLockChecks.csproj -c Release
dotnet run --project verification/preparation/PreparationChecks.csproj -c Release
dotnet run --project verification/shipping-workbench/ShippingWorkbenchChecks.csproj -c Release
dotnet run --project verification/uniform-ui/UniformUiChecks.csproj -c Release
```

---

## 11. Security Boundaries & Operational Constraints

1. **Authenticode Signing:** Current executables and installers are unsigned (`Authenticode: NotSigned`). They are intended for internal and developer preview use until an official code-signing certificate is configured.
2. **Credential Privacy:** Git tokens are held exclusively in volatile RAM and never committed, logged, or saved to preference JSON files.
3. **Repository Scope:** The canonical repository is `https://github.com/ghostventure/OctoShip.git` on branch `main`. The default update feed reference (`ghostventure/OctoCat`) remains legacy and must be updated before publishing production update streams.
4. **Interactive Authentication:** Unlocking the 30-minute inactivity lock requires interactive Windows Hello or Windows password verification. Tests mock the authentication provider; real biometric verification occurs exclusively through OS-level dialogs.
