"""Offline mapping, immutable selective baselines, and account-bound publication."""
import base64
import hashlib
from pathlib import Path
import tempfile
from .core import OctoShipError, GitHub, UploadItem, read_file, validate_path, sensitive
from .scanner import scan_bytes
from .storage import save_json, load_json, state_root
from .inspection import project_files, selective_changes, apply_changes
from . import workflows as flow


def validate_plan(value):
    if not isinstance(value, dict) or value.get('version') != 1 or set(value) - {'version','root','repository','branch','files'}:
        raise OctoShipError('Invalid preparation plan.')
    GitHub.repo_path(None, value.get('repository', '')); flow.validate_branch(value.get('branch', ''))
    if not isinstance(value.get('root'), str) or not Path(value['root']).is_absolute(): raise OctoShipError('Plan requires an absolute project folder.')
    files = value.get('files')
    if not isinstance(files, list) or not 1 <= len(files) <= 100: raise OctoShipError('Plan requires 1–100 files.')
    seen = set()
    for row in files:
        if not isinstance(row, dict) or set(row) != {'source','destination'} or not all(isinstance(v, str) for v in row.values()): raise OctoShipError('Invalid mapping.')
        validate_path(row['destination'])
        if sensitive(row['destination']) or row['destination'] in seen: raise OctoShipError('Sensitive or duplicate destination.')
        if not Path(row['source']).is_absolute(): raise OctoShipError('Source paths must be absolute.')
        seen.add(row['destination'])
    return value


def map_project(root, repo, branch, destination='', exclusions=()):
    root = Path(root).expanduser().absolute()
    if destination: validate_path(destination)
    files = []
    for path in project_files(root, exclusions=exclusions):
        rel = path.relative_to(root).as_posix()
        files.append({'source': str(path), 'destination': destination + '/' + rel if destination else rel})
        if len(files) > 100: raise OctoShipError('Preparation supports at most 100 files. Use exclusions or select a smaller folder.')
    return validate_plan({'version':1, 'root':str(root), 'repository':repo, 'branch':branch, 'files':files})


def stage_bytes(data):
    folder = state_root() / 'prepared'; folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=folder, suffix='.txt', delete=False) as stream:
        stream.write(data); return str(Path(stream.name).absolute())


def placeholder(plan, folder, destination):
    root = Path(plan['root']); folder = Path(folder).absolute()
    if not folder.is_relative_to(root) or any(p.is_symlink() for p in (folder, *folder.parents)) or not folder.is_dir() or any(folder.iterdir()):
        raise OctoShipError('Choose an empty regular folder within the project.')
    validate_path(destination)
    if Path(destination).name != '.gitkeep': raise OctoShipError('Placeholder destination must end with .gitkeep.')
    result = dict(plan, files=plan['files'] + [{'source': stage_bytes(b''), 'destination':destination}])
    return validate_plan(result)


def identity(api, plan, bindings=None):
    user = api.request('/user'); meta = flow.writable(api, plan['repository'])
    key = plan['root'] + '\n' + plan['repository']; binding = (bindings or {}).get(key, {})
    if binding.get('account') and binding['account'].casefold() != user['login'].casefold():
        raise OctoShipError('Connected account does not match this project binding.')
    visibility = meta.get('visibility', 'unknown')
    return {'account': user['login'], 'visibility': visibility,
            'warning': 'Visibility differs from saved binding.' if binding.get('visibility') and binding['visibility'] != visibility else '',
            'name': user.get('name'), 'email': user.get('email'),
            'commit_identity': 'GitHub defaults; exact commit email unavailable. https://github.com/settings/emails'}


def bindings():
    path = state_root() / 'project-bindings.json'
    return load_json(path) if path.exists() else {}


def bind_project(api, plan):
    value = identity(api, plan); values = bindings()
    values[plan['root'] + '\n' + plan['repository']] = {k:value[k] for k in ('account','visibility')}
    save_json(state_root() / 'project-bindings.json', values)
    return value


def review(api, plan, selective=None):
    validate_plan(plan); account = identity(api, plan, bindings()); repo, branch = plan['repository'], plan['branch']
    commit = flow.head(api, repo, branch)
    if selective and (selective['repository'], selective['branch'], selective['commit']) != (repo, branch, commit):
        raise OctoShipError('Selective baseline changed. Reload and select edits again.')
    _, entries = flow.tree_at(api, repo, commit); items = []
    if selective and (len(plan['files']) != 1 or plan['files'][0]['destination'] != selective['destination']):
        raise OctoShipError('Selective destination changed. Reload the baseline.')
    for row in plan['files']:
        data = read_file(row['source']); scan = scan_bytes(data)
        if scan.findings: raise OctoShipError('Potential secrets block preparation publishing.\n' + scan.summary)
        old = entries.get(row['destination'])
        items.append(UploadItem(Path(row['source']), row['destination'], hashlib.sha256(data).hexdigest(), len(data), old.get('sha') if old else None, scan))
    flow.validate_destinations(items, entries)
    return {'plan': plan, 'identity':account, 'commit':commit, 'items':items}


def publish(api, reviewed, message, approved=False, cancel=None):
    account = identity(api, reviewed['plan'], bindings())
    if (account['account'], account['visibility']) != (reviewed['identity']['account'], reviewed['identity']['visibility']):
        raise OctoShipError('Account or visibility changed after review.')
    return flow.atomic_upload(api, reviewed['plan']['repository'], reviewed['plan']['branch'], reviewed['items'], message, reviewed['commit'], approved, cancel)


def selective_baseline(api, plan, row):
    repo, branch = plan['repository'], plan['branch']; commit = flow.head(api, repo, branch)
    target = api.target(repo, commit, row['destination'])
    if not target or target.get('encoding') != 'base64' or target.get('size', 0) > 1024**2:
        raise OctoShipError('Select an existing UTF-8 remote file up to 1 MiB.')
    before = base64.b64decode(target.get('content', ''), validate=False); after = read_file(row['source'])
    lines, changes = selective_changes(before, after)
    return {'repository':repo, 'branch':branch, 'commit':commit, 'destination':row['destination'], 'lines':lines, 'changes':changes}
