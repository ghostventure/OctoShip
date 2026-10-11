# OctoShip for Linux 1.7.0

A native Python/Tk desktop client for the OctoShip GitHub workflow. Version 1.7.0
ports the October 11 Windows shipping workbench, preparation and inspection tools,
workspace retention, inactivity locking, and display settings. It retains atomic
uploads, saved queues, folder comparison, and release publishing. The
original Windows WPF client remains in the repository root.

## Install or run

The **self-contained installer** includes Python, Tcl/Tk, GitHub CLI, and certificate
data. The destination computer does not need to install those separately:

```sh
sh OctoShip-1.7.0-linux-x86_64.run
```

Choose **OctoShip GitHub Sign-in** from the application menu to sign in, then open
OctoShip and connect. The installer works offline; GitHub authentication and remote
operations need internet. See [installer instructions and platform support](packaging/README.md).

Running directly from source still requires Python 3.10+, Tk (`python3-tk` on
Debian/Kali), and GitHub CLI (`gh`). No pip or npm dependencies are needed:

```sh
gh auth login
./linux/octoship-linux
```

Use **Connect / Refresh**, choose a repository and branch, then use **Find &
upload** or **Repository tools**. The interface uses a consistent dark theme across controls, dropdowns, tools,
previews, and review windows. It keeps destination selection and
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
  advance the branch. If the final response is lost, a separate 20-second read
  budget checks the head and ancestry without replaying the update. Unresolved
  publication remains explicitly unconfirmed; inspect the reported commit before retrying.
- **Per-file**: one commit per file, using the reviewed remote file SHA for
  replacements. **Pause between files** and cancel take effect before the next
  request. A failure stops the batch so you can inspect GitHub and re-review;
  completed commits remain. Pause does not apply to atomic mode.
- Both modes support 1–100 files, up to 50 MiB each, and a commit message of
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

## Shipping workbench (new in 1.7.0)

The **Shipping workbench** tab contains five tool pages:

- **Ship project** reviews a local project against a fixed remote commit, applies
  semicolon-separated exclusion globs, skips unchanged files, and displays scan
  findings, possible identical-content moves, account, visibility and branch rules.
  **Ship reviewed project** creates a new branch, atomically commits reviewed bytes,
  verifies the immutable commit, and creates a draft PR. It never deletes old paths.
  Secret findings block shipment; incomplete scans require explicit approval.
  Changed bytes, account, visibility or base head require a new review. Partial
  failures identify the branch for recovery. Import/export portable, credential-free
  recipes (64 KiB maximum); inspect local Git status and redacted remotes.
- **Prepare & map** supports offline folder/file mapping, editable destinations,
  empty-folder `.gitkeep` staging, and explicit private JSON plan saves. Double-click
  a destination to edit it. **Select text edits** loads a fixed UTF-8 remote baseline
  and stages selected independent blocks without changing the source. Unselected
  text and line endings survive. Selective publication supports one file, 1 MiB and
  2,000 lines; its plan cannot be saved. Publication checks the original branch,
  repository, destination and baseline. Other plans reference current local files;
  they are not frozen snapshots. Optional project/account bindings block account
  mismatches in this preparation workflow. Fresh review shows identity, current
  visibility, visibility drift, exact destinations and SHA-256 before publication.
- **Inspect** checks project versions, LFS rules, large files and inline relative
  Markdown links (missing, case mismatches and project escapes). Expected version
  checks cover package.json, .csproj, Inno Setup defines and numeric installer names.
  ZIP inspection never extracts: maximum 512 MiB archive, 10,000 entries, 2 GiB
  declared expansion, 512 KiB per scanned entry and 8 MiB total content scans.
  Unsafe/sensitive paths and unscanned entries remain explicit. ELF/PE architecture
  inspection never executes the file. Support reports redact common credentials,
  private keys, emails and home paths; preview and review before sharing.
- **Delivery checks** retrieves account/permissions, rules/classic protection, Pages
  build/domain health, and the HTTPS Pages URL. Inaccessible endpoints stay unknown;
  HTTP rate-limit/SSO evidence is shown when returned. Artifact verification uses
  `gh attestation verify` with a two-minute timeout. Stable/prerelease channel checks
  inspect the latest 100 releases against the supplied tag and exact asset name.
  Draft recovery uploads only missing asset names and preserves existing mismatches.
  Release tests stream up to 2 GiB per asset, compare byte counts and local/GitHub
  SHA-256 references, and separately report anonymous link access. A redirect alone
  is not called a verified public download. Recovery never creates/publishes a release.
