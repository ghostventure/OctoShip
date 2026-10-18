"""Local editor and workspace controls with atomic, reviewable settings writes.

All operations are local unless the user explicitly invokes an editor CLI action.
No command is run through a shell and profile/config writes stay inside the chosen
editor's user-data directory.
"""
from __future__ import annotations

from dataclasses import dataclass
import difflib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import re
import time

from .core import OctoShipError


EDITORS = {
    'code': ('Visual Studio Code', ('code',)),
    'code-insiders': ('VS Code Insiders', ('code-insiders',)),
    'codium': ('VSCodium', ('codium',)),
    'cursor': ('Cursor', ('cursor',)),
    'windsurf': ('Windsurf', ('windsurf',)),
    'zed': ('Zed', ('zeditor', 'zed')),
    'subl': ('Sublime Text', ('subl',)),
}


def installed_editors(which=shutil.which):
    """Return installed editor command records without launching anything."""
    found = []
    for key, (label, candidates) in EDITORS.items():
        command = None
        for candidate in candidates:
            command = which(candidate)
            if command: break
        if command:
            found.append({'id': key, 'name': label, 'command': command})
    return found


EDITOR_COMMAND_FEATURES = (
    'open', 'new-window', 'reuse-window', 'add-folder', 'diff', 'merge', 'wait',
    'goto', 'skip-recent', 'profile-list', 'profile-create', 'profile-open',
    'extensions-list', 'extensions-list-versions', 'extensions-update',
    'install-extension', 'uninstall-extension', 'show-extension', 'disable-extensions',
    'open-user-settings', 'open-keybindings', 'open-extensions', 'show-versions',
    'show-help', 'status', 'disable-gpu', 'log-startup', 'new-instance',
    'extensions-dir', 'locale', 'open-profile-editor', 'open-trust-editor',
)


SHELL_PROFILES = (
    ('bash', 'Bash', ('bash',), ('--login',)),
    ('zsh', 'Zsh', ('zsh',), ('-l',)),
    ('fish', 'Fish', ('fish',), ('-l',)),
    ('nu', 'Nushell', ('nu',), ()),
    ('pwsh', 'PowerShell', ('pwsh',), ()),
    ('xonsh', 'Xonsh', ('xonsh',), ()),
    ('elvish', 'Elvish', ('elvish',), ()),
    ('tcsh', 'TENEX C Shell', ('tcsh',), ('-l',)),
    ('ksh', 'KornShell', ('ksh', 'mksh'), ('-l',)),
    ('dash', 'Dash', ('dash',), ()),
)


def available_terminal_profiles(which=shutil.which):
    found = []
    for key, label, candidates, args in SHELL_PROFILES:
        executable = next((path for name in candidates if (path := which(name))), None)
        if executable:
            found.append({'id': key, 'name': label, 'path': executable, 'args': list(args)})
    return found


def add_terminal_profile(settings, profile, make_default=False):
    """Add one discovered shell to the editor's Linux terminal profile settings."""
    if not isinstance(settings, dict): raise OctoShipError('Settings must be a JSON object.')
    if not isinstance(profile, dict) or profile.get('id') not in {item[0] for item in SHELL_PROFILES}:
        raise OctoShipError('Choose a supported terminal profile.')
    path = Path(str(profile.get('path', '')))
    try: path = path.resolve(strict=True)
    except (OSError, RuntimeError): raise OctoShipError('Terminal profile must point to an existing executable file.') from None
    if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
        raise OctoShipError('Terminal profile must point to an existing executable file.')
    expected = next(row for row in SHELL_PROFILES if row[0] == profile['id'])
    if Path(profile['path']).name not in expected[2]:
        raise OctoShipError('Terminal executable does not match the selected shell type.')
    args = profile.get('args', list(expected[3]))
    if args != list(expected[3]): raise OctoShipError('Terminal profile arguments must match the safe defaults for this shell.')
    profiles = settings.setdefault('terminal.integrated.profiles.linux', {})
    if not isinstance(profiles, dict): raise OctoShipError('Existing terminal profiles setting must be a JSON object.')
    profiles[expected[1]] = {'path': str(path), 'args': list(args)}
    if make_default: settings['terminal.integrated.defaultProfile.linux'] = expected[1]
    return settings


def remove_terminal_profile(settings, name, clear_default=True):
    profiles = settings.get('terminal.integrated.profiles.linux', {})
    if not isinstance(profiles, dict): raise OctoShipError('Existing terminal profiles setting must be a JSON object.')
    if name not in profiles: raise OctoShipError('That terminal profile is not configured.')
    profiles.pop(name)
    if clear_default and settings.get('terminal.integrated.defaultProfile.linux') == name:
        settings.pop('terminal.integrated.defaultProfile.linux', None)
    return settings


