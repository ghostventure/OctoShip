import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from octoship.workspace_audit import audit_workspace


class WorkspaceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'state' / 'octoship'
        (self.root / 'queues').mkdir(parents=True)
        os.chmod(self.root, 0o700)
        os.chmod(self.root / 'queues', 0o700)

    def tearDown(self):
        self.temp.cleanup()

    def put_queue(self, name='a' * 64 + '.json', entries=None):
        source = Path(self.temp.name) / 'sample.txt'
        source.write_bytes(b'sample\n')
        queue = {
            'version': 1, 'repository': 'owner/repo', 'branch': 'main',
            'mode': 'atomic', 'message': 'reviewed upload',
            'entries': entries if entries is not None else [{
                'source': str(source), 'destination': 'docs/sample.txt',
                'digest': hashlib.sha256(source.read_bytes()).hexdigest(),
                'size': source.stat().st_size, 'status': 'pending',
            }],
        }
        (self.root / 'queues' / name).write_text(json.dumps(queue), encoding='utf-8')
        return source

    def test_reports_51_stable_distinct_checks_without_writes(self):
        self.put_queue()
        before = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}
        report = audit_workspace(self.root)
        after = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(len(report), 51)
        self.assertEqual(len({row.code for row in report}), 51)
        self.assertEqual(before, after)
        self.assertEqual(next(row.status for row in report if row.code == 'QUEUE_SOURCE_CHANGED'), 'ok')

    def test_changed_and_missing_sources_are_reported(self):
        source = self.put_queue()
        source.write_text('changed', encoding='utf-8')
        report = audit_workspace(self.root)
        self.assertEqual(next(row.status for row in report if row.code == 'QUEUE_SOURCE_CHANGED'), 'review')
        source.unlink()
        report = audit_workspace(self.root)
        self.assertEqual(next(row.status for row in report if row.code == 'QUEUE_SOURCE_MISSING'), 'review')

    def test_malformed_state_is_reported_without_echoing_contents(self):
        sentinel = 'ghp_test_secret_value_that_should_not_leak_1234567890'
        (self.root / 'bad.json').write_text(sentinel, encoding='utf-8')
        report = audit_workspace(self.root)
        self.assertEqual(next(row.status for row in report if row.code == 'QUEUE_PARSE'), 'error')
        self.assertNotIn(sentinel, '\n'.join(row.detail for row in report))


if __name__ == '__main__':
    unittest.main()
