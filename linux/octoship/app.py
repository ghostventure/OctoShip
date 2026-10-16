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
from .content_types import detect_content_kind, extension_mismatch, is_known_binary
from .editor import open_in_vscode
from .scanner import scan_bytes
from .queue_store import QueueStore
from . import workflows as flow
from .tools_ui import ToolsPanel
from .theme import apply_dark_theme
from . import theme
from .workbench_ui import WorkbenchPanel

class App:
    def __init__(self, root, queue_store=None):
        self.root = root
        self.session = None
        self.persist_workspace = False
        self.pending_reconnect = False
        root.title(f'OctoShip for GitHub — Linux {__version__}')
        root.geometry('1320x900')
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
        shell = ttk.Frame(root); shell.pack(fill='both', expand=True)
        self.sidebar = ttk.Frame(shell, style='Sidebar.TFrame', width=192, padding=(14,24))
        self.sidebar.pack(side='left', fill='y'); self.sidebar.pack_propagate(False)
        self.brand = ttk.Label(self.sidebar, text='OctoShip', style='Brand.TLabel')
        self.brand.pack(anchor='w', padx=8, pady=(0,5))
        self.brand_hint = ttk.Label(self.sidebar, text='YOUR GITHUB WORKSPACE', style='Sidebar.TLabel', font=(theme.FONT,8))
        self.brand_hint.pack(anchor='w', padx=8)
        ttk.Frame(self.sidebar, height=36, style='Sidebar.TFrame').pack()
        self.nav_buttons=[]
        for index, name in enumerate(('Files & upload', 'Repository tools', 'Ship & inspect')):
            button=ttk.Button(self.sidebar, text=name, style='Nav.TButton', command=lambda i=index: self.notebook.select(i))
            button.pack(fill='x', pady=4); self.nav_buttons.append(button)
        self.sidebar_version=ttk.Label(self.sidebar,text='LINUX  '+__version__,style='Sidebar.TLabel',font=(theme.FONT,9))
        self.sidebar_version.pack(side='bottom',anchor='w',padx=8)
        self.sidebar_note=ttk.Label(self.sidebar,text='Local files.\nThoughtful delivery.',style='Sidebar.TLabel',font=(theme.FONT,10))
        self.sidebar_note.pack(side='bottom',anchor='w',padx=8,pady=(0,18))
        body = ttk.Frame(shell, padding=(24,22,24,14)); body.pack(fill='both', expand=True)
        header = ttk.Frame(body); header.pack(fill='x', pady=(0,10))
        heading=ttk.Frame(header); heading.pack(side='left',fill='x',expand=True)
        self.page_title=tk.StringVar(value='Files & upload')
        self.page_subtitle=tk.StringVar(value='Find the right files. Review every change. Ship with confidence.')
        ttk.Label(heading,textvariable=self.page_title,style='Title.TLabel').pack(anchor='w')
        self.subtitle=ttk.Label(heading,textvariable=self.page_subtitle,style='Muted.TLabel',wraplength=570)
        self.subtitle.pack(anchor='w',pady=(5,0))
        account_controls=ttk.Frame(header); account_controls.pack(side='right',anchor='n',padx=(12,0))
        ttk.Button(account_controls,text='Connect / Refresh',command=self.connect).pack(side='right')
        ttk.Button(account_controls,text='Sign in…',style='Ghost.TButton',command=lambda: messagebox.showinfo('GitHub sign-in',login_instructions(),parent=root)).pack(side='right',padx=(0,6))
        self.account_label=ttk.Label(body,textvariable=self.account,style='Muted.TLabel')
        self.account_label.pack(anchor='w',pady=(0,10))
        target = ttk.LabelFrame(body, text='DESTINATION', padding=10); target.pack(fill='x')
        ttk.Label(target, text='Repository').grid(row=0, column=0, sticky='w')
        self.repos = ttk.Combobox(target, textvariable=self.repo, width=24)
        self.repos.grid(row=0, column=1, sticky='ew', padx=8)
        self.repos.bind('<<ComboboxSelected>>', lambda e: self.load_branches())
        ttk.Button(target, text='Load branches', command=self.load_branches).grid(row=0, column=2)
        ttk.Label(target, text='Branch').grid(row=0, column=3, padx=(12, 4))
        self.branches = ttk.Combobox(target, textvariable=self.branch, width=15, state='readonly')
        self.branches.grid(row=0, column=4, sticky='ew')
        target.columnconfigure(1, weight=1)
        footer = ttk.Frame(body); footer.pack(side='bottom', fill='x')
        notebook = ttk.Notebook(body,style='Workspace.TNotebook'); notebook.pack(fill='both', expand=True, pady=(10,0))
        upload_page = ttk.Frame(notebook, padding=0); tools_page = ttk.Frame(notebook, padding=0)
        notebook.add(upload_page, text='Find & upload'); notebook.add(tools_page, text='Repository tools')
        self.tools = ToolsPanel(self, tools_page)
        workbench_page = ttk.Frame(notebook, padding=0)
        notebook.add(workbench_page, text="Shipping workbench")
        self.workbench = WorkbenchPanel(self, workbench_page)
        self.notebook = notebook
        notebook.bind('<<NotebookTabChanged>>', self.update_navigation)
        root.bind('<Configure>', self.responsive_sidebar, add='+')
        for index in range(3): root.bind(f'<Control-Key-{index+1}>', lambda e,i=index: notebook.select(i), add='+')
        self.update_navigation()
        upload_page.columnconfigure(0, weight=1); upload_page.rowconfigure(2, weight=1)
        search = ttk.LabelFrame(upload_page, text='FIND LOCAL FILES', padding=10); search.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        ttk.Entry(search, textvariable=self.folder).grid(row=0, column=0, columnspan=3, sticky='ew')
        ttk.Button(search, text='Choose folder', command=self.choose_folder).grid(row=0, column=3, padx=(8, 0))
        ttk.Button(search, text='Open folder in VS Code', command=self.open_folder_code).grid(row=0, column=4, padx=(8, 0))
        ttk.Entry(search, textvariable=self.query).grid(row=1, column=0, sticky='ew', pady=(8, 0))
        ttk.Checkbutton(search, text='Search contents', variable=self.contents).grid(row=1, column=1, padx=8, pady=(8, 0))
        ttk.Checkbutton(search, text='Hidden files', variable=self.hidden).grid(row=1, column=2, pady=(8, 0))
        ttk.Button(search, text='Search', style='Primary.TButton', command=self.search).grid(row=1, column=3, sticky='ew', padx=(8, 0), pady=(8, 0))
        search.columnconfigure(0, weight=1)
        row = ttk.Frame(upload_page); row.grid(row=1, column=0, sticky='ew', pady=(2,8))
        ttk.Button(row, text='Add files…', command=self.add_files).pack(side='left')
        ttk.Button(row, text='Select all', command=self.select_all).pack(side='left', padx=6)
        ttk.Button(row, text='Preview selected', command=self.preview).pack(side='left')
        self.open_file_code_button = ttk.Button(row, text='Open in VS Code', command=self.open_selected_code, state='disabled')
        self.open_file_code_button.pack(side='left', padx=6)
        ttk.Button(row, text='Clear', style='Ghost.TButton', command=self.clear).pack(side='right')
        self.file_count=tk.StringVar(value='0 files')
        ttk.Label(row,textvariable=self.file_count,style='Muted.TLabel').pack(side='right',padx=12)
        table = ttk.Frame(upload_page); table.grid(row=2, column=0, sticky='nsew')
        self.tree = ttk.Treeview(table, columns=('file', 'size', 'safety'), show='headings', selectmode='extended', height=5)
        for key, title, width in [('file','LOCAL FILE',480),('size','SIZE',90),('safety','STATUS',110)]:
            self.tree.heading(key, text=title); self.tree.column(key, width=width, minwidth=60, stretch=(key=='file'))
        scrollbar = ttk.Scrollbar(table, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side='left', fill='both', expand=True); scrollbar.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self.update_editor_buttons)
        self.tree.bind('<Double-1>', lambda e: self.preview())
        self.tree.tag_configure('even',background=theme.SURFACE)
        self.tree.tag_configure('odd',background='#1d212b')
        self.empty_state=ttk.Frame(table,style='Empty.TFrame',padding=4)
        style=ttk.Style(root); style.configure('Empty.TFrame',background=theme.SURFACE)
        style.configure('Empty.TLabel',background=theme.SURFACE,foreground=theme.TEXT,font=(theme.FONT,12,'bold'))
        style.configure('EmptyHint.TLabel',background=theme.SURFACE,foreground=theme.MUTED,font=(theme.FONT,10))
        ttk.Label(self.empty_state,text='Your next shipment starts here',style='Empty.TLabel').pack()
        ttk.Label(self.empty_state,text='Search a folder or add files to begin your review.',style='EmptyHint.TLabel').pack(pady=(4,0))
        self.empty_state.place(relx=.5,rely=.5,y=18,anchor='center')

        options = ttk.Frame(upload_page); options.grid(row=3, column=0, sticky='ew', pady=8)
        ttk.Label(options, text='Destination folder').grid(row=0, column=0, sticky='w')
        ttk.Entry(options, textvariable=self.prefix).grid(row=0, column=1, sticky='ew', padx=8)
        ttk.Checkbutton(options, text='Keep search folder structure', variable=self.keep_paths).grid(row=0, column=2)
        ttk.Label(options, text='Existing files').grid(row=0, column=3, padx=(12, 4))
        ttk.Combobox(options, textvariable=self.collision, values=('skip','replace'), state='readonly', width=10).grid(row=0, column=4)
        ttk.Label(options, text='Commit message').grid(row=1, column=0, sticky='w', pady=(8,0))
        ttk.Entry(options, textvariable=self.message).grid(row=1, column=1, columnspan=4, sticky='ew', padx=8, pady=(8,0))
        options.columnconfigure(1, weight=1)
        batch = ttk.Frame(upload_page); batch.grid(row=4, column=0, sticky='ew', pady=(0,8))
        self.batch_options=batch; self.settings_open=False
        ttk.Label(batch, text='Commit mode').pack(side='left')
        ttk.Combobox(batch, textvariable=self.mode, values=('atomic', 'per-file'), state='readonly', width=12).pack(side='left', padx=8)
        ttk.Checkbutton(batch, text='Remember queue on this device', variable=self.remember).pack(side='left')
        ttk.Button(batch, text='Resume saved batch', command=self.resume_queue).pack(side='left', padx=8)
        ttk.Button(batch, text='Forget saved batch', command=self.forget_queue).pack(side='left')
        batch.grid_remove()
        actions = ttk.Frame(upload_page); actions.grid(row=5, column=0, sticky='ew')
        ttk.Button(actions, text='Review upload…', style='Primary.TButton', command=self.review).pack(side='right')
        ttk.Button(actions,text='Upload settings',style='Ghost.TButton',command=self.toggle_upload_settings).pack(side='left')
        ttk.Button(actions, text='Cancel operation', style='Ghost.TButton', command=self.cancel.set).pack(side='left', padx=8)
        self.pause_button = ttk.Checkbutton(actions, text='Pause between files', variable=self.paused, command=self.toggle_pause, state='disabled')
        self.pause_button.pack(side='left')
        ttk.Button(actions, text='Open last result', style='Ghost.TButton', command=self.open_last).pack(side='right',padx=8)
        progress_track = ttk.Frame(footer, height=3)
        progress_track.pack(fill='x', pady=(12,8)); progress_track.pack_propagate(False)
        self.progress = ttk.Progressbar(progress_track, mode='determinate')
        self.progress.place(relwidth=1, relheight=1)
        ttk.Label(footer, textvariable=self.status, style='Muted.TLabel', wraplength=1000).pack(anchor='w')
        self.log = tk.Text(footer, height=3, relief='flat', font=('Monospace', 9), state='disabled')
        self.activity = tk.BooleanVar(value=False)
        ttk.Checkbutton(footer, text='Show transfer activity', variable=self.activity, command=self.toggle_activity).pack(anchor='w')
        self.drain_timer = self.root.after(80, self.drain)
        root.protocol('WM_DELETE_WINDOW', self.close)

    def update_navigation(self, event=None):
        index=self.notebook.index(self.notebook.select())
        names=('Files & upload','Repository tools','Shipping workbench')
        subtitles=('Find the right files. Review every change. Ship with confidence.',
                   'Compare your project, manage branches, and prepare releases.',
                   'Prepare, inspect, and deliver your next project update.')
        self.page_title.set(names[index]); self.page_subtitle.set(subtitles[index])
        for i,button in enumerate(self.nav_buttons): button.configure(style='Active.Nav.TButton' if i==index else 'Nav.TButton')

    def responsive_sidebar(self, event):
        if event.widget is not self.root: return
        compact=event.width<1200
        self.sidebar.configure(width=88 if compact else 192,padding=(8 if compact else 14,24))
        self.brand.configure(text='OS' if compact else 'OctoShip')
        self.brand_hint.configure(text='' if compact else 'YOUR GITHUB WORKSPACE')
        self.sidebar_note.configure(text='' if compact else 'Local files.\nThoughtful delivery.')
        self.sidebar_version.configure(text=__version__ if compact else 'LINUX  '+__version__)
        for button,name in zip(self.nav_buttons,('Files','Repos','Ship') if compact else ('Files & upload','Repository tools','Ship & inspect')):
            button.configure(text=name)
        self.subtitle.configure(wraplength=max(240,event.width-(88 if compact else 192)-360))

    def toggle_upload_settings(self):
        self.settings_open=not self.settings_open
        if self.settings_open: self.batch_options.grid()
        else: self.batch_options.grid_remove()

    def toggle_activity(self):
        if self.activity.get():
            self.log.pack(fill='x', pady=(8, 0)); self.root.minsize(1000, 840)
        else:
            self.log.pack_forget(); self.root.minsize(1000, 760)

    def record(self, text):
        self.status.set(text)
        self.log.configure(state='normal'); self.log.insert('end', text+'\n'); self.log.see('end'); self.log.configure(state='disabled')

    def run(self, label, work, done, on_error=None):
        if self.session and self.session.state.check():
            self.session.shield(); return
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
        # Keep completed callbacks and their potentially sensitive windows hidden until unlock.
        if self.session and self.session.state.check():
            self.session.shield()
            self.drain_timer = self.root.after(80, self.drain)
            return
        if self.pending_reconnect and not self.busy:
            self.pending_reconnect = False
            self.connect()
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
            if self.session: api.guard = self.session.state.guard
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
            self.tree.insert('', 'end', iid=str(i), values=(str(path), size, 'Blocked' if sensitive(path) else 'Ready'),tags=('odd' if i%2 else 'even',))
        self.file_count.set(f'{len(self.files)} files')
        self.update_editor_buttons()
        if self.files: self.empty_state.place_forget()
        else: self.empty_state.place(relx=.5,rely=.5,y=18,anchor='center')
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

    def select_all(self):
        self.tree.selection_set(self.tree.get_children())
        self.update_editor_buttons()

    def update_editor_buttons(self, event=None):
        if hasattr(self, 'open_file_code_button'):
            self.open_file_code_button.configure(state='normal' if len(self.tree.selection()) == 1 else 'disabled')

    def open_selected_code(self):
        files = self.selected()
        if len(files) != 1:
            messagebox.showinfo('Open in VS Code', 'Select one file first.', parent=self.root)
            return
        try:
            open_in_vscode(files[0])
            self.record('Opened ' + files[0].name + ' in VS Code.')
        except (OctoShipError, OSError) as exc:
            messagebox.showerror('Open in VS Code', str(exc), parent=self.root)

    def open_folder_code(self):
        try:
            open_in_vscode(self.folder.get())
            self.record('Opened the selected folder in VS Code.')
        except (OctoShipError, OSError) as exc:
            messagebox.showerror('Open folder in VS Code', str(exc), parent=self.root)

    def preview(self):
        files = self.selected()
        if not files: return
        try: data = read_file(files[0])
        except OctoShipError as exc: messagebox.showerror('Preview', str(exc)); return
        win = tk.Toplevel(self.root); win.title(files[0].name); win.geometry('800x550')
        kind = detect_content_kind(data[:8192])
        mismatch = extension_mismatch(files[0].name, kind)
        details = f'{files[0].name}\n{len(data):,} bytes · detected {kind}\nSHA-256: {hashlib.sha256(data).hexdigest()}'
        if mismatch:
            details += '\nWarning: ' + mismatch
        ttk.Label(win, text=details, padding=12, wraplength=760).pack(fill='x')
        text = tk.Text(win, wrap='word'); text.pack(fill='both', expand=True)
        preview = ('[Binary ' + kind + ' — contents are not displayed]'
                   if is_known_binary(kind) else data[:65536].decode('utf-8', errors='replace'))
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
        if self.persist_workspace:
            try: self.workbench.persist_preferences()
            except OSError: pass
        if self.busy:
            if not messagebox.askyesno('Operation running', 'Cancel and close? A request already sent to GitHub may still finish.'):
                return
            self.cancel.set()
        if self.session: self.session.close()
        self.root.after_cancel(self.drain_timer)
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description='OctoShip Linux desktop client')
    parser.add_argument('--smoke-test', action='store_true', help='Build the GUI and exit without network calls')
    parser.add_argument('--doctor', action='store_true', help='Print offline environment diagnostics and exit')
    parser.add_argument('--doctor-format', choices=('text', 'json'), default='text', help='Select environment diagnostics output format')
    args = parser.parse_args()
    if args.doctor:
        from .diagnostics import environment_report, format_report
        print(format_report(environment_report(), args.doctor_format))
        return
    lock_root = Path(os.environ.get('XDG_RUNTIME_DIR', str(Path.home() / '.cache'))) / 'octoship'
    lock_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (lock_root / 'instance.lock').open('w') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('OctoShip is already running.'); return
        root = tk.Tk(); app = App(root)
        if not args.smoke_test:
            from .session import SessionController
            app.persist_workspace = True
            app.workbench.restore_preferences()
            app.session = SessionController(app)
            app.pending_reconnect = app.workbench.reconnect.get()
            def save_focus(event):
                if event.widget is root:
                    try: app.workbench.persist_preferences()
                    except OSError: pass
            root.bind('<FocusOut>', save_focus, add='+')
        if args.smoke_test: root.after(500, root.destroy)
        root.mainloop()

if __name__ == '__main__':
    main()
