"""Offline, privacy-preserving OctoShip environment diagnostics."""
import importlib.util
import os
from pathlib import Path
import platform
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import tkinter


def _row(name, passed, detail, severity='info'):
    return {'check': name, 'status': 'pass' if passed else severity, 'detail': detail}


def environment_report(environ=None, run=subprocess.run, which=shutil.which, system=platform.system,
                       machine=platform.machine, pyver=sys.version_info, tkversion=tkinter.TkVersion):
    """Return bounded readiness checks. No credentials or subprocess output are retained."""
    env = os.environ if environ is None else environ
    rows = []
    rows.append(_row('Linux host', system() == 'Linux', system(), 'warning'))
    arch = machine().lower()
    rows.append(_row('Supported CPU family', arch in ('x86_64', 'amd64', 'aarch64', 'arm64'), arch, 'warning'))
    rows.append(_row('Python version', tuple(pyver) >= (3, 10), '.'.join(map(str, pyver[:3])), 'error'))
    rows.append(_row('Tk version', float(tkversion) >= 8.6, str(tkversion), 'error'))
    rows.append(_row('TLS support', hasattr(ssl, 'create_default_context'), ssl.OPENSSL_VERSION, 'error'))
    rows.append(_row('Certificate bundle', bool(ssl.get_default_verify_paths().cafile or ssl.get_default_verify_paths().capath),
                     'System certificate paths are configured.' if ssl.get_default_verify_paths().cafile or ssl.get_default_verify_paths().capath else 'No system CA path was found.', 'warning'))

    home = Path(env.get('HOME', str(Path.home()))).expanduser()
    rows.append(_row('Home folder', home.is_dir() and os.access(home, os.R_OK | os.W_OK), 'Readable and writable.' if home.is_dir() and os.access(home, os.R_OK | os.W_OK) else 'Check HOME permissions.', 'error'))
    state = Path(env.get('XDG_STATE_HOME', str(home / '.local' / 'state'))) / 'octoship'
    try:
        state.mkdir(mode=0o700, parents=True, exist_ok=True)
        mode = state.stat().st_mode & 0o777
        # Do not include the absolute path: XDG_STATE_HOME often contains a
        # username or a customer-specific mount point, and reports may be shared.
        rows.append(_row('Private state folder', mode & 0o077 == 0, f'Folder permissions are {mode:04o}.', 'warning'))
    except OSError:
        rows.append(_row('Private state folder', False, 'Unable to create or inspect the OctoShip state folder.', 'error'))
    try:
        with tempfile.NamedTemporaryFile(prefix='octoship-doctor-', dir=env.get('TMPDIR') or None):
            pass
        rows.append(_row('Temporary storage', True, 'Temporary file create/delete succeeded.'))
    except OSError:
        rows.append(_row('Temporary storage', False, 'Temporary file create/delete failed.', 'error'))

    for executable, label, severity in (
        ('gh', 'GitHub CLI', 'warning'), ('git', 'Git', 'warning'), ('code', 'VS Code CLI', 'info'),
        ('xdg-open', 'Desktop URL handler', 'warning'), ('dpkg-deb', 'Debian package tools', 'info'),
        ('sha256sum', 'SHA-256 utility', 'info'), ('tar', 'Tar utility', 'info'),
    ):
        path = which(executable)
        rows.append(_row(label, bool(path), path or f'{executable} is not on PATH.', severity))

    display = bool(env.get('DISPLAY') or env.get('WAYLAND_DISPLAY'))
    rows.append(_row('Graphical session', display, 'Display session detected.' if display else 'No X11 or Wayland display; the desktop UI cannot open.', 'warning'))
    rows.append(_row('GitHub CLI sign-in', False, 'Not checked; run `gh auth status` locally if authentication is needed.', 'info'))
    rows.append(_row('GitHub API network', False, 'Not checked; diagnostics do not make network requests.', 'info'))
    rows.append(_row('Bundled runtime', bool(env.get('OCTOSHIP_BUNDLE_ROOT')), 'Bundled launch environment detected.' if env.get('OCTOSHIP_BUNDLE_ROOT') else 'Running outside the standalone bundle.', 'info'))
    rows.append(_row('Locale', bool(env.get('LANG') or env.get('LC_ALL')), env.get('LC_ALL') or env.get('LANG') or 'No locale variable set.', 'warning'))
    rows.append(_row('CPU count', (os.cpu_count() or 0) > 0, f'{os.cpu_count() or 0} logical CPUs.'))
    rows.append(_row('Python module: tkinter', importlib.util.find_spec('tkinter') is not None, 'Available.' if importlib.util.find_spec('tkinter') else 'Install the system Tk bindings.', 'error'))
    rows.append(_row('Python module: fcntl', importlib.util.find_spec('fcntl') is not None, 'Available.' if importlib.util.find_spec('fcntl') else 'Instance locking is unavailable.', 'error'))
    rows.append(_row('Runtime lock folder', bool(env.get('XDG_RUNTIME_DIR') and Path(env['XDG_RUNTIME_DIR']).is_dir()),
                     'XDG_RUNTIME_DIR is available.' if env.get('XDG_RUNTIME_DIR') and Path(env['XDG_RUNTIME_DIR']).is_dir() else 'OctoShip can fall back to ~/.cache.', 'info'))
    rows.append(_row('Proxy configuration', any(env.get(k) for k in ('HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy')),
                     'Proxy variables are configured.' if any(env.get(k) for k in ('HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy')) else 'No proxy variables detected.', 'info'))
    rows.append(_row('Host name', bool(socket.gethostname()), socket.gethostname() or 'Unavailable.', 'info'))
    try:
        disk = shutil.disk_usage(state if state.exists() else home)
        free = disk.free
        rows.append(_row('Free space', free >= 100 * 1024**2, f'{free // (1024**2)} MiB available.', 'warning'))
    except OSError:
        rows.append(_row('Free space', False, 'Disk usage could not be read.', 'warning'))
    runtime = env.get('OCTOSHIP_UI_RUNTIME', 'auto')
    rows.append(_row('UI runtime selection', runtime in ('auto', 'system', 'bundled'), runtime, 'error'))
    pythonhome_override = bool(env.get('PYTHONHOME'))
    rows.append(_row('Python override variables', not pythonhome_override,
                     'PYTHONHOME is not overriding the runtime.' if not pythonhome_override else 'PYTHONHOME may replace the app-selected Python standard library.', 'warning'))
    tk_overrides = any(env.get(key) for key in ('TCL_LIBRARY', 'TK_LIBRARY'))
    active_runtime = env.get('OCTOSHIP_UI_RUNTIME_ACTIVE', runtime)
    tk_conflict = tk_overrides and active_runtime != 'bundled'
    rows.append(_row('Tcl/Tk override variables', not tk_conflict,
                     'Tcl/Tk paths match the selected runtime.' if not tk_conflict else 'Tcl/Tk overrides may conflict with the system runtime.', 'warning'))
    rows.append(_row('Wayland session', bool(env.get('WAYLAND_DISPLAY')), 'Wayland display available.' if env.get('WAYLAND_DISPLAY') else 'No Wayland display detected.', 'info'))
    rows.append(_row('X11 session', bool(env.get('DISPLAY')), 'X11 display available.' if env.get('DISPLAY') else 'No X11 display detected.', 'info'))
    session = env.get('XDG_SESSION_TYPE', '')
    rows.append(_row('Desktop session type', session in ('x11', 'wayland'), session or 'Not reported by the desktop session.', 'info'))
    for name, variable, default in (
        ('Config folder', 'XDG_CONFIG_HOME', home / '.config'),
        ('Data folder', 'XDG_DATA_HOME', home / '.local' / 'share'),
        ('Cache folder', 'XDG_CACHE_HOME', home / '.cache'),
    ):
        folder = Path(env.get(variable, str(default))).expanduser()
        try:
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)
            writable = folder.is_dir() and os.access(folder, os.R_OK | os.W_OK)
            rows.append(_row(name, writable, 'Readable and writable.' if writable else 'Check folder permissions.', 'warning'))
        except OSError:
            rows.append(_row(name, False, 'Could not create or inspect the XDG folder.', 'warning'))
    runtime_dir = Path(env.get('XDG_RUNTIME_DIR', '/nonexistent')).expanduser()
    if runtime_dir.is_dir():
        runtime_mode = runtime_dir.stat().st_mode & 0o777
        rows.append(_row('Runtime folder privacy', runtime_mode & 0o077 == 0, f'XDG_RUNTIME_DIR mode {runtime_mode:04o}.', 'warning'))
    else:
        rows.append(_row('Runtime folder privacy', False, 'XDG_RUNTIME_DIR is unavailable; OctoShip uses its cache fallback.', 'info'))
    bundled_root = env.get('OCTOSHIP_BUNDLE_ROOT')
    rows.append(_row('Bundle Python executable', bool(bundled_root and (Path(bundled_root) / 'runtime' / 'bin' / 'python3').is_file()),
                     'Bundled Python found.' if bundled_root and (Path(bundled_root) / 'runtime' / 'bin' / 'python3').is_file() else 'Not running from a verified Python bundle.', 'info'))
    rows.append(_row('Bundle GitHub CLI', bool(bundled_root and (Path(bundled_root) / 'bin' / 'gh').is_file()),
                     'Bundled GitHub CLI found.' if bundled_root and (Path(bundled_root) / 'bin' / 'gh').is_file() else 'Not running from a bundle with a private GitHub CLI.', 'info'))
    rows.append(_row('Bundle certificate file', bool(bundled_root and (Path(bundled_root) / 'certs' / 'cacert.pem').is_file()),
                     'Bundled certificate file found.' if bundled_root and (Path(bundled_root) / 'certs' / 'cacert.pem').is_file() else 'No bundled certificate file; system trust paths apply.', 'info'))
    rows.append(_row('Package manager', bool(which('dpkg-deb') or which('rpm')), 'dpkg-deb or rpm is available.' if which('dpkg-deb') or which('rpm') else 'No recognized native package inspection utility.', 'info'))
    rows.append(_row('UTF-8 locale', 'UTF-8' in (env.get('LC_ALL') or env.get('LANG') or '').upper(),
                     'Locale advertises UTF-8.' if 'UTF-8' in (env.get('LC_ALL') or env.get('LANG') or '').upper() else 'Locale may not advertise UTF-8.', 'warning'))
    fatal = sum(row['status'] == 'error' for row in rows)
    summary = 'No required runtime blockers found.' if fatal == 0 else f'{fatal} required runtime check(s) need attention.'
    return {'summary': summary, 'checks': rows, 'network_requests': 0, 'credentials_collected': False}


def format_report(report, output='text'):
    if output == 'json':
        import json
        return json.dumps(report, indent=2, ensure_ascii=False)
    lines = ['OctoShip environment diagnostics', report['summary'], '', 'Status  Check                         Details']
    lines.extend(f"{row['status'].upper():7} {row['check']:<29} {row['detail']}" for row in report['checks'])
    lines.extend(['', 'Network requests: none', 'Credentials collected: no'])
    return '\n'.join(lines)