- **Display & privacy** saves 12–18 point text, compact spacing, optional reconnect,
  and workspace preferences. Privacy mode omits repository, branch, destination and
  project folder from automatic preferences. GitHub credentials remain in CLI storage.

Project traversal rejects links/nonregular files, excludes `.git`, dependency and
virtual-environment folders, and stops at 50,000 files or 10,000 folders. Preparation
plans and atomic shipments support at most 100 files; uploads support 50 MiB per file.
No automatic LFS conversion or deletion synchronization is performed. Exact API
commit email is not authoritative in the identity preview; GitHub supplies defaults.

Explicit plans contain local paths. Bindings, prepared text/placeholder copies,
preferences and lock state live under `$XDG_STATE_HOME/octoship` (default
`~/.local/state/octoship`); new directories/files are private (0700/0600).
Prepared copies may contain project content and remain available for saved plans.
Do not commit these files. Explicit saves are independent of privacy mode.

### Linux account lock

Normal application startup enables a 30-minute inactivity lock; use **Lock account
workspace now** or **Ctrl+Shift+L** to lock immediately. Main/child windows and their
titles are hidden until unlock. New API requests are blocked and completed UI
callbacks wait until unlock. An already-sent request or CLI process may finish;
operations are not automatically retried. Locked/expired/corrupt session state
locks on restart. Session persistence errors are surfaced; a writable state folder
is necessary for restart retention.

Unlock authenticates the process user's Linux account with the system `login` PAM
policy, checks account validity and the resulting UID. Empty passwords, failed,
expired or unavailable authentication keep the workspace locked. Passwords are
not saved or logged; Python/Tk cannot guarantee erasure of all transient in-memory
copies. PAM support and compatible system policy are required (normally present
on Kali/Debian desktop installations). System PAM is not bundled or reconfigured.
See [PAM authentication](https://www.man7.org/linux/man-pages/man3/pam_authenticate.3.html)
and [account validation](https://pubs.opengroup.org/onlinepubs/8329799/pam_acct_mgmt.htm).

Where `$XDG_SESSION_ID` and `loginctl` are available, desktop lock/inactivity is
polled every two seconds. Platforms without that integration still have the app
inactivity/manual lock. This is a local privacy shield, not encryption, protection
from another process running as the same user, or a replacement for the desktop
lock. Successful real PAM authentication remains an interactive verification step.

### Platform differences

Linux uses file/folder pickers and editable mapping instead of Windows Explorer
file drag/drop. Installer inspection reports ELF/PE architecture; Windows
Authenticode trust and Windows version-resource extraction are unavailable and
explicitly labelled unverified. Windows Hello is replaced by Linux PAM. The Linux
UI uses labelled native Tk controls; Windows UI Automation parity is not claimed.

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

The Linux UI covers the first component wave and the October 11 shipping tools. Older Windows-only features
still not ported include image/PDF previews, regex/advanced search filters,
side-by-side text diff, remote folder browser, preferences/presets import/export,
queue reordering, collision renaming, network-adapter warnings, and the updater.
Windows settings and saved queues are not migrated. AppImage is not provided.

## Packages

Build the self-contained installer, bundled Debian package, and portable archive:

```sh
python3 linux/packaging/build-standalone.py
# Bundled Debian/Ubuntu/Kali alternative:
sudo apt install ./dist/linux/octoship_1.7.0-1_amd64.deb
```

These include the runtime and target Intel/AMD x86_64 Linux with glibc 2.17+ and an
X11/XWayland desktop. The older `build-deb.sh` source-only package remains available
for distributions that manage Python/Tk/gh themselves. See [packaging details](packaging/README.md).
Generated packages remain local unless separately attached to a GitHub release.

## Validate

```sh
python3 -m unittest discover -s linux/tests -v
xvfb-run -a ./linux/octoship-linux --smoke-test
xvfb-run -a python3 linux/tests/gui_smoke.py
PYTHONPATH=linux xvfb-run -a python3 linux/tests/gui_workflows.py
PYTHONPATH=linux xvfb-run -a python3 linux/tests/gui_shipping.py
```

Tests use temporary files, mock GitHub services, and loopback HTTP. They do not
write to GitHub. GUI checks exercise explicit confirmations, atomic publication,
queue recovery, content acknowledgements, comparison/PR/branch controls, draft
creation, asset review/upload, and separate publishing. Live write behavior still
requires a user-selected destination and explicit approval in the app.
