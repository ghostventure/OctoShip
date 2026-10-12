# Self-contained Linux installers

[Published Linux 1.7.0 downloads](https://github.com/ghostventure/OctoShip/releases/tag/linux-v1.7.0)
· [Full release handoff and checksums](../../docs/linux-1.7.0-handoff.md)

`python3 linux/packaging/build-standalone.py` builds the x86_64 distribution.
The builder needs Python 3.12+, `dpkg-deb`, and internet access on its first run.
It does not use the build host's Python runtime or copy host credentials/settings.
All upstream downloads are pinned by URL/version and SHA-256 in `bundle-lock.json`;
verified downloads are cached under ignored `dist/linux/bundle-cache`.

Current source builds version **1.8.0**, a source preview. The published release
linked above is still 1.7.0. Substitute 1.8.0 in the example filenames below for
current builds.

Outputs under `dist/linux`:

- `OctoShip-1.7.0-linux-x86_64.run`: offline graphical/per-user installer.
- `octoship_1.7.0-1_amd64.deb`: system-wide bundled Debian package.
- `octoship-1.7.0-linux-x86_64-bundled.tar.gz`: portable bundle.
- `OctoShip-1.7.0-SHA256SUMS.txt`: SHA-256 checksums for those artifacts.

The separate `build-deb.sh` retains the older source-package approach; its `all`
architecture package requires distro Python/Tk/gh. Distribute the **amd64** package
or **.run** installer when the destination does not already have these dependencies.

## Included runtime

Python 3.12.15 from Astral python-build-standalone, Tcl/Tk 9.0.4, GitHub CLI 2.102.0,
and certifi's 2026.7.22 Mozilla CA data. Third-party notices accompany the bundle.
The launcher runs Python in isolated mode. By default it prefers installed Python
3.10+ with Tk 8.6+ for antialiased system fonts. If unavailable, it uses the included
Python and Tcl/Tk scripts. GitHub CLI and the default CA file come from the bundle.
Set `OCTOSHIP_UI_RUNTIME=system` or `bundled` to select a renderer explicitly;
`auto` is the default. `--diagnostics` reports `ui_runtime`. The bundled Tk renderer
can have less smooth fonts; its offline functionality is unchanged. Explicit user `SSL_CERT_FILE` overrides are
preserved for managed/custom certificate authorities.

The installer is approximately 47 MiB; installed payload is about 135 MiB, with
additional temporary space during installation (allow at least 400 MiB free).
No Python, Tkinter, pip, npm, GitHub CLI installation, root password, or dependency
download is needed on the destination. A normal Linux graphical desktop and
standard shell tools (`sh`, `tar`, `gzip`, `sha256sum`, `awk`, `mktemp`, `getconf`)
are still required. Target: Intel/AMD x86_64, glibc 2.17+, X11 or XWayland. This is
not an ARM, 32-bit, musl/Alpine, or headless GUI package. Installation can run
headlessly with `--install`. A desktop terminal/browser is used for GitHub sign-in.

## Installation and authentication

```sh
sh OctoShip-1.7.0-linux-x86_64.run
# Or install without the graphical installer:
sh OctoShip-1.7.0-linux-x86_64.run --install
# Optional custom prefix, without menu entries:
sh OctoShip-1.7.0-linux-x86_64.run --install --prefix "$HOME/Apps/OctoShip" --no-desktop
```

The default prefix is `$XDG_DATA_HOME/octoship` or `~/.local/share/octoship`.
Per-user installation adds `~/.local/bin/octoship` and two application-menu entries:
**OctoShip for GitHub** and **OctoShip GitHub Sign-in**. Use the sign-in entry or
`~/.local/bin/octoship --login`, then **Connect / Refresh** in the app. No account
credentials are included in the installer. The bundle uses your own GitHub CLI
credential storage. Authentication still needs internet access.

For Debian/Ubuntu/Kali, the alternative bundled package can be installed with:

```sh
sudo apt install ./octoship_1.7.0-1_amd64.deb
```

It installs under `/opt/octoship` and declares `libc6 (>= 2.17)`, `libpam0g`,
and `libpam-modules` as package dependencies.
If a prior per-user installation shadows `/usr/bin/octoship`, launch the new system
package explicitly via `/usr/bin/octoship` or update the per-user installation.

Upgrades use separate directories named by version and payload hash, retaining
older builds. The installer backs up the replaced user launcher. To roll back,
launch an older build's `octoship` directly or restore the backed-up launcher.
The outer archive and inner file/symlink manifest are verified before installation.
These detect corruption; they are not an independent publisher signature.

Run `octoship --diagnostics` for the active runtime path/versions/certificate count,
`octoship --cli --version` to inspect the bundled GitHub CLI, or
`octoship --uninstall` to remove the current per-user build after confirmation.
Uninstall preserves saved queues, GitHub credentials, older builds, and launchers
already replaced by a newer installation. Use the package manager to remove the
system-wide Debian package.

## Verification

The clean-environment harness uses Bubblewrap plus a disposable official Debian
12 slim root filesystem, with networking disabled and no system Python/Tk/gh.
It needs the host's `xvfb-run`, `bwrap`, and Python to orchestrate the test; these
are verification tools, not runtime requirements for the installer.

```sh
xvfb-run -a python3 linux/tests/verify_bundle.py \
  dist/linux/OctoShip-1.7.0-linux-x86_64.run /path/to/debian-12-rootfs
```

It installs to a path containing spaces, runs bundled diagnostics and GUI smoke,
runs backend and GUI workflow checks using the bundled interpreter, reinstalls,
then uninstalls and verifies launcher removal. Network-dependent GitHub mutations
use loopback fixtures. It does not authorize or perform live GitHub writes.

Upstream runtime details:
[Python standalone distributions](https://github.com/astral-sh/python-build-standalone/blob/main/docs/running.md),
[Tcl/Tk runtime behavior](https://github.com/astral-sh/python-build-standalone/blob/main/docs/quirks.md),
[GitHub CLI release](https://github.com/cli/cli/releases/tag/v2.102.0).

## Account-lock platform dependency

The 1.7.0 application uses the host Linux PAM library and `login` authentication
policy to unlock the workspace. The bundled Debian package declares `libpam0g`
and `libpam-modules`; portable/.run users need compatible system PAM. No PAM
configuration is installed or changed. Missing or rejecting PAM keeps a locked
workspace locked. Windows Hello and Authenticode are not available on Linux.
