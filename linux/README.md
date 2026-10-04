# OctoShip for Linux 1.6.0

A native Python/Tk desktop client for the OctoShip GitHub workflow. Version 1.6.0
ports the Windows component preview's atomic uploads, saved queues, folder
comparison, branch/PR creation, content scanning, and release publishing. The
original Windows WPF client remains in the repository root.

## Run

Requires Python 3.10+, Tk (`python3-tk` on Debian/Kali), and GitHub CLI (`gh`). No
pip or npm dependencies are needed. Sign in using `gh auth login`, then run:

```sh
./linux/octoship-linux
```

Use **Connect / Refresh**, choose a repository and branch, then use **Find &
upload** or **Repository tools**. The interface keeps destination selection and
transfer status visible across tabs and supports a minimum 1000×760 window.
**Show transfer activity** expands the log (minimum height 840 pixels).
Opening a tool tab does not contact GitHub or make changes.

## Find, review, and upload

Search or add local files, select rows, then choose **Review upload**. Searches
preserve relative paths by default; files added through the picker use their
basenames. Enter an optional destination folder. Duplicate destinations are
rejected. Existing files default to skip; choose replace explicitly to update
them. Review shows visibility, destinations, create/replace/skip decisions,
SHA-256 hashes, and content-scan results before **Upload these files**.

- **Atomic** (default): one commit for the entire batch. Review pins the remote
  commit; the client checks it again before preparing objects and before advancing
  the branch. The final update is never forced. Executable modes are preserved;
  links, submodules, directory collisions, and incomplete remote trees are rejected.
  Cancellation can leave unreferenced Git objects but does not intentionally
  advance the branch. If the final response is lost, inspect the reported commit
  on GitHub before retrying.
- **Per-file**: one commit per file, using the reviewed remote file SHA for
  replacements. **Pause between files** and cancel take effect before the next
  request. A failure stops the batch so you can inspect GitHub and re-review;
  completed commits remain. Pause does not apply to atomic mode.
- Both modes support 1–100 files, up to 25 MiB each, and a commit message of
  1–250 characters. Local bytes are revalidated against their reviewed hash.
  GitHub branch protection and account permissions still apply.

### Saved queues and privacy

**Remember queue on this device** is off by default. When enabled, confirmation
creates a journal and upload progress updates it. **Resume saved batch** uses the
selected repository and branch, omits confirmed successes, validates local bytes,
and restores destinations and the commit mode/message. It never uploads or
restores prior content approvals automatically. Existing files default to skip
on recovery; uncertain operations require checking GitHub before retrying.

Journals are stored under `$XDG_STATE_HOME/octoship/queues` (default
`~/.local/state/octoship/queues`) with a private directory (0700) and files (0600).
They contain local paths, destinations, file hashes/sizes, the user-entered commit
message, and statuses. They have no token or file-content fields. Do not put
credentials in commit messages. Unchecking the option prevents new saves; use
**Forget saved batch** to delete an existing journal for the selected destination.

### Content review

The scanner recognizes common GitHub, AWS, Slack, Google API, private-key, and
credential-assignment patterns in UTF-8 and BOM-marked UTF-16 text. Findings show
only types and line numbers. Files above 2 MiB, binary/unsupported encodings,
lines above 8,192 characters, and the 30-finding limit are reported as incomplete.
Archives are not unpacked. Findings and incomplete scans require a separate
acknowledgement in the upload review. The scanner is heuristic; a clean result
cannot prove that content is safe. Sensitive filename and symlink protections
still apply independently of acknowledgement.

## Repository tools

- **Compare folders**: compares local Git blob hashes to a fixed remote commit,
  with same/changed/local-only/remote-only and unsupported-link statuses. It makes
  no changes. `.git` is excluded; other folders, including hidden/dependency
  folders, are compared. It stops without missing-file conclusions on incomplete
  remote trees, unreadable folders, links, nonregular local files, cancellation,
  or more than 50,000 local files. This is a byte-content comparison, not a Git
  attributes/line-ending normalization or synchronization tool.
- **Branches**: reviews the selected source branch's commit, then creates the
  named branch only after explicit confirmation.
- **Pull requests**: the selected branch is the head; enter the base branch, title,
  and description. Draft is the default. Review and confirmation precede creation.
- **Releases**: enter a tag/title/notes and create a draft from the selected branch.
  Existing tags keep their original commit. Attach assets through a separate
  hash/content review and confirmation, then use **Publish release** separately.
  Assets must be nonempty and smaller than 2 GiB; a temporary private copy ensures
  the sent bytes match review without loading the whole asset into RAM. Temporary
  disk space approximately equal to the asset size is required. Binary/large
  assets require acknowledgement because their contents cannot be fully scanned.
  Failed/uncertain operations disable publishing. Inspect GitHub and use the
  numeric **Existing draft ID** / **Load / refresh draft** to recover. Incomplete
  remote assets block publishing; remove or repair them on GitHub first.

## Authentication and limits

Authentication uses the active github.com account in GitHub CLI. Switch accounts
with `gh auth switch` in a terminal and reconnect. Tokens are held only in memory;
GitHub CLI controls its own credential storage. Authenticated API/asset requests
do not follow redirects. No telemetry or automatic update installation is included.

Search supports case-insensitive filename or file-content matching, hidden files,
cancellation, and at most 5,000 results. Content search reads at most 2 MiB per
file. Version-control, dependency and virtual-environment directories and symlinks
are excluded from search. Preview displays text up to 64 KiB, size, hash, and scan
results. One desktop instance runs per user, using an advisory lock under
`$XDG_RUNTIME_DIR/octoship` (or `~/.cache/octoship`). The transfer log stays in memory.

The Linux UI now covers the first component wave. Older Windows-only features
still not ported include image/PDF previews, regex/advanced search filters,
side-by-side text diff, remote folder browser, preferences/presets import/export,
queue reordering, collision renaming, network-adapter warnings, and the updater.
Windows settings and saved queues are not migrated. AppImage is not provided.

## Packages

```sh
./linux/packaging/build-deb.sh
sudo apt install ./dist/linux/octoship_1.6.0-1_all.deb
octoship
```

The Debian package registers a desktop entry. The portable
`dist/linux/octoship-linux-1.6.0.tar.gz` archive runs with `./octoship-linux` after
extraction and has the same runtime dependencies. Packages contain architecture
independent Python source, not a self-contained executable. Generated packages
remain local unless separately attached to a GitHub release.

## Validate

```sh
python3 -m unittest discover -s linux/tests -v
xvfb-run -a ./linux/octoship-linux --smoke-test
xvfb-run -a python3 linux/tests/gui_smoke.py
xvfb-run -a python3 linux/tests/gui_workflows.py
```

Tests use temporary files, mock GitHub services, and loopback HTTP. They do not
write to GitHub. GUI checks exercise explicit confirmations, atomic publication,
queue recovery, content acknowledgements, comparison/PR/branch controls, draft
creation, asset review/upload, and separate publishing. Live write behavior still
requires a user-selected destination and explicit approval in the app.
