# OctoShip Windows 1.6.0

Windows updates come directly from the public `ghostventure/OctoShip` GitHub releases feed. This release reduces checks from hourly to every two minutes while unlocked and idle, removes update dependence on GitHub account credentials, and lets Preview follow newer stable versions. A ready update is shown in the status area and installed on normal closure. Later releases can supersede an already staged version. Disabling updates or changing channels during a download prevents that download from being queued for installation.

GitHub Actions packages and publishes a new Windows release when the project version changes on `main`. It tests before packaging, uses a draft until the asset digest is verified, and never replaces an already published version. Packages contain all app files; no binary-delta updates or forced restarts are implemented.

Older preview-channel clients need to select Stable once to receive this stable release. Existing clients retain their hourly interval until updated. Windows and Linux release streams remain separate.

Local verification: Release build completed with zero warnings/errors. Passed 26 update/package/helper checks, 25 session-lock checks, 15 upload checks, 18 repository-workflow checks and 54 rendered UI/update-orchestration checks. The update helper replaced files in an isolated temporary installation, retained the previous DLL and preserved unrelated profile data. Mocked HTTP checks covered account-independent access, opt-out, busy-work deferral and rate-limit backoff. No remote uploads were performed by the test harnesses.

The release ZIP and SHA256SUMS are produced under `installers/release-1.6.0/`. The GitHub Actions run is the authoritative publication result. Other physical computers have not been exercised in this session.

Published stable release: https://github.com/ghostventure/OctoShip/releases/tag/v1.6.0

Publication workflow: https://github.com/ghostventure/OctoShip/actions/runs/38506455527 (source commit `ead4c4ce0dc17e7af2e4dc8da86d931bcdaaa850`). The unauthenticated API asset download returned HTTP 200 with `application/octet-stream`; its 6,912,681 bytes matched GitHub's SHA-256 digest `6c9b7a55f861357f3d7699fd237607b05aedd2e3fc5815dfcc19479dca2abbd9`. The downloaded public ZIP passed the same 26 update checks, including package/tag validation and actual replacement in an isolated test installation.

Reproduce package validation with `dotnet run --project verification/updates/UpdateChecks.csproj -c Release -- <downloaded-zip> <expected-sha256>`. The test never replaces the real installed application. The existing local app remains on preview.2; an attempted local install command was rejected by automatic approval review, and its open window was left intact. Upgrade through the app's Check for updates command when ready.
