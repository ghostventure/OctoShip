"""Behavioral checks for Linux component parity; no live GitHub writes."""
import base64
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.parse import unquote, urlsplit, parse_qs
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from octoship.core import GitHub, ApiError, OctoShipError, plan_upload
from octoship.scanner import scan_bytes, MAX_SCAN
from octoship.queue_store import QueueStore
from octoship import workflows as flow

HEAD = 'a' * 40
CHANGED = 'b' * 40
NEW = 'c' * 40
TREE = 'd' * 40


def blob_sha(data):
    return hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()


class FakeGitHub(GitHub):
    def __init__(self):
        super().__init__('fixture-only')
        self.current = HEAD
        self.entries = {}
        self.calls = []
        self.writes = []
        self.push = True
        self.truncated = False
        self.change_after_objects = False
        self.fail_patch = False
        self.release = None
        self.assets = []
        self.blobs = {}

    def request(self, path, method='GET', body=None):
        self.calls.append((method, path, copy.deepcopy(body)))
        if method != 'GET': self.writes.append((method, path, copy.deepcopy(body)))
        route = unquote(urlsplit(path).path.removeprefix('/repos/owner/project'))
        if route == '': return {'permissions': {'push': self.push}, 'visibility': 'private'}
        if route.startswith('/branches/'): return {'name': route.removeprefix('/branches/')}
        if route.startswith('/git/ref/heads/'): return {'object': {'sha': self.current}}
        if route.startswith('/git/commits/') and method == 'GET': return {'tree': {'sha': TREE}}
        if route.startswith('/git/trees/') and method == 'GET':
            return {'truncated': self.truncated, 'tree': list(copy.deepcopy(self.entries).values())}
        if route.startswith('/contents/') and method == 'GET':
            name = route.removeprefix('/contents/')
            if name not in self.entries: raise ApiError(404)
            return {'type': 'file', 'sha': self.entries[name]['sha']}
        if route == '/git/blobs' and method == 'POST':
            data = base64.b64decode(body['content'])
            sha = blob_sha(data); self.blobs[sha] = data
            return {'sha': sha}
        if route == '/git/trees' and method == 'POST': return {'sha': 'e' * 40}
        if route == '/git/commits' and method == 'POST':
            if self.change_after_objects: self.current = CHANGED
            return {'sha': NEW}
        if route.startswith('/git/refs/heads/') and method == 'PATCH':
            if body.get('force') is not False: raise AssertionError('force push attempted')
            if self.fail_patch: raise ApiError(409)
            self.current = body['sha']
            return {'object': {'sha': self.current}}
        if route == '/git/refs' and method == 'POST': return body
        if route == '/pulls' and method == 'POST': return {'html_url': 'https://github.com/owner/project/pull/1', **body}
        if route == '/releases' and method == 'POST':
            self.release = {'id': 42, 'html_url': 'https://github.com/owner/project/releases/tag/test', 'assets': [], **body}
            return copy.deepcopy(self.release)
        if route == '/releases/42' and self.release:
            if method == 'PATCH': self.release.update(body)
            return copy.deepcopy(self.release)
        raise AssertionError((method, path, body))

    def asset_request(self, path, stream, size, cancel=None):
        data = stream.read()
        assert len(data) == size
        self.assets.append((path, data))
        return {'id': 100, 'state': 'uploaded'}

    def entry(self, path, data=b'old', mode='100644', kind='blob'):
        self.entries[path] = {'path': path, 'mode': mode, 'type': kind, 'sha': blob_sha(data)}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.api = FakeGitHub()

    def file(self, name='hello.txt', data=b'hello'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        return path

    def plan(self, files=None, **kw):
        return plan_upload(self.api, 'owner/project', 'feature/test', files or [self.file()], target_ref=HEAD, **kw)[1]

    def upload(self, items, **kw):
        return flow.atomic_upload(self.api, 'owner/project', 'feature/test', items, 'Test upload', HEAD, **kw)


class ScannerTests(unittest.TestCase):
    def test_types_and_redaction(self):
        samples = [b'ghp_' + b'x' * 30, b'github_pat_' + b'x' * 30, b'AKIA' + b'A' * 16,
                   b'xoxb-' + b'x' * 30, b'AIza' + b'x' * 35, b'-----BEGIN PRIVATE KEY-----',
                   b'password = "' + b'a' * 12 + b'"', b'api_key=' + b'a' * 12]
        for sample in samples:
            scan = scan_bytes(b'ordinary\n' + sample)
            self.assertTrue(scan.findings, sample)
            self.assertEqual(scan.findings[0][1], 2)
            self.assertNotIn(sample.decode(), scan.summary)

    def test_utf16_and_incomplete_inputs(self):
        self.assertTrue(scan_bytes(('password="' + 'z' * 12 + '"').encode('utf-16')).findings)
        for data in (b'\x00', b'\xff', b'a' * (MAX_SCAN + 1), b'a' * 9000):
            self.assertFalse(scan_bytes(data).complete)
        self.assertFalse(scan_bytes(b'ordinary source text').needs_review)

    def test_bounded_findings_and_cancellation(self):
        self.assertEqual(len(scan_bytes((b'ghp_' + b'x' * 30 + b'\n') * 100).findings), 30)
        cancel = threading.Event(); cancel.set()
        with self.assertRaises(OctoShipError): scan_bytes(b'hello', cancel)


class AtomicTests(Fixture):
    def test_one_commit_nonforce_and_pinned_review(self):
        self.api.entry('run.sh', b'old', mode='100755')
        items = self.plan([self.file('run.sh', b'new'), self.file('other.txt', b'other')], collision='replace')
        self.assertTrue(all('ref=' + HEAD in p for m, p, _ in self.api.calls if '/contents/' in p))
        result = self.upload(items)
        self.assertTrue(result.endswith(NEW))
        self.assertEqual(len([x for x in self.api.writes if x[1].endswith('/git/commits')]), 1)
        self.assertEqual(len([x for x in self.api.writes if x[0] == 'PATCH']), 1)
        body = next(b for m, p, b in self.api.writes if p.endswith('/git/trees'))
        self.assertEqual(body['tree'][0]['mode'], '100755')
        self.assertEqual(self.api.current, NEW)

    def test_branch_change_before_upload_makes_no_objects(self):
        items = self.plan(); self.api.current = CHANGED
        with self.assertRaisesRegex(OctoShipError, 'Branch changed'): self.upload(items)
        self.assertEqual(self.api.writes, [])

    def test_branch_change_before_publish_never_patches(self):
        self.api.change_after_objects = True
        with self.assertRaisesRegex(OctoShipError, 'Nothing was published'): self.upload(self.plan())
        self.assertFalse(any(m == 'PATCH' for m, _, _ in self.api.writes))
        self.assertEqual(self.api.current, CHANGED)

    def test_uncertain_patch_names_commit_for_recovery(self):
        self.api.fail_patch = True
        with self.assertRaisesRegex(OctoShipError, NEW): self.upload(self.plan())
        self.assertEqual(self.api.writes[-1][2]['force'], False)

    def test_changed_source_is_rejected_before_any_write(self):
        path = self.file(); items = self.plan([path]); path.write_bytes(b'edited')
        with self.assertRaisesRegex(OctoShipError, 'changed since review'): self.upload(items)
        self.assertEqual(self.api.writes, [])

    def test_source_changed_between_preflight_and_blob_is_rejected(self):
        path = self.file(); items = self.plan([path]); original = flow.stable_bytes
        calls = 0
        def read(*args, **kw):
            nonlocal calls
            calls += 1
            if calls == 2: path.write_bytes(b'changed')
            return original(*args, **kw)
        with patch('octoship.workflows.stable_bytes', side_effect=read):
            with self.assertRaises(OctoShipError): self.upload(items)
        self.assertEqual(self.api.writes, [])

    def test_truncated_tree_and_readonly_repo_rejected(self):
        items = self.plan()
        self.api.truncated = True
        with self.assertRaises(OctoShipError): self.upload(items)
        self.api.truncated = False; self.api.push = False
        with self.assertRaises(OctoShipError): self.upload(items)
        self.assertEqual(self.api.writes, [])

    def test_symlink_submodule_directory_and_parent_conflicts(self):
        from dataclasses import replace
        items = self.plan()
        for mode, kind in [('120000', 'blob'), ('160000', 'commit'), ('040000', 'tree')]:
            self.api.entry('hello.txt', mode=mode, kind=kind)
            with self.subTest(mode=mode), self.assertRaises(OctoShipError): self.upload(items)
        self.api.entries.clear(); self.api.entry('parent', mode='100644')
        with self.assertRaises(OctoShipError): self.upload([replace(items[0], destination='parent/file')])
        self.api.entries.clear()
        with self.assertRaises(OctoShipError): self.upload([items[0], replace(items[0], destination='hello.txt/child')])
        self.assertEqual(self.api.writes, [])

    def test_content_acknowledgement_is_required_on_exact_bytes(self):
        path = self.file(data=b'ghp_' + b'x' * 30); items = self.plan([path])
        self.assertTrue(items[0].scan.needs_review)
        with self.assertRaisesRegex(OctoShipError, 'acknowledgement'): self.upload(items)
        self.assertEqual(self.api.writes, [])
        self.upload(items, approved=True)
        self.assertIn(path.read_bytes(), self.api.blobs.values())

    def test_cancel_never_advances_branch(self):
        cancel = threading.Event()
        def progress(*_): cancel.set()
        with self.assertRaisesRegex(OctoShipError, 'cancelled'): self.upload(self.plan(), cancel=cancel, progress=progress)
        self.assertFalse(any(m == 'PATCH' for m, _, _ in self.api.writes))


class WorkflowTests(Fixture):
    def test_compare_reports_same_changed_local_and_remote_only(self):
        self.file('same.txt', b'same'); self.file('changed.txt', b'local'); self.file('local.txt')
        self.api.entry('docs/same.txt', b'same'); self.api.entry('docs/changed.txt', b'remote'); self.api.entry('docs/remote.txt')
        self.api.entry('elsewhere.txt')
        commit, rows = flow.compare_folder(self.api, 'owner/project', 'feature/test', 'docs', self.root)
        self.assertEqual(commit, HEAD)
        self.assertEqual(dict(rows), {'same.txt': 'Same content', 'changed.txt': 'Changed content', 'local.txt': 'Local only', 'remote.txt': 'Remote only'})
        self.assertEqual(self.api.writes, [])

    def test_compare_stops_on_truncated_tree_or_symlink(self):
        self.api.truncated = True
        with self.assertRaises(OctoShipError): flow.compare_folder(self.api, 'owner/project', 'main', '', self.root)
        self.api.truncated = False
        (self.root / 'alias').symlink_to(self.file())
        with self.assertRaises(OctoShipError): flow.compare_folder(self.api, 'owner/project', 'main', '', self.root)

    def test_compare_rejects_nonregular_local_entries(self):
        os.mkfifo(self.root / 'pipe')
        with self.assertRaisesRegex(OctoShipError, 'not a regular file'):
            flow.compare_folder(self.api, 'owner/project', 'main', '', self.root)

    def test_branch_creates_reviewed_commit_and_pr_payload(self):
        result = flow.create_branch(self.api, 'owner/project', 'feature/new', HEAD)
        self.assertEqual(result, {'ref': 'refs/heads/feature/new', 'sha': HEAD})
        pr = flow.create_pr(self.api, 'owner/project', 'feature/new', 'main', 'A change', 'Details')
        self.assertTrue(pr['draft']); self.assertEqual(pr['base'], 'main')
        with self.assertRaises(OctoShipError): flow.create_pr(self.api, 'owner/project', 'main', 'main', 'title', '')

    def test_invalid_branches_are_rejected(self):
        for value in ('', '@', '-start', 'x..y', 'x/.hidden', 'x.lock', 'a\\b', 'a\nb', '/a', 'a/', 'a//b', 'trailing.'):
            with self.subTest(value=value), self.assertRaises(OctoShipError): flow.validate_branch(value)


class QueueTests(Fixture):
    def setUp(self):
        super().setUp(); self.store = QueueStore(self.root / 'state')

    def test_opt_in_journal_is_private_and_allowlisted(self):
        self.assertFalse(self.store.directory.exists())
        snapshot = self.store.snapshot('owner/project', 'feature/test', 'atomic', 'message', self.plan())
        self.store.save(snapshot)
        path = self.store.path('owner/project', 'feature/test')
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.store.directory.stat().st_mode & 0o777, 0o700)
        self.assertNotIn('fixture-only', path.read_text())
        snapshot['token'] = 'forbidden'
        with self.assertRaises(OctoShipError): self.store.save(snapshot)

    def test_resume_skips_completed_and_revalidates_source(self):
        first, second = self.file('first'), self.file('second')
        snapshot = self.store.snapshot('owner/project', 'main', 'per-file', 'message', self.plan([first, second]))
        snapshot['entries'][0]['status'] = 'uploaded'; snapshot['entries'][1]['status'] = 'uploading'
        self.store.save(snapshot)
        _, pending = self.store.resume('owner/project', 'main')
        self.assertEqual([row['source'] for row in pending], [str(second)])
        second.write_bytes(b'changed')
        with self.assertRaisesRegex(OctoShipError, 'changed'): self.store.resume('owner/project', 'main')
        self.store.delete('owner/project', 'main'); self.assertIsNone(self.store.load('owner/project', 'main'))

    def test_corrupt_or_wrong_repository_journal_rejected(self):
        snapshot = self.store.snapshot('owner/project', 'main', 'atomic', 'message', self.plan())
        self.store.save(snapshot)
        path = self.store.path('owner/project', 'main')
        path.write_text('{broken')
        with self.assertRaises(OctoShipError): self.store.load('owner/project', 'main')
        snapshot['repository'] = 'someone/else'; path.write_text(json.dumps(snapshot))
        with self.assertRaises(OctoShipError): self.store.load('owner/project', 'main')


