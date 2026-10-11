# OctoShip 1.6.0-preview.1 local delivery

This local preview combines the 28 requested shipping additions with account/workspace retention and a 30-minute inactivity lock. The full proposed account-center list is not claimed complete: this account change specifically implements retention and session protection using the existing GitHub/Git Credential Manager identity.

Feature behavior and conservative limits: [shipping workbench, features 1-12](SHIPPING-WORKBENCH.md), [preparation tools, features 13-28](SHIPPING-PREPARATION.md), [account retention and lock](ACCOUNT-SESSION.md).

## Artifacts

- Installer: `installers/OctoShip-Setup-v1.6.0-preview.1-win-x64.exe`.
- Portable framework-dependent archive: `installers/OctoShip-v1.6.0-preview.1-win-x64.zip`.
- Published payload: `installer/payload-1.6.0-preview.1/`.
- Installed application: `%LOCALAPPDATA%/Programs/OctoShip for GitHub/OctoShip.exe`.
- Previous installation backup: `installers/OctoShip-before-1.6.0-preview.1-20261011-073037.zip`.

## Verification on 2026-10-11

Release build passed without warnings or errors. All seven suites passed: 25 account-session policy/persistence/WPF/HTTP-gating checks, 28 preparation checks, 15 atomic-upload checks, 18 repository-workflow checks, 33 scanner/release/main-profile render checks, the shipping-workbench integration/UI suite, and 49 uniform UI styling checks across all windows and dialogs. Network writes were mocked. The settings TabControl template exposes its selected content host for accessibility and installed-app automation.

Per-user installer returned exit code 0. Existing profile files were unchanged by installation. Installed payload files were compared with the published payload and matched. The installed app launched successfully, both new feature entry points were present, shared uniform UI controls applied across windows, and the real account lock command masked the main window and opened the Windows unlock controls.

Manual boundary: successful Windows Hello or current-user password authentication must be completed interactively. No password is requested through chat or stored by the application. Live authenticated GitHub writes, release publishing/download checks, Pages checks, attestation trust, and public updater delivery remain separate integration work. The existing updater repository/feed is not repaired or published by this local release. No remote release or source push was performed.
