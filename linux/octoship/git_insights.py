"""Read-only local Git repository diagnostics for OctoShip.

No command in this module writes to the repository. Remote URLs are redacted in
reports so credentials embedded in old URLs are not displayed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import subprocess


@dataclass(frozen=True)
class Insight:
    key: str
    title: str
    status: str
    detail: str


class RepositoryError(ValueError):
    """The selected path is not a usable Git repository."""


def _git(root: Path, *args: str, timeout: int = 8) -> str:
    try:
        proc = subprocess.run(['git', '-C', str(root), '--no-optional-locks',
                               '-c', 'core.fsmonitor=false', '-c', 'core.untrackedCache=false', *args], check=False,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding='utf-8', errors='replace', timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RepositoryError(f'Git could not inspect this repository: {exc}') from exc
    if proc.returncode:
        raise RepositoryError(f'Git could not complete the local {args[0]} inspection (exit {proc.returncode}).')
    return proc.stdout.strip()


def _safe_remote(value: str) -> str:
    value = re.sub(r'(?i)(https?://)[^/@]+@', r'\1[credentials]@', value)
    value = re.sub(r'(?i)(https?://[^/?#]+/)[^?#]+', r'\1[repository]', value)
    value = re.sub(r'(?i)(ssh://)[^/@]+@', r'\1[user]@', value)
    return value


def _has_upstream(root: Path) -> bool:
    result = subprocess.run(['git', '-C', str(root), '--no-optional-locks', '-c',
                             'core.fsmonitor=false', '-c', 'core.untrackedCache=false',
                             'rev-parse', '--abbrev-ref',
                             '--symbolic-full-name', '@{upstream}'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            check=False, timeout=8)
    return result.returncode == 0


def _status_counts(status: str) -> tuple[int, int, int, int]:
    """Count paths from porcelain-v2 -z output without treating rename paths as entries.

    In NUL-delimited porcelain formats, rename and copy records contain a second
    NUL-delimited source pathname. That pathname is payload, not another status
    record. Porcelain v2 gives each record an explicit type marker, making it
    possible to skip that payload reliably even when filenames contain spaces.
    """
    staged = unstaged = untracked = conflicts = 0
    skip_source_path = False
    for record in status.split('\0'):
        if not record:
            continue
        if skip_source_path:
            skip_source_path = False
            continue
        if record.startswith(('1 ', '2 ', 'u ')):
            fields = record.split(' ', 2)
            xy = fields[1]
            staged += xy[0] != '.'
            unstaged += xy[1] != '.'
            conflicts += record.startswith('u ')
            skip_source_path = record.startswith('2 ')
        elif record.startswith('? '):
            untracked += 1
    return staged, unstaged, untracked, conflicts


def inspect_repository(path: str | Path) -> list[Insight]:
    """Return a stable 40-row local health report; never contacts a remote."""
    root = Path(path).expanduser().resolve()
    top = _git(root, 'rev-parse', '--show-toplevel')
    gitdir = Path(_git(root, 'rev-parse', '--git-dir'))
    if not gitdir.is_absolute():
        gitdir = (root / gitdir).resolve()
    branch = _git(root, 'branch', '--show-current') or '(detached HEAD)'
    try:
        status = subprocess.run(['git', '-C', str(root), '--no-optional-locks', '-c',
                                 'core.fsmonitor=false', '-c', 'core.untrackedCache=false',
                                 'status', '--porcelain=v2', '-z', '--untracked-files=all'],
                                check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=8).stdout.decode('utf-8', errors='replace')
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        raise RepositoryError('Git status inspection failed or exceeded its 8-second limit.') from None
    staged, unstaged, untracked, conflicts = _status_counts(status)
    upstream = _git(root, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}') if _has_upstream(root) else ''
    counts = _git(root, 'rev-list', '--left-right', '--count', 'HEAD...@{upstream}') if upstream else ''
    ahead, behind = (map(int, counts.split()) if counts else (0, 0))
    remotes = _git(root, 'remote', '-v').splitlines()
    remotes = list(dict.fromkeys(line.split('\t', 1)[1].rsplit(' (', 1)[0] for line in remotes if '\t' in line))
    tracked = _git(root, 'ls-files', '-z').split('\0')
    tracked = [name for name in tracked if name]
    ignored = _git(root, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z').split('\0')
    ignored = [name for name in ignored if name]
    commits = _git(root, 'rev-list', '--count', 'HEAD')
    head_date = _git(root, 'log', '-1', '--format=%cI')
    head_subject = _git(root, 'log', '-1', '--format=%s')
    head_sha = _git(root, 'rev-parse', '--short=12', 'HEAD')
    tags = _git(root, 'tag', '--list').splitlines()
    branches = _git(root, 'for-each-ref', '--format=%(refname:short)', 'refs/heads').splitlines()
    contributors = _git(root, 'shortlog', '-sne', 'HEAD').splitlines()
    config = _git(root, 'config', '--local', '--list').splitlines()
    config_keys = {line.split('=', 1)[0] for line in config if '=' in line}
    hooks_path = _git(root, 'config', '--local', '--get', 'core.hooksPath') if 'core.hookspath' in config_keys else ''
    default_branch = ''
    if 'origin' in _git(root, 'remote').splitlines():
        default_result = subprocess.run(['git', '-C', str(root), '--no-optional-locks', '-c',
                                         'core.fsmonitor=false', '-c', 'core.untrackedCache=false',
                                         'symbolic-ref', '--quiet',
                                         '--short', 'refs/remotes/origin/HEAD'],
                                        check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        text=True, encoding='utf-8', errors='replace', timeout=8)
        default_branch = default_result.stdout.strip() if default_result.returncode == 0 else ''
    shallow = (gitdir / 'shallow').is_file()
    size_bytes = 0
    object_store = gitdir / 'objects'
    if object_store.exists():
        for index, path in enumerate(object_store.rglob('*'), 1):
            if index > 50000:
                break
            try:
                if path.is_file(): size_bytes += path.stat().st_size
            except OSError:
                pass
    lfs = any(name.endswith('.gitattributes') for name in tracked) and any(
        'filter=lfs' in (Path(top) / name).read_text(encoding='utf-8', errors='replace')
        for name in tracked if name.endswith('.gitattributes') and (Path(top) / name).is_file())
    lock_files = [p.name for p in (gitdir).glob('*.lock')]
    has_readme = any(Path(name).name.lower().startswith('readme') for name in tracked)
    has_license = any(Path(name).name.lower().startswith(('license', 'licence', 'copying')) for name in tracked)
    has_ignore = any(Path(name).name == '.gitignore' for name in tracked)
    has_attributes = any(Path(name).name == '.gitattributes' for name in tracked)
    has_editorconfig = any(Path(name).name == '.editorconfig' for name in tracked)
    has_ci = any(name.startswith('.github/workflows/') for name in tracked)
    has_security = any(Path(name).name.upper() == 'SECURITY.MD' for name in tracked)
    has_contributing = any(Path(name).name.upper() == 'CONTRIBUTING.MD' for name in tracked)
    has_codeowners = any(Path(name).name.upper() == 'CODEOWNERS' for name in tracked)
    large = []
    for name in tracked:
        try:
            size = (Path(top) / name).stat().st_size
            if size >= 50 * 1024 * 1024:
                large.append((name, size))
        except OSError:
            pass
    sensitive = [name for name in tracked if Path(name).name.lower() in {'.env', 'id_rsa', 'id_ed25519', 'credentials.json', 'secrets.json'} or name.lower().endswith(('.pem', '.key'))]
    report = [
        Insight('repository', 'Repository root', 'info', top),
        Insight('branch', 'Current branch', 'info', branch),
        Insight('head', 'HEAD commit', 'info', f'{head_sha} · {head_subject}'),
        Insight('head_date', 'Last commit date', 'info', head_date or 'No commits yet'),
        Insight('commit_count', 'Reachable commit count', 'info', commits),
        Insight('branch_count', 'Local branch count', 'info', str(len(branches))),
        Insight('tag_count', 'Tag count', 'info', str(len(tags))),
        Insight('contributor_count', 'Contributor count', 'info', str(len(contributors))),
        Insight('tracked_count', 'Tracked file count', 'info', str(len(tracked))),
        Insight('remote_count', 'Configured remote count', 'info', str(len(remotes))),
        Insight('remotes', 'Remote endpoints', 'info', ', '.join(_safe_remote(r) for r in remotes) or 'None configured'),
        Insight('upstream', 'Current branch upstream', 'info' if upstream else 'review', upstream or 'No upstream configured'),
        Insight('ahead', 'Commits ahead of upstream', 'review' if ahead else 'ok', str(ahead)),
        Insight('behind', 'Commits behind upstream', 'review' if behind else 'ok', str(behind)),
        Insight('staged', 'Staged paths', 'review' if staged else 'ok', str(staged)),
        Insight('unstaged', 'Unstaged paths', 'review' if unstaged else 'ok', str(unstaged)),
        Insight('untracked', 'Untracked paths', 'review' if untracked else 'ok', str(untracked)),
        Insight('conflicts', 'Unmerged paths', 'error' if conflicts else 'ok', str(conflicts)),
        Insight('shallow', 'Shallow clone', 'review' if shallow else 'ok', 'Yes' if shallow else 'No'),
        Insight('object_store', 'Git object store size', 'info', f'{size_bytes:,} bytes'),
        Insight('default_branch', 'Origin default branch', 'info' if default_branch else 'review', default_branch or 'Not advertised locally'),
        Insight('hooks_path', 'Custom hooks path', 'review' if hooks_path else 'info', hooks_path or 'Git default'),
        Insight('lock_files', 'Stale Git lock files', 'error' if lock_files else 'ok', ', '.join(lock_files) or 'None'),
        Insight('large_files', 'Tracked files at least 50 MiB', 'review' if large else 'ok', ', '.join(f'{n} ({s:,} bytes)' for n, s in large) or 'None'),
        Insight('sensitive_names', 'Sensitive-looking tracked filenames', 'error' if sensitive else 'ok', ', '.join(sensitive) or 'None'),
        Insight('readme', 'README present', 'ok' if has_readme else 'review', 'Yes' if has_readme else 'No'),
        Insight('license', 'License file present', 'ok' if has_license else 'review', 'Yes' if has_license else 'No'),
        Insight('gitignore', 'Git ignore rules present', 'ok' if has_ignore else 'review', 'Yes' if has_ignore else 'No'),
        Insight('gitattributes', 'Git attributes present', 'info', 'Yes' if has_attributes else 'No'),
        Insight('lfs', 'Git LFS filters configured', 'info', 'Yes' if lfs else 'No'),
        Insight('editorconfig', 'EditorConfig present', 'info', 'Yes' if has_editorconfig else 'No'),
        Insight('ci', 'GitHub Actions workflows present', 'info', 'Yes' if has_ci else 'No'),
        Insight('security_policy', 'Security policy present', 'info', 'Yes' if has_security else 'No'),
        Insight('contributing', 'Contribution guide present', 'info', 'Yes' if has_contributing else 'No'),
        Insight('codeowners', 'CODEOWNERS present', 'info', 'Yes' if has_codeowners else 'No'),
        Insight('author_config', 'Local Git author configured', 'ok' if 'user.name' in config_keys and 'user.email' in config_keys else 'review', 'Yes' if 'user.name' in config_keys and 'user.email' in config_keys else 'Incomplete'),
        Insight('credential_helper', 'Credential helper configured', 'info', 'Yes' if 'credential.helper' in config_keys else 'No'),
        Insight('signing', 'Commit signing configured', 'info', 'Yes' if any(k.endswith('.sign') and v == 'true' for line in config if '=' in line for k, v in [line.split('=', 1)]) else 'No'),
        Insight('ignored_count', 'Ignored untracked path count', 'info', str(len(ignored))),
        Insight('clean', 'Working tree clean', 'ok' if not any((staged, unstaged, untracked, conflicts)) else 'review',
                'Yes' if not any((staged, unstaged, untracked, conflicts)) else 'No'),
    ]
    assert len(report) == 40
    return report


def report_json(path: str | Path) -> str:
    """Serialize diagnostics for scripts; content is local and credential-redacted."""
    import json
    return json.dumps([asdict(row) for row in inspect_repository(path)], ensure_ascii=False, indent=2)
