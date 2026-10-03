# OctoShip for Linux

A native Python/Tk desktop client for the OctoShip GitHub upload workflow. The existing Windows WPF client remains in the repository root.

## Run

Requires Python 3.10+, Tk (`python3-tk` on Debian/Kali), and GitHub CLI (`gh`). No pip or npm dependencies are needed. Sign in using `gh auth login`, then run:

```sh
./linux/octoship-linux
```

Use **Connect / Refresh**, choose a repository and branch, find or add local files, select the desired rows, and choose **Review upload**. The review shows repository visibility and every create/replace/skip before **Upload these files** sends anything. Enter an optional destination folder. Searches preserve relative paths by default; files added through the picker use their basenames. Duplicate destinations are rejected. Existing files default to skip; choose replace explicitly to update them.

Authentication uses the active github.com account in GitHub CLI. Switch accounts with `gh auth switch` in a terminal and reconnect. OctoShip only holds the retrieved credential in memory and does not write settings or credentials. GitHub CLI controls its own credential storage. No telemetry or automatic updates are included.

## Packages

```sh
./linux/packaging/build-deb.sh
sudo apt install ./dist/linux/octoship_1.5.0-1_all.deb
octoship
```

The Debian package registers a desktop menu entry. The portable `dist/linux/octoship-linux-1.5.0.tar.gz` archive runs with `./octoship-linux` after extraction and has the same runtime dependencies. The package is architecture independent Python source, not a self-contained binary. Generated packages are local builds; no release has been published.

## Behavior and limits

- Repository and branch catalogs use the real GitHub REST API. Write permission, repository state, branch existence, and target SHA are checked before upload.
- Search supports case-insensitive filename or file-content matching, hidden files, cancellation, and at most 5,000 results. Content scanning reads at most 2 MiB per file. Version-control, dependency and virtual-environment directories and symlinks are excluded.
- Preview shows text up to 64 KiB, byte count, and SHA-256. Binary files show metadata.
- Single and batch uploads support up to 100 files, 25 MiB per file, custom commit messages, skip/replace collision behavior, progress and cancellation. Each file creates its own commit. Cancellation stops before the next request; completed commits remain. Failed files can be selected and reviewed again.
- Sensitive filenames and directories (`.env`, private keys, credential/secret/password patterns) are blocked. This is a filename guard, not content-based secret scanning. Review your selection before uploading.
- Local file changes after review are rejected. Replacements use the reviewed remote SHA, so intervening remote changes are rejected by GitHub. Protected branch requirements still apply.
- One desktop instance runs per user. The only application state on disk is an advisory lock under `$XDG_RUNTIME_DIR/octoship` (or `~/.cache/octoship`). The transfer log stays in memory.

This first Linux implementation covers the core file-search/review/upload workflow. It does not yet reproduce Windows image/PDF previews, regex and advanced search filters, remote text comparison/folder browser, destination presets, preference import/export, pause/queue reordering, collision renaming, network-adapter warnings, or automatic update installation. Windows settings are not migrated. AppImage packaging is not provided.

## Validate

```sh
python3 -m unittest discover -s linux/tests -v
./linux/octoship-linux --smoke-test
# Without a desktop session:
xvfb-run -a ./linux/octoship-linux --smoke-test
xvfb-run -a python3 linux/tests/gui_smoke.py
```

Tests exercise a local HTTP server and temporary files; they do not write to GitHub. Live read-only authentication/catalog checks and GUI launch can be run separately. A live upload requires a user-selected destination and explicit confirmation in the app.
