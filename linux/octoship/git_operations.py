"""Safe local Git change-management actions.

Inspection actions are fixed, read-only Git commands. They never invoke a
shell, hooks, credential helpers, pagers, or remotes. Mutations are separate
functions and require an affirmative confirmation argument.
"""
from dataclasses import dataclass
from pathlib import Path
import os
import re
import subprocess


class GitOperationError(ValueError):
    pass


@dataclass(frozen=True)
class Action:
    key: str
    title: str
    args: tuple[str, ...]


def _build_actions():
    """Build 100 separately selectable views over local repository state."""
    rows = []
    def add(group, variants):
        rows.extend(Action(key, title, tuple(args)) for key, title, args in variants)
    add('status', [
        ('status_short', 'Working tree: short status', ('status','--short','--branch')),
        ('status_porcelain', 'Working tree: machine status', ('status','--porcelain=v2','--branch')),
        ('status_all', 'Working tree: include untracked files', ('status','--short','--untracked-files=all')),
        ('status_ignored', 'Working tree: include ignored files', ('status','--short','--ignored')),
        ('status_staged', 'Staged change summary by directory', ('diff','--cached','--dirstat=files,10')),
        ('status_unstaged', 'Unstaged change summary', ('diff','--numstat')),
        ('status_staged_names', 'Staged path distribution', ('diff','--cached','--dirstat=files,10,cumulative')),
        ('status_unstaged_names', 'Unstaged path distribution', ('diff','--dirstat=files,10')),
        ('status_conflicts', 'Unmerged paths', ('ls-files','--unmerged')),
        ('status_submodules', 'Submodule status', ('submodule','status','--')),
    ])
    add('branches', [
        ('branches_local', 'Local branches', ('branch','--list','--format=%(HEAD) %(refname:short)')),
        ('branches_verbose', 'Local branches with commit summaries', ('branch','--verbose','--no-abbrev')),
        ('branches_upstream', 'Branch upstream mapping', ('branch','--verbose','--verbose')),
        ('branches_merged_head', 'Branches merged into current HEAD', ('branch','--merged','HEAD')),
        ('branches_unmerged_head', 'Branches not merged into current HEAD', ('branch','--no-merged','HEAD')),
        ('branches_contains_head', 'Branches containing current HEAD', ('branch','--contains','HEAD')),
        ('branches_contains_tag', 'Branches containing the newest tag', ('for-each-ref','--sort=-creatordate','--count=1','--format=%(refname:short)','refs/tags')),
        ('branches_remote', 'Remote tracking branches', ('branch','--remotes','--verbose')),
        ('branches_current', 'Current branch name', ('branch','--show-current')),
        ('branches_heads', 'Branch tip commit IDs', ('for-each-ref','--format=%(refname:short) %(objectname:short) %(subject)','refs/heads')),
    ])
    add('history', [
        ('history_recent', 'Recent commits', ('log','-n','20','--date=short','--format=%h %ad %s')),
        ('history_all', 'Recent commits across all branches', ('log','--all','-n','30','--date=short','--format=%h %ad %d %s')),
        ('history_graph', 'Commit graph', ('log','--all','--graph','--decorate','-n','40','--oneline')),
        ('history_authors', 'Commit author summary', ('shortlog','-sne','--all')),
        ('history_files', 'Recent commit file lists', ('log','-n','15','--name-status','--format=commit %h %s')),
        ('history_stats', 'Recent commit size summaries', ('log','-n','15','--stat','--format=commit %h %s')),
        ('history_reflog', 'Recent local reference movements', ('reflog','-n','30','--date=short','--format=%h %gd %gs')),
        ('history_head', 'Current commit details', ('show','--no-ext-diff','--stat','--format=fuller','HEAD')),
        ('history_count', 'Reachable commit count', ('rev-list','--count','HEAD')),
    ])
    add('diff', [
        ('diff_worktree', 'Working tree patch', ('diff','--no-ext-diff','--no-color')),
        ('diff_stat', 'Working tree change statistics', ('diff','--stat')),
        ('diff_staged_stat', 'Staged change statistics', ('diff','--cached','--stat')),
        ('diff_names', 'Changed path names', ('diff','--name-only')),
        ('diff_staged_names', 'Staged path names', ('diff','--cached','--name-only')),
        ('diff_status', 'Working tree path status', ('diff','--name-status')),
        ('diff_staged_status', 'Staged path status', ('diff','--cached','--name-status')),
        ('diff_check', 'Whitespace and conflict marker check', ('diff','--check')),
        ('diff_staged_check', 'Staged whitespace check', ('diff','--cached','--check')),
        ('diff_summary', 'Change summary by status', ('diff','--shortstat')),
        ('diff_staged_summary', 'Staged summary by status', ('diff','--cached','--shortstat')),
    ])
    add('tags', [
        ('tags_all', 'Tags', ('tag','--list','--sort=version:refname')),
        ('tags_recent', 'Most recently created tags', ('for-each-ref','--sort=-creatordate','--count=30','--format=%(refname:short) %(creatordate:short) %(subject)','refs/tags')),
        ('tags_points', 'Tag target commit IDs', ('for-each-ref','--format=%(refname:short) %(objectname:short) %(objecttype)','refs/tags')),
        ('tags_annotated', 'Annotated tag objects', ('for-each-ref','--format=%(refname:short) %(taggername) %(taggerdate:short) %(subject)','refs/tags')),
        ('tags_contains', 'Tags containing current commit', ('tag','--contains','HEAD')),
        ('tags_merged', 'Tags reachable from current branch', ('tag','--merged','HEAD')),
        ('tags_unmerged', 'Tags not reachable from current branch', ('tag','--no-merged','HEAD')),
        ('tags_count', 'Tag count', ('for-each-ref','--count=100000','--format=%(refname)','refs/tags')),
        ('tags_head', 'Tags pointing at current commit', ('tag','--points-at','HEAD')),
        ('tags_peel', 'Tag commit targets', ('for-each-ref','--format=%(refname:short) %(objectname) %(objectname^{commit})','refs/tags')),
    ])
    add('remotes', [
        ('remotes_names', 'Configured remote names', ('remote',)),
        ('remotes_branches', 'Remote tracking refs', ('for-each-ref','--format=%(refname:short) %(objectname:short)','refs/remotes')),
        ('remotes_tracking', 'Remote tracking configuration', ('config','--local','--get-regexp',r'^branch\..*\.(remote|merge)$')),
        ('remotes_fetch_config', 'Remote fetch configuration (URLs redacted)', ('remote','-v')),
        ('remotes_default', 'Advertised origin default branch', ('symbolic-ref','--quiet','--short','refs/remotes/origin/HEAD')),
        ('remotes_compare', 'Ahead/behind summary vs upstream', ('rev-list','--left-right','--count','HEAD...@{upstream}')),
        ('remotes_log_upstream', 'Recent upstream-only commit subjects', ('log','--oneline','--decorate','-n','30','@{upstream}..HEAD')),
        ('remotes_log_incoming', 'Recent commits absent from HEAD', ('log','--oneline','--decorate','-n','30','HEAD..@{upstream}')),
        ('remotes_common', 'Merge base with upstream', ('merge-base','HEAD','@{upstream}')),
        ('remotes_divergence', 'Symmetric difference commit list', ('log','--left-right','--oneline','-n','50','HEAD...@{upstream}')),
    ])
    add('stash', [
        ('stash_list', 'Stash entries', ('stash','list','--date=local')),
        ('stash_count', 'Stash entry count', ('stash','list','--format=%gd')),
        ('stash_latest', 'Latest stash summary', ('stash','show','--stat','stash@{0}')),
        ('stash_latest_patch', 'Latest stash patch', ('stash','show','--patch','--no-ext-diff','stash@{0}')),
        ('stash_paths', 'Latest stash changed paths', ('stash','show','--name-status','stash@{0}')),
        ('stash_all', 'All stash summaries', ('stash','show','--stat','--no-walk','refs/stash')),
        ('stash_reflog', 'Stash reference history', ('reflog','show','refs/stash')),
        ('stash_untracked', 'Latest stash including untracked paths', ('stash','show','--include-untracked','--stat','stash@{0}')),
        ('stash_base', 'Latest stash base commit', ('rev-parse','stash@{0}^1')),
        ('stash_worktree', 'Latest stash worktree commit', ('rev-parse','stash@{0}^2')),
    ])
    add('worktrees', [
        ('worktrees_list', 'Linked working trees', ('worktree','list','--porcelain')),
        ('worktrees_branches', 'Branches checked out in worktrees', ('for-each-ref','--format=%(refname:short) %(worktreepath)','refs/heads')),
        ('worktrees_config', 'Worktree-specific configuration mode', ('config','--local','--get','extensions.worktreeConfig')),
        ('worktrees_paths', 'Current worktree root', ('rev-parse','--show-toplevel')),
        ('worktrees_gitdir', 'Current worktree Git directory', ('rev-parse','--absolute-git-dir')),
        ('worktrees_common', 'Shared Git directory', ('rev-parse','--path-format=absolute','--git-common-dir')),
        ('worktrees_prefix', 'Path from current worktree root', ('rev-parse','--show-prefix')),
        ('worktrees_is_repo', 'Confirm repository worktree context', ('rev-parse','--is-inside-work-tree')),
        ('worktrees_shallow', 'Shallow clone state', ('rev-parse','--is-shallow-repository')),
        ('worktrees_sparse', 'Sparse checkout state', ('sparse-checkout','list')),
    ])
    add('files', [
        ('files_tracked', 'Tracked files', ('ls-files','--cached')),
        ('files_untracked', 'Untracked nonignored files', ('ls-files','--others','--exclude-standard')),
        ('files_ignored', 'Ignored untracked files', ('ls-files','--others','--ignored','--exclude-standard')),
        ('files_deleted', 'Deleted tracked files', ('ls-files','--deleted')),
        ('files_modified', 'Modified tracked files', ('ls-files','--modified')),
        ('files_staged', 'Staged files with raw object changes', ('diff','--cached','--raw')),
        ('files_conflicted', 'Conflicted files', ('diff','--name-only','--diff-filter=U')),
        ('files_executable', 'Tracked file line-ending metadata', ('ls-files','--eol')),
        ('files_submodules', 'Submodule entries', ('ls-files','--stage','--','*.gitmodules')),
        ('files_index', 'Index entries with debug metadata', ('ls-files','--debug')),
    ])
    add('review', [
        ('review_merge_base', 'Merge base with main (if present)', ('merge-base','HEAD','main')),
        ('review_cherry', 'Commits unique to HEAD vs main', ('cherry','-v','main','HEAD')),
        ('review_patch_ids', 'Patch IDs for recent commits', ('log','-n','30','--pretty=format:%H','--patch')),
        ('review_blame_head', 'Blame README lines', ('blame','--','README.md')),
        ('review_grep_todo', 'Tracked TODO markers', ('grep','-n','-I','TODO','--','.:!*.lock')),
        ('review_grep_fixme', 'Tracked FIXME markers', ('grep','-n','-I','FIXME','--','.:!*.lock')),
        ('review_grep_conflict', 'Tracked merge-conflict markers', ('grep','-n','-I','<<<<<<<','--','.:!*.lock')),
        ('review_check_attr', 'Attributes for tracked paths', ('check-attr','--all','--','README.md')),
        ('review_check_ignore', 'Why README is not ignored', ('check-ignore','-v','README.md')),
        ('review_check_ref', 'Validate current HEAD object', ('cat-file','-t','HEAD')),
    ])
    if len(rows) != 100 or len({row.key for row in rows}) != 100:
        raise RuntimeError(f'Git action catalog must contain exactly 100 unique actions (got {len(rows)}).')
    return tuple(rows)


