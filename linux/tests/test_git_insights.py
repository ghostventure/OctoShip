"""Behavioral tests for read-only local Git diagnostics."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from octoship.git_insights import RepositoryError, inspect_repository, report_json


class GitInsightsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'OctoShip Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.root / 'README.md').write_text('hello\n')
        (self.root / '.gitignore').write_text('ignored.tmp\n')
        (self.root / 'src').mkdir()
        (self.root / 'src' / 'main.py').write_text('print(1)\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'initial')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()

    def rows(self):
        return {row.key: row for row in inspect_repository(self.root)}

    def test_report_has_40_stable_distinct_insights(self):
        rows = inspect_repository(self.root)
        self.assertEqual(len(rows), 40)
        self.assertEqual(len({row.key for row in rows}), 40)
        self.assertIn('Repository root', [row.title for row in rows])
        self.assertEqual({row.key: row for row in rows}['clean'].status, 'ok')

    def test_worktree_status_counts_and_clean_detection(self):
        (self.root / 'README.md').write_text('edited\n')
        (self.root / 'new.tmp').write_text('untracked\n')
        rows = self.rows()
        self.assertEqual(rows['unstaged'].detail, '1')
        self.assertEqual(rows['untracked'].detail, '1')
        self.assertEqual(rows['clean'].status, 'review')
        self.assertEqual(rows['clean'].detail, 'No')

    def test_repository_capabilities_and_file_advisories(self):
        rows = self.rows()
        self.assertEqual(rows['readme'].detail, 'Yes')
        self.assertEqual(rows['gitignore'].detail, 'Yes')
        self.assertEqual(rows['author_config'].detail, 'Yes')
        self.assertEqual(rows['tracked_count'].detail, '3')

    def test_json_export_is_valid_and_contains_all_rows(self):
        import json
        payload = json.loads(report_json(self.root))
        self.assertEqual(len(payload), 40)
        self.assertEqual(payload[0]['key'], 'repository')

    def test_invalid_repository_is_explained(self):
        with tempfile.TemporaryDirectory() as other, self.assertRaises(RepositoryError):
            inspect_repository(other)

    def test_report_does_not_mutate_repository(self):
        index = self.root / '.git' / 'index'
        before = self.git('status', '--porcelain=v1')
        original_index = (index.read_bytes(), index.stat().st_mtime_ns)
        inspect_repository(self.root)
        self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), original_index)
        self.assertEqual(self.git('status', '--porcelain=v1'), before)

    def test_remote_credentials_are_redacted(self):
        self.git('remote', 'add', 'origin', 'https://alice:secret@example.com/org/private.git')
        self.git('remote', 'add', 'credential-only', 'https://ghp_verysecretvalue@example.net/private/repo.git')
        rows = self.rows()
        self.assertNotIn('secret', rows['remotes'].detail)
        self.assertNotIn('ghp_verysecretvalue', rows['remotes'].detail)
        self.assertNotIn('alice', rows['remotes'].detail)
        self.assertIn('[credentials]', rows['remotes'].detail)
        self.assertIn('[repository]', rows['remotes'].detail)

    def test_large_files_are_reported_without_opening_contents(self):
        path = self.root / 'large.bin'
        with path.open('wb') as stream:
            stream.truncate(50 * 1024 * 1024)
        self.git('add', 'large.bin')
        rows = self.rows()
        self.assertEqual(rows['large_files'].status, 'review')
        self.assertIn('large.bin', rows['large_files'].detail)


if __name__ == '__main__':
    unittest.main()
