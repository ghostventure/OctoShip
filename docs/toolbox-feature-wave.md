# OctoShip toolbox feature wave

This source branch adds focused local workflow tools to the Windows client. It is a development branch; it does not change or replace a published release.

## Implemented in this branch

- **Repository favorites and groups.** The repository browser can pin favorites and assign a short group label. Favorites sort to the top, a checkbox filters to favorites, and typing a group name in the existing filter finds its repositories. These are local preferences and are omitted while Privacy mode is enabled. Repository access is not cached as authoritative; refresh from GitHub before relying on a saved entry.
- **Quick repository switching.** `Ctrl+K` opens a searchable command palette with saved favorites and recent repositories. Choosing a repository fills the current destination and known default branch; it does not publish or confirm account access.
- **Command palette and keyboard navigation.** The palette exposes existing navigation and file-search actions. Shortcuts are `Ctrl+K` (palette), `Ctrl+1` (Files), `Ctrl+2` (Uploads), `Ctrl+3` (Repositories), `Ctrl+4` (Releases), `Ctrl+,` (Settings), and `Ctrl+Shift+E` (export activity). Bindings are fixed in this first implementation; users cannot remap them yet.
- **Activity-log export.** Export saves the current in-memory transfer log, bounded to the app's existing 400-line window, to a user-selected UTF-8 text file. Common GitHub token patterns are redacted and the file warns that paths, repository names, and file names can be present. Review the export before sharing. The export is not a persistent or complete audit trail.
- **Duplicate-file finder.** Scan a selected project folder for exact byte-identical files using a same-size prefilter and SHA-256. It skips linked folders/files and common generated/dependency folders, never deletes or edits files, and reports full local paths only in the result view or an explicitly saved report. The bounded scan visits up to 200,000 entries, considers up to 20,000 files, hashes files up to 256 MiB, and reads at most 1 GiB total; reaching any limit is reported as an incomplete scan.
- **Repository archive export.** Save a ZIP archive of the selected GitHub repository branch through GitHub's archive endpoint. OctoShip streams to a temporary file, caps downloads at 1 GiB, supports cancellation, checks the ZIP signature, and moves the completed archive to the user-selected path. It does not extract files or mutate the repository. The result is the source archive returned by GitHub, not a release asset or reproducible build.
- **Upload policy profiles.** Create credential-free local named profiles with relative destination include/exclude globs and a per-file size cap (up to the app's 50 MiB upload limit). A blank include list allows all destinations; exclusions win. Patterns use OctoShip's existing `*`/`?` matching on the destination path and filename. Select a profile in the main upload panel; no profile is active by default. Single-file review blocks a mismatch; reviewed folder batches offer to continue with only allowed files and leave blocked files queued. Rules are checked again at upload time against the selected destination and captured file size. Profiles are local preferences and do not replace GitHub rules or permissions. The separate Ship project workbench is not profile-aware yet.
- **Local issue and pull-request template manager.** Browse a local project, list/edit existing Markdown templates, and create new issue/PR Markdown templates under `.github`. It skips linked paths and files above 1 MiB, saves atomically, and never calls GitHub. YAML issue forms, deletion, previews, and remote template management remain deferred. Review the working-tree diff and use the normal upload workflow if you later want to publish the files.

## Status of the other requested ideas

“Existing” means the current source already has a related capability; it does not imply every proposed detail is covered.

| Idea | Current source status |
| --- | --- |
| Multi-account profiles | Existing account picker and add/switch/sign-out flows. |
| Repository favorites | Implemented in this branch. |
| Repository groups | Implemented in this branch. |
| Quick repository switcher | Implemented in this branch for favorites and recent repositories via `Ctrl+K`. |
| Command palette | Implemented in this branch. |
| Custom keyboard shortcuts | Fixed navigation shortcuts added; shortcut remapping and conflict UI deferred. |
| Shipment presets | Named destination presets and shipment recipes exist; typed, project-variable shipment presets are not implemented. |
| Upload policy profiles | Implemented in this branch for the main single-file and reviewed folder-batch upload flows. The separate Ship project workbench is not yet profile-aware. |
| Ignore-file editor | Workbench exclusion rules exist; a standalone `.gitignore` editor and impact report are deferred. |
| Large-file warnings | Existing file-size limits and large-file/LFS guidance; no new change in this branch. |
| Secret detection | Existing bounded, redacted content scanner; heuristic and size/binary limits remain. |
| License and privacy checks | Sensitive-name and privacy safeguards exist; license-compliance checking is deferred. |
| Duplicate-file finder | Implemented in this branch with bounded, read-only hashing and an optional report export. |
| Change summary generator | Existing reviewed shipment comparison summarizes changed files; generated prose summaries are deferred. |
| Commit-message helper | Editable commit fields exist; suggested messages/templates are deferred. |
| Branch comparison | Existing repository comparison is present; a dedicated cross-branch comparison view is deferred. |
| Tag manager | Deferred. |
| Batch revert helper | Deferred. |
| Repository settings viewer | Existing account/repository diagnostics expose selected metadata; broader settings coverage is deferred. |
| Team access viewer | Deferred; current access diagnostics do not enumerate all collaborators. |
| Issue templates manager | Local Markdown create/edit is implemented in this branch; YAML forms, deletion, and remote management are deferred. |
| PR template manager | Local Markdown create/edit is implemented in this branch; deletion and remote management are deferred. |
| Workflow file editor | Deferred. |
| Workflow rerun controls | Deferred. |
| Release asset manager | Existing draft release and reviewed asset upload/recovery; listing/deleting/replacing arbitrary assets is deferred. |
| Download manager | Existing bounded release download checks and repository browsing; queued downloads and progress/history manager are deferred. |
| Repository archive export | Implemented in this branch for the selected branch, saved as a ZIP and never extracted. |
| Offline shipment queue | Existing persistent upload queue and offline preparation plans; plans refer to live local files and are not immutable content snapshots. |
| Desktop notifications | Deferred. |
| Activity-log export | Implemented in this branch, with the limits above. |

## Next implementation candidates

Prioritize a read-only Actions monitor, tag manager, and workflow-file editor. Keep workflow reruns, revert operations, asset deletion, and any unattended publication behind explicit review because they change remote state.

## Verification boundary

This branch was prepared from source and documents local behavior only. The available development host does not have the project's .NET 10 Windows SDK/runtime, so a Windows build, WPF rendering check, packaged installation, and interactive GitHub account verification have not been established here. No test suite was added or run for this change.
