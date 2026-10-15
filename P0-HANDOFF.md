# P0 Windows security implementation and installation handoff

Date: 2026-10-14. Build: **1.6.1-preview.1**. Scope: the Windows client and Windows packaging. The Python/Linux client was not modified or qualified by this pass.

## Product-scope correction (2026-10-15)

OctoShip's purpose is account-connected GitHub code shipping and workflow automation. Publisher signing and signed update manifests are not prerequisites for normal operation. The updater uses HTTPS GitHub release assets and requires the SHA-256 digest reported by GitHub to match the downloaded package. This detects asset mismatch or corruption but does not independently identify the publisher. Windows builds remain unsigned; the historical preview.1 test record below is not the current update policy.

## Outcome and remaining prerequisites

The Windows client builds on .NET 10 and has new publication, account-session, subprocess, input, and update trust checks. The self-contained Windows x64 installer at `installers/OctoShip-Setup-v1.6.1-preview.1-win-x64.exe` was installed successfully.

Installation returned exit code 0. All **474** payload files matched their installed SHA-256 hashes; **3** pre-existing JSON profile files were unchanged by installation. The installed application launched with its own `coreclr.dll`, and its product version is `1.6.1-preview.1`. The application was already closed before replacement; no active workspace was forcibly terminated. It is left running after launch verification. A pre-upgrade application/profile backup was retained.

Installer SHA-256: `46858A626831754FEAB9AC9D404349D63E52DE978A21301FF740FF88AAEB9B7A`. Authenticode status: **NotSigned**. Local hash equality verifies installation consistency, not publisher authenticity.

**The installed build's real GitHub account connection remains to be verified.** A read-only live qualification is tracked as backlog task [399](IMPROVEMENT-BACKLOG.md). It must not expose or save credential values, and it must not perform remote writes.

**The real GitHub account connection remains to be qualified** through read-only task [399](IMPROVEMENT-BACKLOG.md). Publisher signing and signed update manifests are outside the current product requirements and do not block GitHub connection, shipping, or updates.

## Task status

| ID | Windows result | Remaining boundary |
| --- | --- | --- |
| 008 | Central HTTP mutation guard verifies authenticated login and current repository visibility; applies all saved repository bindings to upload, branch, PR, and release writes. | Live GitHub mutation not exercised. Bindings for the same repository apply conservatively across projects; conflicting bindings block writes. Linux remains separate. |
| 029 | Migrated application and verification projects to `net10.0-windows10.0.19041.0`; self-contained Windows package includes runtime. | Keep the bundled runtime patched in future releases. Installation evidence is separate from source build evidence. |
| 030 | Publisher code signing for Windows packages. | **Out of core scope:** Windows packages remain unsigned; this does not block OctoShip workflows. |
| 031 | Signed update manifests and publisher-key enforcement. | **Not required by the current updater:** GitHub HTTPS, its published asset digest, archive checks, package-version checks, and staged/installed file hashes are used instead. |
| 032 | Credential values remain managed by GCM/in memory; active-token redaction, sanitized server error bodies, bounded credential subprocess wait, and concurrent stdout/stderr draining added. | Immutable managed strings cannot promise immediate memory erasure. No guarantee of defending against a process running as the same compromised OS user. |
| 035 | Bounded JSON reads; corrupt binding policy fails closed; source file handles resolve to reviewed paths; junction/link rejection; stronger destination checks and ZIP duplicate/reserved/link/path checks. | Representative malicious fixtures exercised. This is not a full penetration test or proof that every filesystem race has been eliminated. |
| 038 | Background HTTP checks dispatch to the lock's UI thread before authorization; external-process launches use the same lock guard. | Already-sent HTTP requests/started tools may complete. Real Windows Hello/password success requires interactive verification. Linux lock behavior was not changed. |
| 060 | Stale credential requests/responses rejected; account change/sign-out requires child workflows to close; main queue/repository/activity views cleared on account change. | Saved credential-free project plans remain local user data, not a separate encrypted vault per GitHub identity. |
| 064 | Git, gh, PowerShell, and Explorer resolve through explicit standard installation paths, with argument lists for command execution and timeouts for tool work. Git inspection disables fsmonitor/untracked-cache integrations. | Nonstandard tool installations are rejected with guidance. No comprehensive third-party binary supply-chain audit; local user-owned installs are not defended against their owner replacing files. |

