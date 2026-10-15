# OctoShip user and developer guide

## Versions and scope

Windows source and current local package: **1.6.1-preview.10**, .NET 10 WPF, Windows 10 build 19041 or newer, x64 self-contained installer. See the [P1 handoff](P1-HANDOFF.md) for package, SBOM, and verification details. This preview is not a published GitHub release. Linux source and packages are maintained independently under `linux/`; see [Linux guide](linux/README.md) and [packaging](linux/packaging/README.md). Windows verification does not establish Linux package behavior.

The [P1 handoff](P1-HANDOFF.md) records implemented Windows changes, local installation, and remaining work. Earlier release documents are historical; building or installing a package locally does not publish it to GitHub.

## Install and first use

Windows users need Git for Windows with Git Credential Manager for GitHub sign-in. The current self-contained installer bundles .NET 10, so users do not need a separate .NET runtime installation. Developers need the .NET 10 SDK and Inno Setup 6. The per-user installer installs to `%LOCALAPPDATA%\Programs\OctoShip for GitHub`, registers an uninstaller and Start Menu shortcut, and optionally adds a desktop shortcut. Close OctoShip before upgrading.

1. Launch OctoShip, choose a saved GitHub account and Connect, or use Add account.
2. Choose a local folder and search. Review a result before uploading.
3. Select repository, branch and relative destination. Confirm permissions, contents and conflicts.
4. Use Uploads for a reviewed project shipment, Prepare & inspect for offline mapping/inspection, or Releases to prepare a draft.
5. Review Activity for progress and outcomes. Account & settings contains preferences, account details, update controls and diagnostics.

The navigation stays visible: Files, Uploads, Repositories, Releases, Activity, Account & settings. Actions that publish files, branches, PRs or releases require their normal explicit review/confirmation.

## Search, review and upload

Search supports filename/content matching, regular expressions, exact/case-sensitive matching, recursion, hidden files, exclusions, extension, size and modification filters, sorting and result limits. Search runs off the UI thread and supports cooperative cancellation. Content reads are capped at 2 MiB; reparse points are skipped.

File review shows small text/images, SHA-256 and optional remote text comparison; PDFs open in the default Windows viewer. It is not a syntax-aware code editor. Sensitive-name rules and bounded secret scanning assist review; they cannot prove that a file has no secrets. Binary, oversized and unsupported content is explicitly unscanned. Findings omit matched secret values.

Batch uploads support editable destinations, conflict choices, ordering, progress, pause/cancel/retry, and optional queue recovery. Per-file mode makes separate commits; atomic mode creates one commit and a non-forced ref update. A moved branch or changed source can stop publication. Saved queues never automatically replay after restart. Comparison uses raw Git blob hashes at a fixed commit; it does not normalize line endings or synchronize deletions.

## Shipping workbench: first feature group

[SHIPPING-WORKBENCH.md](SHIPPING-WORKBENCH.md) is the detailed behavior and limits reference. The workbench provides:

- Reviewed project shipping to a fresh branch and draft PR, skipping unchanged content.
- Local-byte and remote-head checks, then verification of the immutable published commit.
- Authenticated account/permission diagnostics and accessible branch rules/protection details.
- GitHub Pages status, build and domain checks.
- Artifact attestation checks through `gh attestation verify`, requiring GitHub CLI and its authentication.
- Read-only local Git status/remotes, with credential-bearing URL information redacted.
- Existing-draft asset recovery: uploads missing names, preserves conflicting assets.
- Release download tests with byte counts/SHA-256 and a separate anonymous-link check.
- Credential-free project recipes for repository, branch, destination, exclusions and release naming metadata.

A recipe is not an automatic commit/PR template engine. Recovery does not publish releases. Unsupported API evidence remains unknown. Workbench shipments support 100 changed files and 50 MiB per file. Cancellation can leave a completed remote action; inspect its outcome before retrying.

## Preparation: features 13–28

The exact numbered inventory and limits are in [SHIPPING-PREPARATION.md](SHIPPING-PREPARATION.md): destination mapping; selective UTF-8 edit blocks; possible moves; empty-folder placeholders; bounded ZIP inspection; large-file/LFS advice; identity preview; repository visibility; project/account binding; offline plans; uncertain atomic publication reconciliation; version consistency; PE/signature inspection; release channel checks; relative Markdown links; and redacted support reports.

