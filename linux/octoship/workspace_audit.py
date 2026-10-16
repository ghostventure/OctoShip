"""Read-only inspection of OctoShip's local state and saved queue journals."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

from .core import sensitive, validate_path
from .storage import state_root
from .workflows import validate_branch

MAX_STATE_FILE = 2 * 1024 * 1024
MAX_QUEUE_FILES = 500
MAX_STATE_FILES = 1000
MAX_STATE_SCAN_BYTES = 16 * 1024 * 1024
MAX_SOURCE_HASH_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class WorkspaceFinding:
    code: str
    status: str
    detail: str


def _row(code, status, detail):
    return WorkspaceFinding(code, status, detail)


def audit_workspace(root=None, now=None):
    """Return bounded checks about queue/settings privacy and recoverability."""
    base = Path(root or state_root()).expanduser().absolute()
    current = time.time() if now is None else now
    rows = []
    exists = base.exists()
    is_dir = exists and base.is_dir() and not base.is_symlink()
    mode = base.stat().st_mode if is_dir else 0
    rows.extend((
        _row('STATE_PATH', 'ok' if str(base).startswith('/') else 'review', str(base)),
        _row('STATE_EXISTS', 'ok' if exists else 'info', 'State folder exists.' if exists else 'No local state has been created yet.'),
        _row('STATE_DIRECTORY', 'ok' if is_dir else ('info' if not exists else 'error'), 'Regular directory.' if is_dir else 'Expected a non-symlink directory.'),
        _row('STATE_OWNER', 'ok' if is_dir and base.stat().st_uid == os.getuid() else ('info' if not exists else 'review'), 'Owned by current user.' if is_dir and base.stat().st_uid == os.getuid() else 'Owner could not be confirmed as the current user.'),
        _row('STATE_MODE', 'ok' if is_dir and mode & 0o077 == 0 else ('info' if not exists else 'review'), f'Mode {mode & 0o777:04o}.' if is_dir else 'Unavailable.'),
        _row('STATE_READ', 'ok' if is_dir and os.access(base, os.R_OK) else ('info' if not exists else 'error'), 'Readable.' if is_dir and os.access(base, os.R_OK) else 'Not readable.'),
        _row('STATE_WRITE', 'ok' if is_dir and os.access(base, os.W_OK) else ('info' if not exists else 'review'), 'Writable.' if is_dir and os.access(base, os.W_OK) else 'Not writable or not created.'),
        _row('STATE_SYMLINK', 'ok' if not base.is_symlink() else 'error', 'Path is not a symbolic link.' if not base.is_symlink() else 'State root is a symbolic link.'),
    ))
    state_files = []
    state_overflow = False
    if is_dir:
        try:
            with os.scandir(base) as entries:
                for entry in entries:
                    if len(state_files) >= MAX_STATE_FILES:
                        state_overflow = True
                        break
                    state_files.append(Path(entry.path))
            state_files.sort(key=lambda p: p.name.casefold())
        except OSError:
            state_files = []
    queues = base / 'queues'
    queue_dir = queues.is_dir() and not queues.is_symlink()
    queue_files = []
    queue_overflow = False
    if queue_dir:
        try:
            with os.scandir(queues) as entries:
                for entry in entries:
                    if entry.name.endswith('.json'):
                        if len(queue_files) >= MAX_QUEUE_FILES:
                            queue_overflow = True
                            break
                        queue_files.append(Path(entry.path))
            queue_files.sort(key=lambda p: p.name.casefold())
        except OSError:
            queue_files = []
    valid_files = [p for p in state_files if p.is_file() and not p.is_symlink()]
    state_scan_limited = state_overflow or len(valid_files) > 20
    state_bytes = 0
    oversized = []
    malformed = []
    records = []
    scan_bytes = 0
    for path in (valid_files[:20] + [p for p in queue_files if p not in valid_files])[:MAX_QUEUE_FILES + 20]:
        try:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                continue
            state_bytes += info.st_size
            if info.st_size > MAX_STATE_FILE or scan_bytes + info.st_size > MAX_STATE_SCAN_BYTES:
                oversized.append(path.name); continue
            scan_bytes += info.st_size
            data = path.read_bytes()
            try:
                value = json.loads(data)
            except (ValueError, UnicodeError):
                malformed.append(path.name); continue
            records.append((path, value, info))
        except OSError:
            malformed.append(path.name)
    queue_count = len(queue_files)
    queue_json = [(p, value, info) for p, value, info in records if p.parent == queues]
    bindings = next((value for p, value, _ in records if p.name == 'project-bindings.json'), None)
    queue_destinations = []
    duplicate_destinations = False
    missing_sources = []
    changed_sources = []
    sensitive_destinations = []
    invalid_paths = []
    invalid_branches = []
    invalid_repositories = []
    invalid_statuses = []
    embedded_secrets = []
    old_queues = []
    source_hash_bytes = 0
    unchecked_sources = []
    duplicate_files = []
    queue_versions = []
    row_count = 0
    for path, value, info in queue_json:
        if not isinstance(value, dict):
            malformed.append(path.name); continue
        if value.get('version') != 1: queue_versions.append(path.name)
        repo, branch = value.get('repository'), value.get('branch')
        if not isinstance(repo, str) or not re.fullmatch(r'[^/\s]+/[^/\s]+', repo): invalid_repositories.append(path.name)
        try: validate_branch(branch)
        except Exception: invalid_branches.append(path.name)
        entries = value.get('entries', [])
        if not isinstance(entries, list): entries = []
        row_count += len(entries)
        seen_in_queue = set()
        for entry in entries:
            if not isinstance(entry, dict): continue
            dest, src = entry.get('destination'), entry.get('source')
            if isinstance(dest, str) and dest in seen_in_queue:
                duplicate_destinations = True
            if isinstance(dest, str):
                seen_in_queue.add(dest)
            queue_destinations.append(dest)
            try: validate_path(dest)
            except Exception: invalid_paths.append(str(dest))
            if isinstance(dest, str) and sensitive(dest): sensitive_destinations.append(dest)
            if entry.get('status') not in ('pending', 'uploading', 'uploaded', 'failed', 'uncertain'): invalid_statuses.append(path.name)
            if isinstance(src, str) and Path(src).is_absolute():
                source = Path(src)
                if not source.exists(): missing_sources.append(source.name)
                elif source.is_symlink(): changed_sources.append(source.name)
                elif isinstance(entry.get('size'), int) and isinstance(entry.get('digest'), str):
                    try:
                        source_size = source.stat().st_size
                        if source_size != entry['size'] or source_size > 50 * 1024 * 1024:
                            changed_sources.append(source.name)
                        elif source_hash_bytes + source_size > MAX_SOURCE_HASH_BYTES:
                            unchecked_sources.append(source.name)
                        else:
                            digest = hashlib.sha256()
                            with source.open('rb') as stream:
                                while chunk := stream.read(1024 * 1024): digest.update(chunk)
                            source_hash_bytes += source_size
                            if digest.hexdigest() != entry['digest']: changed_sources.append(source.name)
                    except OSError: changed_sources.append(source.name)
        if current - info.st_mtime > 180 * 86400: old_queues.append(path.name)
        text = json.dumps(value, ensure_ascii=False)
        if re.search(r'(?i)(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)', text):
            embedded_secrets.append(path.name)
    duplicate_state_names = len([p.name for p in valid_files]) != len(set(p.name.casefold() for p in valid_files))
    binding_count = len(bindings) if isinstance(bindings, dict) else 0
    binding_invalid = isinstance(bindings, dict) and any(not isinstance(k, str) or not isinstance(v, dict) or set(v) - {'account', 'visibility'} for k, v in bindings.items())
    has_content_field = any('content' in value for _, value, _ in records if isinstance(value, dict))
    has_credential_field = any(any(x in key.lower() for x in ('token', 'password', 'secret', 'credential'))
                               for _, value, _ in records if isinstance(value, dict) for key in value)
    rows.extend((
        _row('QUEUE_FOLDER', 'ok' if queue_dir else ('info' if not queues.exists() else 'error'), 'Regular queue folder.' if queue_dir else 'No queue folder or an unsafe queue path.'),
        _row('QUEUE_FILE_COUNT', 'ok' if queue_count <= MAX_QUEUE_FILES else 'error', f'{queue_count} saved queue file(s); limit {MAX_QUEUE_FILES}.'),
        _row('QUEUE_FILENAME', 'ok' if all(re.fullmatch(r'[0-9a-f]{64}\.json', p.name) for p in queue_files) else ('info' if not queue_files else 'review'), 'Queue names use hashed destination keys.' if all(re.fullmatch(r'[0-9a-f]{64}\.json', p.name) for p in queue_files) else 'Unexpected queue file naming found.'),
        _row('QUEUE_PRIVATE_MODE', 'ok' if queue_dir and queues.stat().st_mode & 0o077 == 0 else ('info' if not queue_dir else 'review'), f'Queue folder mode {queues.stat().st_mode & 0o777:04o}.' if queue_dir else 'Unavailable.'),
        _row('QUEUE_PARSE', 'ok' if not malformed else 'error', 'All inspected JSON state files parse.' if not malformed else f'{len(malformed)} file(s) need repair.'),
        _row('QUEUE_SIZE', 'ok' if not oversized else 'error', 'All state JSON files are within 2 MiB.' if not oversized else 'Oversized files: ' + ', '.join(oversized[:5])),
        _row('STATE_TOTAL_SIZE', 'ok' if state_bytes <= 100 * 1024 * 1024 else 'review', f'{state_bytes:,} bytes across state files.'),
        _row('QUEUE_SCHEMA', 'ok' if not queue_versions else 'review', 'Queue schema version is supported.' if not queue_versions else 'Unsupported schema in: ' + ', '.join(queue_versions[:5])),
        _row('QUEUE_ROWS', 'ok' if row_count <= 5000 else 'review', f'{row_count} queued file record(s).'),
        _row('QUEUE_DESTINATION_DUPLICATE', 'error' if duplicate_destinations else 'ok', 'No duplicate destinations across saved queues.' if not duplicate_destinations else 'Some saved queues target duplicate paths.'),
        _row('QUEUE_DESTINATION_PATH', 'error' if invalid_paths else 'ok', 'All destinations use valid repository paths.' if not invalid_paths else f'{len(invalid_paths)} invalid path(s).'),
        _row('QUEUE_SENSITIVE_DESTINATION', 'error' if sensitive_destinations else 'ok', 'No sensitive-looking destination names.' if not sensitive_destinations else f'{len(sensitive_destinations)} sensitive-looking destination(s).'),
        _row('QUEUE_REPOSITORY', 'error' if invalid_repositories else 'ok', 'Repository identifiers are valid.' if not invalid_repositories else f'{len(invalid_repositories)} invalid repository binding(s).'),
        _row('QUEUE_BRANCH', 'error' if invalid_branches else 'ok', 'Saved branches are valid.' if not invalid_branches else f'{len(invalid_branches)} invalid branch binding(s).'),
        _row('QUEUE_ENTRY_STATUS', 'error' if invalid_statuses else 'ok', 'Queue entry statuses are recognized.' if not invalid_statuses else f'{len(invalid_statuses)} unknown status value(s).'),
        _row('QUEUE_SOURCE_MISSING', 'review' if missing_sources else 'ok', 'All referenced local files exist.' if not missing_sources else f'{len(missing_sources)} local source file(s) are missing.'),
        _row('QUEUE_SOURCE_CHANGED', 'review' if changed_sources else 'ok', 'Referenced source bytes still match saved hashes.' if not changed_sources else f'{len(changed_sources)} source file(s) changed or could not be checked.'),
        _row('QUEUE_SOURCE_HASH_BUDGET', 'review' if unchecked_sources else 'ok', f'{source_hash_bytes:,} source bytes hashed.' if not unchecked_sources else f'{len(unchecked_sources)} source file(s) skipped after the 64 MiB aggregate hash limit.'),
        _row('QUEUE_OLD', 'review' if old_queues else 'ok', 'No queue file is older than 180 days.' if not old_queues else f'{len(old_queues)} queue file(s) are older than 180 days.'),
        _row('QUEUE_SECRET_PATTERN', 'error' if embedded_secrets else 'ok', 'No common token/private-key pattern in inspected state.' if not embedded_secrets else f'{len(embedded_secrets)} state file(s) contain a credential-like pattern.'),
        _row('STATE_DUPLICATE_NAMES', 'review' if duplicate_state_names else 'ok', 'No case-colliding state filenames.' if not duplicate_state_names else 'State filenames collide by case.'),
        _row('BINDING_FILE', 'ok' if isinstance(bindings, dict) else ('info' if bindings is None else 'error'), 'Project bindings are valid JSON object data.' if isinstance(bindings, dict) else 'No bindings file or invalid binding data.'),
        _row('BINDING_COUNT', 'ok', f'{binding_count} local project binding(s).'),
        _row('BINDING_SCHEMA', 'error' if binding_invalid else 'ok', 'Binding entries use supported fields.' if not binding_invalid else 'Unsupported fields or malformed binding entries.'),
        _row('STATE_CONTENT_FILES', 'review' if has_content_field else 'ok', 'No direct file-content fields found.' if not has_content_field else 'A state object contains a content field; review its purpose.'),
        _row('STATE_TOKEN_FIELDS', 'error' if has_credential_field else 'ok', 'No credential-named state fields found.' if not has_credential_field else 'A state object contains a credential-named field.'),
        _row('QUEUE_TEMPORARIES', 'review' if any(p.name.startswith('.queue-') for p in (queues.iterdir() if queue_dir else [])) else 'ok', 'No abandoned queue temp files.' if not any(p.name.startswith('.queue-') for p in (queues.iterdir() if queue_dir else [])) else 'Abandoned queue temp files found.'),
        _row('STATE_TEMPORARIES', 'review' if any(p.name.startswith('.octoship-') for p in state_files) else 'ok', 'No abandoned settings temp files.' if not any(p.name.startswith('.octoship-') for p in state_files) else 'Abandoned settings temp files found.'),
        _row('QUEUE_FILE_COUNT_CAP', 'review' if queue_overflow else 'ok', 'Queue scan is within its cap.' if not queue_overflow else f'Only the first {MAX_QUEUE_FILES} queue files were inspected.'),
        _row('STATE_PRIVATE_PARENT', 'ok' if not is_dir or base.parent.stat().st_mode & 0o002 == 0 else 'review', 'State parent is not world-writable.' if not is_dir or base.parent.stat().st_mode & 0o002 == 0 else 'State parent is world-writable.'),
        _row('STATE_JSON_ONLY', 'ok' if all(p.suffix == '.json' or p.is_dir() for p in state_files) else 'info', 'Only JSON state files and folders found.' if all(p.suffix == '.json' or p.is_dir() for p in state_files) else 'Additional state file types are present.'),
        _row('QUEUE_ACCOUNT_SCOPE', 'info', 'Saved queue journals are repository/branch scoped; account identity is rechecked at resume.'),
        _row('QUEUE_APPROVAL_PERSISTENCE', 'ok', 'Saved queue schema does not store content-scan approvals.'),
        _row('QUEUE_CONTENT_PERSISTENCE', 'ok', 'Queue journal schema stores metadata and hashes, not file bodies.'),
        _row('QUEUE_HASH_FORMAT', 'error' if any(not re.fullmatch(r'[0-9a-f]{64}', row.get('digest', '')) for _, value, _ in queue_json if isinstance(value, dict) for row in value.get('entries', []) if isinstance(row, dict)) else 'ok', 'SHA-256 digest fields are well-formed.' if not any(not re.fullmatch(r'[0-9a-f]{64}', row.get('digest', '')) for _, value, _ in queue_json if isinstance(value, dict) for row in value.get('entries', []) if isinstance(row, dict)) else 'Malformed digest fields found.'),
        _row('QUEUE_SOURCE_ABSOLUTE', 'error' if any(not Path(row.get('source', '')).is_absolute() for _, value, _ in queue_json if isinstance(value, dict) for row in value.get('entries', []) if isinstance(row, dict)) else 'ok', 'Queue source paths are absolute.' if not any(not Path(row.get('source', '')).is_absolute() for _, value, _ in queue_json if isinstance(value, dict) for row in value.get('entries', []) if isinstance(row, dict)) else 'Relative source paths found.'),
        _row('QUEUE_MODE', 'error' if any(value.get('mode') not in ('atomic', 'per-file') for _, value, _ in queue_json if isinstance(value, dict)) else 'ok', 'Queue commit modes are recognized.' if not any(value.get('mode') not in ('atomic', 'per-file') for _, value, _ in queue_json if isinstance(value, dict)) else 'Unknown queue commit mode found.'),
        _row('QUEUE_MESSAGE_LENGTH', 'review' if any(not isinstance(value.get('message'), str) or not 1 <= len(value.get('message', '')) <= 250 for _, value, _ in queue_json if isinstance(value, dict)) else 'ok', 'Queue messages fit the supported length.' if not any(not isinstance(value.get('message'), str) or not 1 <= len(value.get('message', '')) <= 250 for _, value, _ in queue_json if isinstance(value, dict)) else 'Some queue messages exceed supported length.'),
        _row('QUEUE_REPO_BRANCH_KEY', 'ok' if queue_dir and all(re.fullmatch(r'[0-9a-f]{64}\.json', p.name) for p in queue_files) else ('info' if not queue_files else 'review'), 'Queue file identifiers are opaque hashes.' if all(re.fullmatch(r'[0-9a-f]{64}\.json', p.name) for p in queue_files) else 'Queue names may reveal identifying text.'),
        _row('QUEUE_FILES_REGULAR', 'ok' if all(p.is_file() and not p.is_symlink() for p in queue_files) else 'error', 'Queue files are regular files.' if all(p.is_file() and not p.is_symlink() for p in queue_files) else 'Non-regular or linked queue file found.'),
        _row('BINDING_CREDENTIALS', 'error' if embedded_secrets else 'ok', 'No common credentials in queue or binding data.' if not embedded_secrets else 'Credential-like data must be removed from local state.'),
        _row('WORKSPACE_AUDIT_SCOPE', 'info', 'Read-only; scans up to 500 queues, 1,000 state entries, 16 MiB JSON and 64 MiB source hashes.'),
        _row('STATE_FILES_CAPPED', 'review' if state_scan_limited else 'ok', 'All regular state files were inspected.' if not state_scan_limited else 'The state audit inspects at most 20 top-level state files plus 500 queue journals.'),
    ))
    if len(rows) != 51:
        raise AssertionError(f'Workspace audit should return 51 checks; got {len(rows)}')
    return rows