def set_default_terminal_profile(settings, name):
    profiles = settings.get('terminal.integrated.profiles.linux', {})
    if not isinstance(profiles, dict) or name not in profiles:
        raise OctoShipError('Add the terminal profile before setting it as default.')
    settings['terminal.integrated.defaultProfile.linux'] = name
    return settings


def preview_terminal_profile(settings, profile, make_default=False):
    proposed = json.loads(json.dumps(settings))
    add_terminal_profile(proposed, profile, make_default)
    return settings_diff(settings, proposed)


def user_data_dir(editor='code', env=None):
    """Resolve conventional Linux user data location for supported editors."""
    env = os.environ if env is None else env
    home = Path(env.get('HOME', str(Path.home())))
    xdg = Path(env.get('XDG_CONFIG_HOME', str(home / '.config')))
    locations = {
        'code': xdg / 'Code/User', 'code-insiders': xdg / 'Code - Insiders/User',
        'codium': xdg / 'VSCodium/User', 'cursor': xdg / 'Cursor/User',
        'windsurf': xdg / 'Windsurf/User', 'zed': xdg / 'zed',
        'subl': home / '.config/sublime-text/Packages/User',
    }
    if editor not in locations:
        raise OctoShipError('Choose a supported editor.')
    return locations[editor]


def _regular_file(path, *, must_exist=False):
    path = Path(path).expanduser()
    if must_exist and (not path.exists() or path.is_symlink() or not path.is_file()):
        raise OctoShipError('Choose an existing regular file.')
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise OctoShipError('Settings path must be a regular file, not a link or directory.')
    return path


def read_settings(editor='code', env=None):
    path = user_data_dir(editor, env) / 'settings.json'
    if path.is_symlink(): raise OctoShipError('Editor settings path cannot be a symbolic link.')
    if not path.exists():
        return path, {}
    path = _regular_file(path, must_exist=True)
    if path.stat().st_size > 2 * 1024 * 1024:
        raise OctoShipError('Editor settings exceed the 2 MiB safety limit.')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError):
        raise OctoShipError('Editor settings are unreadable or invalid JSON; no changes were made.') from None
    if not isinstance(value, dict):
        raise OctoShipError('Editor settings must contain a JSON object.')
    return path, value


