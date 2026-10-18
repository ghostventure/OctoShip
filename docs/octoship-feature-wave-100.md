# OctoShip mixed feature wave: 100 workflows

The original feature wave added 100 distinct user-facing workflows across three
Linux OctoShip tools. A follow-up adds one confirmed local branch-switch action,
bringing the current branch total across these inventories to 101. Counts refer
to independently usable outcomes; they do not count buttons, form fields, or the
100 activity templates in the separate lifecycle playbook.

| Area | Outcomes | Inventory |
| --- | ---: | --- |
| Local Git and repository workflows | 34 | [Local Git inventory](linux-local-git-workflows.md) |
| Offline project lifecycle and planning | 33 | [Lifecycle inventory](octoship-lifecycle-33-outcomes.md) |
| Editor and workspace tools | 34 | [Workspace/editor inventory](octoship-workspace-editor-34.md) |
| **Total** | **101** | |

These additions are integrated into the Linux source workbench on this feature
branch. The Python unit suite and Tk GUI suite pass on the current branch. Fresh
standalone, Debian, and portable artifacts were built and checksum-verified; the
portable bundle's diagnostics, GUI startup, and bundled GitHub CLI were exercised.
The clean-rootfs installer and Debian installation harnesses have not been run,
and no release has been published. The individual inventories identify
implementation paths and remaining scope for each area.
