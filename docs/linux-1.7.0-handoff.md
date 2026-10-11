# OctoShip Linux 1.7.0 handoff

This records the Windows-to-Linux port, packaging, verification and GitHub publication completed on 2026-10-11. It contains no account credentials or private runtime settings.

## Release identity and outcome

| Item | Recorded value |
| --- | --- |
| Repository | [ghostventure/OctoShip](https://github.com/ghostventure/OctoShip), public; default branch `main` |
| Previous Linux release | `linux-v1.6.1` |
| Windows source baseline | `eed472eccfba82039bc9a0dc5ca047da5fef2b34` |
| Linux application commit | `9134d3ad6d7664c3c5047e8ee6d27dd44b7a1ca7` |
| Release tag | `linux-v1.7.0`, pointing to that application commit |
| Published release | [OctoShip Linux 1.7.0](https://github.com/ghostventure/OctoShip/releases/tag/linux-v1.7.0) |
| Publication time | 2026-10-11 17:06:04 UTC / 13:06:04 America/New_York |
| Release status at verification | Public, published, stable; GitHub **Latest** |
| Moving latest-release URL | [Latest release](https://github.com/ghostventure/OctoShip/releases/latest) |

The Windows update was fast-forwarded into the local checkout, then its new workflows were ported into the existing Python/Tk Linux application. Windows application sources were retained. The Linux implementation and documentation were pushed to `main`. Tested binaries were subsequently uploaded, verified and published as Latest at the user's request.

The documentation follow-up also incorporates upstream `4a6c35a` (general OctoShip guide and subsequent Windows UI refinements) without discarding that work. Those later Windows refinements are not a rebuild of the released Linux binaries. See the [cross-platform guide](../OCTOSHIP-GUIDE.md) for broader Windows architecture and features.

This handoff is a documentation follow-up: the release tag and uploaded binaries remain pinned to the tested application commit. Newer documentation commits do not imply rebuilt binaries. Installation tests used disposable environments; this work did not upgrade the user's existing desktop installation. Install a download below to use this release locally.

## Published downloads

| Asset | Bytes | Purpose |
| --- | ---: | --- |
| [OctoShip-1.7.0-linux-x86_64.run](https://github.com/ghostventure/OctoShip/releases/download/linux-v1.7.0/OctoShip-1.7.0-linux-x86_64.run) | 48,740,194 | Self-contained graphical/per-user installer |
| [octoship_1.7.0-1_amd64.deb](https://github.com/ghostventure/OctoShip/releases/download/linux-v1.7.0/octoship_1.7.0-1_amd64.deb) | 36,453,920 | Bundled Debian/Ubuntu/Kali package |
| [octoship-1.7.0-linux-x86_64-bundled.tar.gz](https://github.com/ghostventure/OctoShip/releases/download/linux-v1.7.0/octoship-1.7.0-linux-x86_64-bundled.tar.gz) | 48,738,253 | Portable bundle |
| [OctoShip-1.7.0-SHA256SUMS.txt](https://github.com/ghostventure/OctoShip/releases/download/linux-v1.7.0/OctoShip-1.7.0-SHA256SUMS.txt) | 300 | Checksums for the three packages |

SHA-256 values:

```text
15c301663a297a35d5121d0bb6dd730fa80bed347c031fe57979af2d009b2ba3  OctoShip-1.7.0-linux-x86_64.run
80648651dd28663d2cc47a602efca2c9624de927e27be04cf8c4723509101bb0  octoship_1.7.0-1_amd64.deb
a668d86472e2312fbf843a0377f3942da59ea4c2950aafb1b81684177461b084  octoship-1.7.0-linux-x86_64-bundled.tar.gz
445efa4ab3842b061f3d25b4a61a57125c6fc6313fa0f59c19c1c310d8ef1e10  OctoShip-1.7.0-SHA256SUMS.txt
```

All four uploaded assets matched their local size and GitHub-reported SHA-256 digest before publication. After publication, the unauthenticated latest-release API returned `linux-v1.7.0`, and an anonymous checksum-file download matched the local file. The three large binaries were verified through GitHub's uploaded-asset digests; they were not all downloaded again anonymously. Checksums detect corruption but are not an independent publisher signature.

Generated artifacts remain under ignored `dist/linux/`. The source-only `.deb` and source archive also built locally; they were not attached to this release.

## Installation, upgrade and rollback

Supported target: Intel/AMD x86_64 Linux, glibc 2.17+, with X11 or XWayland. The bundle contains Python 3.12.15, Tcl/Tk 9.0.4, GitHub CLI 2.102.0 and certifi 2026.7.22 CA data. The host supplies PAM and its `login` policy for workspace unlocking; PAM configuration is not replaced. ARM, 32-bit and musl/Alpine builds are not provided.

Download the chosen package and checksum file from the release above. If all three package files are present, verify them together:

```sh
sha256sum -c OctoShip-1.7.0-SHA256SUMS.txt
```

If downloading one package, use `sha256sum <filename>` and compare its complete digest to the corresponding published line; `sha256sum -c` otherwise reports the absent packages.

For the graphical per-user installer:

```sh
sh OctoShip-1.7.0-linux-x86_64.run
```

For non-graphical installation, optionally with a custom prefix:

```sh
sh OctoShip-1.7.0-linux-x86_64.run --install
sh OctoShip-1.7.0-linux-x86_64.run --install --prefix "$HOME/Apps/OctoShip" --no-desktop
```

For the bundled Debian package:

```sh
sudo apt install ./octoship_1.7.0-1_amd64.deb
```

The per-user default prefix is `$XDG_DATA_HOME/octoship` or `~/.local/share/octoship`; menu entries and `~/.local/bin/octoship` are registered unless disabled. The Debian package installs in `/opt/octoship`, with `/usr/bin/octoship`. A per-user launcher earlier on PATH can still open an older build; use the intended launcher explicitly and check `octoship --diagnostics`.

Upgrades retain version/payload-hash build directories and back up replaced launchers. Close the old app before launching the updated one: only one instance runs per user. For rollback, launch a retained older build's `octoship` directly. Do not assume older versions understand every newer preference/plan; preserve explicit plans and do not overwrite them during rollback. `octoship --uninstall` removes the selected per-user build after confirmation and preserves user data, CLI credentials and older builds. Remove the system package through the package manager.

Use **OctoShip GitHub Sign-in** or `octoship --login` for CLI-managed authentication, then **Connect / Refresh**. Source-only launches use `gh auth login` followed by `./linux/octoship-linux`. The application has no automatic Linux update installer.

## Feature map

These correspond to the Windows shipping feature numbers documented in [workbench](../SHIPPING-WORKBENCH.md) and [preparation](../SHIPPING-PREPARATION.md). Linux behavior and limits are authoritative in [the Linux guide](../linux/README.md).

| Area | Linux 1.7.0 behavior |
| --- | --- |
| Workbench features 1–12 | Reviewed project shipment; immutable-commit checks; account/rules/Pages evidence; CLI attestation checks; local Git inspection; existing-draft recovery; release download testing; recipes and adjustable display controls |
| 13: Destination mapping | File/folder pickers, explicit destination listing and double-click editing; no Explorer drag/drop |
| 14: Selective publishing | Independent UTF-8 edit blocks, fixed baseline, retained unselected line endings; one file, 1 MiB, 2,000 lines |
| 15: Move hints | Unique identical-content move suggestions in shipment review; old paths remain |
| 16: Empty folders | Stage `.gitkeep` without modifying the source folder |
| 17: ZIP inspection | Bounded entry/content inspection without extraction; unsafe and unscanned entries labelled |
| 18: Large files/LFS | Large-file and `.gitattributes` guidance; no automatic LFS upload |
| 19: Identity | Fresh authenticated login/public profile; exact API commit email remains unavailable |
| 20: Visibility | Fresh visibility displayed and rechecked before publication; saved-binding drift warned |
| 21: Account binding | Project/repository account binding enforced in preparation publication |
| 22: Offline preparation | Private JSON plans reference current local files; fresh review required before publishing |
| 23: Uncertain publication | Read back head/ancestry with a separate timeout budget; never replay the final PATCH automatically |
| 24: Version consistency | package.json, .csproj, Inno Setup defines and supported numeric installer filenames |
| 25: Installer inspection | ELF/PE architecture, no execution; Windows signature trust/version-resource extraction unavailable |
| 26: Download channel | Latest 100 releases, supplied stable/prerelease expectation, exact tag and asset name |
| 27: Markdown links | Inline relative link/image existence, capitalization and project-escape checks; not a complete Markdown parser |
| 28: Support report | Preview/save redacted app/OS/failure/status reports; user review still required |
| Account/session update | Persistent 30-minute/manual lock, Linux PAM verification, window/dialog masking and API guards |
| Uniform display update | Dark native controls, 12–18 point settings, compact spacing, wrapped actions and scrollable workbench pages |

Ship-project review pins account, visibility, local bytes and remote base commit. Publishing creates a fresh branch, atomically uploads changed files, checks the immutable commit and creates a draft PR. It rejects changed review inputs and identifies the branch if an operation becomes uncertain. Preparation publication similarly requires fresh identity, visibility, permissions, head and content review. Neither workflow deletes remote files automatically.

## Architecture and local data

| Module | Responsibility |
| --- | --- |
| `linux/octoship/app.py` | Main UI, asynchronous workers, deferred callbacks during lock, startup preferences/reconnect |
| `core.py` | GitHub transport, lock guards, sensitive-path rules, bounded reads, signed-download redirect credential stripping |
| `workflows.py` | Atomic/per-file upload workflows, branches/PRs/releases, uncertain ref-update reconciliation |
| `workbench.py` | Reviewed shipment, immutable verification, diagnostics, recipes, release checks/recovery |
| `preparation.py` | Offline mappings, bindings, selective baselines, staging and reviewed publication |
| `inspection.py` | ZIP/project/Markdown/version/installer inspection and support redaction |
| `workbench_ui.py` | Five workbench pages and display/privacy settings |
| `session.py` | Persistent timeout state, PAM conversation/account/UID validation, masking and optional logind monitoring |
| `storage.py` | Private atomic JSON saves and bounded JSON reads |
| `scanner.py`, `queue_store.py`, `theme.py`, `tools_ui.py` | Existing scanning, queue journals, shared appearance and repository tools |

Automatic state is under `$XDG_STATE_HOME/octoship` (default `~/.local/state/octoship`):

| Path | Contents / retention |
| --- | --- |
| `preferences.json` | Display/privacy/reconnect settings; workspace/account label omitted in privacy mode |
| `session.json` | Lock flag and last activity; no authentication secrets |
| `project-bindings.json` | Explicit project/repository account and visibility expectations |
| `prepared/` | Explicit staged text/placeholder copies; may contain project content |
| `queues/` | Opt-in upload journals with paths, hashes, size, destinations and statuses |
| User-selected plan path | Explicit JSON plan containing local source paths; no frozen content snapshot |

New state directories/files are private (0700/0600). Explicit plans, bindings and queue saves are separate from automatic privacy preferences. GitHub CLI owns its own credential storage. Passwords are never written to OctoShip settings or reports; Python/Tk cannot guarantee erasure of every transient in-memory string. The single-instance advisory lock is under `$XDG_RUNTIME_DIR/octoship`, falling back to `~/.cache/octoship`.

The workspace lock is a local privacy feature, not encryption or protection from other processes running as the same user. It hides main, child and Tcl-created native dialogs, rejects new API requests, and defers completion dialogs until unlock. Already-sent requests/CLI processes may finish. Unlock requires successful authentication, account validity and matching current UID under system PAM policy. Missing/failed authentication stays locked. Corrupt/expired/locked saved state locks on restart. With a session ID and logind, desktop lock/inactive-session state is polled every two seconds; manual/app timeout locking works without logind.

## Verification and reproducible checks

Completed results: **86 backend tests**, **9 existing GUI tests**, **6 shipping/session GUI tests**, and the loopback HTTP upload smoke test passed. Backend/GUI checks also passed with the bundled runtime in an isolated Debian filesystem. Actual current-user PAM authentication restored the running Linux GUI on Kali. No password or credential value is retained in this documentation or test fixtures.

```sh
python3 -m unittest discover -s linux/tests -v
xvfb-run -a ./linux/octoship-linux --smoke-test
PYTHONPATH=linux xvfb-run -a python3 linux/tests/gui_smoke.py
PYTHONPATH=linux xvfb-run -a python3 linux/tests/gui_workflows.py
PYTHONPATH=linux xvfb-run -a python3 linux/tests/gui_shipping.py
python3 -m compileall -q linux/octoship
git diff --check
```

Build from the release tag in a separate clean checkout to preserve the active workspace:

```sh
git clone --branch linux-v1.7.0 --single-branch https://github.com/ghostventure/OctoShip.git OctoShip-linux-1.7.0
cd OctoShip-linux-1.7.0
python3 linux/packaging/build-standalone.py
sh linux/packaging/build-deb.sh
```

The bundled builder uses pinned download digests from `linux/packaging/bundle-lock.json`; first use needs network access. Archives can vary with build timestamps, so compare released downloads to the published release checksums rather than assuming a rebuild is byte-identical.

Isolated package checks require Bubblewrap, Xvfb and a trusted minimal Debian root filesystem/archive with the desktop libraries required by the harness. The tested filesystem had no system Python, Tk or GitHub CLI. Do not point these commands at the host root filesystem.

```sh
xvfb-run -a python3 linux/tests/verify_bundle.py \
  dist/linux/OctoShip-1.7.0-linux-x86_64.run /path/to/debian-12-rootfs
xvfb-run -a python3 linux/tests/verify_deb.py \
  dist/linux/octoship_1.7.0-1_amd64.deb /path/to/debian-12-rootfs.tar.gz
```

The `.run` check covered offline installation, diagnostics, startup, backend/GUI workflows, reinstall and uninstall. The `.deb` check covered offline installation, diagnostics, startup, package audit and removal. Final bundled Python sources were compared to the committed application sources. Raw temporary logs/screenshots remain local; durable outcomes and boundaries are recorded in [the verification report](../verification/linux-port-1.7.0.md).

Two verification fixes are captured by regressions: Tcl-created file dialogs require string-path enumeration rather than Python-only widget enumeration; the isolated PAM ABI test supplies a fixture identity instead of assuming the host UID exists in the container's account database. Neither test requires a real password. The separate actual PAM check was performed locally and was not added as a credential-bearing fixture.

## Release procedure and maintenance

For this publication, the source was committed/pushed, a draft `linux-v1.7.0` release was created at the exact application commit, and four assets were uploaded. Asset state, byte size and SHA-256 were verified against local files before `gh release edit linux-v1.7.0 --draft=false --latest`. The public latest endpoint and checksum download were then checked. The tag still resolves to the tested application commit; no tag was moved.

For a future release:

1. Review the Windows delta and Linux behavior, document platform differences, update Linux version/package documentation, and keep credentials/runtime state out of the public repository.
2. Run affected behavioral checks and GUI/package verification; record the real outcomes and untested boundaries.
3. Commit/push the source. Build artifacts from that exact revision; generate and verify checksums.
4. Create a **new** versioned draft tag/release at the application commit. Upload reviewed assets and confirm all states, sizes and digests.
5. Publish and mark Latest only when publication is authorized. Confirm public release flags, exact tag target and download access.
6. Keep old releases for rollback. Correct documentation in later commits; do not silently overwrite existing released artifacts or repoint a version tag.

This release's latest status can be checked without credentials:

```sh
curl -fsSL https://api.github.com/repos/ghostventure/OctoShip/releases/latest
```

For operator inspection with authenticated GitHub CLI:

```sh
gh release view linux-v1.7.0 --repo ghostventure/OctoShip
git ls-remote origin refs/tags/linux-v1.7.0
```

## Troubleshooting and limits

- **Older build opens:** inspect `octoship --diagnostics` and launcher/PATH precedence; choose the per-user or system installation intentionally.
- **Cannot connect:** sign in through the active bundle's CLI, confirm its account, then reconnect. Permission, rate-limit and SSO evidence is reported without inventing missing permission names.
- **PAM unlock fails:** use the current Linux account, verify that system PAM/login policy is available and permits that account, and inspect the desktop's authentication setup. Errors retain the lock. Do not delete lock state as an authentication workaround.
- **Session state cannot be saved:** restore access to the configured state folder; restart retention depends on writable storage.
- **Publication unconfirmed:** inspect the reported commit/branch on GitHub before retrying. Do not replay the operation blindly.
- **Draft recovery mismatch:** preserve the existing asset and resolve it deliberately; recovery does not delete or overwrite same-name assets.
- **Unknown diagnostic / unverified download:** absence of API access, a reference digest or endpoint support is not success. Anonymous redirects alone do not prove final public access.

Live production branch/PR/upload/release workflows inside OctoShip were not tested against a user destination; those behavioral tests used fixtures. Publishing this software release with GitHub CLI does not establish production correctness of every in-app mutation. Real release attestations were not generated or trust-verified for these installers. Successful PAM verification covers the tested host/policy; physical desktop lock/resume across all environments remains unverified. Windows Hello, Authenticode, Windows version resources, automatic LFS conversion, deletion synchronization, full Windows accessibility parity and older Windows-only features listed in the Linux guide remain outside the port.
