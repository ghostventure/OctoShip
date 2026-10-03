"""Offline behavioral checks; all HTTP traffic stays on a loopback server."""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, unquote, urlsplit
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from octoship.core import (ApiError, GitHub, OctoShipError, plan_upload,
                           read_file, search_files, sensitive, validate_path)


class LocalGitHub:
    """Stateful Contents API substitute enforcing create/update SHA semantics."""
    def __init__(self):
        self.files = {}
        self.calls = []
        self.writes = []
        self.push = True
        self.redirect = False
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                fixture.calls.append((self.command, self.path, self.headers.get('Authorization')))
                parsed = urlsplit(self.path)
                if fixture.redirect:
                    self.send_response(302)
                    self.send_header('Location', '/redirect-target')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                if parsed.path == '/repos/owner/project':
                    return self.reply(200, {'permissions': {'push': fixture.push}})
                if parsed.path.startswith('/repos/owner/project/branches/'):
                    return self.reply(200, {'name': unquote(parsed.path.rsplit('/', 1)[1])})
                if parsed.path.startswith('/repos/owner/project/contents/'):
                    name = unquote(parsed.path.removeprefix('/repos/owner/project/contents/'))
                    if parse_qs(parsed.query).get('ref') != ['feature/test']:
                        return self.reply(404, {})
                    if name not in fixture.files:
                        return self.reply(404, {})
                    data, sha = fixture.files[name]
                    return self.reply(200, {'type': 'file', 'sha': sha,
                                           'content': base64.b64encode(data).decode()})
                return self.reply(404, {})

            def do_PUT(self):
                fixture.calls.append((self.command, self.path, self.headers.get('Authorization')))
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                fixture.writes.append(payload)
                name = unquote(urlsplit(self.path).path.removeprefix('/repos/owner/project/contents/'))
                current = fixture.files.get(name)
                if current and payload.get('sha') != current[1]:
                    return self.reply(409, {})
                if payload['branch'] != 'feature/test':
                    return self.reply(422, {})
                data = base64.b64decode(payload['content'], validate=True)
                sha = hashlib.sha256(data).hexdigest()
                fixture.files[name] = (data, sha)
                return self.reply(200 if current else 201, {'content': {'sha': sha}})

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.api = GitHub('test-token-only', f'http://127.0.0.1:{self.server.server_port}')

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class FileFixture:

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def file(self, name, content=b'hello'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path


class FilesTest(FileFixture, unittest.TestCase):
    def test_filename_search_casefold_and_exclusions(self):
        expected = self.file('src/ReadMe.TXT')
        self.file('.hidden/ReadMe.txt')
        self.file('node_modules/ReadMe.txt')
        self.file('.git/ReadMe.txt')
        self.file('src/different.txt')
        self.assertEqual(search_files(self.root, 'readme'), [expected])

    def test_content_search_matches_content_not_filename(self):
        expected = self.file('one.txt', b'The NEEDLE is here')
        self.file('needle.txt', b'no match')
        self.assertEqual(search_files(self.root, 'needle', contents=True), [expected])

    def test_hidden_option_and_result_limit(self):
        self.file('.visible-with-option')
        self.file('normal')
        self.assertEqual(len(search_files(self.root)), 1)
        self.assertEqual(len(search_files(self.root, hidden=True)), 2)
        self.assertEqual(len(search_files(self.root, hidden=True, limit=1)), 1)

    def test_cancelled_search_returns_no_results(self):
        self.file('one')
        cancelled = threading.Event()
        cancelled.set()
        self.assertEqual(search_files(self.root, cancel=cancelled), [])

    def test_search_and_read_exclude_symlink_files(self):
        original = self.file('original')
        link = self.root / 'linked'
        link.symlink_to(original)
        self.assertEqual(search_files(self.root), [original])
        with self.assertRaises(OctoShipError):
            read_file(link)

    def test_search_does_not_follow_directory_symlinks(self):
        original = self.file('real/file')
        (self.root / 'alias').symlink_to(original.parent, target_is_directory=True)
        self.assertEqual(search_files(self.root), [original])

    def test_read_rejects_symlink_parent(self):
        original = self.file('real/file')
        (self.root / 'alias').symlink_to(original.parent, target_is_directory=True)
        with self.assertRaises(OctoShipError):
            read_file(self.root / 'alias/file')

    def test_sensitive_names_and_ancestors(self):
        for name in ('.env', '.env.local', 'TLS.KEY', 'id_rsa', 'credentials.json',
                     'private.pem', 'secrets/file.txt', 'passwords.csv'):
            with self.subTest(name=name):
                self.assertTrue(sensitive(name))
                with self.assertRaises(OctoShipError):
                    read_file(self.file(name))
        self.assertFalse(sensitive('src/normal.py'))

    def test_oversize_and_nonregular_reads_rejected(self):
        path = self.file('big', b'12345')
        with patch('octoship.core.MAX_BYTES', 4):
            with self.assertRaises(OctoShipError):
                read_file(path)
        with self.assertRaises(OctoShipError):
            read_file(self.root)

    def test_destination_validation(self):
        for name in ('', '/absolute', '../outside', 'a/../b', 'a/./b', 'a//b',
                     'a/', '.git/config', 'a\\b', 'a\x00b', 'a\nb'):
            with self.subTest(name=name), self.assertRaises(OctoShipError):
                validate_path(name)
        validate_path('docs/hello world.txt')


class ApiTest(FileFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.remote = LocalGitHub()
        self.addCleanup(self.remote.close)
        self.api = self.remote.api

    def plan(self, files, **kwargs):
        return plan_upload(self.api, 'owner/project', 'feature/test', files, **kwargs)

    def test_binary_create_roundtrip_and_encoded_paths(self):
        data = bytes(range(256)) + b'\x00\xff'
        file = self.file('unicode ☃ #?.bin', data)
        _, items, skipped = self.plan([file], prefix='assets')
        self.assertEqual(skipped, [])
        self.assertEqual(items[0].size, len(data))
        result = self.api.upload('owner/project', 'feature/test', items[0], 'Add binary')
        self.assertEqual(self.remote.files[items[0].destination][0], data)
        self.assertEqual(result['content']['sha'], hashlib.sha256(data).hexdigest())
        self.assertNotIn('sha', self.remote.writes[0])
        self.assertEqual(self.remote.writes[0]['message'], 'Add binary')
        target = self.api.target('owner/project', 'feature/test', items[0].destination)
        self.assertEqual(base64.b64decode(target['content']), data)
        self.assertTrue(all(call[2] == 'Bearer test-token-only' for call in self.remote.calls))
        self.assertTrue(any('%23%3F' in call[1] for call in self.remote.calls))

    def test_existing_update_uses_reviewed_sha(self):
        file = self.file('existing.txt', b'new')
        self.remote.files[file.name] = (b'old', 'reviewed-sha')
        _, items, _ = self.plan([file], collision='overwrite')
        self.assertEqual(items[0].sha, 'reviewed-sha')
        self.api.upload('owner/project', 'feature/test', items[0], 'Update')
        self.assertEqual(self.remote.writes[0]['sha'], 'reviewed-sha')
        self.assertEqual(self.remote.files[file.name][0], b'new')

    def test_existing_skip_produces_no_write(self):
        file = self.file('existing.txt')
        self.remote.files[file.name] = (b'old', 'old-sha')
        _, items, skipped = self.plan([file])
        self.assertEqual(items, [])
        self.assertEqual(skipped, ['existing.txt'])
        self.assertEqual(self.remote.writes, [])

    def test_remote_conflict_preserves_remote(self):
        file = self.file('existing.txt', b'local')
        self.remote.files[file.name] = (b'old', 'old-sha')
        _, items, _ = self.plan([file], collision='overwrite')
        self.remote.files[file.name] = (b'concurrent edit', 'new-sha')
        with self.assertRaises(ApiError) as error:
            self.api.upload('owner/project', 'feature/test', items[0], 'Update')
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.remote.files[file.name][0], b'concurrent edit')

    def test_changed_after_review_never_sends_put(self):
        file = self.file('changing.txt')
        _, items, _ = self.plan([file])
        file.write_bytes(b'changed')
        with self.assertRaisesRegex(OctoShipError, 'changed since review'):
            self.api.upload('owner/project', 'feature/test', items[0], 'Update')
        self.assertEqual(self.remote.writes, [])

    def test_duplicate_destinations_rejected(self):
        files = [self.file('one/same.txt'), self.file('two/same.txt')]
        with self.assertRaisesRegex(OctoShipError, 'same destination'):
            self.plan(files)
        self.assertEqual(self.remote.writes, [])

    def test_preserve_relative_paths(self):
        files = [self.file('one/same.txt'), self.file('two/same.txt')]
        _, items, _ = self.plan(files, root=self.root, prefix='upload')
        self.assertEqual([item.destination for item in items],
                         ['upload/one/same.txt', 'upload/two/same.txt'])

    def test_sensitive_destination_and_traversal_rejected(self):
        file = self.file('normal.txt')
        for prefix in ('../outside', 'docs/../outside', '.git', 'secrets'):
            with self.subTest(prefix=prefix), self.assertRaises(OctoShipError):
                self.plan([file], prefix=prefix)
        self.assertEqual(self.remote.writes, [])

    def test_nonwritable_repository_rejected(self):
        self.remote.push = False
        with self.assertRaisesRegex(OctoShipError, 'not writable'):
            self.plan([self.file('normal.txt')])

    def test_redirect_not_followed_with_authorization(self):
        self.remote.redirect = True
        with self.assertRaises(ApiError) as error:
            self.api.request('/repos/owner/project')
        self.assertEqual(error.exception.status, 302)
        self.assertEqual(len(self.remote.calls), 1)


if __name__ == '__main__':
    unittest.main()