## Implementation locations

- `SessionLockHttpHandler.cs`: common HTTP enforcement, identity/visibility preflight for every mutation, stale-account rejection, error-body sanitization.
- `SecurityBoundaries.cs`: regular/resolved source paths, bounded JSON, diagnostic redaction, saved binding enforcement, standard-path tool resolution and process wait/lock behavior.
- `MainWindow.xaml.cs`: HTTP context wiring, account switching constraints, view clearing, credential subprocess handling, GitHub release-feed selection and asset SHA-256 validation.
- `AccountSessionLock.cs`: checks from worker threads run against the authoritative UI-thread lock state.
- `UpdatePackage.cs` / `UpdateInstaller.cs`: archive entry validation and staged/installed hash checks.
- `GitHubAtomicBatchService.cs`, `GitHubReleaseService.cs`, `UploadQueueService.cs`, preparation/queue readers: file/path/input hardening.
- `installer/OctoShip.iss`: 1.6.1-preview.1 self-contained Windows packaging description.
- `verification/p0-security`: new security harness with fake HTTP and synthetic credentials/keys.

## Verification performed

- Release build: **0 errors, 0 warnings** after adapting Authenticode certificate loading for .NET 10.
- **38** P0 tests: account/visibility enforcement, stale sessions, upload host restriction, all mutation verbs, corrupt bindings, credential redaction, standard-path tool resolution, signed manifest/tamper/key/version checks, unsafe ZIP entries, and regular source handles.
- **15** atomic upload/queue checks; **18** repository workflow checks; **28** preparation checks.
- Shipping-workbench harness passed review, immutable verification, draft recovery, diagnostics, recipe validation, and small-window rendering scenarios.
- **26** update checks, including actual helper replacement inside a temporary test installation.
- **27** session checks, including background lock checks and refusal to create a subprocess while locked.
- **51** uniform UI checks and **33** scanner/release checks, including WPF rendering. The updated main-window screenshot was visually inspected.
- HTTP write tests used fake transports. No user repositories, PRs, releases, visibility settings, or credentials were changed by verification.
- The former UI expectation that an unprovisioned update client queries the feed was replaced with an assertion that it makes no update request. Signature success/failure uses generated test keys solely inside the test process.

## Build and verification commands

Build verification used the .NET 10 SDK (10.0.402) and Inno Setup 6. These are developer tools; end users do not need to install the SDK. Ensure `dotnet` and `ISCC.exe` are available on PATH, or substitute their local executable paths.

```powershell
$dotnet = (Get-Command dotnet -ErrorAction Stop).Source
& $dotnet build FileToGitHub.csproj -c Release
& $dotnet run --project verification/p0-security/P0SecurityChecks.csproj -c Release
& $dotnet run --project verification/session-lock/SessionLockChecks.csproj -c Release
& $dotnet run --project verification/uniform-ui/UniformUiChecks.csproj -c Release
& $dotnet publish FileToGitHub.csproj -c Release -r win-x64 --self-contained true -p:DebugType=None -o installer/payload-p0-1.6.1-preview.1
ISCC.exe /DPayloadDir=payload-p0-1.6.1-preview.1 installer/OctoShip.iss
```

Other verification projects remain under `verification/`. For `verification/secrets-release/run.ps1`, put the .NET 10 SDK directory first in the current process PATH before running it.

## Optional distribution hardening

Code signing could give Windows users an independent publisher identity, and signed update metadata could add another trust layer. Neither is provisioned or required by the current OctoShip release workflow. Reassess only if distribution needs change; private signing material must remain outside source control and application settings.

## Operational changes users will notice

- Standard-path Git for Windows/GCM is still needed for account sign-in. The package supplies .NET 10 itself.
- Close tool windows before changing accounts or signing out. Unsaved work is not discarded to force an account switch.
- A saved binding's changed visibility now blocks all publishing paths. Review conflicting project bindings explicitly; corrupt files are not silently replaced.
- Every mutation performs identity and repository preflight reads. This trades additional API requests for consistent enforcement; rate-limit exhaustion fails closed.
- The updater can install a published GitHub package after HTTPS download, GitHub digest validation, archive and version checks, and staged-file hash validation. The unsigned installer does not establish independent publisher identity.

No public deployment, source push, GitHub release publication, or Linux release was performed in this pass. P1–P3 feature work was not started.
