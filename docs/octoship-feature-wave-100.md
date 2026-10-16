# OctoShip mixed feature wave: 100 workflows

This source branch adds 100 distinct user-facing workflows across three Linux
OctoShip tools. The counts refer to independently usable outcomes documented
in each inventory; they do not count buttons, form fields, or the 100 activity
templates in the separate lifecycle playbook.

| Area | Outcomes | Inventory |
| --- | ---: | --- |
| Local Git and repository workflows | 33 | [Local Git inventory](linux-local-git-workflows.md) |
| Offline project lifecycle and planning | 33 | [Lifecycle inventory](octoship-lifecycle-33-outcomes.md) |
| Editor and workspace tools | 34 | [Workspace/editor inventory](octoship-workspace-editor-34.md) |
| **Total** | **100** | |

These additions are integrated into the Linux source workbench and were included
in a locally built 1.8.1 installer and per-user installation. SHA-256 checks
passed for the `.run`, `.deb`, and bundled tarball. The installed app was not
launched interactively, no tests were run for this feature wave, and no release
was published. The individual inventories identify implementation paths and
the remaining scope for each area.
