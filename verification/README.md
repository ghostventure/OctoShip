# Component preview verification

Run from the repository root on Windows with the .NET 6 SDK and Windows Desktop Runtime:

```powershell
dotnet build FileToGitHub.csproj -c Release --no-restore
dotnet run --project verification/uploads/AtomicUploadChecks.csproj -c Release
dotnet run --project verification/repository-workflows/WorkflowTests.csproj -c Release
powershell -NoProfile -ExecutionPolicy Bypass -File verification/secrets-release/run.ps1
```

Verified 2026-10-03: application Release build passed with zero warnings/errors; 15 upload/persistence checks, 17 workflow service/GUI checks, and 30 scanner/release/integration checks passed (62 total). `git diff --check` passed. Tests use temporary files and mock HTTP handlers, not real GitHub changes.

WPF checks show/render/close the release and workflow windows, render the batch window with persistence off, and construct/render MainWindow home/tools without its Loaded handler. This checks UI construction and feature entry controls without triggering account or updater startup. It is not a full installed-application login or live upload test.

The root application excludes generated verification C# files from compilation. Harness sources use `.cs.txt` and explicit compile items. Existing distributable archives and installers remain the previous release; the updated runnable development executable is `bin/Release/net6.0-windows/OctoShip.exe`.

Remaining verification boundary: live authenticated single-file/batch upload, branch/PR creation, release assets/publishing, restart recovery through the installed app, and repackaged installer/update delivery.

GUI arrangement update, 2026-10-04: separate Release build in `dist-layout-preview` passed with zero warnings/errors. The existing 30-check scanner/release/main-window harness passed again. Additional temporary layout checks rendered 1240x820 and 1040x680 content areas, both upload modes, expanded transfer activity, and all four tools tabs. Live WPF checks confirmed editable search text round-trips, filter selection, the filter flyout, its nested dropdown, and toggle reset on dismissal. Account/update startup was disabled in the GUI harness; no GitHub writes were performed. The old running app was preserved while the separate preview was built.

## Native Linux 1.6.0

The first component wave is now ported to Linux. See [Linux port verification](linux-port-1.6.0.md) for the 48 backend tests, 9 GUI workflow tests, loopback GUI upload, live read-only comparison, and package/installation checks. Live GitHub writes are not covered by these checks.