class ReleaseTests(Fixture):
    def draft(self):
        return flow.create_draft(self.api, 'owner/project', 'v1.6.0', 'main', 'Release', 'Notes')

    def test_creation_is_draft_publish_is_separate(self):
        self.assertTrue(self.draft()['draft'])
        self.assertFalse(any(m == 'PATCH' for m, _, _ in self.api.writes))
        result = flow.publish_release(self.api, 'owner/project', 42)
        self.assertFalse(result['draft'])
        with self.assertRaises(OctoShipError): flow.publish_release(self.api, 'owner/project', 42)

    def test_notes_scan_blocks_without_ack(self):
        with self.assertRaisesRegex(OctoShipError, 'acknowledgement'):
            flow.create_draft(self.api, 'owner/project', 'v1', 'main', 'title', 'ghp_' + 'x' * 30)
        self.assertEqual(self.api.writes, [])

    def test_asset_bytes_name_and_changed_source(self):
        self.draft(); path = self.file('asset #☃.txt', b'asset content')
        size, digest, scan = flow.inspect_asset(path)
        flow.upload_asset(self.api, 'owner/project', 42, path, digest)
        self.assertEqual(self.api.assets[0][1], b'asset content')
        self.assertEqual(parse_qs(urlsplit(self.api.assets[0][0]).query)['name'], [path.name])
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(OctoShipError, 'changed since review'):
            flow.upload_asset(self.api, 'owner/project', 42, path, digest)
        self.assertEqual(len(self.api.assets), 1)

    def test_asset_binary_needs_ack_and_symlink_rejected(self):
        self.draft(); path = self.file('asset.bin', b'\0\xff')
        _, digest, _ = flow.inspect_asset(path)
        with self.assertRaisesRegex(OctoShipError, 'acknowledgement'):
            flow.upload_asset(self.api, 'owner/project', 42, path, digest)
        flow.upload_asset(self.api, 'owner/project', 42, path, digest, approved=True)
        alias = self.root / 'alias'; alias.symlink_to(path)
        with self.assertRaises(OctoShipError): flow.inspect_asset(alias)

    def test_incomplete_asset_blocks_publication(self):
        self.draft(); self.api.release['assets'] = [{'name': 'incomplete.zip', 'state': 'starter'}]
        with self.assertRaisesRegex(OctoShipError, 'incomplete assets'):
            flow.publish_release(self.api, 'owner/project', 42)
        self.assertTrue(self.api.release['draft'])
        self.assertFalse(any(m == 'PATCH' for m, _, _ in self.api.writes))

    def test_asset_transport_streams_to_upload_host_without_redirects(self):
        fixture = self
        received = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                data = self.rfile.read(int(self.headers['Content-Length']))
                received.append((self.path, data, self.headers['Content-Type']))
                if self.path == '/redirect':
                    self.send_response(302); self.send_header('Location', '/other'); self.end_headers(); return
                encoded = b'{"id": 1}'
                self.send_response(201); self.send_header('Content-Length', str(len(encoded))); self.end_headers(); self.wfile.write(encoded)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            api = GitHub('fixture-only', uploads_url=f'http://127.0.0.1:{server.server_port}')
            import io
            data = b'\0\xff' * 100000
            api.asset_request('/asset', io.BytesIO(data), len(data))
            self.assertEqual(received[0], ('/asset', data, 'application/octet-stream'))
            with self.assertRaises(OctoShipError): api.asset_request('/redirect', io.BytesIO(data), len(data))
            self.assertEqual(len(received), 2)
        finally:
            server.shutdown(); server.server_close(); thread.join()


class HttpAtomicTests(Fixture):
    def test_atomic_plan_and_publication_through_http(self):
        backend = self.api
        received = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def handle_request(self):
                received.append((self.command, self.path, self.headers.get('Authorization')))
                size = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(size)) if size else None
                try:
                    result = backend.request(self.path, self.command, body); status = 200
                except ApiError as exc:
                    result, status = {}, exc.status
                data = json.dumps(result).encode()
                self.send_response(status); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
            do_GET = do_POST = do_PATCH = handle_request
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            api = GitHub('fixture-only', f'http://127.0.0.1:{server.server_port}')
            branch = 'feature/test'
            sha = flow.head(api, 'owner/project', branch)
            items = plan_upload(api, 'owner/project', branch, [self.file('unicode #☃.txt')], target_ref=sha)[1]
            url = flow.atomic_upload(api, 'owner/project', branch, items, 'Upload', sha)
            self.assertTrue(url.endswith(NEW)); self.assertEqual(backend.current, NEW)
            self.assertTrue(all(auth == 'Bearer fixture-only' for _, _, auth in received))
            self.assertEqual([m for m, _, _ in received].count('PATCH'), 1)
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': unittest.main()
