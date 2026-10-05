"""Offline per-user installer, using only the Python/Tk shipped in the payload."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

ROOT = Path(__file__).resolve().parent
VERSION = json.loads((ROOT / 'bundle.json').read_text())['version']


def atomic_text(path, text, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text); stream.flush(); os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def desktop_arg(value):
    # Desktop Exec has its own quoting rules; it is not a shell command.
    escaped = str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
    return '"' + escaped + '"'


def verify_payload(root):
    expected = json.loads((root / 'payload-hashes.json').read_text())
    for name, digest in expected['files'].items():
        path = root / name
        if path.is_symlink() or not path.is_file() or root.resolve() not in path.resolve().parents:
            raise ValueError('Invalid payload file: ' + name)
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != digest:
            raise ValueError('Payload checksum mismatch: ' + name)

    for name, target in expected['symlinks'].items():
        path = root / name
        if not path.is_symlink() or os.readlink(path) != target or root.resolve() not in path.resolve().parents:
            raise ValueError('Invalid payload symlink: ' + name)


def install(prefix, register=True):
    prefix = Path(os.path.abspath(Path(prefix).expanduser()))
    if any(c in str(prefix) for c in '\n\r\0'):
        raise ValueError('Choose an installation folder without control characters.')
    if prefix == ROOT or ROOT in prefix.parents:
        raise ValueError('Choose a folder outside the temporary installer.')
    verify_payload(ROOT)
    prefix.mkdir(parents=True, exist_ok=True)
    builds = prefix / 'builds'; builds.mkdir(exist_ok=True)
    identity = hashlib.sha256((ROOT / 'payload-hashes.json').read_bytes()).hexdigest()[:12]
    target = builds / (VERSION + '-' + identity)
    # Every build has an immutable directory, so a running older version remains usable.
    if target.exists():
        verify_payload(target)
    else:
        staged = Path(tempfile.mkdtemp(prefix='.install-', dir=builds))
        try:
            shutil.copytree(ROOT, staged, dirs_exist_ok=True, symlinks=True,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            verify_payload(staged)
            os.replace(staged, target)
        finally:
            if staged.exists(): shutil.rmtree(staged)
    launcher = target / 'octoship'
    # Keep the previous launcher as a rollback aid, including a pre-bundle installation.
    prefix_launcher = prefix / 'octoship'
    if prefix_launcher.is_file() and not prefix_launcher.is_symlink():
        shutil.copy2(prefix_launcher, prefix / 'octoship.previous')
    atomic_text(prefix_launcher, '#!/bin/sh\nexec ' + shlex.quote(str(launcher)) + ' "$@"\n', 0o755)
    registered = []
    if register:
        home_launcher = Path.home() / '.local/bin/octoship'
        if home_launcher.is_file() and not home_launcher.is_symlink():
            shutil.copy2(home_launcher, prefix / 'desktop-launcher.previous')
        atomic_text(home_launcher, '#!/bin/sh\nexec ' + shlex.quote(str(launcher)) + ' "$@"\n', 0o755)
        data = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
        icon = target / 'octoship.svg'
        for filename, label, arguments, terminal in (
            ('octoship.desktop', 'OctoShip for GitHub', '', False),
            ('octoship-login.desktop', 'OctoShip GitHub Sign-in', ' --login', True),
        ):
            desktop = data / 'applications' / filename
            content = ('[Desktop Entry]\nType=Application\nName=' + label + '\nComment=Self-contained GitHub desktop client\n'
                       + 'Exec=' + desktop_arg(launcher) + arguments + '\nIcon=' + str(icon)
                       + '\nTerminal=' + str(terminal).lower() + '\nCategories=Development;\nStartupNotify=true\n')
            atomic_text(desktop, content)
            registered.append(str(desktop))
        registered.append(str(home_launcher))
    atomic_text(target / 'installation.json', json.dumps({'prefix': str(prefix), 'registered': registered}, indent=2) + '\n')
    return prefix_launcher


def uninstall(root):
    marker = root / 'installation.json'
    if not marker.is_file():
        raise SystemExit('This bundle was not installed per-user. Use your package manager or remove the extracted portable folder.')
    info = json.loads(marker.read_text())
    prefix = Path(info['prefix'])
    print('Uninstall this OctoShip build from ' + str(root) + '?')
    print('Saved queues and GitHub credentials will be kept.')
    if input('Type uninstall to continue: ').strip() != 'uninstall': return
    for item in info['registered'] + [str(prefix / 'octoship')]:
        path = Path(item)
        # Do not remove launchers that a newer installation has replaced.
        if path.is_file() and str(root) in path.read_text(): path.unlink()
    if root.parent == prefix / 'builds' and (root / 'bundle.json').is_file():
        shutil.rmtree(root)
    print('Removed this build. Older builds and user data were preserved.')


def gui(prefix):
    from octoship.theme import apply_dark_theme
    root = tk.Tk(); root.title('Install OctoShip ' + VERSION); root.geometry('740x440'); root.minsize(680, 420)
    apply_dark_theme(root)
    panel = ttk.Frame(root, padding=24); panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Install OctoShip', style='Header.TLabel').pack(anchor='w')
    ttk.Label(panel, text='Everything the app needs, in one offline package.', padding=(0, 12)).pack(anchor='w')
    ttk.Label(panel, text='Includes Python, Tcl/Tk, GitHub CLI, and certificate data.\nFor Intel/AMD 64-bit Linux desktops with glibc 2.17+ and X11/XWayland.\nNo administrator password or dependency downloads are needed.', wraplength=650).pack(anchor='w', pady=(0, 18))
    destination = tk.StringVar(value=str(prefix))
    ttk.Label(panel, text='Install folder').pack(anchor='w')
    row = ttk.Frame(panel); row.pack(fill='x', pady=(4, 12))
    entry = ttk.Entry(row, textvariable=destination); entry.pack(side='left', fill='x', expand=True)
    def browse():
        folder = filedialog.askdirectory(parent=root)
        if folder: destination.set(str(Path(folder) / 'octoship'))
    choose = ttk.Button(row, text='Choose…', command=browse); choose.pack(side='right', padx=(8, 0))
    status = tk.StringVar(value='Adds OctoShip and GitHub Sign-in to your application menu.')
    ttk.Label(panel, textvariable=status, wraplength=650).pack(anchor='w', pady=10)
    bar = ttk.Progressbar(panel, mode='indeterminate'); bar.pack(fill='x', pady=6)
    messages = queue.Queue(); busy = False; installed = None
    buttons = ttk.Frame(panel); buttons.pack(fill='x', side='bottom')
    def start():
        nonlocal busy
        selected = destination.get()
        busy = True; button.configure(state='disabled'); choose.configure(state='disabled'); entry.configure(state='disabled')
        status.set('Verifying and installing the bundled runtime…'); bar.start()
        def worker():
            try: messages.put((True, install(selected)))
            except Exception as exc: messages.put((False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()
    def launch():
        if installed:
            subprocess.Popen([str(installed)], start_new_session=True, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            root.destroy()
    button = ttk.Button(buttons, text='Install', command=start); button.pack(side='right')
    open_button = ttk.Button(buttons, text='Open OctoShip', command=launch, state='disabled'); open_button.pack(side='right', padx=8)
    def close():
        if busy: messagebox.showinfo('Installing', 'Wait for installation to finish.', parent=root)
        else: root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    def poll():
        nonlocal busy, installed
        try:
            success, result = messages.get_nowait(); busy = False; bar.stop()
            if success:
                installed = result; status.set('Installed. Open OctoShip, then use GitHub Sign-in from your application menu to connect your account.')
                open_button.configure(state='normal'); button.configure(text='Done', command=close, state='normal')
            else:
                status.set('Installation failed: ' + result); button.configure(state='normal'); choose.configure(state='normal'); entry.configure(state='normal')
        except queue.Empty: pass
        root.after(100, poll)
    root.after(100, poll); root.mainloop()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Install the self-contained OctoShip Linux desktop client.')
    parser.add_argument('--install', action='store_true', help='Install noninteractively instead of opening the installer window')
    parser.add_argument('--prefix', default=str(Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'octoship'))
    parser.add_argument('--no-desktop', action='store_true', help='Create only the launcher under the install folder')
    args = parser.parse_args(argv)
    if args.install:
        print('Installed: ' + str(install(args.prefix, not args.no_desktop)))
    else:
        if not os.environ.get('DISPLAY'):
            parser.error('A desktop display is required for the installer window. Use --install for command-line installation.')
        gui(Path(args.prefix))