Selective preparation supports one file, up to 2,000 lines/1 MiB. Contiguous edit blocks are selected together; the original local file is unchanged. Move detection is a suggestion and does not delete the old remote path. There is no automatic LFS conversion. Markdown checks exclude web/anchor URLs and are not a complete Markdown parser. Support reports must be reviewed before sharing.

## Accounts, retention and locking

See [ACCOUNT-SESSION.md](ACCOUNT-SESSION.md) for the full security model. Selected account, configurable GitHub auto-connect, destinations and preferences persist locally. Auto-connect reuses Git Credential Manager's selected account; OctoShip does not persist the token or password. A separate preference controls OctoShip's own Windows-authentication inactivity prompt; Windows' own sign-in lock remains in effect. Main-window settings save on deactivation and closing. Privacy mode suppresses search/history/workspace fields as documented; explicit preparation saves have separate rules.

GitHub tokens are retrieved through Git Credential Manager and retained in memory, never intentionally written into OctoShip settings. This is local retention, not a cloud account service.

After 30 minutes without input in OctoShip, WPF windows are masked and owned native dialogs hidden. Background transfers and activity in another app do not reset the timer. Windows session lock/disconnect also locks OctoShip. Ctrl+Shift+L or the profile lock action locks immediately. Session state persists across restart; corrupt state fails closed.

Unlock requires Windows Hello or the current Windows account password. Password fallback uses native buffers, validates the Windows SID and clears those buffers. Cancellation and authentication failures leave the app locked. New requests through the shared HTTP handlers are blocked; already-sent requests and started CLI operations can finish. This is a privacy shield, not file encryption or protection against processes running as the same Windows user. Unsaved editors are retained while locked, but not universally persisted across app termination.

## Local data inventory

Root: `%LOCALAPPDATA%\OctoShipForGitHub`. Existing legacy `OctoCat` preferences may be copied on first launch without removing the originals.

| Location | Purpose |
|---|---|
| `settings.json` | Account/reconnect and remembered workspace selections |
| `preferences.json` | Privacy, histories, destinations, update channel and automatic-update preference |
| `display.json` | Global font size and compact/comfortable spacing; separate from settings export |
| `session.json` | Lock flag and last activity; no credentials |
| `UploadQueues` | Credential-free queue recovery metadata |
| `project-bindings.json` | Explicit expected account/visibility bindings |
| `PreparedFiles` | Staged placeholder or selectively prepared content |
| `updates` | Downloaded update ZIPs, extracted packages and backup files |
| `update-failed.txt` | Update helper failure report, shown on next startup |

Explicit saved plans include local paths; prepared files can contain project content. Keep these out of source control. Settings export is credential-free but can include histories; review before sharing. Uninstalling the app preserves user settings and GCM credentials.

## Uniform GUI and extension rules

`Theme.xaml` supplies shared control resources. `UniformUi.cs` initializes resources, normalizes legacy controls, applies display preferences, adds child-window context/footer controls, and refreshes account/destination labels. `AppearanceControls.cs` edits global text size (12/14/16/18) and compact/comfortable spacing. `OctoShipDialog.cs` supplies consistent modal confirmations with safe dismissal defaults. Windows authentication and native file pickers remain OS dialogs.

| Token | Color |
|---|---|
| Canvas | `#0B1020` |
| Surface | `#121B2B` |
| Input | `#0C1422` |
| Text | `#E9EFF8` |
| Border | `#34465E` |
| Primary action | `#116866` |
| Accent | `#50D6D0` |

Shared styles cover buttons, inputs, tabs, grids, groups, scrollbars, menus, tooltips and keyboard focus. Main content scrolls when large text or a short window needs more space. Display changes apply immediately and persist separately. New windows should call `UniformUi.Prepare(this)` before `InitializeComponent`, use dynamic resources, label inputs, register destination context where appropriate and use `OctoShipDialog` for confirmations. Do not put account context on the unlock shield. Check large text, keyboard traversal and every tab after adding controls.

## GitHub automatic updates

