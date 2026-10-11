# Linux 1.7.0 — October 11 Windows update port

Source baseline: Windows commit `eed472eccfba82039bc9a0dc5ca047da5fef2b34`
(`Add shipping workbench, preparation tools, account lock, and uniform UI`).
The existing Linux 1.6.1 client was updated in place; Windows sources were retained.

## Implemented

- Reviewed project shipment to a new branch and draft PR, immutable-commit byte
  verification, unchanged-file skipping and unique identical-content move hints.
- Account/rules/Pages diagnostics, portable recipes, local Git inspection,
  attestation verification, stable/prerelease channel checks, draft asset recovery
  and release-download verification.
- Offline plans, editable destination mappings, selective UTF-8 edit blocks,
  empty-folder placeholders, account bindings and fresh visibility/identity review.
- Bounded ZIP, LFS/large-file, version, Markdown and ELF/PE architecture inspection;
  redacted support reports.
- Private preferences, optional reconnect, adjustable display/spacing, scrollable
  tool pages and wrapped action rows at large font sizes.
- Persistent inactivity/manual workspace lock, Linux PAM account authentication,
  optional logind monitoring, hidden main/child/native Tcl dialogs, deferred UI
  callbacks and transport guards while locked.
- Lost ref-update response reconciliation without replaying PATCH; 50 MiB upload
  limit matching the current Windows uploader.

## Verification completed on 2026-10-11

- **86 backend tests passed** on host Python 3.14 and bundled Python 3.12.15.
  They include stale local/head/account/visibility rejection, content and path
  protections, uncertain publication reconciliation, selective reconstruction
  (100 randomized repeated-line examples), plan persistence, ZIP/Markdown/version
  checks, recovery mismatch preservation, streaming asset redirect credential
  stripping, session persistence and PAM native ABI/UID/account-validation behavior.
- **9 existing GUI workflow tests and 6 new GUI tests passed**, on host Tk and
  bundled Tcl/Tk 9.0.4. They cover explicit shipment/preparation publication,
  default/18-point layouts, privacy settings, locked callbacks, child windows,
  Tcl-created native dialogs and restored modal grabs. A rendered workbench
  screenshot was visually reviewed locally.
- The actual GUI review/confirm/upload loop passed against a loopback HTTP server.
- **Actual current-user Linux PAM authentication passed** in the running Tk GUI
  on the Kali host: locked contents were hidden, successful authentication restored
  the workspace, and no password was saved. No privileged execution was needed.
- Live authenticated GitHub read-only access verified the public OctoShip repository,
  current main commit and push permission. Tests did not create remote branches,
  commits, PRs, releases or assets.
- The self-contained `.run` installer passed offline installation, diagnostics,
  GUI startup, all backend/GUI workflows, reinstall and uninstall inside an isolated
  minimal Debian filesystem without system Python, Tk or GitHub CLI.
- The bundled `.deb` passed offline installation, diagnostics, GUI launch, package
  audit and removal inside a disposable minimal Debian filesystem. The source-only
  Debian package and portable source archive also built successfully.
- Python compilation and `git diff --check` passed.

Commands are in [the Linux guide](../linux/README.md). Installer isolation harnesses:
`linux/tests/verify_bundle.py` and `linux/tests/verify_deb.py`.

## Artifact checksums

Built locally under ignored `dist/linux/`; binaries are not committed or attached
to a GitHub release by this source update.

```text
15c301663a297a35d5121d0bb6dd730fa80bed347c031fe57979af2d009b2ba3  OctoShip-1.7.0-linux-x86_64.run
80648651dd28663d2cc47a602efca2c9624de927e27be04cf8c4723509101bb0  octoship_1.7.0-1_amd64.deb
a668d86472e2312fbf843a0377f3942da59ea4c2950aafb1b81684177461b084  octoship-1.7.0-linux-x86_64-bundled.tar.gz
```

## Boundaries

GitHub mutations and real release/attestation trust workflows were exercised with
fixtures, not against a live destination. The real PAM success check covers this
host's account/policy, not every Linux distribution or desktop. Desktop lock
monitoring depends on logind and a session ID; the app's timeout/manual lock works
independently. The lock does not encrypt project data.

Linux uses pickers instead of Explorer drag/drop; Windows Hello is replaced by
PAM. Windows Authenticode trust and version-resource inspection remain explicitly
unverified on Linux. Full Windows UI Automation parity, automatic LFS conversion,
deletions, automatic updater installation and pre-existing Windows-only features
listed in the Linux guide are outside this port. Settings are retained locally;
Windows preference stores are not migrated.
