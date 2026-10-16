"""Linux shipping, preparation, inspection and delivery tools."""
import json
from pathlib import Path
import platform
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from . import __version__, workbench as ship, preparation as prep, inspection as inspect
from .core import OctoShipError
from .storage import load_json, save_json, state_root
from .tools_ui import field, text_box
from . import workflows as flow
from .lifecycle_ui import LifecyclePanel


class WorkbenchPanel:
    def __init__(self, app, parent):
        self.app = app; self.plan = None; self.selective = None; self.reviewed = None
        self.tabs = ttk.Notebook(parent); self.tabs.pack(fill='both', expand=True)
        pages = []; self.viewports = []
        for name in ('Ship project', 'Prepare & map', 'Inspect', 'Delivery checks', 'Display & privacy', 'Project lifecycle'):
            outer = ttk.Frame(self.tabs); self.tabs.add(outer, text=name)
            canvas = tk.Canvas(outer, highlightthickness=0, borderwidth=0)
            scroll = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
            scroll.pack(side='right', fill='y'); canvas.pack(fill='both', expand=True)
            canvas.configure(yscrollcommand=scroll.set)
            page = ttk.Frame(canvas, padding=10); item = canvas.create_window(0,0,window=page,anchor='nw')
            def resize(event=None, c=canvas, p=page, i=item):
                for child in p.winfo_children():
                    if isinstance(child, ttk.Label): child.configure(wraplength=max(250,c.winfo_width()-24))
                c.itemconfigure(i, width=max(1,c.winfo_width()), height=max(c.winfo_height(),p.winfo_reqheight()))
                c.configure(scrollregion=c.bbox('all'))
            canvas.bind('<Configure>',resize); page.bind('<Configure>',resize)
            pages.append(page); self.viewports.append(canvas)
        project, prepare, inspection, delivery, display, lifecycle_page = pages
        self.lifecycle = LifecyclePanel(app, lifecycle_page)
        form = ttk.Frame(project); form.pack(fill='x')
        self.folder = field(form, 'Project folder', '', 0)
        self.destination = field(form, 'Repository folder', '', 1)
        self.exclusions = field(form, 'Exclusion globs (semicolon separated)', 'dist/*;bin/*;obj/*', 2)
        self.new_branch = field(form, 'New shipping branch', '', 3)
        self.title = field(form, 'Commit / draft PR title', '', 4)
        self.release_name = field(form, 'Recipe release naming convention', 'v{version}', 5)
        self.buttons(project, [('Choose folder…', self.choose_folder), ('Review shipment', self.review_ship), ('Ship reviewed project…', self.publish_ship)])
        self.buttons(project, [('Import recipe…', self.import_recipe), ('Export recipe…', self.export_recipe), ('Inspect local Git', self.git_status)])
        self.ship_report = text_box(project, 8)
        self.set_text(self.ship_report, 'Select repository and base branch above. Review pins account, visibility, local bytes and remote commit. Shipping creates a new branch and draft PR.')

        ttk.Label(prepare, text='Offline plans reference local files. Double-click a destination to edit it. Publication always requires a fresh review.').pack(anchor='w')
        self.buttons(prepare, [('Map project folder', self.map_project), ('Add files…', self.add_files), ('Remove selected', self.remove_mapping), ('Stage empty folder…', self.empty_folder)])
        self.mapping = ttk.Treeview(prepare, columns=('source','destination'), show='headings', height=6)
        for name in ('source','destination'): self.mapping.heading(name, text=name.title()); self.mapping.column(name, width=390)
        self.mapping.pack(fill='both', expand=True); self.mapping.bind('<Double-1>', self.edit_destination)
        self.buttons(prepare, [('Save plan…', self.save_plan), ('Load plan…', self.load_plan), ('Select text edits…', self.select_edits)])
        self.buttons(prepare, [('Refresh identity / visibility', self.identity), ('Bind account to project…', self.bind), ('Review & publish…', self.review_preparation)])
        self.prep_report = text_box(prepare, 5)

        form = ttk.Frame(inspection); form.pack(fill='x')
        self.expected = field(form, 'Expected version / release tag', '', 0)
        self.buttons(inspection, [('Check project', self.check_project), ('Inspect ZIP…', self.zip), ('Inspect installer…', self.installer)])
        ttk.Label(inspection, text='Checks use the project folder from Ship project. ZIPs are never extracted; installers are never executed.').pack(anchor='w', pady=5)
        self.inspect_report = text_box(inspection, 10)
        ttk.Label(inspection, text='Support report: describe the failure (review redactions before sharing)').pack(anchor='w')
        self.failure = ttk.Entry(inspection); self.failure.pack(fill='x')
        self.buttons(inspection, [('Preview support report', self.support), ('Save displayed report…', self.save_report)])

        form = ttk.Frame(delivery); form.pack(fill='x')
        self.release_id = field(form, 'Release ID', '', 0)
        self.tag = field(form, 'Expected release tag', '', 1)
        self.asset_name = field(form, 'Expected asset filename', '', 2)
        self.prerelease = tk.BooleanVar()
        ttk.Checkbutton(delivery, text='Check prerelease channel', variable=self.prerelease).pack(anchor='w')
        self.buttons(delivery, [('Account / rules / Pages', self.diagnostics), ('Verify attestation…', self.attestation), ('Check download channel', self.channel), ('Open Pages', self.open_pages)])
        self.buttons(delivery, [('List drafts', self.drafts), ('Recover missing assets…', self.recover), ('Test release downloads…', self.test_release)])
        self.delivery_report = text_box(delivery, 10)

        ttk.Label(display, text='Display settings apply across OctoShip windows.').pack(anchor='w')
        self.size = tk.IntVar(value=12); self.compact = tk.BooleanVar(value=True)
        row = ttk.Frame(display); row.pack(fill='x', pady=8)
        ttk.Label(row, text='Text size').pack(side='left')
        ttk.Spinbox(row, from_=12, to=18, width=5, textvariable=self.size).pack(side='left', padx=8)
        ttk.Checkbutton(row, text='Compact spacing', variable=self.compact).pack(side='left')
        self.privacy = tk.BooleanVar(value=False); self.reconnect = tk.BooleanVar(value=False)
        ttk.Checkbutton(display, text='Privacy mode: do not retain repository, branch or local folder', variable=self.privacy).pack(anchor='w')
        ttk.Checkbutton(display, text='Reconnect GitHub CLI account at startup after unlock', variable=self.reconnect).pack(anchor='w')
        self.buttons(display, [('Save display & preferences', self.save_preferences), ('Lock account workspace now', self.lock)])
        ttk.Label(display, text='OctoShip locks after 30 minutes without activity in the app.\nCtrl+Shift+L locks immediately. Unlock uses your Linux account through PAM.\nExplicitly saved preparation plans and project bindings are retained independently of privacy mode.\nCredentials remain managed by GitHub CLI; passwords are never saved.\nThis privacy shield does not encrypt local files or replace the desktop lock.', wraplength=850).pack(anchor='w', pady=16)

    def buttons(self, parent, entries):
        row = ttk.Frame(parent); row.pack(fill='x', pady=4)
        buttons = [ttk.Button(row, text=title, command=lambda c=command: self.safe(c)) for title, command in entries]
        def layout(event=None):
            width = max(300, row.winfo_width()); used = column = line = 0
            for button in buttons:
                needed = button.winfo_reqwidth() + 6
                if used and used + needed > width: line += 1; used = column = 0
                button.grid(row=line, column=column, sticky='w', padx=(0,6), pady=2)
                used += needed; column += 1
            parent.event_generate('<Configure>', when='tail')
        row.bind('<Configure>', layout)
        row.after_idle(layout)

    def safe(self, action):
        if self.app.busy: return
        try:
            if self.app.session: self.app.session.state.guard()
            action()
        except (OctoShipError, OSError, ValueError, KeyError, TypeError) as exc:
            messagebox.showerror('OctoShip', str(exc) if isinstance(exc, OctoShipError) else 'Check the selected paths and input format.', parent=self.app.root)

    def context(self): return self.app.tools.context()
    def confirm(self, title, message): return self.app.tools.confirm(title, message)

    @staticmethod
    def set_text(widget, value):
        widget.configure(state='normal'); widget.delete('1.0','end')
        widget.insert('end', value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False))
        widget.configure(state='disabled')

    def report(self, label, work, widget): self.app.run(label, work, lambda value: self.set_text(widget, value))

    def choose_folder(self):
        path = filedialog.askdirectory(parent=self.app.root)
        if path: self.folder.set(path); self.reviewed = None

    def patterns(self): return [p.strip() for p in self.exclusions.get().split(';') if p.strip()]

    def review_ship(self):
        context = self.context()
        if not context: return
        api, repo, branch = context; folder, destination, patterns = self.folder.get(), self.destination.get(), self.patterns()
        self.reviewed = None
        def work():
            review = ship.review_project(api, repo, branch, folder, destination, patterns, self.app.cancel)
            return review, ship.diagnostics(api, repo, branch)
        def done(result):
            review, checks = result
            self.reviewed = (api, review, (folder, destination, tuple(patterns)))
            self.set_text(self.ship_report, f'{repo} / {branch} · {review.visibility} · {review.account}\nPinned commit: {review.commit}\n{len(review.items)} changed files\n\n' + '\n'.join(p + ': ' + s for p,s in review.rows) + '\n\nRules / account / Pages:\n' + json.dumps(checks, indent=2))
        self.app.run('Reviewing shipment…', work, done)

    def publish_ship(self):
        context = self.context()
        if not context or not self.reviewed: raise OctoShipError('Review the shipment first.')
        api, review, inputs = self.reviewed
        if context != (api, review.repo, review.branch) or inputs != (self.folder.get(), self.destination.get(), tuple(self.patterns())):
            raise OctoShipError('Project or destination changed. Review again.')
        branch, title = self.new_branch.get().strip(), self.title.get().strip()
        risk = any(item.scan.needs_review for item in review.items)
        if not self.confirm('Ship reviewed project', f'{review.repo} · {review.visibility}\n{review.branch} → NEW {branch}\n{title}\n{len(review.items)} changed files\n' + ('Some contents were incompletely scanned. Review those files before approving.\n' if risk else '') + '\nCreate the branch, atomic commit and draft PR?'): return
        self.reviewed = None
        self.report('Shipping reviewed project…', lambda: ship.ship_project(api, review, branch, title, True, self.app.cancel), self.ship_report)

    def import_recipe(self):
        path = filedialog.askopenfilename(filetypes=[('Recipe JSON','*.json')])
        if not path: return
        value = ship.recipe(load_json(path, 65536))
        self.app.repo.set(value['repository']); self.app.branch.set(value['branch']); self.destination.set(value.get('destination',''))
        self.exclusions.set(';'.join(value.get('exclusions',[]))); self.release_name.set(value.get('release_name','')); self.reviewed = None

    def export_recipe(self):
        value = ship.recipe({'version':1, 'repository':self.app.repo.get(), 'branch':self.app.branch.get(), 'destination':self.destination.get(), 'exclusions':self.patterns(), 'release_name':self.release_name.get()})
        path = filedialog.asksaveasfilename(defaultextension='.json')
        if path: save_json(path, value)

    def git_status(self):
        folder = self.folder.get()
        self.report('Inspecting local Git…', lambda: ship.local_git(folder), self.ship_report)

    def show_plan(self):
        self.mapping.delete(*self.mapping.get_children())
        if self.plan:
            for i, row in enumerate(self.plan['files']): self.mapping.insert('', 'end', iid=str(i), values=(row['source'],row['destination']))
            self.set_text(self.prep_report, f"{self.plan['repository']} / {self.plan['branch']}\n{len(self.plan['files'])} mapped files. Local paths are included in saved plans.")

    def map_project(self):
        root, repo, branch, dest, patterns = self.folder.get(), self.app.repo.get(), self.app.branch.get(), self.destination.get(), self.patterns()
        def done(value): self.plan = value; self.selective = None; self.show_plan()
        self.app.run('Mapping local project…', lambda: prep.map_project(root, repo, branch, dest, patterns), done)

    def add_files(self):
        paths = filedialog.askopenfilenames()
        if not paths: return
        plan = self.plan or {'version':1,'root':str(Path(self.folder.get() or Path(paths[0]).parent).absolute()), 'repository':self.app.repo.get(),'branch':self.app.branch.get(),'files':[]}
        dest = self.destination.get().strip('/')
        rows = [{'source':str(Path(p).absolute()),'destination':(dest + '/' if dest else '') + Path(p).name} for p in paths]
        self.plan = prep.validate_plan(dict(plan, files=plan['files'] + rows)); self.selective = None; self.show_plan()

    def selected_row(self):
        selected = self.mapping.selection()
        if not self.plan or len(selected) != 1: raise OctoShipError('Select exactly one mapped file.')
        return int(selected[0]), self.plan['files'][int(selected[0])]

    def edit_destination(self, event=None):
        def edit():
            index, row = self.selected_row()
            value = simpledialog.askstring('Destination', 'Relative repository destination', initialvalue=row['destination'], parent=self.app.root)
            if value:
                rows = list(self.plan['files']); rows[index] = dict(row, destination=value)
                self.plan = prep.validate_plan(dict(self.plan, files=rows)); self.selective = None; self.show_plan()
        self.safe(edit)

    def remove_mapping(self):
        if not self.plan: return
        indices = {int(i) for i in self.mapping.selection()}
        self.plan = dict(self.plan, files=[r for i,r in enumerate(self.plan['files']) if i not in indices]); self.selective = None; self.show_plan()

    def empty_folder(self):
        if not self.plan:
            self.plan = {'version':1, 'root':str(Path(self.folder.get()).absolute()),'repository':self.app.repo.get(),'branch':self.app.branch.get(),'files':[]}
        folder = filedialog.askdirectory(initialdir=self.plan['root'])
        if not folder: return
        rel = Path(folder).relative_to(self.plan['root']).as_posix()
        suggested = '/'.join(p for p in (self.destination.get().strip('/'), rel if rel != '.' else '', '.gitkeep') if p)
        dest = simpledialog.askstring('Empty folder', 'Placeholder destination', initialvalue=suggested)
        if dest: self.plan = prep.placeholder(self.plan, folder, dest); self.selective = None; self.show_plan()

    def save_plan(self):
        if self.selective: raise OctoShipError('Selective plans cannot be saved. Publish or remap first.')
        prep.validate_plan(self.plan)
        path = filedialog.asksaveasfilename(defaultextension='.json')
        if path: save_json(path, self.plan)

    def load_plan(self):
        path = filedialog.askopenfilename(filetypes=[('Preparation plan','*.json')])
        if path:
            self.plan = prep.validate_plan(load_json(path)); self.selective = None; self.show_plan()
            self.folder.set(self.plan['root']); self.app.repo.set(self.plan['repository']); self.app.branch.set(self.plan['branch'])

    def plan_context(self):
        prep.validate_plan(self.plan)
        context = self.context()
        if context and context[1:] != (self.plan['repository'], self.plan['branch']): raise OctoShipError('Selected repository/branch differs from the plan. Select the plan destination or remap.')
        return context

    def identity(self):
        context = self.plan_context()
        if context: self.report('Refreshing identity…', lambda: prep.identity(context[0], self.plan, prep.bindings()), self.prep_report)

    def bind(self):
        context = self.plan_context()
        if not context: return
        api = context[0]; plan = self.plan
        def done(value):
            if self.confirm('Bind project account', f"Save {value['account']} / {value['visibility']} as the expected account and visibility for\n{plan['root']}\n{plan['repository']}?"):
                # Bind exactly the reviewed account rather than silently accepting an account switch.
                values = prep.bindings(); values[plan['root'] + '\n' + plan['repository']] = {k:value[k] for k in ('account','visibility')}
                save_json(state_root() / 'project-bindings.json', values); self.set_text(self.prep_report, value)
        self.app.run('Reviewing account binding…', lambda: prep.identity(api, plan), done)

    def select_edits(self):
        context = self.plan_context()
        if not context: return
        _, row = self.selected_row(); api = context[0]; plan = self.plan
        def done(value):
            win = tk.Toplevel(self.app.root); win.title('Select independent text edits'); win.geometry('850x600'); win.transient(self.app.root); win.grab_set()
            ttk.Label(win, text='Selected blocks are staged as one file. Other mapped files are removed from this selective plan.', wraplength=800).pack(padx=12,pady=8)
            listing = tk.Listbox(win, selectmode='multiple', exportselection=False, height=7); listing.pack(fill='x', padx=12)
            preview = text_box(win, 12)
            for index,(start,end,added) in enumerate(value['changes']):
                listing.insert('end', f'Block {index+1}: line {start+1}, remove {end-start}, add {len(added)}')
                preview.insert('end', f'Block {index+1}\n' + ''.join('- ' + s for s in value['lines'][start:end]) + ''.join('+ ' + s for s in added) + '\n')
            preview.configure(state='disabled'); listing.select_set(0,'end')
            def stage():
                data = inspect.apply_changes(value['lines'], value['changes'], set(listing.curselection()))
                self.plan = dict(plan, files=[{'source':prep.stage_bytes(data),'destination':value['destination']}]); self.selective = value
                win.destroy(); self.show_plan()
            ttk.Button(win,text='Stage selected blocks',command=stage).pack(side='right',padx=12,pady=12)
            ttk.Button(win,text='Cancel',command=win.destroy).pack(side='right')
        self.app.run('Loading fixed text baseline…', lambda: prep.selective_baseline(api, plan, row), done)

    def review_preparation(self):
        context = self.plan_context()
        if not context: return
        api, plan, selective = context[0], self.plan, self.selective
        def done(value):
            info = value['identity']; items = value['items']
            report = json.dumps(info, indent=2) + '\nCommit: ' + value['commit'] + '\n\n' + '\n\n'.join(f'{i.destination}\nSHA-256 {i.digest}\n{i.scan.summary}' for i in items)
            self.set_text(self.prep_report, report)
            win = tk.Toplevel(self.app.root); win.title('Review prepared publication'); win.geometry('860x620'); win.transient(self.app.root); win.grab_set()
            report_box = text_box(win, 16); self.set_text(report_box, report)
            form = ttk.Frame(win); form.pack(fill='x',padx=12)
            message = field(form, 'Commit message', 'Publish prepared files with OctoShip')
            risk = any(i.scan.needs_review for i in items); approved = tk.BooleanVar(value=not risk)
            if risk: ttk.Checkbutton(win,text='I reviewed the incomplete content scans and approve these files.',variable=approved).pack(anchor='w',padx=12)
            def send():
                if not approved.get(): return
                text = message.get(); win.destroy()
                self.report('Publishing prepared files…', lambda: prep.publish(api, value, text, True, self.app.cancel), self.prep_report)
            ttk.Button(win,text='Publish reviewed files',command=send).pack(side='right',padx=12,pady=12)
            ttk.Button(win,text='Back',command=win.destroy).pack(side='right')
        self.app.run('Reviewing prepared publication…', lambda: prep.review(api, plan, selective), done)

    def check_project(self):
        root, expected = self.folder.get(), self.expected.get()
        self.report('Checking project…', lambda: inspect.inspect_project(root, expected, self.app.cancel), self.inspect_report)

    def zip(self):
        path = filedialog.askopenfilename(filetypes=[('ZIP archive','*.zip')])
        if path: self.report('Inspecting archive…', lambda: inspect.inspect_zip(path, self.app.cancel), self.inspect_report)

    def installer(self):
        path = filedialog.askopenfilename()
        if path: self.report('Inspecting installer…', lambda: inspect.inspect_installer(path), self.inspect_report)

    def support(self):
        value = f'OctoShip Linux {__version__}\nOS: {platform.system()} {platform.release()}\nFailure: {self.failure.get()}\nStatus: {self.app.status.get()}\nReport:\n{self.inspect_report.get("1.0","end-1c")}'
        self.set_text(self.inspect_report, inspect.redact(value))

    def save_report(self):
        path = filedialog.asksaveasfilename(defaultextension='.txt')
        if path:
            import os
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor,'w') as stream: stream.write(inspect.redact(self.inspect_report.get('1.0','end-1c')))

    def diagnostics(self):
        context = self.context()
        if context: self.report('Checking account, branch rules and Pages…', lambda: ship.diagnostics(*context), self.delivery_report)

    def open_pages(self):
        context = self.context()
        if not context: return
        api, repo, _ = context
        def done(value):
            from urllib.parse import urlsplit
            import webbrowser
            url = value.get('html_url', '')
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username:
                messagebox.showerror('Pages', 'Pages did not return a supported HTTPS URL.', parent=self.app.root); return
            webbrowser.open(url)
        self.app.run('Loading Pages URL…', lambda: api.request(api.repo_path(repo) + '/pages'), done)

    def attestation(self):
        context = self.context()
        if not context: return
        path = filedialog.askopenfilename()
        if path: self.report('Verifying attestation with GitHub CLI…', lambda: ship.verify_attestation(context[1], path), self.delivery_report)

    def channel(self):
        context = self.context()
        if context:
            prerelease, tag, name = self.prerelease.get(), self.tag.get(), self.asset_name.get()
            self.report('Checking download channel…', lambda: ship.release_channel(context[0], context[1], prerelease, tag, name), self.delivery_report)

    def drafts(self):
        context = self.context()
        if context:
            api,repo,_ = context
            self.report('Listing drafts…', lambda: [{'id':r['id'],'tag':r['tag_name'],'assets':[a['name'] for a in r.get('assets',[])]} for r in api.request(api.repo_path(repo) + '/releases?per_page=100') if r.get('draft')], self.delivery_report)

    def recover(self):
        context = self.context()
        if not context: return
        identity = int(self.release_id.get()); flow.release_id(identity)
        paths = [Path(p) for p in filedialog.askopenfilenames()]
        if not paths: return
        if len({p.name for p in paths}) != len(paths): raise OctoShipError('Asset filenames must be unique.')
        api,repo,_ = context
        def done(items):
            report = '\n\n'.join(f'{p.name}\n{size} bytes\nSHA-256 {digest}\n{scan.summary}' for p,size,digest,scan in items)
            self.set_text(self.delivery_report, report)
            if self.confirm('Recover existing draft', f'{repo} / draft {identity}\n\n{report}\n\nApprove these contents and upload only missing names? Existing mismatches will be preserved. The draft will not be published.'):
                self.report('Recovering draft assets…', lambda: ship.recover_assets(api,repo,identity,[(p,digest) for p,_,digest,_ in items],True,self.app.cancel), self.delivery_report)
        self.app.run('Reviewing recovery assets…', lambda: [(p,*flow.inspect_asset(p,self.app.cancel)) for p in paths], done)

    def test_release(self):
        context = self.context()
        if not context: return
        identity = int(self.release_id.get()); flow.release_id(identity)
        paths = [Path(p) for p in filedialog.askopenfilenames(title='Optional local reference assets (Cancel uses GitHub digests)')]
        api,repo,_ = context
        def work():
            references = {p.name:flow.inspect_asset(p,self.app.cancel)[1] for p in paths}
            return ship.test_release(api,repo,identity,references,self.app.cancel)
        self.report('Testing release downloads…', work, self.delivery_report)

    def apply_display(self):
        from tkinter import font
        from . import theme
        try: size = max(12,min(18,int(self.size.get())))
        except (ValueError, tk.TclError): raise OctoShipError('Text size must be a number from 12 to 18.') from None
        self.size.set(size)
        style = ttk.Style(self.app.root)
        font.nametofont('TkDefaultFont').configure(size=size)
        font.nametofont('TkTextFont').configure(size=size)
        style.configure('.',font=(theme.FONT,size)); style.configure('Treeview',rowheight=size*2+4)
        style.configure('TButton',padding=(8,3) if self.compact.get() else (12,6))
        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child,tk.Text): child.configure(font=(theme.FONT,size))
                walk(child)
        walk(self.app.root)
        self.app.root.option_add('*Text.font', (theme.FONT,size))

    def save_preferences(self):
        self.apply_display()
        self.persist_preferences()
        self.app.record('Display and workspace preferences saved on this device.')

    def persist_preferences(self):
        try: size = max(12,min(18,int(self.size.get())))
        except (ValueError, tk.TclError): size = 12
        value = {'text_size':size,'compact':self.compact.get(),'privacy':self.privacy.get(),'reconnect':self.reconnect.get()}
        if not self.privacy.get(): value.update(repository=self.app.repo.get(),branch=self.app.branch.get(),destination=self.app.prefix.get(),project=self.folder.get(),account_label=self.app.account.get())
        save_json(state_root() / 'preferences.json',value)

    def restore_preferences(self):
        path = state_root() / 'preferences.json'
        if not path.exists(): return
        try:
            value = load_json(path,65536)
            if not isinstance(value, dict): raise OctoShipError('Invalid saved preferences.')
            if any(not isinstance(value.get(k, ''), str) for k in ('repository','branch','destination','project','account_label')): raise OctoShipError('Invalid workspace preferences.')
            self.size.set(max(12,min(18,int(value.get('text_size',12))))); self.compact.set(bool(value.get('compact',True)))
            self.privacy.set(bool(value.get('privacy',False))); self.reconnect.set(bool(value.get('reconnect',False)))
            if not self.privacy.get():
                for key,var in [('repository',self.app.repo),('branch',self.app.branch),('destination',self.app.prefix),('project',self.folder)]: var.set(value.get(key,''))
                if value.get('account_label'): self.app.account.set('Previously: ' + value['account_label'].removeprefix('Previously: '))
            self.apply_display()
        except (OctoShipError,ValueError,TypeError,tk.TclError): self.app.record('Saved preferences could not be loaded; defaults retained.')

    def lock(self):
        if self.app.session: self.app.session.lock()