ACTIONS = _build_actions()
ACTION_BY_KEY = {action.key: action for action in ACTIONS}
MAX_OUTPUT = 512 * 1024


def _root(path):
    root = Path(path).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise GitOperationError('Choose a local Git repository folder.')
    return root


def run_action(path, key):
    """Run one catalogued inspection action, without shell/network/hooks."""
    action = ACTION_BY_KEY.get(key)
    if action is None:
        raise GitOperationError('Choose a supported Git inspection action.')
    root = _root(path)
    args = list(action.args)
    if args[0] in ('diff', 'show'):
        args[1:1] = ['--no-ext-diff', '--no-textconv']
    elif args[0] == 'log' and '--patch' in args:
        args[1:1] = ['--no-ext-diff', '--no-textconv']
    try:
        proc = subprocess.run(
            ['git', '-C', str(root), '--no-optional-locks', '--no-pager', '-c', 'core.fsmonitor=false',
             '-c', 'core.untrackedCache=false', '-c', 'diff.external=',
             '-c', 'core.pager=cat', *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=12, check=False,
            text=False, env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_OPTIONAL_LOCKS': '0'},
        )
    except (OSError, subprocess.TimeoutExpired):
        raise GitOperationError('Git inspection was unavailable or exceeded its 12-second limit.') from None
    if proc.returncode:
        error = proc.stderr.decode('utf-8', 'replace')[:1000]
        raise GitOperationError('Git inspection failed: ' + (error.strip() or 'the requested local data is unavailable.'))
    output = proc.stdout[:MAX_OUTPUT].decode('utf-8', 'replace')
    if len(proc.stdout) > MAX_OUTPUT:
        output += '\n[Output truncated at 512 KiB.]'
    # Remotes and local config may contain embedded userinfo or access tokens.
    output = re.sub(r'(?i)(https?://)[^/@\s]+@', r'\1[credentials]@', output)
    output = re.sub(r'(?i)\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b', '[credential]', output)
    return output or '(No matching local data.)'


def _git(root, *args):
    try:
        proc = subprocess.run(['git','-C',str(root),'--no-pager',*args], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=12, check=False, text=True)
    except (OSError, subprocess.TimeoutExpired):
        raise GitOperationError('Git operation unavailable or timed out.') from None
    if proc.returncode:
        raise GitOperationError(proc.stderr.strip()[:1000] or 'Git operation failed.')
    return proc.stdout.strip()


def _branch_name(name):
    if not isinstance(name, str) or not name or name.startswith('-') or len(name) > 240:
        raise GitOperationError('Enter a valid local branch name.')
    if any(part in ('', '.', '..') for part in name.split('/')) or '..' in name or '@{' in name:
        raise GitOperationError('Enter a valid local branch name.')
    return name


def create_branch(path, name, start='HEAD'):
    root = _root(path); _branch_name(name)
    if not isinstance(start, str) or not start or start.startswith('-') or any(ord(ch) < 32 for ch in start):
        raise GitOperationError('Choose a valid commit or ref as the branch start point.')
    try:
        subprocess.run(['git','-C',str(root),'show-ref','--verify','--quiet','refs/heads/'+name],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
    except subprocess.CalledProcessError:
        pass
    else:
        raise GitOperationError('That local branch already exists.')
    resolved = _git(root, 'rev-parse', '--verify', start + '^{commit}')
    _git(root, 'branch', '--no-track', name, resolved)
    return f'Created local branch {name} at {resolved[:12]}. No remote was contacted.'


def switch_branch(path, name, confirmed=False):
    """Switch to an existing local branch only from a clean worktree.

    Checkout hooks are disabled. Git may still run a configured smudge/process
    filter for the target tree, so callers must disclose that before confirming.
    """
    root = _root(path)
    _branch_name(name)
    if confirmed is not True:
        raise GitOperationError('Confirm switching the local branch explicitly.')
    _git(root, 'check-ref-format', '--branch', name)
    current = _git(root, 'branch', '--show-current')
    if current == name:
        raise GitOperationError('That branch is already checked out.')
    if _git(root, 'status', '--porcelain=v1', '--untracked-files=all'):
        raise GitOperationError('Switching is blocked while tracked or untracked changes exist. Commit or stash them first.')
    try:
        _git(root, 'show-ref', '--verify', '--quiet', f'refs/heads/{name}')
    except GitOperationError:
        raise GitOperationError('That local branch does not exist. Remote branches are not fetched or switched.') from None

    env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_CONFIG_NOSYSTEM': '1'}
    try:
        proc = subprocess.run(
            ['git', '-C', str(root), '-c', 'core.hooksPath=/dev/null', 'switch', '--no-guess', name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=False, text=True, env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise GitOperationError('Git could not switch branches within the 15-second limit.') from None
    if proc.returncode:
        detail = proc.stderr.strip()[:700]
        raise GitOperationError('Git could not switch to that branch.' + (f' {detail}' if detail else ''))
    return f'Switched to local branch {name}. No remote was contacted; post-checkout hooks were disabled.'


def delete_branch(path, name, confirmed=False):
    root = _root(path); _branch_name(name)
    if confirmed is not True:
        raise GitOperationError('Confirm the local branch deletion explicitly.')
    current = _git(root, 'branch', '--show-current')
    if current == name:
        raise GitOperationError('Switch away from the current branch before deleting it.')
    _git(root, 'branch', '--delete', name)
    return f'Deleted merged local branch {name}. Remote branches are unchanged.'


def stash_save(path, message, confirmed=False, include_untracked=False):
    root = _root(path)
    if confirmed is not True:
        raise GitOperationError('Confirm saving the working tree to a local stash.')
    if not isinstance(message, str) or not message.strip() or len(message) > 120:
        raise GitOperationError('Enter a stash message of 1–120 characters.')
    args = ['stash','push','-m',message.strip()]
    if include_untracked is True: args.append('--include-untracked')
    elif include_untracked is not False: raise GitOperationError('Invalid untracked-file choice.')
    result = _git(root, *args)
    return result or 'No local changes were available to stash.'
