# OctoShip for GitHub — User Guide

This guide describes OctoShip for Windows. It helps you find and review local files and send the files you select to GitHub using an account you authorize. OctoShip is not GitHub. Available screens and features can vary by version.

## Before installing

- Use 64-bit Windows 10 or Windows 11 (Windows 10 build 19041 or later).
- Install Git for Windows with Git Credential Manager and sign in to your own GitHub account. These are required for GitHub sign-in and are not bundled by the Windows installer.
- Read the installer agreement and notices. Choose **I accept** to continue or **Cancel** to stop setup.
- OctoShip itself installs per-user. If the .NET 10 Desktop Runtime is missing, Setup downloads it from Microsoft and may request administrator approval to install the shared runtime. An internet connection is needed for that download. The versioned ZIP package includes its own runtime and can run offline after download.

The Windows installer, app executable, and OctoShip window title bars use the OctoShip icon. The installed application also includes the vector logo and icon files in its `Branding` folder. Existing installations show a new icon only after they are updated or reinstalled with a build that contains it; a source change by itself does not update the installed app.

## First launch and connect

1. Open **OctoShip for GitHub** from the Start menu.
2. On a fresh Windows profile, OctoShip starts disconnected. Choose or add your own GitHub account, then connect through Git Credential Manager.
3. Automatic sign-in is off by default on a fresh profile. You may enable it after selecting your account. It reuses the local credential manager; it does not put your token in OctoShip settings.
4. Check the account shown in OctoShip before performing a repository action.

OctoShip can use the local Git Credential Manager account you select. The credential manager and GitHub control authentication and permissions.

## Find and review files

Choose a local folder, enter a filename or content search, and narrow results with available filters such as file type, size, date, exclusions, recursion, and hidden-file settings. Select a result to review its path, preview where supported, local SHA-256, and any available remote comparison.

Previews are for review; they are not a code editor or a safety certification. Secret scanning and sensitive filename checks are limited aids. They may miss sensitive or harmful content. Large, binary, or unsupported files may not be scanned. Inspect the exact files and destinations yourself, especially for credentials, personal information, private source, or confidential material.

## Send files to GitHub

Before confirming a write, review the account, repository, branch, destination path, commit message, file list, and conflict choice. OctoShip checks some permissions, branch state, destination conflicts, and file-safety rules, then sends the operation to GitHub. GitHub decides whether to accept it under the account's permissions and repository rules.

Batch workflows can offer ordering, conflict handling, progress, pause, cancel, retry, and saved-queue recovery, depending on the build. A saved queue does not automatically upload after restart. Some workflows create commits, branches, pull requests, or draft releases; publishing a release is a distinct action where provided. Read each confirmation dialog before proceeding.

If a transfer is interrupted or times out, the remote write may still have completed. Check the GitHub repository, branch, commits, pull requests, or release before retrying to avoid duplicate work.

## More review, operations and repository tools

Recent Windows previews add a shipping operations panel with attempt history, workflow sequencing, closeout summaries, network-change safeguards, repository relink guidance, storage and duplicate checks, temporary-file cleanup preview, and safer queued-job reordering. Account & settings adds workspace health and archive controls, credential-free settings backup/import with conflict choices, profile repair, retention preview/purge, screen-share masking, private-repository rules, settings search, pending-change review, and section reset.

File review adds policy review/import preview, navigation history, clearer empty states and search errors, adjustable columns, long-path copying, range selection, diff navigation, draft recovery, and revision markers. Repository and release tools add saved GitHub queries, issue triage and creation from a file path, milestone/project linking, reviewer requests, stale-branch cleanup preview, tag management, private-repository setup, draft-release asset repair, and release comparison. These actions remain subject to GitHub permissions and explicit confirmation. Project linking uses classic GitHub Projects; lists can be page-limited. Some local storage and duplicate checks are heuristic, and screen-share masking does not cover every editable field or dialog.

## Settings and local information

Windows preferences are stored under `%LOCALAPPDATA%\OctoShipForGitHub`. Depending on options and actions, local files can include preferences, selected account/workspace names, local paths, search or repository history, queue recovery data, prepared files, and update packages. Privacy mode suppresses some history; it does not erase data already sent to GitHub, Windows credential storage, backups, or all local artifacts. Review settings exports before sharing them because they may contain histories or local paths.

GitHub tokens are retrieved from Git Credential Manager and are not intentionally written to ordinary OctoShip settings. Tokens are present in memory while connected, and the security of that memory depends on your Windows account and device. OctoShip's inactivity lock is a privacy shield, not encryption or protection against another process running with the same user privileges.

## Updates and troubleshooting

When enabled, the Windows updater checks OctoShip's public GitHub releases, downloads a compatible package over HTTPS, and verifies it against GitHub's SHA-256 asset digest before staging. The digest checks that downloaded bytes match GitHub's selected asset; it is not Authenticode signing or independent publisher identity verification. Update availability requires internet access.

- **Cannot connect:** confirm Git for Windows/Git Credential Manager is installed, your intended account is signed in, and the account can access GitHub.
- **Write denied:** check the selected account, repository permission, branch protection, and organization approval requirements.
- **File flagged or unscanned:** inspect it manually and remove secrets or content you are not authorized to publish.
- **Uncertain result after an error:** check GitHub before retrying.
- **Need to remove OctoShip:** use Windows Installed apps or the Start-menu uninstaller. Uninstalling preserves user preferences and Git Credential Manager credentials; manage those separately if you want them removed.

For pre-install terms, privacy, third-party software, and copyright reporting, read `OCTOSHIP-TERMS-AND-NOTICES.txt`, `OCTOSHIP-PRIVACY-NOTICE.txt`, `THIRD-PARTY-NOTICES.txt`, and `OCTOSHIP-COPYRIGHT-AND-DMCA-NOTICE.txt` in the installed `Docs` folder. These notice files are drafts until the publisher verifies and completes them with qualified counsel.