The updater uses the public `ghostventure/OctoShip` GitHub releases feed and is active in this build. Automatic updates default on and can be disabled in Settings; users can select Stable or Preview. It checks after startup and every two minutes while unlocked and idle, with backoff for failures and GitHub rate limits. The public feed is read anonymously, so GitHub account sign-in is not needed for update checks or downloads. Drafts and Linux-only releases are skipped; the newest compatible Windows package among the latest 100 releases is selected, without intentional downgrades.

The release must attach **`OctoShip-win-x64.zip`**, with a GitHub `sha256:` asset digest, containing published app files at ZIP root. The updater downloads the package over HTTPS from GitHub and requires the digest to match the downloaded bytes. It does not require code signing, publisher signing keys, or signed update manifests. The digest checks package correspondence/integrity; it is not an independent publisher identity check. Source commits/source ZIPs alone are not installable updates. Updates download a complete package, not binary delta patches.

The `Windows update release` GitHub Actions workflow runs when Windows source, project version or release workflow changes on `main`, and can be dispatched manually from `main`. Increment `<Version>` in `FileToGitHub.csproj` for each release. The workflow builds, runs focused checks, publishes a Windows x64 payload, verifies the packaged version, uploads a draft ZIP and SHA256SUMS, checks GitHub's asset digest, then publishes the release. Hyphenated versions are prereleases; other versions are stable. Published versions are never overwritten; source changes without a version bump skip publication. A failed upload remains a draft, invisible to installed clients. Run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Publish-WindowsRelease.ps1 -PackageOnly` for local verification and packaging without publishing.

Older release documents describe updater behavior for those historical builds and may not reflect the current public-feed flow.

Downloads are bounded to 250 MiB, checked against the GitHub release digest, and extracted only after path and expanded-size checks. The packaged DLL product version must match the tag. Automatic downloads stage while the app remains open and install when the app closes normally; manual installation asks before restarting. The helper backs up the app directory and attempts restoration if replacement fails. Pending downloads are not automatically recovered across a crash. Current preview packages are unsigned, but signing is not a prerequisite for this updater.

The updater requires a writable installation directory. HTTPS validates the GitHub connection; the matching SHA-256 digest confirms correspondence with GitHub's selected asset, not independent publisher identity. No signing key or signed manifest is required to perform an update.

## Source map

| Files | Responsibility |
|---|---|
| `App.xaml.cs`, `SplashWindow.*` | Lifecycle, single-instance mutex, splash |
| `MainWindow.*`, `SearchService.cs` | Navigation, account/search/upload orchestration and updater; background search |
| `GitHubRepositoryService.cs` | Repository metadata, target files and permissions |
| `UploadQueueService.cs`, `PersistentUploadQueueStore.cs`, `BatchUploadWindow.*` | Planning, execution, queue recovery |
| `GitHubAtomicBatchService.cs` | Git Data API single-commit publication and uncertain-response reconciliation |
| `ContentSecretScanner.cs`, `FileSafetyRules.cs`, `FileReviewWindow.*` | Bounded scans, filename rules and previews |
| `RepositoryWorkflowService.cs`, `RepositoryWorkflowWindow.cs` | Fixed-commit comparisons, branches and draft PRs |
| `GitHubReleaseService.cs`, `ReleasePublisherWindow.cs` | Draft creation, assets and explicit publish |
| `ShippingWorkbenchService.cs`, `ShippingWorkbenchWindow.cs` | Reviewed shipping, diagnostics, delivery/recovery and recipes |
| `ShippingInspectionService.cs`, `SelectiveTextChanges.cs`, `ShippingPreparationWindow.cs` | Offline plans, selective content and inspections |
| `OctoCatPreferencesService.cs`, `OctoCatSettingsWindow.*` | Preferences, export/import and publisher checks |
| `AccountSessionState.cs`, `AccountSessionLock.cs` | Persistent timeout policy, Windows Hello and WPF shielding |
| `SessionNativeWindows.cs`, `WindowsAccountPasswordVerifier.cs`, `SessionLockHttpHandler.cs` | Native dialog/input protection, password verification and HTTP gate |
| `ReleaseVersion.cs`, `WindowsUpdateRelease.cs`, `UpdatePackage.cs` | Version ordering, Windows release selection and validated staging |
| `Theme.xaml`, `UniformUi.cs`, `AppearanceControls.cs`, `OctoShipDialog.cs` | Shared design system |
| `installer/OctoShip.iss` | Per-user installer |

