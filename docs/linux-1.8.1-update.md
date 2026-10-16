# OctoShip Linux 1.8.1 update preview

Status: local source preview; not published as a GitHub release. The source was
fast-forwarded to upstream `main` at `2ad93d5` on October 15, 2026. The Linux
client was separately updated to carry over portable improvements; it is not a
mechanical build of the Windows WPF client.

## Changes

- **VS Code integration:** open the selected file, project/search folder, or a
  `.code-workspace` file with the installed `code` command. Arguments are passed
  directly without a shell. VS Code is optional.
- **Safer previews:** detect PNG, JPEG, GIF, BMP, TIFF, PDF, text, and unknown
  binary signatures from a bounded prefix. Warn when a known filename extension
  does not match the detected content. Do not display recognized binary payloads
  as text.
- **Rate-limit guidance:** HTTP 429 and GitHub primary-rate-limit 403 responses
  show a retry estimate from `Retry-After` or `X-RateLimit-Reset`. OctoShip does
  not automatically retry a request.
- **Dependency health:** the Repository tools window includes a read-only
  Dependencies tab that lists open Dependabot alerts for the selected repository,
  including severity, package, first patched version, and manifest. It links to
  GitHub for full advisory details and does not dismiss alerts or apply fixes.
  Access requires Dependabot alerts to be available and the connected token to
  have read permission; denied or unavailable access is shown as an error, not as
  an empty alert list.
- Linux version is `1.8.1`. Existing PAM/session-lock, upload review, and explicit
  remote-confirmation behavior remains in place.

These are selected portable updates from the newer Windows code. Windows-only
installer/legal workflows, Windows Hello, WPF controls, and Windows-specific
credential isolation were not represented as Linux parity.

## Verification

- `python3 -m unittest discover -s linux/tests -v`: 90 tests passed.
- `gui_workflows.py`: 9 checks passed; `gui_shipping.py`: 6 passed.
- `gui_smoke.py`: loopback review/confirm/upload plus VS Code file/folder action
  wiring passed with the external editor launch mocked.
- The rebuilt `.run` installer passed `verify_bundle.py` in an isolated Debian
  rootfs: bundled Python/Tk/GitHub CLI diagnostics, all 90 backend tests, both GUI
  suites, install, reinstall, and uninstall passed without host Python/Tk/GitHub
  CLI dependencies. No live GitHub writes were made.
- `sha256sum -c dist/linux/OctoShip-1.8.1-SHA256SUMS.txt` passed for all three
  distribution artifacts. The `.deb` metadata reports `amd64`, version `1.8.1-1`.

## Artifacts

Built locally under ignored `dist/linux/`; checksums are in
`dist/linux/OctoShip-1.8.1-SHA256SUMS.txt`.

| Artifact | SHA-256 |
| --- | --- |
| `OctoShip-1.8.1-linux-x86_64.run` | `aaa652af1eb0a6a071045f811b25af36027243038d18aa3f0ecb0aad332d4323` |
| `octoship_1.8.1-1_amd64.deb` | `852b2d245b87a4e681f729499f2dfe5f6ff133c582a98bef42c7ae90b55f4770` |
| `octoship-1.8.1-linux-x86_64-bundled.tar.gz` | `e7f801d79bfb0062f7d37e11c29320aa6504839c3c5bd9658fbd3559d964f8cc` |

The published stable Linux release remains 1.7.0. This handoff records the
state before its source changes were committed to the
`feature/octoship-linux-1.8.1-installer-docs` branch. No 1.8.1 GitHub release
was published; a source branch is not a release.

## Local install update — October 16, 2026

- Added the read-only Dependabot alert panel to the local 1.8.1 source preview.
- Rebuilt the self-contained `.run` installer and verified all three distribution
  artifacts against `OctoShip-1.8.1-SHA256SUMS.txt`.
- Installed the `.run` package per-user at
  `/home/sniper-lion-main/.local/share/octoship`; `~/.local/bin/octoship
  --diagnostics` reports version 1.8.1 using its installed bundle.
- Python syntax compilation passed for the Dependabot service, tools UI, and
  existing VS Code integration. No automated test suite or live Dependabot API
  request was run for this addition. The panel remains read-only; GitHub may
  require the connected token to have Dependabot alerts read permission.
- This is a local installation, not a GitHub release. The published stable
  Linux release remains 1.7.0.