def write_settings(editor, settings, env=None):
    if not isinstance(settings, dict):
        raise OctoShipError('Settings must be a JSON object.')
    path = user_data_dir(editor, env) / 'settings.json'
    if path.exists():
        _regular_file(path, must_exist=True)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.octoship-settings-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(settings, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return path


def settings_diff(before, after):
    """Return a readable, secret-conscious structural JSON diff."""
    left = json.dumps(before, indent=2, sort_keys=True).splitlines()
    right = json.dumps(after, indent=2, sort_keys=True).splitlines()
    return ''.join(difflib.unified_diff(left, right, fromfile='current', tofile='proposed', lineterm='\n'))


def backup_settings(editor='code', backup_dir=None, env=None):
    source, settings = read_settings(editor, env)
    if not source.exists():
        raise OctoShipError('This editor has no settings file to back up yet.')
    root = Path(backup_dir).expanduser() if backup_dir else source.parent / 'octoship-backups'
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = root / 'settings.json'
    if target.exists() or target.is_symlink():
        raise OctoShipError('A settings backup already exists at that path; choose another folder.')
    payload = json.dumps(settings, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    fd, tmp = tempfile.mkstemp(prefix='.octoship-backup-', dir=root)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return target


def restore_settings(editor, backup, env=None):
    backup = _regular_file(backup, must_exist=True)
    try:
        value = json.loads(backup.read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError):
        raise OctoShipError('Backup is not valid JSON; current settings were left unchanged.') from None
    if not isinstance(value, dict):
        raise OctoShipError('Backup must contain a JSON object; current settings were left unchanged.')
    return write_settings(editor, value, env)


def editor_command(editor, action, paths=(), extension=None, extra=()):
    """Build safe argv for explicit editor actions; never invokes a shell."""
    if editor not in EDITORS:
        raise OctoShipError('Choose a supported editor.')
    if editor in ('zed', 'subl') and action != 'open':
        raise OctoShipError(f'{EDITORS[editor][0]} currently supports folder/file opening in OctoShip; use its own command palette for other controls.')
    executable = next((shutil.which(c) for c in EDITORS[editor][1] if shutil.which(c)), None)
    if not executable:
        raise OctoShipError(f'{EDITORS[editor][0]} command was not found on PATH.')
    args = [executable]
    path_args = []
    for raw in paths:
        try: target = Path(raw).expanduser().resolve(strict=True)
        except (OSError, RuntimeError): raise OctoShipError('Editor targets must be existing files or folders.') from None
        if not (target.is_file() or target.is_dir()):
            raise OctoShipError('Editor targets must be existing files or folders.')
        path_args.append(str(target))
    if action not in EDITOR_COMMAND_FEATURES:
        raise OctoShipError('Unsupported editor action.')
    supported = {
        'open': [], 'new-window': ['--new-window'], 'reuse-window': ['--reuse-window'],
        'add-folder': ['--add'], 'diff': ['--diff'], 'merge': ['--merge'], 'wait': ['--wait'],
        'goto': ['--goto'], 'skip-recent': ['--skip-add-to-recently-opened'],
        'profile-list': ['--list-profiles'], 'profile-create': ['--profile-temp'],
        'profile-open': [], 'extensions-list': ['--list-extensions'],
        'extensions-list-versions': ['--list-extensions', '--show-versions'],
        'extensions-update': ['--update-extensions'], 'install-extension': ['--install-extension'],
        'uninstall-extension': ['--uninstall-extension'], 'show-extension': ['--open-url'],
        'disable-extensions': ['--disable-extensions'], 'open-user-settings': ['--open-url'],
        'open-keybindings': ['--open-url'], 'open-extensions': ['--open-url'],
        'show-versions': ['--version'], 'show-help': ['--help'], 'status': ['--status'],
        'disable-gpu': ['--disable-gpu'], 'log-startup': ['--prof-startup'],
        'new-instance': ['--user-data-dir'], 'extensions-dir': ['--extensions-dir'],
        'locale': ['--locale'], 'open-profile-editor': ['--open-url'], 'open-trust-editor': ['--open-url'],
    }
    args.extend(supported[action])
    if action in ('new-instance', 'extensions-dir'):
        if len(path_args) != 1 or not Path(path_args[0]).is_dir():
            raise OctoShipError('Choose one existing folder for this editor action.')
        args.append(path_args.pop(0))
    expected_files = {'diff': 2, 'merge': 4}
    if action in expected_files and len(path_args) != expected_files[action]:
        raise OctoShipError(f'{action} needs exactly {expected_files[action]} existing file paths.')
    if action in ('diff', 'merge') and any(not Path(p).is_file() for p in path_args):
        raise OctoShipError('Diff accepts files only.')
    if action == 'add-folder' and len(path_args) != 1:
        raise OctoShipError('Add-folder needs exactly one existing folder.')
    if action in ('open', 'new-window', 'reuse-window', 'wait', 'disable-gpu', 'log-startup', 'disable-extensions', 'skip-recent'):
        args.extend(path_args)
    if action == 'profile-create':
        if not path_args: raise OctoShipError('Choose a workspace folder or file to open with a temporary profile.')
        args.extend(path_args)
    if action == 'profile-open':
        if len(extra) != 1 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _.-]{0,47}', str(extra[0])):
            raise OctoShipError('Enter a profile name for this editor action.')
        if not path_args: raise OctoShipError('Choose a workspace folder or file to open with this profile.')
        args.extend(['--profile', str(extra[0]).strip(), *path_args])
    if action == 'locale':
        if len(extra) != 1 or not re.fullmatch(r'[a-z]{2,3}(?:-[A-Z]{2})?', str(extra[0])):
            raise OctoShipError('Enter a locale such as en or en-US.')
        args.append(str(extra[0]))
    if action == 'goto':
        if len(path_args) != 1 or not Path(path_args[0]).is_file():
            raise OctoShipError('Go-to-line needs exactly one existing file.')
        if len(extra) != 1 or not re.fullmatch(r'[1-9][0-9]{0,7}(?::[1-9][0-9]{0,7})?', str(extra[0])):
            raise OctoShipError('Enter a line or line:column location.')
        args.append(path_args[0] + ':' + str(extra[0]))
    if action in ('extensions-list', 'extensions-list-versions') and extra:
        if len(extra) != 2 or extra[0] != '--profile' or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _.-]{0,47}', str(extra[1])):
            raise OctoShipError('Editor extension profile name is invalid.')
        args.extend(extra)
    if action in ('open-user-settings', 'open-keybindings', 'open-extensions', 'open-profile-editor', 'open-trust-editor', 'show-extension'):
        if action == 'open-user-settings': target_url = 'vscode://settings'
        elif action == 'open-keybindings': target_url = 'vscode://keybindings'
        elif action == 'open-extensions': target_url = 'vscode:extensions'
        elif action == 'open-profile-editor': target_url = 'vscode://settings/profiles'
        elif action == 'open-trust-editor': target_url = 'vscode://settings/workspaceTrust'
        else:
            extension = extension_identifier(extension)
            target_url = 'vscode:extension/' + extension
        args.append(target_url)
    if action in ('install-extension', 'uninstall-extension'):
        if action == 'install-extension' and isinstance(extension, str) and extension.lower().endswith('.vsix'):
            package = _regular_file(extension, must_exist=True)
            if package.stat().st_size > 100 * 1024 * 1024: raise OctoShipError('VSIX package exceeds the 100 MiB limit.')
            extension = str(package)
        else:
            extension = extension_identifier(extension)
        args.append(extension)
    elif extension is not None and action != 'show-extension':
        raise OctoShipError('This action does not accept an extension identifier.')
    if action not in ('profile-create', 'profile-open', 'locale', 'goto', 'extensions-list', 'extensions-list-versions') and extra:
        raise OctoShipError('This editor action does not accept extra command arguments.')
    if action in ('diff', 'merge', 'add-folder'):
        args.extend(path_args)
    if action not in ('open','new-window','reuse-window','wait','disable-gpu','log-startup','disable-extensions','skip-recent','diff','merge','add-folder','new-instance','extensions-dir','profile-create','profile-open','goto') and path_args:
        raise OctoShipError(f'{action} does not accept file or folder paths.')
    return args


