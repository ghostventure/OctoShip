# Linux local Git workflows

This inventory tracks 33 independently usable local repository outcomes exposed in the Tools → Local Git screen. Read-only views run fixed Git argument lists without a shell and do not contact remotes. Local changes that update refs or the index have separate explicit confirmation. None of these workflows pushes, fetches, or writes to a remote.

## 33 implemented outcomes

1. **Inspect concise working-tree and current-branch state** — `status_short` in `linux/octoship/git_operations.py`.
2. **Inspect full porcelain-v2 status for automation-oriented diagnosis** — `status_porcelain`.
3. **Find every untracked path, including nested paths** — `status_all`.
4. **See ignored paths alongside working-tree changes** — `status_ignored`.
5. **Summarize staged changes by directory** — `status_staged`.
6. **Summarize unstaged file additions and deletions** — `status_unstaged`.
7. **List merge-conflict index stages** — `status_conflicts`.
8. **Review the working-tree patch without external diff drivers** — `diff_worktree`.
9. **Review staged changes separately from the working tree** — `diff_staged_stat`.
10. **Identify changed paths and their change kinds** — `diff_status`.
11. **Check unstaged changes for whitespace errors** — `diff_check`.
12. **Check staged changes for whitespace errors** — `diff_staged_check`.
13. **List local branches with their tip summaries** — `branches_verbose`.
14. **See each local branch's upstream relationship** — `branches_upstream`.
15. **Find branches already merged into the current commit** — `branches_merged_head`.
16. **Find local branches not merged into the current commit** — `branches_unmerged_head`.
17. **Review the recent current-branch commit history** — `history_recent`.
18. **Compare commit history across local refs using a graph** — `history_graph`.
19. **Review changed paths in recent commits** — `history_files`.
20. **Inspect local reference movement history for recovery clues** — `history_reflog`.
21. **See the current commit metadata and change summary** — `history_head`.
22. **List tags in version order** — `tags_all`.
23. **Find tags that point at the current commit** — `tags_head`.
24. **Inspect tag object and commit targets** — `tags_peel`.
25. **List configured remote names without contacting them** — `remotes_names`.
26. **Review upstream-only commits already present in local refs** — `remotes_log_incoming`.
27. **Compare local HEAD and its configured upstream when available** — `remotes_compare`.
28. **Review the stash inventory** — `stash_list`.
29. **Preview the most recent stash's changed paths** — `stash_paths`.
30. **Inspect linked worktrees and their Git state** — `worktrees_list`.
31. **Create a local branch from a reviewed commit/ref** — `create_branch`, surfaced by `ToolsPanel.create_local_branch` in `linux/octoship/tools_ui.py`.
32. **Save current local edits to a named stash, optionally including untracked files** — `stash_save`, surfaced by `ToolsPanel.stash_local_changes`.
33. **Delete a merged local branch after an explicit confirmation** — `delete_branch`, surfaced by `ToolsPanel.delete_local_branch`.

The inspection outcomes are selected from the fixed-action picker in `ToolsPanel.run_git_operation`; each reports a different repository fact or review result. The local branch and stash actions are distinct state-changing workflows. Branch deletion is constrained by Git's merged-branch deletion rule and refuses the current branch. Branch creation and stash save require a valid local repository; stash save and deletion also require affirmative confirmation.

## Partial or not included

The feature wave does not provide local commit creation, branch switching/merging, stash apply/drop, worktree creation/removal, cherry-pick, conflict resolution, LFS object management, clone, or any remote publication operation. The 100-entry inspection catalog is broader than this 33-outcome inventory; entries outside this list are not claimed here as additional independently validated workflows.
