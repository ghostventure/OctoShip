# OctoShip Windows 1.6.0

Windows updates come directly from the public `ghostventure/OctoShip` GitHub releases feed. This release reduces checks from hourly to every two minutes while unlocked and idle, removes update dependence on GitHub account credentials, and lets Preview follow newer stable versions. A ready update is shown in the status area and installed on normal closure. Later releases can supersede an already staged version. Disabling updates or changing channels during a download prevents that download from being queued for installation.

GitHub Actions packages and publishes a new Windows release when the project version changes on `main`. It tests before packaging, uses a draft until the asset digest is verified, and never replaces an already published version. Packages contain all app files; no binary-delta updates or forced restarts are implemented.

Older preview-channel clients need to select Stable once to receive this stable release. Existing clients retain their hourly interval until updated. Windows and Linux release streams remain separate.

Local verification: Release build completed with zero warnings/errors. Passed 26 update/package/helper checks, 25 session-lock checks, 15 upload checks, 18 repository-workflow checks and 54 rendered UI/update-orchestration checks. The update helper replaced files in an isolated temporary installation, retained the previous DLL and preserved unrelated profile data. Mocked HTTP checks covered account-independent access, opt-out, busy-work deferral and rate-limit backoff. No remote uploads were performed by the test harnesses.

The release ZIP and SHA256SUMS are produced under `installers/release-1.6.0/`. The GitHub Actions run is the authoritative publication result. Other physical computers have not been exercised in this session.