def run_editor_action(editor, action, paths=(), extension=None, extra=(), popen=subprocess.Popen):
    argv = editor_command(editor, action, paths, extension, extra)
    cwd = str(Path(paths[0]).expanduser().resolve().parent) if paths and Path(paths[0]).expanduser().is_file() else (str(Path(paths[0]).expanduser().resolve()) if paths else None)
    return popen(argv, cwd=cwd, shell=False, close_fds=True)


@dataclass(frozen=True)
class AccessibilityOption:
    key: str
    label: str
    value: object


# Each option controls a separate editor setting with a direct accessibility or
# readability effect; applying a preset is still previewed before writing.
ACCESSIBILITY_OPTIONS = (
    AccessibilityOption('editor.accessibilitySupport', 'Screen reader support', 'on'),
    AccessibilityOption('editor.fontSize', 'Larger editor text', 16),
    AccessibilityOption('terminal.integrated.fontSize', 'Larger terminal text', 15),
    AccessibilityOption('window.zoomLevel', 'Larger interface scale', 1),
    AccessibilityOption('editor.lineHeight', 'More line spacing', 24),
    AccessibilityOption('editor.wordWrap', 'Wrap long lines', 'on'),
    AccessibilityOption('editor.minimap.enabled', 'Hide minimap', False),
    AccessibilityOption('editor.stickyScroll.enabled', 'Keep context while scrolling', True),
    AccessibilityOption('editor.cursorStyle', 'Block cursor', 'block'),
    AccessibilityOption('editor.cursorWidth', 'Wider cursor', 3),
    AccessibilityOption('editor.renderWhitespace', 'Show whitespace markers', 'boundary'),
    AccessibilityOption('editor.guides.indentation', 'Show indentation guides', True),
    AccessibilityOption('editor.guides.bracketPairs', 'Show bracket-pair guides', True),
    AccessibilityOption('editor.bracketPairColorization.enabled', 'Color matching brackets', True),
    AccessibilityOption('editor.renderLineHighlight', 'Highlight current line', 'all'),
    AccessibilityOption('editor.lineNumbers', 'Show line numbers', 'on'),
    AccessibilityOption('editor.smoothScrolling', 'Enable smooth scrolling', True),
    AccessibilityOption('workbench.reduceMotion', 'Reduce interface motion', 'on'),
    AccessibilityOption('workbench.colorTheme', 'Use high contrast theme', 'Default High Contrast'),
    AccessibilityOption('terminal.integrated.minimumContrastRatio', 'Increase terminal contrast', 7),
)


def accessibility_preview(editor='code', env=None):
    path, current = read_settings(editor, env)
    proposed = dict(current)
    for option in ACCESSIBILITY_OPTIONS:
        proposed[option.key] = option.value
    return path, proposed, settings_diff(current, proposed)


def apply_accessibility_preset(editor='code', env=None):
    _, proposed, _ = accessibility_preview(editor, env)
    return write_settings(editor, proposed, env)


def workspace_files(root):
    """Return recognized editor workspace metadata without traversing links."""
    root = Path(root).expanduser().resolve(strict=True)
    if not root.is_dir(): raise OctoShipError('Choose an existing workspace folder.')
    names = ('.vscode/settings.json', '.vscode/tasks.json', '.vscode/launch.json',
             '.vscode/extensions.json', '.editorconfig', '.vscodeignore', '.zed/settings.json')
    found = []
    for relative in names:
        path = root / relative
        if path.is_file() and not path.is_symlink(): found.append(path)
    for path in sorted(root.glob('*.code-workspace')):
        if path.is_file() and not path.is_symlink(): found.append(path)
    return tuple(found)


