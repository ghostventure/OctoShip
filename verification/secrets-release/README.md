Run on Windows with the .NET 6 SDK and desktop runtime:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File verification/secrets-release/run.ps1
```

Builds a temporary test project referencing the application project. Test source has a `.cs.txt` extension so the application does not compile it. Test build intermediates stay in the temporary directory.

Checks secret detection, redaction, scan limits, cancellation, draft-only creation, asset request bytes/host, explicit publishing and safe errors through a mock HTTP handler. An STA WPF smoke test shows, renders, and closes the release window, verifies publishing starts disabled, and proves opening it makes no HTTP requests. No GitHub changes occur. The rendered screenshot is `%TEMP%\OctoShip-release-smoke.png`.

Also constructs MainWindow without showing it, renders its home/tools content, and checks the Resume saved batch and Prepare a release controls. The test verifies MainWindow's Loaded handler is not invoked, avoiding authentication/update startup actions. BatchUploadWindow is constructed and rendered with queue persistence disabled. Additional screenshots: `%TEMP%\OctoShip-main-smoke.png`, `%TEMP%\OctoShip-tools-smoke.png`, `%TEMP%\OctoShip-batch-smoke.png`.
