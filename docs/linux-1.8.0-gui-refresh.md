# Linux 1.8.0 GUI refresh

Status: source preview on `main`; not published to GitHub Releases. The published stable Linux
release remains 1.7.0. This work is based on main at `af5d2a6`.

## What changed

- Charcoal surfaces, violet primary actions, rounded controls, smooth system fonts,
  larger page headings, muted secondary text, and alternating file rows.
- Sidebar navigation for uploads, repository tools, and shipping. It switches to
  short labels below 1200 pixels. Ctrl+1, Ctrl+2, and Ctrl+3 switch workspaces.
- A file count and empty-state guidance; batch/queue options expand through
  **Upload settings**. The existing review and explicit publication steps remain.
- The shipping workbench recalculates its scroll area when button rows wrap, so
  controls remain reachable at the largest display text setting.
- The bundle launcher uses installed Python 3.10+/Tk 8.6+ when available, giving
  this Kali desktop antialiased fonts. It clears bundled Tcl script paths before
  launching system Tk. Python stays isolated; bundled GitHub CLI and CA data remain.
- `OCTOSHIP_UI_RUNTIME=auto|system|bundled` controls runtime selection.
  `octoship --diagnostics` identifies the active runtime. Machines without distro
  Python/Tk continue using the complete offline bundle. Its font rendering can be
  less smooth than distro Tk.

## Build and verification

```sh
python3 -m unittest discover -s linux/tests -v
PYTHONPATH=linux xvfb-run -a python3 linux/tests/gui_workflows.py
PYTHONPATH=linux xvfb-run -a python3 linux/tests/gui_shipping.py
python3 linux/packaging/build-standalone.py
xvfb-run -a python3 linux/tests/verify_bundle.py \
  dist/linux/OctoShip-1.8.0-linux-x86_64.run \
  dist/linux/debian-bookworm-test-root
```

The shipping GUI test teardown collects destroyed Tk objects on the main thread;
otherwise a subsequent background worker can collect old Tk variables and stall.
Layout checks cover 1000x760 and 1180x860, including shipping text at 18 points.
GUI workflow tests use fake GitHub responses and do not publish remote changes.

## Installation and rollback

The per-user installer preserves older builds, queues, preferences, and GitHub CLI
credentials. Reinstall with:

```sh
sh dist/linux/OctoShip-1.8.0-linux-x86_64.run --install
```

Close OctoShip normally before reopening it through the desktop launcher. The old
1.7.0 payload is retained below `~/.local/share/octoship/builds/`; reinstalling the
verified 1.7.0 installer restores its launcher if a rollback is needed. Do not
remove application state or sign out as part of a visual rollback.

## Verified local result — October 11, 2026

- All 86 backend tests, 9 upload/repository GUI tests, and 6 shipping/session GUI
  tests passed on the host. The same suites and GUI smoke tests passed inside an
  offline Debian rootfs without system Python, Tk, or GitHub CLI.
- Installer reinstall and uninstall checks passed in the isolated test home.
- SHA-256 verification passed for the `.run`, bundled `.deb`, and portable tarball.
- At 1000x760 with saved 12-point text, the file list remains 120 pixels high;
  expanding upload settings leaves 76 pixels. At 1320x900 it has more room.
- Installed payload: `~/.local/share/octoship/builds/1.8.0-4f0b8f30ae3d`.
  Auto diagnostics confirmed Python 3.14.7/Tk 8.6 in isolated system mode;
  forced bundled diagnostics confirmed Python 3.12.15/Tk 9.0.
- Closed the old 1.7.0 window normally and launched the installed 1.8.0 window.
  The desktop reported it viewable at 1320x900; its launch log had no errors.
- Source changes and documentation are included on `main`. The validated installer
  artifacts remain local; no 1.8.0 GitHub release was published.

Artifact checksums:

```
3a41257783f48e79702a1dd838e675300bf9cc745568fe1168784ca14fbee208  OctoShip-1.8.0-linux-x86_64.run
ff0a69941b606c5edfa43d4aee6009a4c8f423f64577a1f84d5360c05b434cee  octoship_1.8.0-1_amd64.deb
283a1d5be9579a3b151d3b5dc97de5299f89aaa0af036afee40547c6a3914b39  octoship-1.8.0-linux-x86_64-bundled.tar.gz
```
