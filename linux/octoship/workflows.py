"""Atomic uploads, fixed-commit comparisons, branches, PRs, and draft releases."""
import base64
import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile
from urllib.parse import quote, urlencode
from .core import OctoShipError, read_file, open_regular, validate_path, sensitive
from .scanner import check_cancel, require_scan_approval


def validate_branch(branch):
    if (not branch or len(branch) > 255 or branch == '@' or branch.startswith('-')
            or branch.endswith('.') or '..' in branch or '@{' in branch
            or any(ord(c) < 33 or ord(c) == 127 or c in '~^:?*[\\' for c in branch)
            or any(not p or p.startswith('.') or p.lower().endswith('.lock') for p in branch.split('/'))):
        raise OctoShipError('Enter a valid Git branch name.')


def validate_sha(sha):
    if not isinstance(sha, str) or not re.fullmatch('[0-9a-fA-F]{40}', sha):
        raise OctoShipError('A valid reviewed commit SHA is required.')
    return sha


def writable(api, repo):
    meta = api.request(api.repo_path(repo))
    if meta.get('archived') or meta.get('disabled') or meta.get('permissions', {}).get('push') is not True:
        raise OctoShipError('Repository is archived, disabled, or not writable by this account.')
    return meta


def head(api, repo, branch):
    validate_branch(branch)
    return validate_sha(api.request(api.repo_path(repo) + '/git/ref/heads/' + quote(branch, safe='/'))['object']['sha'])


def tree_at(api, repo, commit):
    validate_sha(commit)
    root = api.repo_path(repo)
    tree_sha = api.request(root + '/git/commits/' + commit)['tree']['sha']
    tree = api.request(root + '/git/trees/' + quote(tree_sha, safe='') + '?recursive=1')
    if tree.get('truncated') is not False:
        raise OctoShipError('Incomplete remote tree. No missing-file conclusions or uploads were made.')
    return tree_sha, {entry['path']: entry for entry in tree['tree']}


def validate_destinations(items, entries):
    paths = set()
    for item in items:
        validate_path(item.destination)
        if sensitive(item.destination) or item.destination in paths:
            raise OctoShipError('Sensitive or duplicate destination in batch.')
        paths.add(item.destination)
    for path in paths:
        entry = entries.get(path)
        if entry and (entry.get('type') != 'blob' or entry.get('mode') not in ('100644', '100755')):
            raise OctoShipError('Destination is a directory, link, or submodule: ' + path)
        parts = path.split('/')
        for i in range(1, len(parts)):
            parent = '/'.join(parts[:i])
            if parent in paths or (parent in entries and entries[parent].get('mode') != '040000'):
                raise OctoShipError('A destination parent is a file, link, or submodule: ' + parent)


def stable_bytes(item, approved=False, cancel=None):
    check_cancel(cancel)
    data = read_file(item.local)
    if len(data) != item.size or hashlib.sha256(data).hexdigest() != item.digest:
        raise OctoShipError('Local file changed since review: ' + item.local.name)
    require_scan_approval(data, approved, cancel)
    return data


