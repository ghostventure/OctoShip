from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from octoship.app import App


class EditorWorkspaceGUI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = tk.Tk()
        self.root.geometry('1280x900')
        self.app = App(self.root); self.addCleanup(self.app.close)
        self.app.notebook.select(1)
        self.root.update()
        self.tools = self.app.tools
        index = next(i for i in range(self.tools.tabs.index('end')) if self.tools.tabs.tab(i, 'text') == 'Editors')
        self.tools.tabs.select(index); self.root.update()

    def test_editor_tab_renders_scrollable_profile_terminal_and_accessibility_controls(self):
        self.assertEqual(self.tools.editor_action.get(), 'open')
        self.assertTrue(self.tools.editor_report.winfo_exists())
        self.assertTrue(self.tools.terminal_shell_picker.winfo_exists())

    def test_workspace_config_validation_is_local_and_reports_schema_result(self):
        project = Path(self.temp.name) / 'project'; (project / '.vscode').mkdir(parents=True)
        (project / '.vscode' / 'tasks.json').write_text('{"version":"2.0.0","tasks":[]}')
        self.tools.editor_workspace_root.set(str(project))
        self.tools.workspace_config_kind.set('tasks')
        self.tools.validate_editor_workspace_config()
        self.assertIn('valid', self.tools.editor_report.get('1.0', 'end'))
        self.assertIn('without executing tasks', self.tools.editor_status.get())

    def test_diff_action_uses_reviewed_file_picker_selection(self):
        left = Path(self.temp.name) / 'left.txt'; right = Path(self.temp.name) / 'right.txt'
        left.write_text('left'); right.write_text('right')
        self.tools.editor_action.set('diff')
        self.tools.editor_action_paths = [str(left), str(right)]
        class Process: pid = 71
        with patch('octoship.tools_ui.editorflow.run_editor_action', return_value=Process()) as invoke:
            self.tools.run_editor_action()
        invoke.assert_called_once_with('code', 'diff', paths=[str(left), str(right)], extension=None, extra=())
        self.assertIn('process 71', self.tools.editor_status.get())

    def test_workspace_config_open_delegates_only_selected_local_file(self):
        project = Path(self.temp.name) / 'project'; (project / '.vscode').mkdir(parents=True)
        (project / '.vscode' / 'settings.json').write_text('{}')
        self.tools.editor_workspace_root.set(str(project))
        self.tools.workspace_config_kind.set('settings')
        class Process: pid = 72
        with patch('octoship.editor_workspace.run_editor_action', return_value=Process()) as invoke:
            self.tools.open_editor_workspace_config()
        args = invoke.call_args.args
        self.assertEqual(args[0], 'code')
        self.assertEqual(args[1], 'open')
        self.assertEqual(Path(args[2][0]), project / '.vscode' / 'settings.json')


if __name__ == '__main__': unittest.main()
