# Linux rebuild verification, 2026-10-04

Pulled and verified source commit `16033bc36a1a9d7b04c2946be3c17040d458ec6d`.
This update changes the Windows client; the native Linux client remains at its
documented feature coverage. The new Windows workflow layout, atomic uploads,
persistent queue, comparison/PR tools, content scanner, and release publisher
have not been ported to the Linux UI.

## Results

- .NET SDK 6.0.400: `dotnet build FileToGitHub.csproj -c Release -p:EnableWindowsTargeting=true` passed with zero warnings and errors.
- `dotnet publish FileToGitHub.csproj -c Release -p:EnableWindowsTargeting=true -r win-x64 --self-contained false -p:DebugType=None -o dist/windows/win-x64` passed. Warning NETSDK1074 means the Windows host executable resources cannot be customized on Linux. Windows runtime/GUI verification and Inno Setup packaging were not performed.
- `python3 -m unittest discover -s linux/tests -v`: all 20 tests passed.
- `xvfb-run -a ./linux/octoship-linux --smoke-test`: passed.
- `xvfb-run -a python3 linux/tests/gui_smoke.py`: passed review, explicit confirmation, HTTP upload, and result status against the loopback fixture. No live GitHub upload was performed.
- `./linux/packaging/build-deb.sh`: rebuilt the Debian package and portable archive; Debian package metadata inspection passed.
- Installed the portable archive under `~/.local/share/octoship/builds/16033bc`, updated `~/.local/bin/octoship`, and refreshed the menu icon. The existing desktop entry uses this launcher. Python byte compilation and the installed launcher's Xvfb smoke test passed. This is a per-user installation, not a system-wide Debian package installation.

Runtime dependencies (`python3-tk` and `gh`) were already installed. The Windows
targeting/runtime build dependencies were restored by .NET. Generated artifacts
remain ignored by Git; this verification record does not publish a GitHub release.

## Local Linux artifacts

| Artifact | SHA-256 |
| --- | --- |
| `dist/linux/octoship_1.5.0-1_all.deb` | `23f8eb68d37db1b634d63822627688e0c63e1a40275bad9594ab7b9118a78318` |
| `dist/linux/octoship-linux-1.5.0.tar.gz` | `e292ad2579e3ec46134ee10326cf93e9fc3b6e68340958887caae8dccdc72886` |

These hashes identify this local build; the packaging script does not currently
normalize timestamps for reproducible output.