def atomic_upload(api, repo, branch, items, message, expected_head, approved=False, cancel=None, progress=None):
    validate_branch(branch)
    validate_sha(expected_head)
    if not 1 <= len(items) <= 100 or not message.strip() or len(message) > 250:
        raise OctoShipError('Select 1–100 files and a commit message of 1–250 characters.')
    check_cancel(cancel)
    writable(api, repo)
    if head(api, repo, branch) != expected_head:
        raise OctoShipError('Branch changed after review. Review the batch again.')
    tree_sha, entries = tree_at(api, repo, expected_head)
    validate_destinations(items, entries)
    for item in items:
        entry = entries.get(item.destination)
        if (entry['sha'] if entry else None) != item.sha:
            raise OctoShipError('Remote destination changed after review. Review the batch again.')
        stable_bytes(item, approved, cancel)
    root = api.repo_path(repo)
    tree = []
    for index, item in enumerate(items):
        data = stable_bytes(item, approved, cancel)
        blob = api.request(root + '/git/blobs', 'POST', {'content': base64.b64encode(data).decode(), 'encoding': 'base64'})
        tree.append({'path': item.destination, 'mode': entries.get(item.destination, {}).get('mode', '100644'),
                     'type': 'blob', 'sha': blob['sha']})
        if progress: progress(index + 1, 'Prepared ' + item.destination)
    check_cancel(cancel)
    created_tree = api.request(root + '/git/trees', 'POST', {'base_tree': tree_sha, 'tree': tree})
    check_cancel(cancel)
    commit = api.request(root + '/git/commits', 'POST',
                         {'message': message, 'tree': created_tree['sha'], 'parents': [expected_head]})['sha']
    check_cancel(cancel)
    if head(api, repo, branch) != expected_head:
        raise OctoShipError('Branch changed during preparation. Nothing was published; review again.')
    check_cancel(cancel)
    try:
        api.request(root + '/git/refs/heads/' + quote(branch, safe='/'), 'PATCH', {'sha': commit, 'force': False})
    except OctoShipError:
        raise OctoShipError(f'Publication not confirmed. Inspect commit {commit} on GitHub before retrying; the branch may have advanced.') from None
    return 'https://github.com/' + repo + '/commit/' + commit


def compare_folder(api, repo, branch, remote_folder, local_folder, cancel=None):
    prefix = remote_folder.strip('/')
    if prefix: validate_path(prefix)
    local = Path(os.path.abspath(Path(local_folder).expanduser()))
    if not local.is_dir() or any(p.is_symlink() for p in (local, *local.parents)):
        raise OctoShipError('Choose a regular local folder without symlink ancestors.')
    commit = head(api, repo, branch)
    _, entries = tree_at(api, repo, commit)
    prefix = prefix + '/' if prefix else ''
    remote = {p[len(prefix):]: e for p, e in entries.items() if p.startswith(prefix) and e['type'] != 'tree'}
    seen, rows = set(), []
    def walk_error(error):
        raise OctoShipError('Comparison incomplete: a local directory could not be read.') from error
    for folder, dirs, files in os.walk(local, followlinks=False, onerror=walk_error):
        check_cancel(cancel)
        dirs[:] = [d for d in dirs if d != '.git']
        for name in dirs + files:
            if Path(folder, name).is_symlink():
                raise OctoShipError('Comparison incomplete: symbolic links are not followed.')
        for name in files:
            check_cancel(cancel)
            if len(seen) >= 50000:
                raise OctoShipError('Comparison incomplete: select a folder with at most 50,000 files.')
            path = Path(folder, name)
            if not stat.S_ISREG(path.lstat().st_mode):
                raise OctoShipError('Comparison incomplete: a local entry is not a regular file.')
            rel = path.relative_to(local).as_posix()
            seen.add(rel)
            target = remote.get(rel)
            if not target:
                status = 'Local only'
            elif target.get('mode') not in ('100644', '100755') or target.get('type') != 'blob':
                status = 'Unsupported remote link/submodule'
            else:
                with open_regular(path) as stream:
                    before = os.fstat(stream.fileno())
                    digest = hashlib.sha1(f'blob {before.st_size}\0'.encode())
                    while chunk := stream.read(1024 * 1024):
                        check_cancel(cancel)
                        digest.update(chunk)
                    after = os.fstat(stream.fileno())
                    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                        raise OctoShipError('Comparison incomplete: local file changed while hashing.')
                status = 'Same content' if digest.hexdigest() == target['sha'] else 'Changed content'
            rows.append((rel, status))
    rows.extend((p, 'Remote only' if e.get('mode') in ('100644', '100755') and e.get('type') == 'blob'
                 else 'Unsupported remote link/submodule') for p, e in remote.items() if p not in seen)
    return commit, sorted(rows)


