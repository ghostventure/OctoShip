"""Native Tk desktop client; all network and search work runs off the UI thread."""
import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser
from . import __version__
from .core import GitHub, OctoShipError, search_files, plan_upload, read_file, sensitive, login_instructions
from .scanner import scan_bytes
from .queue_store import QueueStore
from . import workflows as flow
from .tools_ui import ToolsPanel
from .theme import apply_dark_theme

class App:
    def __init__(self, root, queue_store=None):
        self.root = root
        root.title(f'OctoShip for GitHub — Linux {__version__}')
        root.geometry('1180x860')
        root.minsize(1000, 760)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.api = None
        self.files = []
        self.search_root = None
        self.last_url = None
        self.queue_store = queue_store or QueueStore()
        self.restored_destinations = {}
        self.mode = tk.StringVar(value='atomic')
        self.remember = tk.BooleanVar(value=False)
        self.pause = threading.Event()
        self.paused = tk.BooleanVar(value=False)
        self.repo = tk.StringVar()
        self.branch = tk.StringVar()
        self.folder = tk.StringVar(value=str(Path.home()))
        self.query = tk.StringVar()
        self.prefix = tk.StringVar()
        self.message = tk.StringVar(value='Upload files with OctoShip')
        self.collision = tk.StringVar(value='skip')
        self.contents = tk.BooleanVar()
        self.hidden = tk.BooleanVar()
        self.keep_paths = tk.BooleanVar(value=True)
        self.account = tk.StringVar(value='Connect using your GitHub account')
        self.status = tk.StringVar(value='Ready. Choose Sign in… to connect your GitHub account.')
        apply_dark_theme(root)
        body = ttk.Frame(root, padding=16)
        body.pack(fill='both', expand=True)
        header = ttk.Frame(body); header.pack(fill='x')
        ttk.Label(header, text='OctoShip', style='Header.TLabel').pack(side='left')
        ttk.Label(header, text=f'  for GitHub · Linux {__version__}', font=('Sans', 12)).pack(side='left', pady=9)
        ttk.Button(header, text='Connect / Refresh', command=self.connect).pack(side='right')
        ttk.Button(header, text='Sign in…', command=lambda: messagebox.showinfo('GitHub sign-in', login_instructions(), parent=root)).pack(side='right', padx=8)
        ttk.Label(body, textvariable=self.account).pack(anchor='w', pady=(4, 12))
        target = ttk.LabelFrame(body, text='GitHub destination', padding=10); target.pack(fill='x')
        ttk.Label(target, text='Repository').grid(row=0, column=0, sticky='w')
        self.repos = ttk.Combobox(target, textvariable=self.repo, width=48)
        self.repos.grid(row=0, column=1, sticky='ew', padx=8)
        self.repos.bind('<<ComboboxSelected>>', lambda e: self.load_branches())
        ttk.Button(target, text='Load branches', command=self.load_branches).grid(row=0, column=2)
        ttk.Label(target, text='Branch').grid(row=0, column=3, padx=(12, 4))
        self.branches = ttk.Combobox(target, textvariable=self.branch, width=22, state='readonly')
        self.branches.grid(row=0, column=4, sticky='ew')
        target.columnconfigure(1, weight=1)
        footer = ttk.Frame(body); footer.pack(side='bottom', fill='x')
        notebook = ttk.Notebook(body); notebook.pack(fill='both', expand=True, pady=10)
        upload_page = ttk.Frame(notebook, padding=8); tools_page = ttk.Frame(notebook, padding=8)
        notebook.add(upload_page, text='Find & upload'); notebook.add(tools_page, text='Repository tools')
        self.tools = ToolsPanel(self, tools_page)
        self.notebook = notebook
        upload_page.columnconfigure(0, weight=1); upload_page.rowconfigure(2, weight=1)
        search = ttk.LabelFrame(upload_page, text='Find local files', padding=10); search.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        ttk.Entry(search, textvariable=self.folder).grid(row=0, column=0, columnspan=3, sticky='ew')
        ttk.Button(search, text='Choose folder', command=self.choose_folder).grid(row=0, column=3, padx=(8, 0))
        ttk.Entry(search, textvariable=self.query).grid(row=1, column=0, sticky='ew', pady=(8, 0))
        ttk.Checkbutton(search, text='Search contents', variable=self.contents).grid(row=1, column=1, padx=8, pady=(8, 0))
        ttk.Checkbutton(search, text='Hidden files', variable=self.hidden).grid(row=1, column=2, pady=(8, 0))
        ttk.Button(search, text='Search', command=self.search).grid(row=1, column=3, sticky='ew', padx=(8, 0), pady=(8, 0))
        search.columnconfigure(0, weight=1)
        row = ttk.Frame(upload_page); row.grid(row=1, column=0, sticky='ew', pady=(0, 7))
        ttk.Button(row, text='Add files…', command=self.add_files).pack(side='left')
        ttk.Button(row, text='Select all', command=lambda: self.tree.selection_set(self.tree.get_children())).pack(side='left', padx=6)
        ttk.Button(row, text='Preview selected', command=self.preview).pack(side='left')
        ttk.Button(row, text='Clear', command=self.clear).pack(side='right')
        table = ttk.Frame(upload_page); table.grid(row=2, column=0, sticky='nsew')
        self.tree = ttk.Treeview(table, columns=('file', 'size', 'safety'), show='headings', selectmode='extended', height=5)
        for key, title, width in [('file','Local file',650),('size','Size',90),('safety','Status',130)]:
            self.tree.heading(key, text=title); self.tree.column(key, width=width)
        scrollbar = ttk.Scrollbar(table, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side='left', fill='both', expand=True); scrollbar.pack(side='right', fill='y')
        self.tree.bind('<Double-1>', lambda e: self.preview())
        options = ttk.Frame(upload_page); options.grid(row=3, column=0, sticky='ew', pady=8)
        ttk.Label(options, text='Destination folder').grid(row=0, column=0, sticky='w')
        ttk.Entry(options, textvariable=self.prefix).grid(row=0, column=1, sticky='ew', padx=8)
        ttk.Checkbutton(options, text='Keep search folder structure', variable=self.keep_paths).grid(row=0, column=2)
        ttk.Label(options, text='Existing files').grid(row=0, column=3, padx=(12, 4))
        ttk.Combobox(options, textvariable=self.collision, values=('skip','replace'), state='readonly', width=10).grid(row=0, column=4)
        ttk.Label(options, text='Commit message').grid(row=1, column=0, sticky='w', pady=(8,0))
        ttk.Entry(options, textvariable=self.message).grid(row=1, column=1, columnspan=4, sticky='ew', padx=8, pady=(8,0))
        options.columnconfigure(1, weight=1)
        batch = ttk.Frame(upload_page); batch.grid(row=4, column=0, sticky='ew', pady=(0, 8))
        ttk.Label(batch, text='Commit mode').pack(side='left')
        ttk.Combobox(batch, textvariable=self.mode, values=('atomic', 'per-file'), state='readonly', width=12).pack(side='left', padx=8)
        ttk.Checkbutton(batch, text='Remember queue on this device', variable=self.remember).pack(side='left')
        ttk.Button(batch, text='Resume saved batch', command=self.resume_queue).pack(side='left', padx=8)
        ttk.Button(batch, text='Forget saved batch', command=self.forget_queue).pack(side='left')
        actions = ttk.Frame(upload_page); actions.grid(row=5, column=0, sticky='ew')
        ttk.Button(actions, text='Review upload…', command=self.review).pack(side='left')
        ttk.Button(actions, text='Cancel operation', command=self.cancel.set).pack(side='left', padx=8)
        self.pause_button = ttk.Checkbutton(actions, text='Pause between files', variable=self.paused, command=self.toggle_pause, state='disabled')
        self.pause_button.pack(side='left')
        ttk.Button(actions, text='Open last result', command=self.open_last).pack(side='right')
        self.progress = ttk.Progressbar(footer, mode='determinate'); self.progress.pack(fill='x', pady=(10,5))
        ttk.Label(footer, textvariable=self.status, wraplength=1000).pack(anchor='w')
        self.log = tk.Text(footer, height=3, relief='flat', font=('Monospace', 9), state='disabled')
        self.activity = tk.BooleanVar(value=False)
        ttk.Checkbutton(footer, text='Show transfer activity', variable=self.activity, command=self.toggle_activity).pack(anchor='w')
        self.drain_timer = self.root.after(80, self.drain)
        root.protocol('WM_DELETE_WINDOW', self.close)

    def toggle_activity(self):
        if self.activity.get():
            self.log.pack(fill='x', pady=(8, 0)); self.root.minsize(1000, 840)
        else:
            self.log.pack_forget(); self.root.minsize(1000, 760)

    def record(self, text):
        self.status.set(text)
        self.log.configure(state='normal'); self.log.insert('end', text+'\n'); self.log.see('end'); self.log.configure(state='disabled')

    def run(self, label, work, done, on_error=None):
        if self.busy:
            self.record('An operation is running. Wait or cancel it first.')
            return
        self.busy = True; self.cancel.clear(); self.record(label)
        def worker():
            try:
                result = work()
                self.events.put(('done', done, result))
            except Exception as exc:
                self.events.put(('error', str(exc) if isinstance(exc, OctoShipError) else 'Operation failed. Check local access and GitHub state before retrying.', on_error))
        threading.Thread(target=worker, daemon=True).start()

    def drain(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == 'done':
                    self.busy = False; self.pause_button.configure(state='disabled'); event[1](event[2])
                elif event[0] == 'error':
                    self.busy = False; self.pause_button.configure(state='disabled'); self.record(event[1])
                    if event[2]: event[2](event[1])
                    messagebox.showerror('OctoShip', event[1])
                elif event[0] == 'progress':
                    self.progress['value'] = event[1]; self.record(event[2])
        except queue.Empty:
            pass
        self.drain_timer = self.root.after(80, self.drain)

    def connect(self):
        def work():
            api = GitHub.from_cli()
            return api, api.request('/user'), api.repositories()
        def done(result):
            self.api, user, repos = result
            self.repos['values'] = [r['full_name'] for r in repos]
            self.account.set(f"Connected as {user['login']} · {len(repos)} repositories")
            self.record('Connected. Choose a repository to load its branches.')
        self.run('Connecting to GitHub…', work, done)

    def load_branches(self):
        if not self.api:
            messagebox.showinfo('Connect first', 'Connect to your GitHub account first.'); return
        api, repo = self.api, self.repo.get().strip()
        def work():
            return api.request(api.repo_path(repo)), api.branches(repo)
        def done(result):
            meta, branches = result
            self.branches['values'] = [b['name'] for b in branches]
            self.branch.set(meta.get('default_branch', ''))
            self.record(f"{repo} · {meta.get('visibility', 'unknown')} · {len(branches)} branches")
        self.run('Loading branches…', work, done)

    def choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.folder.get())
        if folder: self.folder.set(folder)

    def show_files(self, files):
        self.restored_destinations = {}
        self.files = list(dict.fromkeys(files))
        self.tree.delete(*self.tree.get_children())
        for i, path in enumerate(self.files):
            try: size = f'{path.stat().st_size / 1024:.1f} KiB'
            except OSError: size = 'Unavailable'
            self.tree.insert('', 'end', iid=str(i), values=(str(path), size, 'Blocked' if sensitive(path) else 'Ready'))
        self.record(f'{len(files)} files listed (maximum 5,000 search results). Select files to upload.')

    def search(self):
        root = Path(self.folder.get()).expanduser()
        query, contents, hidden = self.query.get(), self.contents.get(), self.hidden.get()
        def done(files):
            self.search_root = root; self.show_files(files)
        self.run('Searching local files…', lambda: search_files(root, query, contents, hidden, self.cancel), done)

    def add_files(self):
        if self.busy: return
        paths = filedialog.askopenfilenames()
        if paths:
            self.search_root = None; self.show_files(self.files + [Path(p) for p in paths])

    def clear(self):
        if not self.busy: self.show_files([])

    def selected(self):
        return [self.files[int(i)] for i in self.tree.selection()]

    def preview(self):
        files = self.selected()
        if not files: return
        try: data = read_file(files[0])
        except OctoShipError as exc: messagebox.showerror('Preview', str(exc)); return
        win = tk.Toplevel(self.root); win.title(files[0].name); win.geometry('800x550')
        ttk.Label(win, text=f'{files[0].name}\n{len(data):,} bytes\nSHA-256: {hashlib.sha256(data).hexdigest()}', padding=12).pack(fill='x')
        text = tk.Text(win, wrap='word'); text.pack(fill='both', expand=True)
        preview = data[:65536].decode('utf-8', errors='replace') if b'\0' not in data[:8192] else '[Binary file — contents are not displayed]'
        text.insert('1.0', scan_bytes(data).summary + '\n\n' + preview); text.configure(state='disabled')

    def toggle_pause(self):
        if self.paused.get(): self.pause.set()
        else: self.pause.clear()

    def resume_queue(self):
        if self.busy: return
        repo, branch = self.repo.get().strip(), self.branch.get()
        def done(result):
            snapshot, pending = result
            self.show_files([Path(row['source']) for row in pending])
            self.restored_destinations = {row['source']: row['destination'] for row in pending}
            self.search_root = None; self.prefix.set('')
            self.message.set(snapshot['message']); self.mode.set(snapshot['mode'])
            self.remember.set(True); self.collision.set('skip')
            self.tree.selection_set(self.tree.get_children())
            uncertain = any(row['status'] in ('uploading', 'uncertain') for row in pending)
            self.record(f'{len(pending)} pending files restored. Fresh review required; existing files default to skip.')
            if uncertain:
                messagebox.showwarning('Check GitHub first', 'A previous upload may have completed. Inspect the branch before selecting replace or retrying.')
        self.run('Validating saved source files…', lambda: self.queue_store.resume(repo, branch), done)

    def forget_queue(self):
        if self.busy: return
        repo, branch = self.repo.get().strip(), self.branch.get()
        if not messagebox.askyesno('Forget saved batch', f'Delete the local saved queue for {repo} / {branch}?', default='no'): return
        try:
            self.queue_store.delete(repo, branch); self.remember.set(False)
            self.record('Saved queue removed. Local files and GitHub are unchanged.')
        except (OctoShipError, OSError) as exc: messagebox.showerror('Saved queue', str(exc))

    def review(self):
        if self.busy: return
        if not self.api: messagebox.showinfo('Connect first', 'Connect to GitHub first.'); return
        repo, branch, prefix = self.repo.get().strip(), self.branch.get(), self.prefix.get()
        files, api = self.selected(), self.api
        message = self.message.get().strip()
        if not message or len(message) > 250:
            messagebox.showerror('Commit message', 'Enter a commit message of 1–250 characters.'); return
        root = self.search_root if self.keep_paths.get() else None
        collision, mode, remember = self.collision.get(), self.mode.get(), self.remember.get()
        destinations = dict(self.restored_destinations)
        def work():
            flow.validate_branch(branch)
            reviewed_head = flow.head(api, repo, branch) if mode == 'atomic' else None
            result = plan_upload(api, repo, branch, files, prefix, root, collision, self.cancel,
                                 target_ref=reviewed_head, destinations=destinations)
            if reviewed_head:
                _, entries = flow.tree_at(api, repo, reviewed_head)
                flow.validate_destinations(result[1], entries)
            return result, reviewed_head
        def done(result):
            (meta, planned, skipped), reviewed_head = result
            self.record(f'Review ready: {len(planned)} uploads; {len(skipped)} existing files skipped.')
            if not planned: return
            win = tk.Toplevel(self.root); win.title('Review GitHub upload'); win.geometry('860x620'); win.transient(self.root); win.grab_set()
            commits = 'One atomic commit' if mode == 'atomic' else f'{len(planned)} individual commits'
            ttk.Label(win, text=f"{repo} · {meta.get('visibility', 'unknown').upper()} · branch {branch}\n{commits}. Message: {message}", padding=12).pack(fill='x')
            text = tk.Text(win, wrap='word'); text.pack(fill='both', expand=True, padx=12)
            if reviewed_head: text.insert('end', 'Reviewed branch commit: ' + reviewed_head + '\n\n')
            for item in planned:
                text.insert('end', f"{'REPLACE' if item.sha else 'CREATE'}  {item.destination}  ({item.size:,} bytes)\nSHA-256: {item.digest}\n{item.scan.summary}\n\n")
            for path in skipped: text.insert('end', f'SKIP  {path}\n')
            text.configure(state='disabled')
            description = ('The branch advances once after all files are prepared. Branch conflicts stop publication.' if mode == 'atomic'
                           else 'Pause/cancel stops before the next file. Completed commits remain.')
            ttk.Label(win, text=description, padding=12).pack(fill='x')
            acknowledged = tk.BooleanVar(value=False)
            risk = any(item.scan.needs_review for item in planned)
            def confirm():
                if risk and not acknowledged.get(): return
                win.destroy()
                self.upload(api, repo, branch, planned, message, mode, reviewed_head, remember, risk)
            button = ttk.Button(win, text='Upload these files', command=confirm, state='disabled' if risk else 'normal')
            if risk:
                ttk.Checkbutton(win, text='I reviewed the findings and unscanned files and approve uploading them.', variable=acknowledged,
                                command=lambda: button.configure(state='normal' if acknowledged.get() else 'disabled')).pack(anchor='w', padx=12)
            button.pack(side='right', padx=12, pady=12)
            ttk.Button(win, text='Back', command=win.destroy).pack(side='right', pady=12)
        self.run('Checking permissions, destinations, and content…', work, done)

    def upload(self, api, repo, branch, planned, message, mode='per-file', reviewed_head=None, remember=False, approved=False):
        self.progress['maximum'] = len(planned); self.progress['value'] = 0
        self.paused.set(False); self.pause.clear()
        self.pause_button.configure(state='normal' if mode == 'per-file' else 'disabled')
        snapshot = self.queue_store.snapshot(repo, branch, mode, message, planned)
        def save():
            if remember: self.queue_store.save(snapshot)
        def progress(value, text): self.events.put(('progress', value, text))
        def work():
            save()
            if mode == 'atomic':
                for row in snapshot['entries']: row['status'] = 'uploading'
                save()
                try:
                    url = flow.atomic_upload(api, repo, branch, planned, message, reviewed_head, approved, self.cancel, progress)
                except OctoShipError:
                    for row in snapshot['entries']: row['status'] = 'uncertain'
                    save()
                    raise
                for row in snapshot['entries']: row['status'] = 'uploaded'
                save()
                progress(len(planned), 'Atomic batch published.')
                return len(planned), [], url, False
            completed, failed, last_url = 0, [], None
            for index, item in enumerate(planned):
                while self.pause.is_set() and not self.cancel.wait(0.1): pass
                if self.cancel.is_set(): break
                row = snapshot['entries'][index]; row['status'] = 'uploading'; save()
                try:
                    result = api.upload(repo, branch, item, message, approved)
                    completed += 1; row['status'] = 'uploaded'
                    last_url = result.get('content', {}).get('html_url') or last_url
                    progress(index+1, f'Uploaded {item.destination}')
                except OctoShipError as exc:
                    row['status'] = 'uncertain'
                    failed.append(f'{item.destination}: {exc}')
                    progress(index+1, f'Failed {item.destination}: {exc}')
                    # A lost response may represent a completed write. Stop and re-review.
                    save(); break
                save()
            return completed, failed, last_url, self.cancel.is_set()
        def done(result):
            completed, failed, url, cancelled = result
            self.last_url = url or self.last_url
            summary = f'{completed} uploaded, {len(failed)} failed' + ('; cancelled.' if cancelled else '.')
            self.record(summary)
            if failed: messagebox.showerror('Upload results', summary+'\n\n'+'\n'.join(failed) + '\nInspect GitHub before retrying.')
        self.run('Uploading reviewed files…', work, done)

    def open_last(self):
        if self.last_url and self.last_url.startswith('https://github.com/'):
            webbrowser.open(self.last_url)

    def close(self):
        if self.busy:
            if not messagebox.askyesno('Operation running', 'Cancel and close? A request already sent to GitHub may still finish.'):
                return
            self.cancel.set()
        self.root.after_cancel(self.drain_timer)
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description='OctoShip Linux desktop client')
    parser.add_argument('--smoke-test', action='store_true', help='Build the GUI and exit without network calls')
    args = parser.parse_args()
    lock_root = Path(os.environ.get('XDG_RUNTIME_DIR', str(Path.home() / '.cache'))) / 'octoship'
    lock_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (lock_root / 'instance.lock').open('w') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('OctoShip is already running.'); return
        root = tk.Tk(); app = App(root)
        if args.smoke_test: root.after(500, root.destroy)
        root.mainloop()

if __name__ == '__main__':
    main()
