# OctoShip workspace and editor workflows (34)

This slice adds a local editor workspace panel for Linux OctoShip. It supports
seven editor integrations and uses argument arrays (never a shell) for editor
CLI calls. Settings writes are atomic, settings backups are private, portable
exports filter credential-like keys, and workspace metadata inspection only
reads recognized files. Extension installs, removals, updates, profile
activation/removal, settings restoration, and terminal settings changes ask
before writing or invoking a mutating editor operation.

The following 34 independently usable actions are exposed in the Editors tab.
Each CLI workflow can be selected through **Editor action** and run explicitly;
file operands are selected in the file picker where required.

| # | User outcome | Implementation |
|---:|---|---|
| 1 | Open a selected file or workspace | `editor_command` / `run_editor_action` |
| 2 | Open in a new editor window | `editor_command` (`new-window`) |
| 3 | Reuse the current editor window | `editor_command` (`reuse-window`) |
| 4 | Add a folder to the current workspace | `editor_command` (`add-folder`) |
| 5 | Compare two local files in the editor | `editor_command` (`diff`) |
| 6 | Open a four-file merge session | `editor_command` (`merge`) |
| 7 | Wait for the editor to close after opening targets | `editor_command` (`wait`) |
| 8 | Jump to a line and optional column | `editor_command` (`goto`) |
| 9 | Open targets without adding them to recent items | `editor_command` (`skip-recent`) |
| 10 | List editor profiles | `editor_cli_report` (`profile-list`) |
| 11 | Create a temporary editor profile for a workspace | `editor_command` (`profile-create`) |
| 12 | Open a workspace with a named editor profile | `editor_command` (`profile-open`) |
| 13 | List installed extensions | `extension_list` (`extensions-list`) |
| 14 | List installed extensions with versions | `extension_list` (`extensions-list-versions`) |
| 15 | Update installed extensions | `editor_command` (`extensions-update`) |
| 16 | Install a marketplace extension | `extension_cli_plan` (`install-extension`) |
| 17 | Remove an installed extension | `extension_cli_plan` (`uninstall-extension`) |
| 18 | Open a specific extension's editor page | `editor_command` (`show-extension`) |
| 19 | Start the editor with extensions disabled | `editor_command` (`disable-extensions`) |
| 20 | Open user settings in the editor | `editor_command` (`open-user-settings`) |
| 21 | Open keybindings in the editor | `editor_command` (`open-keybindings`) |
| 22 | Open the extension manager in the editor | `editor_command` (`open-extensions`) |
| 23 | Read the installed editor version | `editor_cli_report` (`show-versions`) |
| 24 | Read editor command help | `editor_cli_report` (`show-help`) |
| 25 | Read editor runtime status | `editor_cli_report` (`status`) |
| 26 | Open a workspace with GPU acceleration disabled | `editor_command` (`disable-gpu`) |
| 27 | Profile editor startup | `editor_command` (`log-startup`) |
| 28 | Start an isolated editor user-data instance | `editor_command` (`new-instance`) |
| 29 | Use a separate extension directory | `editor_command` (`extensions-dir`) |
| 30 | Start the editor with a selected locale | `editor_command` (`locale`) |
| 31 | Open the editor profile manager | `editor_command` (`open-profile-editor`) |
| 32 | Open workspace trust controls | `editor_command` (`open-trust-editor`) |
| 33 | Create a local settings backup | `backup_settings` |
| 34 | Restore settings from a selected backup | `restore_settings` |

Implementation and UI live in `linux/octoship/editor_workspace.py` and
`linux/octoship/tools_ui.py`. The supporting local verification sources are
`linux/tests/test_editor_workspace.py` and
`linux/tests/gui_editor_workspace.py`.

This inventory describes implemented source paths; it does not claim a GUI
launch, full test run, package build, or release for this worktree.
