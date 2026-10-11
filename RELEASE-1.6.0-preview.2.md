# Windows 1.6.0-preview.2 release and handoff

## Changes

- Shared dark theme, controls, dialog styling, account/destination context and six persistent navigation actions.
- Global text size and compact/comfortable spacing; main content scrolls at larger text sizes.
- Existing retained-account and 30-minute lock behavior remains covered by regression checks.
- Automatic GitHub release updates from ghostventure/OctoShip: startup/hourly checks, private-repository authentication, preview version ordering, digest/version/path checks, download staging and installation on normal close. Settings can disable automatic updates. No forced close for automatic installation.
- Corrected feature inventory, storage/security boundaries, architecture, build instructions and updater contract in OCTOSHIP-GUIDE.md.

## Verification on this Windows host

Release build: succeeded with zero warnings/errors. All eight offline suites passed:

| Suite | Result |
|---|---|
| Atomic uploads | 15 checks |
| Repository workflows | 18 checks |
| Account/session lock | 25 checks |
| Preparation | 28 checks |
| Scanner/release | 33 checks |
| Uniform UI | 49 checks plus rendered windows/tabs |
| Updates | 18 version/package/preferences and platform/channel selection checks |
| Shipping workbench | Integration and small-window render passed |

Update checks include stable/prerelease ordering, downgrade comparison, opt-out persistence, a valid staged package, invalid digest, archive traversal/alternate streams, missing binaries and tag/package mismatch. They do not launch the update replacement helper or contact GitHub. GUI images are under `%TEMP%\OctoShip-uniform-ui-preview2`.

## Artifacts

- `installer/payload-1.6.0-preview.2/`: framework-dependent Windows payload.
- `installers/OctoShip-Setup-v1.6.0-preview.2-win-x64.exe`: per-user installer, Authenticode NotSigned.
- `installers/OctoShip-v1.6.0-preview.2-win-x64.zip`: portable payload.
- `installers/OctoShip-win-x64.zip`: identical ZIP under the updater-required asset name, ready for a separately authorized release publication.

SHA-256:

```
Setup  154B19804B9821FD7CEEAF0926EBC2C13138CD19BDD3F766019DA95DF70AA998
ZIP    C29D116D9689C54F5A08B87476D3F8789AEA241B0B64FB81F0BF4D8ADF17E907
```

## Installation status

Installed on 2026-10-11: installer exit 0, ProductVersion 1.6.0-preview.2, all six installed payload files match the final published payload, and both existing saved profile files remain byte-identical across installation. The installed UI exposes Files, Uploads, Repositories, Releases, Activity and Account & settings. A verified pre-upgrade backup was created after normal closure: installers/OctoShip-before-1.6.0-preview.2-20261011-180543.zip. The final build includes Windows-only release selection to skip Linux releases.

## Remaining validation boundaries

Real Windows Hello/password success, live GitHub writes, actual remote self-update delivery and Linux packages were not tested in this release task. No GitHub release was published. The repository needs a newer selected-channel release with `OctoShip-win-x64.zip`, matching package version, and GitHub SHA-256 metadata; a private release also needs account access. Downloaded/staged updates do not themselves establish successful replacement. The helper backs up and attempts restoration on failure; that restoration is not a guarantee against every filesystem failure.

## Next developer steps

Use the current commands in OCTOSHIP-GUIDE.md. Keep generated installers, backups, prepared content and credentials out of Git. Source changes are prepared for main with the concurrent Linux documentation preserved; publication status is recorded in the Git history and GitHub release. Other concurrent Linux work is preserved. Historical releases retain their own documents.
