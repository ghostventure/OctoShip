# P1 implementation and installation handoff

Date: 2026-10-15
Current installed Windows package: **1.6.1-preview.13**; latest GitHub-published package: **1.6.1-preview.13**
Scope: installed and released P1 work. Preview.13 was published as GitHub release [v1.6.1-preview.13](https://github.com/ghostventure/OctoShip/releases/tag/v1.6.1-preview.13) after the Windows update release workflow passed for commit `942e019ad25bf32271670bcbf31f0a3c583e9e2f`.

## Installed changes

- GitHub auto-connect is a visible account-bar option. It uses the preferred account already saved by Git Credential Manager; OctoShip does not store the password or token in settings.
- Account settings now let the user disable OctoShip's own Windows-authentication inactivity prompt. It is on by default for existing profiles. For this user's profile, it was turned off to match the request to stop prompting for Windows account information at startup. Windows' own sign-in lock remains in effect. The setting can be changed in Account & settings â†’ Profile.
- P1 task 020: a non-blocking startup readiness report checks Git/runtime, Git Credential Manager and saved-account availability, profile-folder writability, and read-only GitHub API connectivity. The report is also available from Updates & diagnostics; it displays the count of saved accounts, not their names.
- P1 task 033: fine-grained token permission guidance is shown in the account profile and maps browse/read, upload, pull-request, and release actions.
- P1 task 129: `SECURITY-OPERATIONS.md` maps trust boundaries and misuse cases to controls and verification evidence.
- P1 task 138: `SECURITY-OPERATIONS.md` provides credential revocation, GCM sign-out, activity review, and replacement steps. It states that local sign-out does not revoke GitHub access.
- P1 task 203: the existing five-second retry delay and Windows Hello/password recovery path are now tracked as complete.

These five P1 tasks are checked in `IMPROVEMENT-BACKLOG.md`; wave 1 is installed. 153 P1 tasks were still open at that point.

## P1 wave 2 - installed

- P1 task 066 adds `UploadPathAudit` to batch upload review. Before a batch is sent, OctoShip flags case-only destination collisions, Windows-reserved names, trailing spaces/dots, Unicode NFC differences, mixed Latin/Greek/Cyrillic letters, and invisible or direction-control characters. It leaves the reviewed destination unchanged and asks the user to confirm the warning.
- The upload verification harness now covers these path cases and explicitly enables the Windows-authentication policy in its lock test, so results do not depend on this user's saved auto-login preference.
- P1 wave 2 is installed as **1.6.1-preview.3** from `installers/OctoShip-Setup-v1.6.1-preview.3-win-x64.exe`; package SHA-256 is `431533F54B2D19E5DB0E5118B02AE211F0EB0505D50DFDF7193DCF537481690A`. The installer is unsigned.
- Release build completed with 0 warnings and 0 errors. Eight offline verification projects passed: upload (22 checks), P0 security (38), preparation (28), session-lock (30), shipping-workbench, uniform UI (51), updates (26), and repository workflows. Tests used fake HTTP where applicable; no GitHub writes occurred.
- Installer exit code was 0. All 474 published payload files matched the installed files by SHA-256; `SECURITY-OPERATIONS.md` is present. The installed process launched from the per-user program folder, loaded the bundled `coreclr.dll`, and reported product version `1.6.1-preview.3+55b634c9f04ce8fa1c344310c117009d23bcc6a0`.
- The user's saved `autoConnect=true` and `requireWindowsAuthentication=false` preferences remained in place; the saved account field remained present. Startup GCM authentication and the readiness report were not independently qualified during this wave. No GitHub write or release publication was attempted.
- A pre-upgrade backup was retained.
- Six P1 tasks are implemented and 152 remain open after wave 2. This does not complete the P1 backlog.

## P1 wave 3 - installed

- P1 task 061 adds an optional clipboard-clear delay in Settings: keep copied text, 30 seconds, 1 minute, or 5 minutes. It applies to copied file paths, SHA-256 hashes, and diagnostics. The timer clears only when the clipboard still contains the exact text OctoShip copied; if the user replaces it, the new contents are preserved. Clearing is off by default, and OctoShip does not copy credentials.
- The preference is credential-free, survives settings export/import, and invalid delay values normalize to off. Verification covers the opt-in default, valid/invalid intervals, exact-content clearing, and preservation of replaced clipboard text.
- Installed as **1.6.1-preview.4** from `installers/OctoShip-Setup-v1.6.1-preview.4-win-x64.exe`; SHA-256 is `39D924436EB4AF49D3551E390AED887AF6090F40605ADEA9F27474A8DDFAF5A2`. The installer is unsigned. It exited 0; all 474 published files matched installed hashes.
- The app launched from the per-user folder with product version `1.6.1-preview.4+55b634c9f04ce8fa1c344310c117009d23bcc6a0` and loaded the bundled runtime. Auto-connect remains enabled, Windows-authentication prompt remains disabled in the app profile, and the saved-account field remains present. Clipboard auto-clear is currently off until enabled in Settings.
- Build: 0 warnings and errors. Offline checks passed: upload (22), P0 security (38), preparation (28), session-lock (30), uniform UI (52), updates/preferences (32), shipping-workbench, and repository workflows. No GitHub writes or release publication occurred.
- A pre-upgrade backup was retained.
- Seven P1 tasks are implemented and 151 remain open after wave 3. This does not complete the P1 backlog.

## P1 wave 4 - installed

- P1 task 131 adds a 2 MiB content limit, 150 ms timeout for each secret-scanning rule, and a two-second end-to-end per-file deadline covering file reads, decoding, and regex work. Timeouts and budget exhaustion return **incomplete / not scanned**, never a clean result. Cancellation still propagates to the caller.
- The release harness checks an exhausted budget produces an incomplete status and runs a maximum-size adversarial text sample under a four-second outer bound. The scan stays heuristic and cannot prove content safe.
- Installed as **1.6.1-preview.5** from `installers/OctoShip-Setup-v1.6.1-preview.5-win-x64.exe`; SHA-256 is `0083E47C1E173575EA4324657C62F396559AC1B83EE1B7B4602ADD640B542F63`. The installer is unsigned. It exited 0; all 474 payload files matched installed hashes, and the app launched with its bundled runtime.
- Build: 0 warnings and errors. Verification passed: scanner/release (36 checks), upload (22), P0 security (38), preparation (28), session-lock (30), uniform UI (52), updates/preferences (32), shipping-workbench, and repository workflows. No GitHub writes or release publication occurred.
- Eight P1 tasks were implemented and 150 remained open after wave 4.

## P1 wave 5 - installed

- P1 task 208 hardens queue-journal and uniform-preference writes. Saves use random temporary names, `CreateNew`, exclusive sharing, write-through flushing, and atomic replacement. Cleanup deletes only the current operation's temp file. Other settings/session temp files already use that pattern under the user's LocalAppData profile.
- The queue test pre-creates a predictable `.tmp` file and proves the save leaves it untouched, then verifies that no temp file created by the operation remains.
- Installed as **1.6.1-preview.6** from `installers/OctoShip-Setup-v1.6.1-preview.6-win-x64.exe`; SHA-256 is `60CABF9FE56CED011634BBB269CD539E17E3AE3A9D772922DF7DB5070367F759`. The installer is unsigned. It exited 0; all 474 payload files matched installed hashes.
- The app launched from the per-user folder with product version `1.6.1-preview.6+55b634c9f04ce8fa1c344310c117009d23bcc6a0` and loaded the bundled runtime. Auto-connect remains enabled, the app-level Windows-authentication prompt remains disabled, and the saved account remains present. Clipboard clearing remains off until the user enables it.
- Build: 0 warnings and errors. Verification passed: upload (24 checks), scanner/release (36), P0 security (38), preparation (28), session-lock (30), uniform UI (52), updates/preferences (32), shipping-workbench, and repository workflows. No GitHub writes or release publication occurred.
- A pre-upgrade backup was retained.
- Nine P1 tasks were implemented and 149 remained open after wave 5. This did not complete the P1 backlog.

## P1 waves 6-7 - installed in preview.9

- P1 task 228 makes preview-handler selection depend on bounded content signatures for PNG, JPEG, GIF, BMP, TIFF, and PDF instead of extensions. Known extension mismatches are labeled in the review warning; unknown binary files receive no preview handler. PDF launch is offered only for detected PDF content and the signature is checked again at click time. Image previews use a 1600-pixel decode width.
- Offline preparation checks cover recognized signatures, plain text, unknown binary, extension mismatch, and matching extensions. These checks do not prove every malformed image/PDF decoder edge case safe.
- Included in **1.6.1-preview.9**, together with the next operations, security, and performance wave; installation and payload verification are summarized in the previous preview.9 installation section below.

- P1 task 144 adds source readiness checks before review and again before transfer. Per-file uploads can continue past an unavailable source; the failed entry can be retried after releasing the lock or removed. A single-commit batch stops before invoking its publisher if any source is missing, inaccessible, locked, or changed. No remote write is retried automatically.
- P1 task 234 removes GitHub error-body display from the main upload path and retains only status-based guidance; the atomic batch client also avoids reading error bodies. Fake 403 regression cases prove credential-like text, private data, and HTML never enter error messages.
- P1 task 072 prunes `.git`, `bin`, `obj`, and `node_modules` by default; supports ordered `*`, `?`, `**`, and negated exclusions; and bounds traversal to 50,000 examined entries by default while retaining reparse-point protections.
- These changes and wave 6 were packaged as **1.6.1-preview.9**. Integrated release build had 0 warnings/errors; all ten offline verification projects passed, including 7 busy-file checks and 4 traversal checks. The main upload and atomic batch HTTP-body tests passed. No GitHub writes were sent.
- The installer exited 0. All 474 payload files match the installed files by SHA-256; product version is `1.6.1-preview.9+55b634c9f04ce8fa1c344310c117009d23bcc6a0`; the installed app launched and loaded bundled `coreclr.dll`. The installer and app are unsigned.
- The saved account field remains present; `autoConnect=true`, `requireWindowsAuthentication=false`, and clipboard auto-clear remains off (`ClearCopiedTextAfterSeconds=0`). Live credential authentication was not qualified. A pre-upgrade backup was retained.
- Thirteen P1 tasks are installed and 145 remain open. No remote publication occurred.

## P1 wave 10 - included in preview.10

- P1 task 037 now generates a CycloneDX 1.5 SBOM for the Windows release payload. It lists resolved .NET package dependencies and every shipped payload file, with SHA-256 hashes for file components.
- The release workflow also runs `dotnet list FileToGitHub.csproj package --vulnerable --include-transitive` and attaches the human-readable audit output with the package, `SHA256SUMS.txt`, and SBOM. The preview.10 local audit reported no vulnerable packages from its configured sources; that result is time- and source-dependent, not proof of vulnerability-free software.
- The SBOM fixture checks passed using `verification/sbom/Test-ReleaseSbom.ps1`. The preview.10 package build produced the CycloneDX SBOM and dependency-audit artifacts.
- The Windows updater is active: it checks the public GitHub release feed at startup and every two minutes while enabled and idle, downloads over HTTPS, and requires GitHub's SHA-256 asset digest to match. Code signing and signed update manifests are not prerequisites.
- Locally built self-contained installer: `installers/OctoShip-Setup-v1.6.1-preview.10-win-x64.exe`; size 56,327,688 bytes; SHA-256 `27B5297D0DF4750C014B931933F9F834DC9BCE48E548501A2D362C379A70E049`. Installer and app are unsigned. No GitHub release publication is claimed.
- Fourteen P1 tasks are implemented in the current source; 138 P1 tasks remain open after moving optional signing/update-manifest work out of P1. This does not complete the P1 backlog.

## Previous preview.9 installation verification

- Previously installed self-contained x64 installer: `installers/OctoShip-Setup-v1.6.1-preview.9-win-x64.exe`
- SHA-256: `5BB3F96BE0082ACAC66F6C5AC077B28DB0AA5568005FC84A5E384A701761DD46`
- Installer exit code: 0.
- Installed product version: `1.6.1-preview.9+55b634c9f04ce8fa1c344310c117009d23bcc6a0`.
- All 474 published payload files matched the installed files by SHA-256. The installed app loaded its bundled `coreclr.dll`.
- `SECURITY-OPERATIONS.md` and its Start menu shortcut were included in the installer.
- A pre-upgrade backup was retained.
- The package contains the .NET 10 runtime. Git for Windows with Git Credential Manager remains an external dependency for GitHub account sign-in.
- The installer is unsigned. Preview.9 predates the current updater behavior; see the preview.10 section above.

## Local P1 follow-up - installed as preview.13

- P1-211 adds synthetic percent-encoded credential fixtures and verifies redaction in diagnostic handling, local Git inspection reports, and support-report previews.
- P1-212 narrows environment inheritance for `TrustedProcess.Create` children while preserving Windows/profile state, PATH, proxy settings, and noninteractive prompt flags; arbitrary token and Git override variables are excluded.
- P1-262 restores keyboard focus to the initiating control after a modal dialog, with a fallback when that control disappears.
- Partial progress remains explicitly open for P1-021 (header-based wait guidance; safe-read retry policy remains open), P1-040 (recycling virtualization and bounded viewports; paging/history coverage remains open), P1-242 (sensitive-pattern input validation only), and P1-245 (settings history/preset confirmations only).
- Release build completed with 0 warnings/errors. `scripts/Publish-WindowsRelease.ps1 -PackageOnly` passed the integrated release checks, including the added environment and destructive-action harnesses; NuGet audit found no vulnerable packages in its configured sources.
- Locally built installer: `installers/OctoShip-Setup-v1.6.1-preview.13-win-x64.exe`; size 56,321,716 bytes; SHA-256 `769E3062C1B08D5521E275264A9626C3F397CDB62A370A88FED24B4ABEEB1C30`. It exited 0, installed product version `1.6.1-preview.13+208915b16af552cd60660be9745d75df1d90eeab`, and all 474 payload files matched the installed copies by SHA-256. The installed app launched with bundled `coreclr.dll` loaded. Installer and app are unsigned.
- Profile backup retained at `%LOCALAPPDATA%\OctoShipBackups\profile-before-preview13-20261015-063712`. Preview.13 changes are local; no commit, push, or public release occurred.

## Verification

- Release build: 0 warnings, 0 errors.
- The preview.9 run passed ten verification projects: uploads, updates, uniform UI, shipping workbench, session lock, repository workflows, P0 security, preparation, busy-file recovery, and traversal.
- Session-lock checks include the option to bypass a stale app-lock prompt when Windows authentication is disabled.
- P0 security checks: 38 passed; write-path checks used fake HTTP and made no GitHub changes.
- Uniform UI checks: 51 passed; screenshots were captured and inspected for the account controls.
- Update checks: 26 passed, including the test installation helper inside a temporary directory.
- Installer payload: 474/474 file hashes matched; installer exit code 0; installed process remained running from the per-user app folder.
- No GitHub write or release publication was exercised in the preview.9 installation verification. Live Git Credential Manager authentication and the readiness report were not qualified there.

Preview.13 package verification was run separately from the historical preview.9 checks above:

- The integrated `scripts/Publish-WindowsRelease.ps1 -PackageOnly` run passed the updater (33), session (30), upload (26), uniform UI (99), P0 security (37), preparation (41), environment (16), and destructive-action (8) checks, plus shipping-workbench, repository-workflow, and SBOM fixture checks.
- The configured NuGet vulnerability audit reported no vulnerable packages from its configured sources. This result is time- and source-dependent.
- The installed preview.13 package was verified locally as described above. These checks do not qualify live GitHub authentication, test a GitHub write, or constitute publication of a GitHub release.

## Remaining work and limits

Preview.13 is installed locally and is the latest published release. The Windows update release workflow succeeded for commit `942e019ad25bf32271670bcbf31f0a3c583e9e2f` and published [v1.6.1-preview.13](https://github.com/ghostventure/OctoShip/releases/tag/v1.6.1-preview.13) with the Windows ZIP, SBOM, dependency-audit report, and SHA256SUMS file. The current working tree marks 17 P1 tasks complete and 135 open by backlog checkbox. This local sprint fully completes P1-211, P1-212, and P1-262. P1-021, P1-040, P1-242, and P1-245 have bounded partial improvements recorded in `IMPROVEMENT-BACKLOG.md` and remain open. Many remaining items need substantial workflow implementation, dedicated failure-injection coverage, accessibility review, or real-user qualification. Publisher signing and signed update manifests are optional distribution assurances outside OctoShip's core GitHub transport scope. Live GCM authentication success and the displayed readiness result remain unqualified.
