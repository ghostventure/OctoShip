# Self-contained Linux installer 1.6.1 — 2026-10-04

The destination system no longer needs distro Python, Tkinter, or GitHub CLI.
The installer contains a portable Python runtime, Tcl/Tk, GitHub CLI, CA data,
and the dark-themed OctoShip application. `.run` installation is offline and
per-user, with a graphical installer and a command-line alternative. A bundled
`amd64.deb` and portable archive are also generated. The source-only `all.deb`
builder remains separate.

## Runtime and integrity

- Python 3.12.15 (Astral python-build-standalone 20261003), Tcl/Tk 9.0.4,
  GitHub CLI 2.102.0, certifi CA data 2026.7.22.
- Runtime URLs, versions, and SHA-256 hashes are pinned in
  `linux/packaging/bundle-lock.json`; third-party notices accompany the payload.
- Python runs with `-I -B`, using the bundled Tcl/Tk scripts and GitHub CLI.
  The default TLS context loads 121 bundled CA roots; an explicit user CA override
  is honored. No credentials, local settings, or developer home data are packaged.
- The installer checks the outer payload checksum before extraction. It checks
  individual file hashes and symlink targets before installing. Corrupted payload,
  modified-file, and retargeted-symlink checks passed. These are integrity checks,
  not a publisher signature.

## Verification

A clean Debian 12 slim root filesystem (glibc 2.36) was run with Bubblewrap and
networking disabled. `python3`, `wish`, and `gh` were absent from the system PATH.
The installer itself ran using `/bin/sh`; only its bundled interpreter ran the app.
Xvfb supplied a test desktop over the Unix display socket.

- Offline per-user installation into a path containing spaces passed.
- Bundled diagnostics identified Python/Tk/gh under the installed payload.
- Installed app GUI smoke passed without host Python/Tk/gh.
- 54 backend/installer tests, 9 GUI workflow tests, and the loopback GUI upload
  integration passed using the bundled Python in the clean environment.
- Reinstallation reused the verified build; the upgrade test preserved older
  builds. Uninstallation removed this build's launchers while preserving user data
  and newer launchers. Declining uninstall left the installation intact.
- The dark installer window's actual Install/Done flow and created menu entries
  passed, with screenshots visually inspected.
- The bundled Debian package was installed, launched, audited, and removed in a
  disposable Debian 12 root filesystem without adding Python/Tk/gh packages.

Reproducible harnesses are `linux/tests/verify_bundle.py` and
`linux/tests/verify_deb.py`. The test filesystem came from the official
`debuerreotype/docker-debian-artifacts` repository, commit
`8f962b15d7884a90e17876a9303cbac909d119aa`, path
`bookworm/slim/oci/blobs/rootfs.tar.gz`, SHA-256
`774043ccc8ccd0d0833a9ee0792142ab7ad93df971e59dd248fbf82db16d0150`.
It is only a verification fixture and is not included in the installer.

Additional final checks: the installed bundle passed a live authenticated read
through both bundled GitHub CLI and Python HTTPS transport. All Python/Tk ELF
version requirements were inspected; the highest required glibc symbol version
was 2.17. Final artifact checksums and installed desktop-entry syntax passed.

## Scope

Target: Intel/AMD x86_64 Linux with glibc 2.17+ and an X11/XWayland desktop.
Testing covers the installed runtime on Kali and isolated Debian 12 userspace;
it is not a test of every distribution or older glibc baseline. ARM, 32-bit,
and Alpine/musl need separate builds. A normal desktop, basic shell utilities,
and internet for GitHub sign-in/operations remain necessary. The installer needs
no internet. Live GitHub mutation checks use mocks/loopback fixtures.

See [installation, build, sign-in, and rollback instructions](../linux/packaging/README.md).
