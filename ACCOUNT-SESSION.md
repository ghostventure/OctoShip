# Retained account information and inactivity locking

This document describes the Windows implementation. For Linux 1.7.0 behavior, platform differences and verification, see the [Linux guide](linux/README.md) and [release handoff](docs/linux-1.7.0-handoff.md).

The Windows development build retains the selected GitHub account, reconnect preference, destination presets, repository/branch/destination selection, and existing application preferences on this computer. Settings are saved when the main window loses focus or closes, as well as during existing save actions. Privacy mode continues to suppress search history, the previous local search folder, and the newly remembered repository/branch/path workspace fields. GitHub credentials remain managed by Git Credential Manager; OctoShip settings never contain tokens or passwords. This is local retention, not cloud synchronization or a new OctoShip account service.

After **30 minutes without activity in OctoShip**, the application replaces the contents and titles of its WPF windows with a privacy shield. Native dialogs owned by the application are hidden and disabled until unlock. Keyboard/mouse/touch activity in the application resets the timeout; network transfers and activity in unrelated applications do not. The first input after an expired interval does not reset it. A Windows session lock/disconnect also locks OctoShip. The profile card includes **Lock account workspace now**.

Unlock through Windows Hello or the Windows account password fallback. Only a verified Hello result or a successfully authenticated password for the current Windows user's SID restores the workspace. Cancellation, errors, a different Windows identity, and unavailable authentication keep the workspace locked. Passwords exist briefly in native buffers and are cleared before release; they are not stored or converted to managed strings. Passwordless users should use Windows Hello. Windows policy and account type can affect password authentication.

The credential-free `session.json` records the lock flag and last activity. A locked session stays locked across normal restarts; a saved session older than 30 minutes locks on startup. Corrupt existing state fails closed. Pending startup account connection waits for unlock. Session state is refreshed at most every 30 seconds during activity, so a restart can conservatively lock up to 30 seconds earlier than the last input. A storage failure is surfaced in the lock window; retaining the state across restart depends on a writable LocalAppData folder.

New requests made through the main application's shared HTTP clients are rejected while locked. Requests already sent can finish. Existing uploads are not automatically replayed after unlocking; review their state before retrying. A CLI process already started can continue. The shield retains open windows and their in-memory work; closing the app retains existing saved preferences/queues, but does not make every unsaved editor persistent. Explicitly saved preparation plans have their own storage rules documented in SHIPPING-PREPARATION.md.

This is a convenience/privacy lock within the current Windows user session. It is not encryption of project files or settings, protection from another process running as that Windows user, or a replacement for the Windows workstation lock. Windows user authentication protects the local workspace; it is distinct from reauthenticating a GitHub account.

## Build and verification

The app now targets `net6.0-windows10.0.19041.0` to reference Windows authentication APIs. Windows Hello desktop interop requires a supported Windows version; the native password fallback remains available when Hello cannot complete. SDK restore includes the Windows SDK reference package.

```powershell
dotnet build FileToGitHub.csproj -c Release
dotnet run --project verification/session-lock/SessionLockChecks.csproj -c Release
```

The session harness checks exact timeout boundaries, activity extension, sleep/clock rollback, lock persistence, corrupt state, WPF main/child-window masking, close prevention, HTTP blocking before send, and renders the actual lock screen using temporary state. It never prompts for credentials or modifies the real user's account settings. Actual successful Windows Hello/password authentication and an installed-app end-to-end session remain interactive checks, not automated test claims.

Authentication APIs: [Windows Hello desktop verification](https://learn.microsoft.com/en-us/uwp/api/windows.security.credentials.ui.userconsentverifier), [Windows credential prompt](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-creduipromptforwindowscredentialsa), [LogonUser](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-logonusera).