def validate_workspace_json(path):
    path = _regular_file(path, must_exist=True)
    if path.stat().st_size > 1024 * 1024: raise OctoShipError('Workspace config exceeds 1 MiB.')
    try: value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError): raise OctoShipError('Workspace config is invalid JSON.') from None
    if not isinstance(value, dict): raise OctoShipError('Workspace config must be a JSON object.')
    return value


def extension_identifier(value):
    value = str(value or '').strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.[A-Za-z0-9][A-Za-z0-9_.-]*', value):
        raise OctoShipError('Extension identifier must use publisher.extension format.')
    return value


def extension_install_spec(value):
    """Validate a marketplace extension identifier and optional pinned version."""
    value = str(value or '').strip()
    match = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9_.-]*\.[A-Za-z0-9][A-Za-z0-9_.-]*)(?:@([A-Za-z0-9][A-Za-z0-9.+_-]{0,63}))?', value)
    if not match: raise OctoShipError('Use publisher.extension or publisher.extension@version.')
    return value


def extension_cli_plan(action, extension=None, editor='code', profile=None):
    """Build the reviewed argv for an extension operation or a profile-specific one."""
    if action == 'install-extension':
        extension = extension_install_spec(extension)
        base = editor_command(editor, action, extension=extension.split('@', 1)[0])
        base[-1] = extension
        if profile:
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _.-]{0,47}', profile): raise OctoShipError('Profile name is invalid.')
            base.extend(['--profile', profile])
        return base
    if action in ('uninstall-extension', 'show-extension'):
        extension = extension_identifier(extension)
        if profile and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _.-]{0,47}', profile): raise OctoShipError('Profile name is invalid.')
        base = editor_command(editor, action, extension=extension)
        if profile: base.extend(['--profile', profile])
        return base
    if action in ('extensions-list', 'extensions-list-versions', 'extensions-update', 'disable-extensions'):
        if profile and action.startswith('extensions-list'):
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _.-]{0,47}', profile): raise OctoShipError('Profile name is invalid.')
            extra = ('--profile', profile)
        else: extra = ()
        return editor_command(editor, action, extra=extra)
    raise OctoShipError('Unsupported extension workflow.')


def extension_list(editor='code', profile=None, show_versions=True, run=subprocess.run):
    action = 'extensions-list-versions' if show_versions else 'extensions-list'
    argv = extension_cli_plan(action, editor=editor, profile=profile)
    try: result = run(argv, shell=False, check=False, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired): raise OctoShipError('Editor extension listing did not finish. Check the editor installation and retry.') from None
    if result.returncode: raise OctoShipError('Editor could not list extensions. Check the selected profile and editor status.')
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def editor_cli_report(editor, action, run=subprocess.run):
    """Capture bounded read-only CLI information for profiles and versions."""
    if action not in ('profile-list', 'extensions-list', 'extensions-list-versions', 'show-versions', 'show-help', 'status'):
        raise OctoShipError('Only read-only editor information actions can be captured here.')
    argv = editor_command(editor, action)
    try: result = run(argv, shell=False, check=False, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired): raise OctoShipError('Editor query did not finish. Check the editor installation and retry.') from None
    output = (result.stdout or '') + (result.stderr or '')
    if len(output) > 1024 * 1024: output = output[:1024 * 1024] + '\n[output truncated at 1 MiB]'
    if result.returncode: raise OctoShipError('Editor query failed. Check the selected editor and try again.')
    return output.strip()


def install_local_vsix(path, editor='code', profile=None):
    path = _regular_file(path, must_exist=True)
    if path.suffix.casefold() != '.vsix' or path.stat().st_size > 100 * 1024 * 1024:
        raise OctoShipError('Choose a VSIX package no larger than 100 MiB.')
    extra = ('--profile', profile) if profile else ()
    if profile and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _.-]{0,47}', profile): raise OctoShipError('Profile name is invalid.')
    return editor_command(editor, 'install-extension', extension=str(path), extra=extra)


def workspace_extension_recommendations(root):
    path = workspace_config_path(root, 'extensions')
    value = validate_workspace_json(path)
    recommendations = value.get('recommendations', [])
    if not isinstance(recommendations, list) or len(recommendations) > 500:
        raise OctoShipError('Workspace extension recommendations must be a list of at most 500 entries.')
    cleaned = []
    for item in recommendations:
        if not isinstance(item, str): raise OctoShipError('Workspace recommendations contain a non-text entry.')
        cleaned.append(extension_identifier(item))
    return tuple(dict.fromkeys(cleaned))