## Build, package and verify

From the repository root in PowerShell:

```powershell
dotnet build FileToGitHub.csproj -c Release
dotnet publish FileToGitHub.csproj -c Release -r win-x64 --self-contained true -p:DebugType=None -o installer\payload
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" /Q /DPayloadDir=payload installer\OctoShip.iss
```

Run the focused verification projects under `verification`: uploads/AtomicUploadChecks, repository-workflows/WorkflowTests, session-lock/SessionLockChecks, preparation/PreparationChecks, shipping-workbench/ShippingWorkbenchChecks, uniform-ui/UniformUiChecks and updates/UpdateChecks using `dotnet run --project verification/<folder>/<project>.csproj -c Release`. Scanner/release checks use `powershell -NoProfile -ExecutionPolicy Bypass -File verification/secrets-release/run.ps1`.

Tests use temporary files and fake HTTP. They do not establish live GitHub writes, real Windows authentication or real remote self-update delivery. Render harnesses produce screenshots in Temp. Before distributing, check installed executable version, installed/published hashes, launch, account retention, real authentication and the intended download route. Do not commit artifacts, local settings, tokens or signing keys. The component roadmap includes unfinished proposals; it is not a completed-feature inventory.

## Troubleshooting and handoff

- Cannot connect: verify Git/GCM availability, selected account and repository access. Never paste tokens into diagnostics.
- Cannot upload: inspect branch head/permissions/rules, sensitive findings, destination conflicts and changed local bytes; refresh/review before retrying.
- Locked after restart: unlock through Windows authentication. Corrupt or old session state intentionally stays locked.
- Update unavailable: ensure repository access, selected channel, newer tag, exact ZIP asset name, SHA-256 digest and matching package version. Source pushes do not create updates.
- Update replacement failed: review the startup error and retained backup, then reinstall a verified package if needed.
- GUI density: open Settings and adjust text size/compact spacing; settings apply across existing windows.

See [developer notes](DEVELOPMENT.md), [account security](ACCOUNT-SESSION.md), [workbench](SHIPPING-WORKBENCH.md), [preparation](SHIPPING-PREPARATION.md) and [release evidence](RELEASE-1.6.0-preview.2.md). No license grant or public publication is implied by the local package.

## Linux release and handoff

The Linux implementation (`linux/`) offers a native Python/Tk experience without Mono or Wine. **Linux 1.7.0 is published** as [linux-v1.7.0](https://github.com/ghostventure/OctoShip/releases/tag/linux-v1.7.0), marked Latest on 2026-10-11.

- **Technology stack:** source execution uses Python 3.10+, Tkinter and GitHub CLI; the self-contained distribution bundles its runtime.
- **Workflows:** atomic/per-file uploads, saved queues, scanning, folder comparison, branches, PRs and releases, plus the shipping workbench, offline preparation plans, selective text edits, account bindings, local inspection and delivery checks.
- **Session protection:** a persistent 30-minute/manual privacy lock authenticates the current Linux account with system PAM. Windows Hello is not used on Linux.
- **Credential storage:** GitHub CLI owns its credential storage; OctoShip does not write tokens or passwords to its settings. CLI storage protection depends on the host configuration.
- **Distribution:** `linux/packaging/build-standalone.py` builds a `.run` installer, bundled `.deb`, portable `.tar.gz` and SHA-256 file. The target is x86_64/glibc Linux with X11/XWayland and compatible host PAM policy.
- **Verification:** 86 backend tests, 15 GUI tests, loopback HTTP upload checks, isolated installer checks and a real current-user PAM GUI unlock passed. In-app production mutations and real attestation trust remain separate verification boundaries.

The [Linux user guide](linux/README.md) records behavior and limits. The [complete release handoff](docs/linux-1.7.0-handoff.md) records downloads, checksums, architecture, storage, installation/rollback, verification commands and publication procedure. Windows-only features and platform differences are listed there; full feature parity is not claimed.

