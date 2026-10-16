"""Local Git change-management actions; no remotes or credentials are used."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from octoship import git_operations as ops


class GitOperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'OctoShip Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.root / 'README.md').write_text('initial\n')
        self.git('add', 'README.md')
        self.git('commit', '-qm', 'initial commit')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()

    def test_catalog_has_100_distinct_fixed_local_views(self):
        self.assertEqual(len(ops.ACTIONS), 100)
        self.assertEqual(len(ops.ACTION_BY_KEY), 100)
        self.assertEqual(len({action.args for action in ops.ACTIONS}), 100)
        forbidden = {'push', 'fetch', 'pull', 'clone', 'reset', 'clean', 'checkout', 'switch', 'commit'}
        for action in ops.ACTIONS:
            self.assertNotIn(action.args[0], forbidden, action.key)
            self.assertTrue(all(isinstance(arg, str) for arg in action.args))

    def test_selected_actions_run_and_do_not_mutate_worktree(self):
        before = self.git('status', '--porcelain')
        index = self.root / '.git' / 'index'
        index_before = (index.read_bytes(), index.stat().st_mtime_ns)
        for key in ('status_short', 'branches_local', 'history_recent', 'diff_check',
                    'tags_all', 'remotes_names', 'stash_list', 'worktrees_list',
                    'files_tracked', 'review_check_ref'):
            with self.subTest(key=key):
                output = ops.run_action(self.root, key)
                self.assertIsInstance(output, str)
        self.assertEqual(index_before, (index.read_bytes(), index.stat().st_mtime_ns))
        after = self.git('status', '--porcelain')
        self.assertEqual(before, after)

    def test_unknown_action_and_nonrepository_are_rejected(self):
        with self.assertRaises(ops.GitOperationError):
            ops.run_action(self.root, 'status; touch /tmp/not-allowed')
        with tempfile.TemporaryDirectory() as other, self.assertRaises(ops.GitOperationError):
            ops.run_action(other, 'status_short')

    def test_remote_userinfo_is_redacted_from_action_output(self):
        self.git('remote', 'add', 'origin', 'https://alice:supersecret@example.invalid/org/repo.git')
        output = ops.run_action(self.root, 'remotes_fetch_config')
        self.assertNotIn('supersecret', output)
        self.assertIn('[credentials]', output)

    def test_create_branch_is_local_and_validates_name_and_startpoint(self):
        current = self.git('branch', '--show-current')
        result = ops.create_branch(self.root, 'feature/local', 'HEAD')
        self.assertIn('No remote was contacted', result)
        self.assertEqual(self.git('branch', '--show-current'), current)
        self.assertEqual(self.git('rev-parse', 'feature/local'), self.git('rev-parse', 'HEAD'))
        with self.assertRaises(ops.GitOperationError):
            ops.create_branch(self.root, 'feature/local')
        with self.assertRaises(ops.GitOperationError):
            ops.create_branch(self.root, 'feature/bad', '--help')

    def test_delete_requires_confirmation_and_only_deletes_merged_local_branch(self):
        ops.create_branch(self.root, 'feature/merged')
        with self.assertRaises(ops.GitOperationError):
            ops.delete_branch(self.root, 'feature/merged')
        self.assertIn('Deleted merged local branch', ops.delete_branch(self.root, 'feature/merged', True))
        self.assertNotIn('feature/merged', self.git('branch','--list'))
        with self.assertRaises(ops.GitOperationError):
            ops.delete_branch(self.root, 'master', True)

    def test_stash_requires_confirmation_and_valid_message(self):
        (self.root / 'README.md').write_text('changed\n')
        with self.assertRaises(ops.GitOperationError):
            ops.stash_save(self.root, 'checkpoint')
        with self.assertRaises(ops.GitOperationError):
            ops.stash_save(self.root, '   ', True)
        output = ops.stash_save(self.root, 'checkpoint', True)
        self.assertIn('Saved working directory', output)
        self.assertEqual(self.git('status','--porcelain'), '')
        self.assertIn('checkpoint', self.git('stash','list'))


if __name__ == '__main__':
    unittest.main()
