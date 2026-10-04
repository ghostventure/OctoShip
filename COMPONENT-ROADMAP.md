# OctoShip component assignments

Assigned 2026-10-03. Numbers refer to the 60-component proposal. Only the first wave is in active implementation; later waves are assigned backlog, not completed features. No deployment or remote repository mutation is part of local verification.

First-wave update: implemented and integrated locally. Release build and 62 offline/service/GUI checks passed. See [verification/README.md](verification/README.md) for commands and remaining live-integration boundaries. P1-P3 remain planned work, not running agents.

Linux update, 2026-10-04: the P0 feature group now has native Python/Tk implementations and an upload/tools layout. See [Linux verification](verification/linux-port-1.6.0.md) for coverage and boundaries. This does not mark the later P1–P3 backlog complete.

## Owners

- `reliable_uploads`: upload reliability, queue behavior, reusable jobs, local workflow integration.
- `compare_and_pr`: comparison, branches, pull requests, repository navigation and collaboration.
- `secrets_and_releases`: content review, safety checks, releases and build visibility.
- Root: integration, shared MainWindow wiring, documentation, final build and smoke verification.

## P0 - active first wave

| Owner | Components | Acceptance |
| --- | --- | --- |
| reliable_uploads | 1 Single-commit batch uploads; 2 Persistent upload queue | Explicit review, branch conflict detection, credential-free recovery, source revalidation, privacy-mode handling. |
| compare_and_pr | 21 Folder comparison panel; 11 Branch creation; 12 Pull-request creation | Read-only comparison with incomplete-result reporting; explicit user action for remote writes. Branch creation and PR creation form one feature group. |
| secrets_and_releases | 27 Content-based secret scanner; 44 Release publisher | Redacted findings on actual upload content; draft-first releases with explicit publishing and attachment controls. |

## P1 - correctness and daily workflow

| Owner | Components |
| --- | --- |
| reliable_uploads | 6 Upload dry run; 8 Connection recovery; 9 Saved upload jobs; 10 Upload receipts |
| compare_and_pr | 19 Remote-change detection; 22 Side-by-side text diff; 15 Commit history browser; 16 File version restore; 39 Repository favorites |
| secrets_and_releases | 29 Ignore-rule editor; 30 File-size advisor; 32 Filename compatibility checker; 33 Encoding and line-ending checker; 46 Checksum manifest generator; 50 Release readiness checklist |

## P2 - richer project workflows

| Owner | Components |
| --- | --- |
| reliable_uploads | 3 Folder synchronization planner; 4 Folder watch mode; 7 Bandwidth controls; 54 Activity dashboard; 55 Desktop notifications; 56 Windows Explorer integration |
| compare_and_pr | 13 Pull-request dashboard; 14 Branch comparison; 17 Batch revert assistant; 18 Conflict resolution panel; 20 Tag manager; 35 Repository creation wizard; 40 Repository groups; 42 Remote file operations; 43 Repository download manager; 57 Command palette |
| secrets_and_releases | 24 Markdown preview; 25 Structured-data viewer; 26 Syntax-highlighted preview; 31 Duplicate-file detector; 34 Upload policy profiles; 45 Release package builder; 48 GitHub Actions monitor; 49 Build artifact browser |

## P3 - expansion after core workflows stabilize

| Owner | Components |
| --- | --- |
| reliable_uploads | 5 Scheduled uploads; 58 Command-line companion; 59 Extension system; 60 Cross-platform application core |
| compare_and_pr | 36 Project template library; 37 README builder; 38 License setup assistant; 41 Cross-repository search; 51 Issue creation from files; 52 Issue-linked uploads; 53 Review request controls |
| secrets_and_releases | 23 Image comparison; 28 Personal-data scanner; 47 Changelog assistant |

## Dependency notes

Persistent queues and saved jobs should precede watchers and schedules. Comparison and remote-change checks should precede synchronization and restore/revert workflows. Extract reusable services before implementing CLI, extensions, or another platform. Approval of this roadmap does not authorize scheduled or automatic remote writes; users configure and approve those behaviors in the implemented application.
