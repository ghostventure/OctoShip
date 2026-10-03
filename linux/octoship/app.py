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
from .core import GitHub, OctoShipError, search_files, plan_upload, read_file, sensitive

class App:
    def __init__(self, root):
        self.root = root
        root.title('OctoShip for GitHub — Linux')
        root.geometry('1100x790')
        root.minsize(1100, 790)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.api = None
        self.files = []
        self.search_root = None
        self.last_url = None
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
        self.account = tk.StringVar(value='Connect using your GitHub CLI account')
        self.status = tk.StringVar(value='Ready. Sign in with gh auth login, then connect.')
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('TFrame', background='#f1f5f9')
        style.configure('TLabel', background='#f1f5f9', foreground='#172033')
        style.configure('Header.TLabel', font=('Sans', 23, 'bold'))
        style.configure('TButton', padding=7)
        style.configure('Treeview', rowheight=26)
        body = ttk.Frame(root, padding=20)
        body.pack(fill='both', expand=True)
        header = ttk.Frame(body); header.pack(fill='x')
        ttk.Label(header, text='OctoShip', style='Header.TLabel').pack(side='left')
        ttk.Label(header, text='  for GitHub · Linux', font=('Sans', 12)).pack(side='left', pady=9)
        ttk.Button(header, text='Connect / Refresh', command=self.connect).pack(side='right')
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
        search = ttk.LabelFrame(body, text='Find local files', padding=10); search.pack(fill='x', pady=10)
        ttk.Entry(search, textvariable=self.folder).grid(row=0, column=0, columnspan=3, sticky='ew')
        ttk.Button(search, text='Choose folder', command=self.choose_folder).grid(row=0, column=3, padx=(8, 0))
        ttk.Entry(search, textvariable=self.query).grid(row=1, column=0, sticky='ew', pady=(8, 0))
        ttk.Checkbutton(search, text='Search contents', variable=self.contents).grid(row=1, column=1, padx=8, pady=(8, 0))
        ttk.Checkbutton(search, text='Hidden files', variable=self.hidden).grid(row=1, column=2, pady=(8, 0))
        ttk.Button(search, text='Search', command=self.search).grid(row=1, column=3, sticky='ew', padx=(8, 0), pady=(8, 0))
        search.columnconfigure(0, weight=1)
        row = ttk.Frame(body); row.pack(fill='x', pady=(0, 7))
        ttk.Button(row, text='Add files…', command=self.add_files).pack(side='left')
        ttk.Button(row, text='Select all', command=lambda: self.tree.selection_set(self.tree.get_children())).pack(side='left', padx=6)
        ttk.Button(row, text='Preview selected', command=self.preview).pack(side='left')
        ttk.Button(row, text='Clear', command=self.clear).pack(side='right')
        table = ttk.Frame(body); table.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(table, columns=('file', 'size', 'safety'), show='headings', selectmode='extended', height=5)
        for key, title, width in [('file','Local file',650),('size','Size',90),('safety','Status',130)]:
            self.tree.heading(key, text=title); self.tree.column(key, width=width)
        scrollbar = ttk.Scrollbar(table, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side='left', fill='both', expand=True); scrollbar.pack(side='right', fill='y')
        self.tree.bind('<Double-1>', lambda e: self.preview())
        options = ttk.Frame(body); options.pack(fill='x', pady=10)
        ttk.Label(options, text='Destination folder').grid(row=0, column=0, sticky='w')
        ttk.Entry(options, textvariable=self.prefix).grid(row=0, column=1, sticky='ew', padx=8)
        ttk.Checkbutton(options, text='Keep search folder structure', variable=self.keep_paths).grid(row=0, column=2)
        ttk.Label(options, text='Existing files').grid(row=0, column=3, padx=(12, 4))
        ttk.Combobox(options, textvariable=self.collision, values=('skip','replace'), state='readonly', width=10).grid(row=0, column=4)
        ttk.Label(options, text='Commit message').grid(row=1, column=0, sticky='w', pady=(8,0))
        ttk.Entry(options, textvariable=self.message).grid(row=1, column=1, columnspan=4, sticky='ew', padx=8, pady=(8,0))
        options.columnconfigure(1, weight=1)
        actions = ttk.Frame(body); actions.pack(fill='x')
        ttk.Button(actions, text='Review upload…', command=self.review).pack(side='left')
        ttk.Button(actions, text='Cancel operation', command=self.cancel.set).pack(side='left', padx=8)
        ttk.Button(actions, text='Open last upload', command=self.open_last).pack(side='right')
        self.progress = ttk.Progressbar(body, mode='determinate'); self.progress.pack(fill='x', pady=(10,5))
        ttk.Label(body, textvariable=self.status, wraplength=1000).pack(anchor='w')
        self.log = tk.Text(body, height=3, bg='#182235', fg='#dce7f5', relief='flat', font=('Monospace', 9), state='disabled')
        self.log.pack(fill='x', pady=(8,0))
        self.root.after(80, self.drain)
        root.protocol('WM_DELETE_WINDOW', self.close)

    def record(self, text):
        self.status.set(text)
        self.log.configure(state='normal'); self.log.insert('end', text+'\n'); self.log.see('end'); self.log.configure(state='disabled')

    def run(self, label, work, done):
        if self.busy:
            self.record('An operation is running. Wait or cancel it first.')
            return
        self.busy = True; self.cancel.clear(); self.record(label)
        def worker():
            try:
                result = work()
                self.events.put(('done', done, result))
            except Exception as exc:
                self.events.put(('error', str(exc) if isinstance(exc, (OctoShipError, OSError, ValueError)) else 'Operation failed. Please retry.'))
        threading.Thread(target=worker, daemon=True).start()

    def drain(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == 'done':
                    self.busy = False; event[1](event[2])
                elif event[0] == 'error':
                    self.busy = False; self.record(event[1]); messagebox.showerror('OctoShip', event[1])
                elif event[0] == 'progress':
                    self.progress['value'] = event[1]; self.record(event[2])
        except queue.Empty:
            pass
        self.root.after(80, self.drain)

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
        text.insert('1.0', preview); text.configure(state='disabled')

    def review(self):
        if not self.api: messagebox.showinfo('Connect first', 'Connect to GitHub first.'); return
        repo, branch, prefix = self.repo.get().strip(), self.branch.get(), self.prefix.get()
        files, api = self.selected(), self.api
        message = self.message.get().strip()
        if not message: messagebox.showerror('Commit message', 'Enter a commit message.'); return
        root = self.search_root if self.keep_paths.get() else None
        collision = self.collision.get()
        def work():
            return plan_upload(api, repo, branch, files, prefix, root, collision, self.cancel)
        def done(result):
            meta, planned, skipped = result
            self.record(f'Review ready: {len(planned)} uploads; {len(skipped)} existing files skipped.')
            if not planned: return
            win = tk.Toplevel(self.root); win.title('Review GitHub upload'); win.geometry('820x540'); win.transient(self.root); win.grab_set()
            ttk.Label(win, text=f"{repo} · {meta.get('visibility', 'unknown').upper()} · branch {branch}\n{len(planned)} commits will be created. Commit message: {message}", padding=12).pack(fill='x')
            text = tk.Text(win, wrap='word'); text.pack(fill='both', expand=True, padx=12)
            for item in planned:
                text.insert('end', f"{'REPLACE' if item.sha else 'CREATE'}  {item.destination}  ({item.size:,} bytes)\n")
            for path in skipped: text.insert('end', f'SKIP  {path}\n')
            text.configure(state='disabled')
            ttk.Label(win, text='Uploads are individual commits. Cancel stops before the next file; completed commits remain.', padding=12).pack(fill='x')
            ttk.Button(win, text='Upload these files', command=lambda: (win.destroy(), self.upload(api, repo, branch, planned, message))).pack(side='right', padx=12, pady=12)
            ttk.Button(win, text='Back', command=win.destroy).pack(side='right', pady=12)
        self.run('Checking permissions, destinations, and local files…', work, done)

    def upload(self, api, repo, branch, planned, message):
        self.progress['maximum'] = len(planned); self.progress['value'] = 0
        def work():
            completed, failed, last_url = 0, [], None
            for index, item in enumerate(planned):
                if self.cancel.is_set(): break
                try:
                    result = api.upload(repo, branch, item, message)
                    completed += 1
                    last_url = result.get('content', {}).get('html_url') or last_url
                    self.events.put(('progress', index+1, f'Uploaded {item.destination}'))
                except OctoShipError as exc:
                    failed.append(f'{item.destination}: {exc}')
                    self.events.put(('progress', index+1, f'Failed {item.destination}: {exc}'))
            return completed, failed, last_url, self.cancel.is_set()
        def done(result):
            completed, failed, url, cancelled = result
            self.last_url = url or self.last_url
            summary = f'{completed} uploaded, {len(failed)} failed' + ('; cancelled.' if cancelled else '.')
            self.record(summary)
            if failed: messagebox.showerror('Upload results', summary+'\n\n'+'\n'.join(failed))
        self.run('Uploading reviewed files…', work, done)

    def open_last(self):
        if self.last_url and self.last_url.startswith('https://github.com/'):
            webbrowser.open(self.last_url)

    def close(self):
        if self.busy:
            if not messagebox.askyesno('Operation running', 'Cancel and close? A request already sent to GitHub may still finish.'):
                return
            self.cancel.set()
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