def compare_workspace_extensions(root, installed):
    recommended = workspace_extension_recommendations(root)
    present = {str(item).split('@', 1)[0].casefold() for item in installed}
    return {'recommended': list(recommended), 'installed': [x for x in recommended if x.casefold() in present],
            'missing': [x for x in recommended if x.casefold() not in present]}


def install_recommended_extension(root, identifier, editor='code', profile=None):
    identifier = extension_identifier(identifier)
    if identifier not in workspace_extension_recommendations(root):
        raise OctoShipError('This extension is not in the selected workspace recommendations.')
    argv = extension_cli_plan('install-extension', identifier, editor, profile)
    return subprocess.Popen(argv, shell=False, close_fds=True)


def workspace_profile_path(name, root=None):
    """Resolve a named local settings snapshot; reject traversal and links."""
    name = str(name or '').strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _.-]{0,47}', name) or name in ('.', '..'):
        raise OctoShipError('Profile names may contain letters, numbers, spaces, dot, underscore, and dash.')
    base = Path(root) if root else Path.home() / '.local/share/octoship/editor-profiles'
    base = base.expanduser()
    if base.exists() and (base.is_symlink() or not base.is_dir()):
        raise OctoShipError('Profile storage must be a regular folder.')
    return base / (name + '.json')


