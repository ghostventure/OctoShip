"""Native repository tools. Opening tabs never sends GitHub requests."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .core import OctoShipError
from .scanner import scan_bytes, check_cancel
from . import workflows as flow


def field(parent, label, value='', row=0):
    variable = tk.StringVar(value=value)
    ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=5)
    entry = ttk.Entry(parent, textvariable=variable)
    entry.grid(row=row, column=1, sticky='ew', pady=5)
    parent.columnconfigure(1, weight=1)
    return variable


def text_box(parent, height=8):
    box = tk.Text(parent, height=height, wrap='word', font=('Sans', 11))
    box.pack(fill='both', expand=True, pady=8)
    return box


class ToolsPanel:
    def __init__(self, app, parent):
        self.app = app
        self.release = None
        self.release_context = None
        self.assets_ready = True
        self.tabs = ttk.Notebook(parent)
        self.tabs.pack(fill='both', expand=True)
        compare, branches, pulls, releases = [ttk.Frame(self.tabs, padding=16) for _ in range(4)]
        for tab, name in zip((compare, branches, pulls, releases), ('Compare folders', 'Branches', 'Pull requests', 'Releases')):
            self.tabs.add(tab, text=name)
        ttk.Label(compare, text='Compare local bytes against one fixed GitHub commit. This does not change either folder.').pack(anchor='w')
        form = ttk.Frame(compare); form.pack(fill='x', pady=8)
        self.local = field(form, 'Local folder', str(Path.home()), 0)
        self.remote = field(form, 'Repository folder', '', 1)
        row = ttk.Frame(compare); row.pack(fill='x')
        ttk.Button(row, text='Choose local folder…', command=self.choose_local).pack(side='left')
        ttk.Button(row, text='Compare folders', command=self.compare).pack(side='left', padx=8)
        self.comparison = text_box(compare)
        self.comparison.configure(state='disabled')

        ttk.Label(branches, text='Create a branch from the selected source branch after reviewing its commit.').pack(anchor='w')
        form = ttk.Frame(branches); form.pack(fill='x', pady=12)
        self.new_branch = field(form, 'New branch')
        ttk.Button(branches, text='Review new branch…', command=self.branch).pack(anchor='w')

        ttk.Label(pulls, text='The selected destination branch above is the PR head branch.').pack(anchor='w')
        form = ttk.Frame(pulls); form.pack(fill='x', pady=8)
        self.base = field(form, 'Base branch', 'main', 0)
        self.pr_title = field(form, 'Title', '', 1)
        self.draft = tk.BooleanVar(value=True)
        ttk.Checkbutton(pulls, text='Create as draft', variable=self.draft).pack(anchor='w')
        ttk.Label(pulls, text='Description').pack(anchor='w', pady=(8, 0))
        self.pr_body = text_box(pulls, 6)
        ttk.Button(pulls, text='Review pull request…', command=self.pull_request).pack(anchor='w')

        ttk.Label(releases, text='Create a draft, attach reviewed assets, then publish separately. Existing tags retain their commit.').pack(anchor='w')
        form = ttk.Frame(releases); form.pack(fill='x', pady=4)
        self.tag = field(form, 'Tag', '', 0)
        self.release_title = field(form, 'Title', '', 1)
        self.prerelease = tk.BooleanVar()
        ttk.Checkbutton(releases, text='Pre-release', variable=self.prerelease).pack(anchor='w')
        ttk.Label(releases, text='Release notes').pack(anchor='w')
        self.notes = text_box(releases, 4)
        row = ttk.Frame(releases); row.pack(fill='x')
        self.create_button = ttk.Button(row, text='Create draft…', command=self.create_release)
        self.create_button.pack(side='left')
        self.asset_button = ttk.Button(row, text='Attach assets…', command=self.attach_assets, state='disabled')
        self.asset_button.pack(side='left', padx=6)
        self.publish_button = ttk.Button(row, text='Publish release…', command=self.publish, state='disabled')
        self.publish_button.pack(side='left')
        recovery = ttk.Frame(releases); recovery.pack(fill='x', pady=8)
        self.identity = field(recovery, 'Existing draft ID')
        ttk.Button(recovery, text='Load / refresh draft', command=self.load_release).grid(row=0, column=2, padx=8)
        self.release_status = tk.StringVar(value='No draft loaded. Draft ID can be recovered from GitHub’s release API.')
        ttk.Label(releases, textvariable=self.release_status, wraplength=850).pack(anchor='w', pady=4)

    def context(self):
        if self.app.busy: return None
        if not self.app.api:
            messagebox.showinfo('Connect first', 'Connect to GitHub first.'); return None
        api, repo, branch = self.app.api, self.app.repo.get().strip(), self.app.branch.get()
        try:
            api.repo_path(repo); flow.validate_branch(branch)
        except OctoShipError as exc:
            messagebox.showerror('Destination', str(exc)); return None
        return api, repo, branch

    def confirm(self, title, text):
        return messagebox.askyesno(title, text, parent=self.app.root, default='no')

    def approve_text(self, value):
        scan = scan_bytes(value.encode())
        return not scan.needs_review or self.confirm('Content review', scan.summary + '\n\nContinue with this text?')

    def choose_local(self):
        folder = filedialog.askdirectory()
        if folder: self.local.set(folder)

    def compare(self):
        context = self.context()
        if not context: return
        api, repo, branch = context
        remote, local = self.remote.get(), self.local.get()
        self.comparison.configure(state='normal'); self.comparison.delete('1.0', 'end')
        self.comparison.insert('end', 'Comparison running. No results yet.'); self.comparison.configure(state='disabled')
        def done(result):
            commit, rows = result
            self.comparison.configure(state='normal'); self.comparison.delete('1.0', 'end')
            self.comparison.insert('end', f'{repo} · {branch}\nCommit: {commit}\n\n')
            for path, status in rows: self.comparison.insert('end', f'{status:34} {path}\n')
            self.comparison.configure(state='disabled')
            self.app.record(f'Comparison complete: {len(rows)} files at {commit[:12]}.')
        def error(_):
            self.comparison.configure(state='normal'); self.comparison.delete('1.0', 'end')
            self.comparison.insert('end', 'Comparison incomplete. No missing-file conclusions were made.')
            self.comparison.configure(state='disabled')
        self.app.run('Comparing folders…', lambda: flow.compare_folder(api, repo, branch, remote, local, self.app.cancel), done, error)

    def branch(self):
        context = self.context()
        if not context: return
        api, repo, source = context
        new = self.new_branch.get().strip()
        def work():
            flow.validate_branch(new)
            return flow.head(api, repo, source)
        def reviewed(sha):
            if self.confirm('Create branch', f'{repo}\nCreate {new} from {source}\nCommit: {sha}?'):
                self.app.run('Creating branch…', lambda: flow.create_branch(api, repo, new, sha),
                             lambda result: self.app.record('Created ' + result['ref'] + ' in ' + repo))
        self.app.run('Reviewing source branch…', work, reviewed)

    def pull_request(self):
        context = self.context()
        if not context: return
        api, repo, source = context
        base, title = self.base.get().strip(), self.pr_title.get().strip()
        body, draft = self.pr_body.get('1.0', 'end-1c'), self.draft.get()
        if not self.approve_text(title + '\n' + body): return
        if not self.confirm('Create pull request', f'{repo}\n{source} → {base}\n{title}\nDraft: {draft}\n\nCreate this pull request?'): return
        self.app.run('Creating pull request…', lambda: flow.create_pr(api, repo, source, base, title, body, draft, True),
                     lambda result: self.show_url('Pull request created', result))

    def show_url(self, label, result):
        self.app.last_url = result.get('html_url')
        self.app.record(label + ': ' + (self.app.last_url or 'Check GitHub.'))

    def set_release(self, context, result):
        self.release_context, self.release = context, result
        self.assets_ready = True
        self.identity.set(str(result['id']))
        self.release_status.set(f"Draft {result.get('tag_name', '')} · ID {result['id']}\n{result.get('html_url', '')}")
        self.asset_button.configure(state='normal')
        self.publish_button.configure(state='normal')
        self.show_url('Draft ready', result)

    def create_release(self):
        context = self.context()
        if not context: return
        api, repo, target = context
        tag, title, notes = self.tag.get().strip(), self.release_title.get(), self.notes.get('1.0', 'end-1c')
        prerelease = self.prerelease.get()
        if not self.approve_text(title + '\n' + notes): return
        if not self.confirm('Create draft', f'Create draft {tag} in {repo} from {target}?\nPre-release: {prerelease}'): return
        self.release = None; self.release_context = None
        self.asset_button.configure(state='disabled'); self.publish_button.configure(state='disabled')
        self.app.run('Creating draft release…', lambda: flow.create_draft(api, repo, tag, target, title, notes, prerelease, True),
                     lambda result: self.set_release(context, result), self.release_error)

    def release_error(self, error):
        self.assets_ready = False
        self.publish_button.configure(state='disabled')
        self.release_status.set(error + '\nInspect GitHub before retrying. A draft, asset, or publication may already exist. Load / refresh the draft to recover.')

    def load_release(self):
        context = self.context()
        if not context: return
        api, repo, _ = context
        try: identity = int(self.identity.get())
        except ValueError:
            messagebox.showerror('Draft ID', 'Enter the numeric GitHub release ID.'); return
        def done(result):
            assets = result.get('assets', [])
            incomplete = any(a.get('state') != 'uploaded' for a in assets)
            self.set_release(context, result)
            if incomplete:
                self.release_error('Draft contains incomplete assets. Remove or repair them on GitHub, then refresh.'); return
            self.release_status.set(self.release_status.get() + '\nCurrent assets: ' + (', '.join(a['name'] for a in assets) or '(none)'))
        self.app.run('Loading draft state…', lambda: flow.draft_release(api, repo, identity), done, self.release_error)

    def active_release(self):
        context = self.context()
        if not context or not self.release: return None
        if context[:2] != self.release_context[:2]:
            messagebox.showerror('Draft destination', 'Select the draft’s repository and connected account, or load another draft.'); return None
        return context[0], context[1], self.release['id']

    def attach_assets(self):
        context = self.active_release()
        if not context: return
        paths = [Path(p) for p in filedialog.askopenfilenames(title='Choose release assets')]
        if not paths: return
        if len({p.name.casefold() for p in paths}) != len(paths):
            messagebox.showerror('Asset names', 'Asset filenames must be unique.'); return
        api, repo, identity = context
        def work():
            return [(p, *flow.inspect_asset(p, self.app.cancel)) for p in paths]
        def reviewed(items):
            win = tk.Toplevel(self.app.root); win.title('Review release assets'); win.geometry('850x560'); win.transient(self.app.root); win.grab_set()
            ttk.Label(win, text=f'Attach to draft {identity} in {repo}', padding=12).pack(fill='x')
            text = text_box(win)
            for path, size, digest, scan in items:
                text.insert('end', f'{path.name} · {size:,} bytes\nSHA-256: {digest}\n{scan.summary}\n\n')
            text.configure(state='disabled')
            acknowledged = tk.BooleanVar()
            risk = any(item[3].needs_review for item in items)
            def send():
                if risk and not acknowledged.get(): return
                win.destroy()
                self.assets_ready = False; self.publish_button.configure(state='disabled')
                def upload():
                    for path, size, digest, scan in items:
                        check_cancel(self.app.cancel)
                        flow.upload_asset(api, repo, identity, path, digest, True, self.app.cancel)
                    return flow.draft_release(api, repo, identity)
                self.app.run('Uploading reviewed assets…', upload, lambda result: self.set_release(self.release_context, result), self.release_error)
            button = ttk.Button(win, text='Upload reviewed assets', command=send, state='disabled' if risk else 'normal')
            if risk:
                ttk.Checkbutton(win, text='I reviewed the findings and unscanned assets and approve uploading them.', variable=acknowledged,
                                command=lambda: button.configure(state='normal' if acknowledged.get() else 'disabled')).pack(anchor='w', padx=12)
            button.pack(side='right', padx=12, pady=12)
            ttk.Button(win, text='Back', command=win.destroy).pack(side='right')
        self.app.run('Hashing and inspecting assets…', work, reviewed)

    def publish(self):
        context = self.active_release()
        if not context or not self.assets_ready: return
        api, repo, identity = context
        if not self.confirm('Publish release', f'Publish draft {identity} ({self.release.get("tag_name", "")}) in {repo}?\nIt will become visible to repository readers.'): return
        self.publish_button.configure(state='disabled')
        def done(result):
            self.asset_button.configure(state='disabled')
            self.assets_ready = False
            self.release_status.set('Published: ' + result.get('html_url', 'Check GitHub.'))
            self.show_url('Release published', result)
        self.app.run('Publishing release…', lambda: flow.publish_release(api, repo, identity), done, self.release_error)
