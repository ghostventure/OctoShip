"""Installer integrity, destination quoting, reinstallation, and rollback checks."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.payload = self.folder / 'payload'; self.payload.mkdir()
        self.home = self.folder / 'home'; self.home.mkdir()
        self.prefix = self.home / 'an app folder $with spaces'
        source = Path(__file__).resolve().parents[1] / 'packaging/installer.py'
        (self.payload / 'installer.py').write_bytes(source.read_bytes())
        (self.payload / 'bundle.json').write_text('{"version":"1.6.1"}')
        (self.payload / 'octoship').write_text('#!/bin/sh\nprintf "bundled app\\n"\n')
        (self.payload / 'octoship').chmod(0o755)
        (self.payload / 'octoship.svg').write_text('<svg/>')
        (self.payload / 'alias').symlink_to('octoship')
        self.manifest()
        spec = importlib.util.spec_from_file_location('installer_under_test', self.payload / 'installer.py')
        self.installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.installer)
        env = patch.dict(os.environ, {'HOME': str(self.home), 'XDG_DATA_HOME': str(self.home / '.local/share')})
        env.start(); self.addCleanup(env.stop)

    def manifest(self):
        files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.payload.iterdir()
                 if p.is_file() and not p.is_symlink() and p.name != 'payload-hashes.json'}
        (self.payload / 'payload-hashes.json').write_text(json.dumps({'files': files, 'symlinks': {'alias': 'octoship'}}))

    def test_modified_file_rejected_before_installing(self):
        (self.payload / 'octoship').write_text('corrupt')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'): self.installer.install(self.prefix)
        self.assertFalse(self.prefix.exists())

    def test_retargeted_symlink_rejected(self):
        (self.payload / 'alias').unlink(); (self.payload / 'alias').symlink_to('/bin/sh')
        with self.assertRaisesRegex(ValueError, 'symlink'): self.installer.install(self.prefix)
        self.assertFalse(self.prefix.exists())

    def test_install_with_spaces_registers_working_shell_and_desktop_launchers(self):
        import subprocess
        launcher = self.installer.install(self.prefix)
        self.assertEqual(subprocess.check_output([str(launcher)], text=True), 'bundled app\n')
        self.assertEqual(subprocess.check_output([str(self.home / '.local/bin/octoship')], text=True), 'bundled app\n')
        desktop = (self.home / '.local/share/applications/octoship.desktop').read_text()
        self.assertIn('\\$with spaces', desktop)
        login = (self.home / '.local/share/applications/octoship-login.desktop').read_text()
        self.assertIn(' --login', login); self.assertIn('Terminal=true', login)

    def test_reinstall_reuses_build_and_upgrade_preserves_old_build(self):
        self.installer.install(self.prefix, register=False)
        first = list((self.prefix / 'builds').iterdir())
        self.installer.install(self.prefix, register=False)
        self.assertEqual(list((self.prefix / 'builds').iterdir()), first)
        (self.payload / 'octoship').write_text('#!/bin/sh\nprintf "upgraded app\\n"\n'); self.manifest()
        self.installer.install(self.prefix, register=False)
        self.assertEqual(len(list((self.prefix / 'builds').iterdir())), 2)
        self.assertTrue(first[0].exists())
        self.assertTrue((self.prefix / 'octoship.previous').exists())

    def test_uninstall_preserves_user_data_and_newer_launcher(self):
        self.installer.install(self.prefix)
        installed = next((self.prefix / 'builds').iterdir())
        saved = self.home / '.local/state/octoship/queues/test.json'; saved.parent.mkdir(parents=True); saved.write_text('saved')
        newer = self.home / '.local/bin/octoship'; newer.write_text('#!/bin/sh\nexec /newer/octoship\n')
        with patch('builtins.input', return_value='uninstall'):
            self.installer.uninstall(installed)
        self.assertTrue(newer.exists()); self.assertEqual(saved.read_text(), 'saved')
        self.assertFalse(installed.exists())

    def test_declined_uninstall_leaves_installation(self):
        self.installer.install(self.prefix)
        installed = next((self.prefix / 'builds').iterdir())
        with patch('builtins.input', return_value='no'): self.installer.uninstall(installed)
        self.assertTrue(installed.exists()); self.assertTrue((self.home / '.local/bin/octoship').exists())


if __name__ == '__main__': unittest.main()
