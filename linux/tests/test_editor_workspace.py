import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from octoship import editor_workspace as ew
from octoship.core import OctoShipError


class EditorWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.env = {'HOME': str(self.home), 'XDG_CONFIG_HOME': str(self.home / '.config')}
        self.settings = ew.user_data_dir('code', self.env) / 'settings.json'
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text('{"editor.fontSize": 12, "custom.keep": true}\n')

    def tearDown(self): self.temp.cleanup()

    def test_editor_detection_does_not_launch_and_is_deterministic(self):
        mapping = {'code': '/usr/bin/code', 'zed': '/usr/bin/zeditor'}
        found = ew.installed_editors(lambda name: mapping.get(name))
        self.assertEqual([row['id'] for row in found], ['code', 'zed'])

    def test_accessibility_preset_previews_then_preserves_unrelated_settings(self):
        _, proposed, diff = ew.accessibility_preview('code', self.env)
        self.assertIn('editor.accessibilitySupport', proposed)
        self.assertIn('custom.keep', proposed)
        self.assertIn('editor.fontSize', diff)
        ew.apply_accessibility_preset('code', self.env)
        saved = json.loads(self.settings.read_text())
        self.assertEqual(saved['editor.fontSize'], 16)
        self.assertTrue(saved['custom.keep'])

    def test_each_accessibility_control_can_be_enabled_or_reset_separately(self):
        self.assertEqual(len(ew.ACCESSIBILITY_OPTIONS), 20)
        self.assertEqual(len({row.key for row in ew.ACCESSIBILITY_OPTIONS}), 20)
        for option in ew.ACCESSIBILITY_OPTIONS:
            ew.set_accessibility_option('code', option.key, True, self.env)
            self.assertEqual(json.loads(self.settings.read_text())[option.key], option.value)
            ew.set_accessibility_option('code', option.key, False, self.env)
            self.assertNotIn(option.key, json.loads(self.settings.read_text()))

    def test_atomic_backup_and_restore(self):
        backup = ew.backup_settings('code', env=self.env)
        self.settings.write_text('{"new": 1}')
        ew.restore_settings('code', backup, self.env)
        self.assertEqual(json.loads(self.settings.read_text()), {'custom.keep': True, 'editor.fontSize': 12})
        self.assertEqual(backup.stat().st_mode & 0o077, 0)

    def test_profiles_are_private_listable_previewable_activatable_and_removable(self):
        profile = ew.save_profile('Work laptop', 'code', env=self.env)
        self.assertEqual(profile.stat().st_mode & 0o077, 0)
        self.assertEqual(ew.list_profiles(), (profile,))
        self.settings.write_text('{"changed": true}')
        _, diff = ew.preview_profile('Work laptop', 'code', env=self.env)
        self.assertIn('custom.keep', diff)
        ew.activate_profile('Work laptop', 'code', env=self.env)
        self.assertTrue(json.loads(self.settings.read_text())['custom.keep'])
        self.assertEqual(ew.remove_profile('Work laptop'), profile)
        self.assertEqual(ew.list_profiles(), ())

    def test_profile_rejects_traversal(self):
        for name in ('../escape', '.', 'x' * 80):
            with self.assertRaises(OctoShipError): ew.workspace_profile_path(name, self.home / 'profiles')

    def test_import_export_snapshot_preserves_settings_keybindings_and_snippets(self):
        user = ew.user_data_dir('code', self.env)
        (user / 'keybindings.json').write_text('[]')
        (user / 'snippets').mkdir()
        (user / 'snippets' / 'python.json').write_text('{"Print": {"prefix": "p"}}')
        bundle = ew.settings_snapshot('code', self.env)
        (user / 'keybindings.json').unlink(); (user / 'snippets' / 'python.json').unlink()
        written = ew.import_settings_snapshot('code', bundle, self.env)
        self.assertEqual(set(written), set(bundle['files']))
        self.assertTrue((user / 'snippets' / 'python.json').exists())

    def test_settings_export_strips_credential_like_keys(self):
        self.settings.write_text(json.dumps({'custom.keep': True, 'service.token': 'secret', 'oauth_password': 'hidden', 'api_key': 'key'}))
        snapshot = ew.settings_snapshot('code', self.env)
        exported = json.loads(snapshot['files']['settings.json'])
        self.assertEqual(exported, {'custom.keep': True})
        self.assertNotIn('secret', json.dumps(snapshot))

    def test_editor_command_catalog_has_32_distinct_reviewed_actions(self):
        self.assertEqual(len(ew.EDITOR_COMMAND_FEATURES), 32)
        self.assertEqual(len(set(ew.EDITOR_COMMAND_FEATURES)), 32)
        for editor in ('code', 'code-insiders', 'codium', 'cursor', 'windsurf'):
            self.assertIn(editor, ew.EDITORS)

    def test_feature_catalog_maps_100_unique_capabilities_to_implementation(self):
        self.assertEqual(len(ew.FEATURE_CATALOG), 100)
        self.assertEqual(len({item.feature_id for item in ew.FEATURE_CATALOG}), 100)
        self.assertTrue(all(item.title and item.category and callable(item.handler) for item in ew.FEATURE_CATALOG))
        self.assertEqual(len([item for item in ew.FEATURE_CATALOG if item.category == 'Accessibility']), 20)

    def test_cli_path_actions_create_temporary_and_named_profile_windows(self):
        folder = self.home / 'project'; folder.mkdir()
        with patch('octoship.editor_workspace.shutil.which', return_value='/usr/bin/code'):
            temp_profile = ew.editor_command('code', 'profile-create', [folder])
            named = ew.editor_command('code', 'profile-open', [folder], extra=('Web Work',))
        self.assertIn('--profile-temp', temp_profile)
        self.assertIn(str(folder), temp_profile)
        self.assertEqual(named[-3:], ['--profile', 'Web Work', str(folder)])

    def test_cli_line_location_and_diff_validate_exact_local_files(self):
        files = []
        for name in ('a.txt', 'b.txt', 'base.txt', 'result.txt'):
            path = self.home / name; path.write_text(name); files.append(path)
        with patch('octoship.editor_workspace.shutil.which', return_value='/usr/bin/code'):
            goto = ew.editor_command('code', 'goto', [files[0]], extra=('7:2',))
            diff = ew.editor_command('code', 'diff', files[:2])
            merge = ew.editor_command('code', 'merge', files)
        self.assertEqual(goto[-1], str(files[0].resolve()) + ':7:2')
        self.assertEqual(diff[-3:], ['--diff', str(files[0].resolve()), str(files[1].resolve())])
        self.assertEqual(merge[-5], '--merge')

    def test_cli_extra_arguments_cannot_be_used_to_inject_unreviewed_flags(self):
        with patch('octoship.editor_workspace.shutil.which', return_value='/usr/bin/code'):
            with self.assertRaises(OctoShipError): ew.editor_command('code', 'open', extra=('--force',))
            with self.assertRaises(OctoShipError): ew.editor_command('code', 'profile-open', extra=('--disable-extensions',))

    def test_extension_workflows_validate_ids_versions_profiles_and_local_vsix(self):
        with patch('octoship.editor_workspace.shutil.which', return_value='/usr/bin/code'):
            pinned = ew.extension_cli_plan('install-extension', 'publisher.tool@1.2.0')
            profile = ew.extension_cli_plan('install-extension', 'publisher.tool', profile='Web Work')
            remove = ew.extension_cli_plan('uninstall-extension', 'publisher.tool', profile='Web Work')
        self.assertEqual(pinned[-1], 'publisher.tool@1.2.0')
        self.assertEqual(profile[-2:], ['--profile', 'Web Work'])
        self.assertEqual(remove[-2:], ['--profile', 'Web Work'])
        package = self.home / 'local.vsix'; package.write_bytes(b'package')
        with patch('octoship.editor_workspace.shutil.which', return_value='/usr/bin/code'):
            argv = ew.install_local_vsix(package)
        self.assertEqual(argv[-1], str(package))

    def test_extension_list_captures_bounded_machine_output_without_shell(self):
        captured = {}
        class Result: returncode = 0; stdout = 'publisher.one\npublisher.two@2.0\n'; stderr = ''
        def fake(args, **kwargs): captured.update(args=args, kwargs=kwargs); return Result()
        result = ew.extension_list(profile='Web Work', run=fake)
        self.assertEqual(result, ('publisher.one', 'publisher.two@2.0'))
        self.assertFalse(captured['kwargs']['shell'])
        self.assertIn('--profile', captured['args'])

    def test_ten_supported_terminal_shell_profiles_are_distinct_and_detected(self):
        self.assertEqual(len(ew.SHELL_PROFILES), 10)
        found = ew.available_terminal_profiles(lambda name: '/usr/bin/' + name if name in ('bash','zsh','fish','nu','pwsh','xonsh','elvish','tcsh','ksh','dash') else None)
        self.assertEqual(len(found), 10)
        self.assertEqual(len({item['id'] for item in found}), 10)

    def test_terminal_profile_add_remove_default_and_bad_paths(self):
        shell = self.home / 'bash'; shell.write_text('#!/bin/sh\n'); shell.chmod(0o755)
        settings = {'unrelated': True}
        profile = {'id': 'bash', 'name': 'Bash', 'path': str(shell), 'args': ['--login']}
        ew.add_terminal_profile(settings, profile, make_default=True)
        self.assertEqual(settings['terminal.integrated.defaultProfile.linux'], 'Bash')
        self.assertEqual(settings['terminal.integrated.profiles.linux']['Bash']['path'], str(shell.resolve()))
        ew.remove_terminal_profile(settings, 'Bash')
        self.assertNotIn('terminal.integrated.defaultProfile.linux', settings)
        with self.assertRaises(OctoShipError): ew.add_terminal_profile(settings, {'id':'bash','path':'/etc/passwd'})
        with self.assertRaises(OctoShipError): ew.add_terminal_profile(settings, {'id':'bash','path':str(shell),'args':['-c','touch /tmp/no']})

    def test_workspace_config_contexts_validate_without_running_anything(self):
        project = self.home / 'project'; (project / '.vscode').mkdir(parents=True)
        (project / '.vscode' / 'settings.json').write_text('{"editor.wordWrap":"on"}')
        (project / '.vscode' / 'tasks.json').write_text('{"tasks":[]}')
        (project / '.vscode' / 'launch.json').write_text('{"configurations":[]}')
        (project / '.vscode' / 'extensions.json').write_text('{"recommendations":[]}')
        (project / 'work.code-workspace').write_text('{"folders":[]}')
        for kind in ('settings','tasks','launch','extensions','code-workspace'):
            self.assertTrue(ew.validate_workspace_config(project, kind)['valid'])
        self.assertEqual(len(ew.workspace_files(project)), 5)

    def test_workspace_config_paths_reject_links_malformed_json_and_unknown_kind(self):
        project = self.home / 'project'; (project / '.vscode').mkdir(parents=True)
        (project / '.vscode' / 'tasks.json').write_text('{bad')
        with self.assertRaises(OctoShipError): ew.validate_workspace_config(project, 'tasks')
        with self.assertRaises(OctoShipError): ew.workspace_config_path(project, 'unknown')
        (project / '.vscode' / 'tasks.json').unlink()
        target = self.home / 'target.json'; target.write_text('{"tasks":[]}')
        (project / '.vscode' / 'tasks.json').symlink_to(target)
        with self.assertRaises(OctoShipError): ew.workspace_config_path(project, 'tasks')

    def test_editor_readonly_report_limits_supported_actions(self):
        with self.assertRaises(OctoShipError): ew.editor_cli_report('code', 'install-extension')
        class Result: returncode = 0; stdout = '1.2.3'; stderr = ''
        with patch('octoship.editor_workspace.shutil.which', return_value='/usr/bin/code'):
            self.assertEqual(ew.editor_cli_report('code','show-versions',run=lambda *a,**k: Result()), '1.2.3')

    def test_import_rejects_path_traversal_before_any_write(self):
        bundle = {'format': 1, 'editor': 'code', 'files': {'../escape.json': '{}'}}
        with self.assertRaises(OctoShipError): ew.import_settings_snapshot('code', bundle, self.env)
        self.assertFalse((self.home / '.config/escape.json').exists())

    def test_settings_symlinks_and_invalid_json_are_rejected(self):
        self.settings.unlink(); self.settings.symlink_to(self.home / 'victim')
        with self.assertRaises(OctoShipError): ew.read_settings('code', self.env)
        self.settings.unlink(); self.settings.write_text('{invalid')
        with self.assertRaises(OctoShipError): ew.read_settings('code', self.env)

    def test_workspace_metadata_reads_only_supported_config_without_running_tasks(self):
        project = self.home / 'project'; (project / '.vscode').mkdir(parents=True)
        (project / '.vscode/tasks.json').write_text('{"version":"2.0.0","tasks":[{"command":"touch /tmp/unsafe"}]}')
        result = ew.workspace_metadata(project)
        self.assertTrue(result['.vscode/tasks.json']['valid'])
        self.assertFalse((self.home / 'unsafe').exists())

    def test_workspace_links_are_skipped(self):
        project = self.home / 'project'; project.mkdir()
        outside = self.home / 'outside'; outside.write_text('{}')
        (project / '.vscode').symlink_to(outside.parent)
        self.assertEqual(ew.workspace_files(project), ())

    def test_cli_argv_build_is_shell_free_and_validates_targets(self):
        target = self.home / 'file.py'; target.write_text('pass\n')
        with patch('octoship.editor_workspace.shutil.which', return_value='/usr/bin/code'):
            args = ew.editor_command('code', 'open', [target])
        self.assertEqual(args[-1], str(target.resolve()))
        with patch('octoship.editor_workspace.shutil.which', return_value='/usr/bin/code'):
            with self.assertRaises(OctoShipError): ew.editor_command('code', 'diff', [target])
            with self.assertRaises(OctoShipError): ew.editor_command('code', 'open', ['--exec touch'])

    def test_extension_changes_require_valid_identifier(self):
        with patch('octoship.editor_workspace.shutil.which', return_value='/usr/bin/code'):
            with self.assertRaises(OctoShipError): ew.editor_command('code', 'install-extension', extension='publisher;rm -rf')
            with self.assertRaises(OctoShipError): ew.editor_command('code', 'uninstall-extension', extension='bad')

    def test_cli_runs_without_shell_and_never_passes_user_text_as_shell_code(self):
        target = self.home / 'folder'; target.mkdir()
        captured = {}
        class Process: pid = 47
        def fake(args, **kwargs): captured.update(args=args, kwargs=kwargs); return Process()
        with patch('octoship.editor_workspace.shutil.which', return_value='/usr/bin/code'):
            ew.run_editor_action('code', 'open', [target], popen=fake)
        self.assertFalse(captured['kwargs']['shell'])
        self.assertEqual(captured['kwargs']['cwd'], str(target.resolve()))
        self.assertEqual(captured['args'][-1], str(target.resolve()))

    def test_action_contracts_have_unique_names(self):
        actions = ew.EDITOR_COMMAND_FEATURES
        self.assertEqual(len(actions), len(set(actions)))
        self.assertEqual(len(actions), len(ew.EDITOR_COMMAND_FEATURES))


if __name__ == '__main__': unittest.main()
