"""Reviewed project shipping and evidence-based delivery diagnostics."""
import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import quote
from .core import GitHub, OctoShipError, UploadItem, read_file, validate_path, sensitive
from .scanner import scan_bytes, check_cancel
from .inspection import project_files, redact
from . import workflows as flow


def blob_hash(data):
    return hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()


def recipe(value):
    if not isinstance(value, dict) or value.get('version') != 1: raise OctoShipError('Unsupported recipe version.')
    keys = {'version', 'repository', 'branch', 'destination', 'exclusions', 'release_name'}
    if set(value) - keys: raise OctoShipError('Recipe contains unsupported fields.')
    repo, branch, dest = (value.get(k, '') for k in ('repository', 'branch', 'destination'))
    if not all(isinstance(v, str) for v in (repo, branch, dest, value.get('release_name', ''))): raise OctoShipError('Invalid recipe fields.')
    GitHub.repo_path(None, repo); flow.validate_branch(branch)
    if dest: validate_path(dest)
    exclusions = value.get('exclusions', [])
    if not isinstance(exclusions, list) or len(exclusions) > 100: raise OctoShipError('Invalid exclusions.')
    for pattern in exclusions:
        if not isinstance(pattern, str) or len(pattern) > 255 or pattern.startswith(('/', '~')) or '\\' in pattern or ':' in pattern or '..' in pattern.split('/'):
            raise OctoShipError('Exclusions must be relative globs.')
    if scan_bytes(json.dumps(value).encode()).findings: raise OctoShipError('Recipe contains potential credentials.')
    if len(json.dumps(value).encode()) > 65536: raise OctoShipError('Recipe exceeds 64 KiB.')
    return {k: value[k] for k in keys if k in value}


@dataclass
class Shipment:
    repo: str
    branch: str
    commit: str
    items: list
    rows: list
    visibility: str
    account: str


def review_project(api, repo, branch, root, destination='', exclusions=(), cancel=None):
    if destination: validate_path(destination)
    commit = flow.head(api, repo, branch); meta = flow.writable(api, repo)
    account = api.request('/user')['login']
    _, entries = flow.tree_at(api, repo, commit)
    items, rows, local_hashes = [], [], {}
    root = Path(root).expanduser().absolute()
    for path in project_files(root, cancel, exclusions):
        check_cancel(cancel)
        rel = path.relative_to(root).as_posix(); dest = destination + '/' + rel if destination else rel
        validate_path(dest)
        if sensitive(dest): raise OctoShipError('Sensitive destination blocked: ' + dest)
        data = read_file(path); sha = blob_hash(data); local_hashes[dest] = sha
        entry = entries.get(dest)
        scan = scan_bytes(data, cancel)
        if scan.findings: raise OctoShipError('Potential secrets block shipping: ' + rel + '\n' + scan.summary)
        if entry and entry.get('sha') == sha and entry.get('mode') in ('100644', '100755'):
            rows.append((dest, 'Same content')); continue
        items.append(UploadItem(path, dest, hashlib.sha256(data).hexdigest(), len(data), entry.get('sha') if entry else None, scan))
        rows.append((dest, ('Changed' if entry else 'Local only') + '\n' + scan.summary))
        if len(items) > 100: raise OctoShipError('Shipping supports at most 100 changed files.')
    flow.validate_destinations(items, entries)
    # Only unique identical-content candidates are suggested, and never deleted.
    prefix = destination + '/' if destination else ''
    missing = {}
    for path, entry in entries.items():
        if path.startswith(prefix) and path not in local_hashes and entry.get('mode') in ('100644', '100755'):
            missing.setdefault(entry['sha'], []).append(path)
    for item in items:
        sha = local_hashes[item.destination]
        old = missing.get(sha, [])
        if item.sha is None and len(old) == 1 and list(local_hashes.values()).count(sha) == 1:
            rows.append((item.destination, 'Possible move from ' + old[0] + ' (old path will remain)'))
    return Shipment(repo, branch, commit, items, rows, meta.get('visibility', 'unknown'), account)


def verify_commit(api, repo, commit, items):
    try:
        _, entries = flow.tree_at(api, repo, commit)
        expected = {item.destination: blob_hash(flow.stable_bytes(item, True)) for item in items}
        mismatches = [p for p, sha in expected.items() if entries.get(p, {}).get('sha') != sha]
        return 'Mismatch: ' + ', '.join(mismatches) if mismatches else 'Verified: immutable commit contains the reviewed bytes.'
    except OctoShipError: return 'Could not verify the immutable commit; inspect GitHub before retrying.'


def ship_project(api, review, new_branch, title, approved=False, cancel=None):
    flow.validate_branch(new_branch)
    if new_branch == review.branch or not review.items: raise OctoShipError('Choose a new branch and at least one changed file.')
    if not title.strip() or len(title) > 250: raise OctoShipError('Enter a title of 1–250 characters.')
    if api.request('/user')['login'] != review.account: raise OctoShipError('Account changed after review.')
    if flow.writable(api, review.repo).get('visibility', 'unknown') != review.visibility: raise OctoShipError('Repository visibility changed. Review again.')
    if flow.head(api, review.repo, review.branch) != review.commit: raise OctoShipError('Base branch changed. Review again.')
    for item in review.items:
        data = flow.stable_bytes(item, approved, cancel)
        if scan_bytes(data).findings: raise OctoShipError('Potential secrets block shipping.')
    check_cancel(cancel)
    # The POST itself may have succeeded even if its response was lost.
    try:
        flow.create_branch(api, review.repo, new_branch, review.commit)
        url = flow.atomic_upload(api, review.repo, new_branch, review.items, title, review.commit, approved, cancel)
        commit = url.rsplit('/', 1)[-1]
        verification = verify_commit(api, review.repo, commit, review.items)
        check_cancel(cancel)
        pr = flow.create_pr(api, review.repo, new_branch, review.branch, title, 'Prepared with OctoShip.\n\n' + verification, True, True)
        return {'commit': url, 'verification': verification, 'pull_request': pr.get('html_url', '')}
    except Exception as exc:
        raise OctoShipError(f'Shipment incomplete or unconfirmed. Inspect branch {new_branch} in {review.repo} before retrying. ' + (str(exc) if isinstance(exc, OctoShipError) else 'Operation failed.')) from None


