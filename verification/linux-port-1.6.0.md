# Linux component port 1.6.0 — 2026-10-04

Ports the first Windows component wave from `16033bc` to native Python/Tk on
Linux. The upload workspace now has atomic/per-file modes, explicit content review,
opt-in saved queues, recovery and per-file pause/cancel. Repository tools provide
fixed-commit comparison, confirmed branch/PR creation, and draft/asset/publish
release steps. The native layout uses upload/tools tabs and expandable activity;
it is not a pixel-for-pixel reproduction of WPF.

## Verification

- 48 backend tests passed (`python3 -m unittest discover -s linux/tests -v`).
- 9 native GUI workflow tests passed (`xvfb-run -a python3 linux/tests/gui_workflows.py`).
- The existing loopback GUI review/confirm/Contents upload integration passed
  (`xvfb-run -a python3 linux/tests/gui_smoke.py`).
- Atomic upload and release-asset transports were exercised through local HTTP
  servers, including JSON methods, request bodies, authentication, binary bytes,
  name encoding, and refusal to follow authenticated redirects.
- Conflict, changed-source, incomplete-tree, symlink, cancellation, scan-approval,
  corrupt-queue, incomplete-asset, and failure-recovery cases passed. GUI checks
  prove declined confirmations make no remote writes; restored queues require
  fresh content approval; failed asset uploads keep publishing disabled.
- Layout checks passed at 1000×760 and 1180×860, with screenshots of upload and
  release tools inspected locally. File rows and primary actions remain visible.
- A live read-only comparison against `ghostventure/OctoShip`, `main`, folder
  `linux/octoship` passed at `af80f0f5a96446f47bf38fb564c38c2bae276214`.
- Linux source byte compilation passed. Both `.deb` and portable artifacts were
  rebuilt. The extracted Debian payload and installed portable launcher passed
  GUI smoke tests. Installed Python modules match the repository source bytes.
- Installed per-user under `~/.local/share/octoship/builds/1.6.0`, with the existing
  desktop entry using the updated `~/.local/bin/octoship` launcher. The previous
  launcher was backed up. No privileged/system-wide package installation was used.

## Boundaries

The tests make no live GitHub upload, branch, PR, or release writes. The live
check covers authenticated reads only. No GitHub release is published as part of
this source update. Older Windows-only features and Linux limits are listed in
[the Linux guide](../linux/README.md); these are not claims of complete Windows
feature parity. The Windows application code is unchanged by this port.

The implementation uses GitHub's documented
[non-forced reference updates](https://docs.github.com/en/rest/git/refs#update-a-reference),
[recursive trees and truncation reporting](https://docs.github.com/en/rest/git/trees#get-a-tree),
and [release asset upload endpoint](https://docs.github.com/en/rest/releases/assets#upload-a-release-asset).