def create_branch(api, repo, new_branch, reviewed_sha):
    validate_branch(new_branch)
    validate_sha(reviewed_sha)
    writable(api, repo)
    return api.request(api.repo_path(repo) + '/git/refs', 'POST', {'ref': 'refs/heads/' + new_branch, 'sha': reviewed_sha})


def create_pr(api, repo, source, base, title, body, draft=True, approved=False):
    validate_branch(source)
    validate_branch(base)
    if source == base or not title.strip():
        raise OctoShipError('Choose different head/base branches and enter a title.')
    require_scan_approval((title + '\n' + body).encode(), approved)
    return api.request(api.repo_path(repo) + '/pulls', 'POST',
                       {'head': source, 'base': base, 'title': title.strip(), 'body': body, 'draft': bool(draft)})


def create_draft(api, repo, tag, target, title, notes, prerelease=False, approved=False):
    validate_branch(tag)
    if not target.strip(): raise OctoShipError('Choose a release target.')
    require_scan_approval((title + '\n' + notes).encode(), approved)
    writable(api, repo)
    return api.request(api.repo_path(repo) + '/releases', 'POST',
                       {'tag_name': tag, 'target_commitish': target, 'name': title, 'body': notes,
                        'draft': True, 'prerelease': bool(prerelease)})


def release_id(value):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise OctoShipError('Invalid release ID.')
    return str(value)


def draft_release(api, repo, identity):
    release = api.request(api.repo_path(repo) + '/releases/' + release_id(identity))
    if release.get('draft') is not True:
        raise OctoShipError('Release is no longer a draft. Refresh its state on GitHub.')
    return release


def publish_release(api, repo, identity):
    release = draft_release(api, repo, identity)
    if any(asset.get('state') != 'uploaded' for asset in release.get('assets', [])):
        raise OctoShipError('Draft contains incomplete assets. Inspect GitHub before publishing.')
    return api.request(api.repo_path(repo) + '/releases/' + release_id(identity), 'PATCH', {'draft': False})


def stage_asset(path, cancel=None):
    path = Path(path)
    validate_path(path.name)
    if sensitive(path): raise OctoShipError('Sensitive asset filename blocked.')
    staged = tempfile.TemporaryFile()
    try:
        with open_regular(path) as source:
            before = os.fstat(source.fileno())
            if not 0 < before.st_size < 2 * 1024**3:
                raise OctoShipError('Assets must be nonempty and smaller than 2 GiB.')
            digest = hashlib.sha256()
            size = 0
            while chunk := source.read(1024 * 1024):
                check_cancel(cancel)
                size += len(chunk)
                if size >= 2 * 1024**3: raise OctoShipError('Asset grew beyond 2 GiB.')
                digest.update(chunk)
                staged.write(chunk)
            after = os.fstat(source.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (size, after.st_mtime_ns, after.st_ctime_ns):
                raise OctoShipError('Asset changed while reading. Review it again.')
        staged.seek(0)
        return staged, size, digest.hexdigest()
    except BaseException:
        staged.close()
        raise


def inspect_asset(path, cancel=None):
    from .scanner import scan_bytes, MAX_SCAN
    staged, size, digest = stage_asset(path, cancel)
    with staged:
        scan = scan_bytes(staged.read(MAX_SCAN + 1), cancel)
    return size, digest, scan


def upload_asset(api, repo, identity, path, expected_digest, approved=False, cancel=None):
    from .scanner import MAX_SCAN
    draft_release(api, repo, identity)
    staged, size, digest = stage_asset(path, cancel)
    with staged:
        if digest != expected_digest: raise OctoShipError('Asset changed since review.')
        require_scan_approval(staged.read(MAX_SCAN + 1), approved, cancel)
        staged.seek(0)
        route = api.repo_path(repo) + '/releases/' + release_id(identity) + '/assets?' + urlencode({'name': Path(path).name})
        return api.asset_request(route, staged, size, cancel)