def diagnostics(api, repo, branch):
    root = api.repo_path(repo); result = {}
    endpoints = {'account': '/user', 'repository': root, 'rules': root + '/rules/branches/' + quote(branch, safe=''),
                 'protection': root + '/branches/' + quote(branch, safe='') + '/protection',
                 'pages': root + '/pages', 'pages_build': root + '/pages/builds/latest', 'pages_health': root + '/pages/health'}
    for key, route in endpoints.items():
        try:
            value = api.request(route)
            if key == 'account': value = {k: value.get(k) for k in ('login', 'name', 'email')}
            if key == 'repository': value = {k: value.get(k) for k in ('full_name', 'visibility', 'permissions', 'archived')}
            result[key] = value
        except OctoShipError as exc: result[key] = 'Unknown / unavailable: ' + str(exc)
    result['identity_note'] = 'Commit identity uses GitHub defaults; exact commit email is unavailable. https://github.com/settings/emails'
    return result


def local_git(root):
    outputs = []
    for args in (['status', '--short', '--branch'], ['remote', '-v']):
        try:
            result = subprocess.run(['git', '--no-optional-locks', '-c', 'core.fsmonitor=false', '-c', 'core.untrackedCache=false', '-C', str(Path(root).expanduser()), *args], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired): raise OctoShipError('Local Git inspection unavailable.') from None
        outputs.append(redact(result.stdout if result.returncode == 0 else 'Git inspection failed. Choose a Git working tree.'))
    return '\n'.join(outputs)


def verify_attestation(repo, path):
    GitHub.repo_path(None, repo)
    try:
        result = subprocess.run(['gh', 'attestation', 'verify', str(Path(path).absolute()), '--repo', repo, '--format', 'json'], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired): raise OctoShipError('Attestation NOT verified: CLI unavailable or timed out.') from None
    if result.returncode: raise OctoShipError('Attestation NOT verified. Check CLI authentication, artifact and repository attestations.')
    try: evidence = json.loads(result.stdout)
    except ValueError: raise OctoShipError('Attestation NOT verified: invalid CLI evidence.') from None
    if not evidence: raise OctoShipError('Attestation NOT verified: empty CLI evidence.')
    return evidence


def release_channel(api, repo, prerelease, expected_tag, asset_name):
    releases = api.request(api.repo_path(repo) + '/releases?per_page=100')
    selected = next((r for r in releases if not r.get('draft') and bool(r.get('prerelease')) == prerelease), None)
    if not selected: return 'No matching channel in the latest 100 releases.'
    names = [a['name'] for a in selected.get('assets', [])]
    return {'tag': selected['tag_name'], 'expected_tag_matches': selected['tag_name'] == expected_tag,
            'expected_asset_present': asset_name in names, 'assets': names,
            'boundary': 'Checks supplied expectations, not arbitrary updater code or download behavior.'}


def test_release(api, repo, identity, references=None, cancel=None):
    references = references or {}
    release = api.request(api.repo_path(repo) + '/releases/' + flow.release_id(identity))
    rows = []
    for asset in release.get('assets', []):
        check_cancel(cancel)
        expected = references.get(asset['name']) or asset.get('digest', '')
        if expected.startswith('sha256:'): expected = expected[7:]
        try:
            size, digest = api.download_digest(api.repo_path(repo) + '/releases/assets/' + flow.release_id(asset['id']), cancel)
            status = 'Mismatch' if size != asset['size'] or (expected and digest != expected) else ('Verified' if expected else 'Content unverified: no reference digest')
        except OctoShipError as exc: status = 'Could not verify: ' + str(exc)
        rows.append((asset['name'], status, api.public_download_status(asset.get('browser_download_url', ''))))
    for name in references.keys() - {a['name'] for a in release.get('assets', [])}: rows.append((name, 'Missing asset', 'Not checked'))
    return rows


def recover_assets(api, repo, identity, assets, approved=False, cancel=None):
    release = flow.draft_release(api, repo, identity); existing = {a['name']: a for a in release.get('assets', [])}
    rows = []
    for path, expected_digest in assets:
        check_cancel(cancel)
        if path.name in existing:
            asset = existing[path.name]
            size, digest = api.download_digest(api.repo_path(repo) + '/releases/assets/' + flow.release_id(asset['id']), cancel)
            rows.append((path.name, 'Already present and verified' if digest == expected_digest and size == asset['size'] else 'Mismatch — preserved for manual resolution'))
        else:
            flow.upload_asset(api, repo, identity, path, expected_digest, approved, cancel)
            rows.append((path.name, 'Uploaded missing asset'))
    return rows