def save_profile(name, editor='code', root=None, env=None):
    """Save a local editor settings snapshot, excluding extension/credential data."""
    target = workspace_profile_path(name, root)
    _, settings = read_settings(editor, env)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        raise OctoShipError('That local profile already exists; choose another name.')
    fd, tmp = tempfile.mkstemp(prefix='.octoship-profile-', dir=target.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump({'format': 1, 'editor': editor, 'created': int(time.time()), 'settings': settings}, stream, indent=2, sort_keys=True)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return target


def list_profiles(root=None):
    base = Path(root) if root else Path.home() / '.local/share/octoship/editor-profiles'
    if not base.exists(): return ()
    if base.is_symlink() or not base.is_dir(): raise OctoShipError('Profile storage must be a regular folder.')
    return tuple(sorted((p for p in base.glob('*.json') if p.is_file() and not p.is_symlink()), key=lambda p: p.name.casefold()))


def preview_profile(name, editor='code', root=None, env=None):
    target = workspace_profile_path(name, root)
    target = _regular_file(target, must_exist=True)
    if target.stat().st_size > 2 * 1024 * 1024: raise OctoShipError('Profile exceeds the 2 MiB safety limit.')
    try: profile = json.loads(target.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError): raise OctoShipError('Profile is invalid JSON.') from None
    if not isinstance(profile, dict) or profile.get('format') != 1 or profile.get('editor') != editor or not isinstance(profile.get('settings'), dict):
        raise OctoShipError('Profile format or editor does not match.')
    _, current = read_settings(editor, env)
    return dict(profile['settings']), settings_diff(current, profile['settings'])


def activate_profile(name, editor='code', root=None, env=None):
    settings, _ = preview_profile(name, editor, root, env)
    return write_settings(editor, settings, env)


def remove_profile(name, root=None):
    path = workspace_profile_path(name, root)
    path = _regular_file(path, must_exist=True)
    path.unlink()
    return path


def workspace_metadata(root):
    """Read project editor metadata in a bounded, no-execution manner."""
    result = {}
    for path in workspace_files(root):
        if path.suffix.lower() == '.json':
            try: value = validate_workspace_json(path)
            except OctoShipError as exc: result[str(path.relative_to(root))] = {'valid': False, 'message': str(exc)}
            else: result[str(path.relative_to(root))] = {'valid': True, 'keys': sorted(value.keys())}
        else:
            result[str(path.relative_to(root))] = {'valid': True, 'bytes': path.stat().st_size}
    return result


WORKSPACE_CONFIGS = {
    'settings': '.vscode/settings.json', 'tasks': '.vscode/tasks.json',
    'launch': '.vscode/launch.json', 'extensions': '.vscode/extensions.json',
    'editorconfig': '.editorconfig', 'vscodeignore': '.vscodeignore',
    'zed-settings': '.zed/settings.json',
}


def workspace_config_path(root, kind):
    root = Path(root).expanduser().resolve(strict=True)
    if not root.is_dir(): raise OctoShipError('Choose an existing workspace folder.')
    if kind == 'code-workspace':
        matches = tuple(path for path in root.glob('*.code-workspace') if path.is_file() and not path.is_symlink())
        if len(matches) != 1: raise OctoShipError('Workspace folder must contain exactly one regular .code-workspace file.')
        return matches[0]
    if kind not in WORKSPACE_CONFIGS: raise OctoShipError('Choose a supported workspace configuration type.')
    path = root / WORKSPACE_CONFIGS[kind]
    try: path.resolve(strict=True).relative_to(root)
    except (OSError, ValueError): raise OctoShipError('Workspace config path is missing or escapes the selected folder.') from None
    if not path.is_file() or path.is_symlink(): raise OctoShipError('Workspace config must be a regular file.')
    return path


def validate_workspace_config(root, kind):
    path = workspace_config_path(root, kind)
    if kind in ('editorconfig', 'vscodeignore'):
        if path.stat().st_size > 1024 * 1024: raise OctoShipError('Workspace text config exceeds 1 MiB.')
        return {'path': str(path), 'valid': True, 'lines': len(path.read_text(encoding='utf-8').splitlines())}
    value = validate_workspace_json(path)
    if kind == 'tasks' and not isinstance(value.get('tasks'), list): raise OctoShipError('tasks.json must contain a tasks array.')
    if kind == 'launch' and not isinstance(value.get('configurations'), list): raise OctoShipError('launch.json must contain a configurations array.')
    if kind == 'extensions' and not isinstance(value.get('recommendations', []), list): raise OctoShipError('extensions.json recommendations must be an array.')
    if kind == 'code-workspace' and not isinstance(value.get('folders'), list): raise OctoShipError('Workspace file must contain a folders array.')
    return {'path': str(path), 'valid': True, 'top_level_keys': sorted(value)}


def open_workspace_config(root, kind, editor='code', popen=subprocess.Popen):
    path = workspace_config_path(root, kind)
    return run_editor_action(editor, 'open', [path], popen=popen)


def set_accessibility_option(editor, key, enabled=True, env=None):
    option = next((item for item in ACCESSIBILITY_OPTIONS if item.key == key), None)
    if option is None: raise OctoShipError('Choose an accessibility setting from the supported list.')
    path, settings = read_settings(editor, env)
    if enabled: settings[option.key] = option.value
    else: settings.pop(option.key, None)
    return write_settings(editor, settings, env)


def settings_snapshot(editor='code', env=None):
    """Export settings and keybindings as a local archive directory, no secrets."""
    source = user_data_dir(editor, env)
    data = {}
    for name in ('settings.json', 'keybindings.json'):
        path = source / name
        if path.exists():
            _regular_file(path, must_exist=True)
            if path.stat().st_size > 2 * 1024 * 1024: raise OctoShipError(f'{name} exceeds the 2 MiB limit.')
            try: value = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, UnicodeError, ValueError): raise OctoShipError(f'{name} is invalid JSON and cannot be exported safely.') from None
            data[name] = json.dumps(_without_sensitive_settings(value), ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    snippets = source / 'snippets'
    if snippets.is_dir() and not snippets.is_symlink():
        for path in sorted(snippets.glob('*.json'))[:100]:
            if path.is_file() and not path.is_symlink() and path.stat().st_size <= 512 * 1024:
                data['snippets/' + path.name] = path.read_text(encoding='utf-8')
    return {'format': 1, 'editor': editor, 'files': data}


def _without_sensitive_settings(value):
    if isinstance(value, dict):
        blocked = ('token', 'password', 'secret', 'credential', 'privatekey', 'api_key', 'apikey')
        return {key: _without_sensitive_settings(item) for key, item in value.items()
                if not any(word in str(key).casefold().replace('-', '').replace('_', '') for word in blocked)}
    if isinstance(value, list): return [_without_sensitive_settings(item) for item in value]
    return value


def import_settings_snapshot(editor, snapshot, env=None):
    """Validate and stage safe user configuration files; never imports extensions."""
    if not isinstance(snapshot, dict) or snapshot.get('format') != 1 or snapshot.get('editor') != editor or not isinstance(snapshot.get('files'), dict):
        raise OctoShipError('Settings export format or selected editor does not match.')
    files = snapshot['files']
    allowed = {'settings.json', 'keybindings.json'}
    for key, content in files.items():
        if key not in allowed and not re.fullmatch(r'snippets/[A-Za-z0-9_.-]{1,120}\.json', key):
            raise OctoShipError('Settings export contains an unsupported path.')
        if not isinstance(content, str) or len(content.encode('utf-8')) > 2 * 1024 * 1024:
            raise OctoShipError('Settings export contains invalid or oversized content.')
        try: parsed = json.loads(content)
        except ValueError: raise OctoShipError(f'{key} is invalid JSON; nothing was imported.') from None
        if key.endswith('.json') and not isinstance(parsed, (dict, list)):
            raise OctoShipError(f'{key} must contain a JSON object or array.')
    target = user_data_dir(editor, env)
    destinations = [(target / key, key) for key in files]

    # Checking only the leaf file is not enough: a `snippets` directory (or
    # the editor's User directory itself) can be a symlink to an arbitrary
    # location.  Preflight every destination and all existing parent
    # directories before creating anything or replacing any files.
    for path, _ in destinations:
        parent = path.parent
        chain = list(reversed((parent, *parent.parents)))
        for directory in chain:
            if directory.is_symlink():
                raise OctoShipError('Settings import destination cannot contain symbolic links; nothing was imported.')
            if directory.exists() and not directory.is_dir():
                raise OctoShipError('Settings import destination contains a non-folder path; nothing was imported.')
        if path.is_symlink():
            raise OctoShipError('Settings import destination cannot contain symbolic links; nothing was imported.')
        if path.exists() and not path.is_file():
            raise OctoShipError('Settings import destination must be a regular file; nothing was imported.')
    for path, _ in destinations:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Recheck after mkdir so a changed path fails closed before file writes.
        if path.parent.is_symlink() or not path.parent.is_dir():
            raise OctoShipError('Settings import destination changed during preparation; nothing was imported.')
    for key, content in files.items():
        path = target / key
        if path.exists(): _regular_file(path, must_exist=True)
        fd, temp = tempfile.mkstemp(prefix='.octoship-import-', dir=path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                stream.write(content); stream.flush(); os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            if os.path.exists(temp): os.unlink(temp)
    return tuple(files)


@dataclass(frozen=True)
class WorkspaceFeature:
    feature_id: str
    category: str
    title: str
    handler: object


def _build_feature_catalog():
    rows = []
    for action in EDITOR_COMMAND_FEATURES:
        rows.append(WorkspaceFeature('editor.command.' + action, 'Editor command', action.replace('-', ' ').title(), editor_command))
    for option in ACCESSIBILITY_OPTIONS:
        rows.append(WorkspaceFeature('accessibility.' + option.key, 'Accessibility', option.label, set_accessibility_option))
    for shell_id, label, _, _ in SHELL_PROFILES:
        rows.append(WorkspaceFeature('terminal.shell.' + shell_id, 'Terminal shell', label + ' terminal profile', add_terminal_profile))
    for feature_id, title, handler in (
        ('terminal.detect', 'Detect installed terminal shells', available_terminal_profiles),
        ('terminal.preview', 'Preview a terminal shell profile', preview_terminal_profile),
        ('terminal.add', 'Add a terminal shell profile', add_terminal_profile),
        ('terminal.remove', 'Remove a terminal shell profile', remove_terminal_profile),
        ('terminal.default', 'Set the default terminal profile', set_default_terminal_profile),
    ):
        rows.append(WorkspaceFeature(feature_id, 'Terminal', title, handler))
    for editor, (label, _) in EDITORS.items():
        rows.append(WorkspaceFeature('editor.integration.' + editor, 'Editor integration', 'Open files with ' + label, run_editor_action))
    for feature_id, title, handler in (
        ('settings.read', 'Read settings safely', read_settings),
        ('settings.diff', 'Preview a settings change', settings_diff),
        ('settings.atomic-write', 'Atomically update settings', write_settings),
        ('settings.backup', 'Back up settings locally', backup_settings),
        ('settings.restore', 'Restore settings from a backup', restore_settings),
        ('settings.export', 'Export portable settings', settings_snapshot),
        ('settings.import', 'Import portable settings', import_settings_snapshot),
        ('profile.save', 'Save a named local profile', save_profile),
        ('profile.list', 'List local profiles', list_profiles),
        ('profile.preview', 'Preview a saved profile', preview_profile),
        ('profile.activate', 'Activate a saved profile', activate_profile),
        ('profile.remove', 'Remove a saved profile', remove_profile),
    ):
        rows.append(WorkspaceFeature(feature_id, 'Settings and profiles', title, handler))
    for kind in (*WORKSPACE_CONFIGS.keys(), 'code-workspace'):
        rows.append(WorkspaceFeature('workspace.validate.' + kind, 'Workspace configuration', 'Validate ' + kind, validate_workspace_config))
    for feature_id, title, handler in (
        ('extensions.install-pinned', 'Install a pinned marketplace extension version', extension_cli_plan),
        ('extensions.install-vsix', 'Install a local VSIX package', install_local_vsix),
        ('extensions.install-profile', 'Install an extension into a profile', extension_cli_plan),
        ('extensions.remove-profile', 'Remove an extension from a profile', extension_cli_plan),
        ('extensions.compare-recommendations', 'Compare installed and workspace-recommended extensions', compare_workspace_extensions),
        ('extensions.install-recommendation', 'Install a selected workspace recommendation', install_recommended_extension),
    ):
        rows.append(WorkspaceFeature(feature_id, 'Extensions', title, handler))
    return tuple(rows)


FEATURE_CATALOG = _build_feature_catalog()
