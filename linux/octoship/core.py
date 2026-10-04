"""UI-independent Linux search, GitHub transport, and upload planning."""
import base64
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from dataclasses import dataclass
from contextlib import contextmanager

MAX_BYTES = 25 * 1024 * 1024
SENSITIVE = ('.env', '.env.*', '*.pem', '*.key', '*.p12', '*.pfx', 'id_rsa*',
             'id_ed25519*', '*credential*', '*secret*', '*password*', '*.publishsettings', '*.keystore')
EXCLUDED = {'.git', '.hg', '.svn', 'node_modules', '__pycache__', '.venv', 'venv'}

class OctoShipError(Exception):
    pass

class ApiError(OctoShipError):
    def __init__(self, status):
        self.status = status
        messages = {401: 'Authentication expired. Run gh auth login and reconnect.',
                    403: 'Access denied or API rate limit reached.',
                    404: 'Repository, branch, or file not found.',
                    409: 'Remote file changed. Review the upload again.',
                    422: 'GitHub rejected the change. Check branch protection and file path.'}
        super().__init__(messages.get(status, f'GitHub returned HTTP {status}.'))

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class GitHub:
    def __init__(self, token, base_url='https://api.github.com', uploads_url='https://uploads.github.com'):
        self._token = token
        self.base_url = base_url.rstrip('/')
        self.uploads_url = uploads_url.rstrip('/')
        self.opener = build_opener(NoRedirect())

    @classmethod
    def from_cli(cls):
        try:
            result = subprocess.run(['gh', 'auth', 'token', '--hostname', 'github.com'],
                                    capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            raise OctoShipError('Install GitHub CLI and run gh auth login in a terminal.') from None
        if result.returncode or not result.stdout.strip():
            raise OctoShipError('Sign in first: run gh auth login in a terminal.')
        return cls(result.stdout.strip())

    def request(self, path, method='GET', body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = Request(self.base_url + path, data=data, method=method, headers={
            'Authorization': 'Bearer ' + self._token, 'User-Agent': 'OctoShip-Linux/1.6.0',
            'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': 'application/json'})
        try:
            with self.opener.open(req, timeout=45) as response:
                return json.load(response)
        except HTTPError as exc:
            status = exc.code
            exc.close()
            raise ApiError(status) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise OctoShipError('GitHub connection failed. Check your network and try again.') from None

    def asset_request(self, path, stream, size, cancel=None):
        from .scanner import check_cancel
        def chunks():
            while chunk := stream.read(1024 * 1024):
                check_cancel(cancel)
                yield chunk
        check_cancel(cancel)
        req = Request(self.uploads_url + path, data=chunks(), method='POST', headers={
            'Authorization': 'Bearer ' + self._token, 'User-Agent': 'OctoShip-Linux/1.6.0',
            'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
            'Content-Type': 'application/octet-stream', 'Content-Length': str(size)})
        try:
            with self.opener.open(req, timeout=120) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            if isinstance(exc, HTTPError): exc.close()
            raise OctoShipError('Asset upload not confirmed. Inspect the draft assets on GitHub before retrying.') from None

    def pages(self, path):
        items = []
        for page in range(1, 101):
            batch = self.request(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
            items.extend(batch)
            if len(batch) < 100:
                return items
        raise OctoShipError('Too many results; use a more specific repository.')

    def repositories(self):
        return self.pages('/user/repos?sort=updated&affiliation=owner,collaborator,organization_member')

    def repo_path(self, repo):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) or any(p in ('.', '..') for p in repo.split('/')):
            raise OctoShipError('Choose a repository in owner/name format.')
        return '/repos/' + repo

    def branches(self, repo):
        return self.pages(self.repo_path(repo) + '/branches')

    def target(self, repo, branch, path):
        validate_path(path)
        try:
            result = self.request(self.repo_path(repo) + '/contents/' + quote(path, safe='/') + '?' + urlencode({'ref': branch}))
        except ApiError as exc:
            if exc.status == 404:
                return None
            raise
        if not isinstance(result, dict) or result.get('type') != 'file':
            raise OctoShipError(f'Destination is not a regular file: {path}')
        return result

    def upload(self, repo, branch, item, message, approved=False):
        content = read_file(item.local)
        if hashlib.sha256(content).hexdigest() != item.digest:
            raise OctoShipError(f'Local file changed since review: {item.local.name}')
        from .scanner import require_scan_approval
        require_scan_approval(content, approved)
        body = {'message': message, 'content': base64.b64encode(content).decode(), 'branch': branch}
        if item.sha:
            body['sha'] = item.sha
        return self.request(self.repo_path(repo) + '/contents/' + quote(item.destination, safe='/'), 'PUT', body)


def validate_path(path):
    if (not path or len(path) > 1024 or '\\' in path or any(ord(c) < 32 or ord(c) == 127 for c in path)
            or any(p in ('', '.', '..', '.git') for p in path.split('/'))):
        raise OctoShipError('Use a relative destination without empty segments, .., or .git.')


def sensitive(path):
    return any(fnmatch.fnmatchcase(part.lower(), pattern) for part in Path(path).parts for pattern in SENSITIVE)


@contextmanager
def open_regular(path):
    """Open through directory descriptors; no symlink component may redirect reads."""
    absolute = Path(os.path.abspath(path))
    try:
        directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        try:
            for component in absolute.parts[1:-1]:
                next_directory = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = next_directory
            fd = os.open(absolute.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        finally:
            os.close(directory)
        with os.fdopen(fd, 'rb') as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise OctoShipError('Only regular files are supported: ' + absolute.name)
            yield source
    except OSError:
        raise OctoShipError('Cannot read file (symlinks are excluded): ' + absolute.name) from None


def read_file(path):
    path = Path(path)
    if sensitive(path):
        raise OctoShipError(f'Sensitive filename blocked: {path.name}')
    with open_regular(path) as source:
        before = os.fstat(source.fileno())
        if before.st_size > MAX_BYTES:
            raise OctoShipError(f'Only regular files up to 25 MiB can be uploaded: {path.name}')
        content = source.read(MAX_BYTES + 1)
        after = os.fstat(source.fileno())
        if len(content) > MAX_BYTES:
            raise OctoShipError(f'File exceeds 25 MiB: {path.name}')
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (len(content), after.st_mtime_ns, after.st_ctime_ns):
            raise OctoShipError('Local file changed while reading: ' + path.name)
        return content


def search_files(root, query='', contents=False, hidden=False, cancel=None, limit=5000):
    root = Path(root).expanduser()
    if not root.is_dir():
        raise OctoShipError('Choose an existing search folder.')
    found = []
    query = query.casefold()
    for folder, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not Path(folder, d).is_symlink()
                         and (hidden or not d.startswith('.')))
        for name in sorted(files):
            if cancel and cancel.is_set():
                return found
            path = Path(folder, name)
            if path.is_symlink() or not path.is_file() or (not hidden and name.startswith('.')):
                continue
            match = query in name.casefold()
            if contents and query:
                try:
                    with path.open('rb') as source:
                        match = query in source.read(2 * 1024 * 1024).decode('utf-8', errors='replace').casefold()
                except OSError:
                    continue
            if match:
                found.append(path)
                if len(found) >= limit:
                    return found
    return found

@dataclass(frozen=True)
class UploadItem:
    local: Path
    destination: str
    digest: str
    size: int
    sha: str | None
    scan: object = None


def plan_upload(api, repo, branch, files, prefix='', root=None, collision='skip', cancel=None, target_ref=None, destinations=None):
    if not files or len(files) > 100:
        raise OctoShipError('Select between 1 and 100 files.')
    if not branch:
        raise OctoShipError('Select a branch first.')
    metadata = api.request(api.repo_path(repo))
    if metadata.get('archived') or metadata.get('disabled') or not metadata.get('permissions', {}).get('push'):
        raise OctoShipError('Repository is archived, disabled, or not writable by this account.')
    api.request(api.repo_path(repo) + '/branches/' + quote(branch, safe=''))
    prefix = prefix.strip('/')
    if prefix:
        validate_path(prefix)
    overrides = destinations or {}
    planned, skipped, seen_destinations = [], [], set()
    for file in files:
        if cancel and cancel.is_set():
            raise OctoShipError('Review cancelled.')
        path = Path(file)
        relative = path.relative_to(root).as_posix() if root else path.name
        destination = overrides.get(str(path), prefix + '/' + relative if prefix else relative)
        validate_path(destination)
        if sensitive(destination):
            raise OctoShipError(f'Sensitive destination blocked: {destination}')
        if destination in seen_destinations:
            raise OctoShipError(f'Two files have the same destination: {destination}')
        seen_destinations.add(destination)
        data = read_file(path)
        target = api.target(repo, target_ref or branch, destination)
        if target and collision == 'skip':
            skipped.append(destination)
            continue
        from .scanner import scan_bytes
        planned.append(UploadItem(path, destination, hashlib.sha256(data).hexdigest(), len(data), target['sha'] if target else None, scan_bytes(data, cancel)))
    return metadata, planned, skipped
