"""Native repository tools. Opening tabs never sends GitHub requests."""
from pathlib import Path
from dataclasses import asdict
import json
import os
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser
from .core import OctoShipError
from .scanner import scan_bytes, check_cancel
from . import workflows as flow
from . import git_insights
from . import project_audit
from . import release_audit
from . import workspace_audit
from . import project_recipes
from . import editor_workspace as editorflow


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
        self._report_rows = {}
        self._report_trees = {}
        self._report_controls = {}
        self._sort_reverse = {}
        self.tabs = ttk.Notebook(parent)
        self.tabs.pack(fill='both', expand=True)
        compare, branches, pulls, releases, security, local_git, project, artifacts, workspace, recipes, editors = [ttk.Frame(self.tabs, padding=16) for _ in range(11)]
        for tab, name in zip((compare, branches, pulls, releases, security, local_git, project, artifacts, workspace, recipes, editors), ('Compare', 'Branches', 'Pulls', 'Releases', 'Alerts', 'Local Git', 'Project', 'Artifacts', 'Workspace', 'Recipes', 'Editors')):
            self.tabs.add(tab, text=name)
        self._build_editor_panel(editors)
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

        ttk.Label(security, text='Read-only Dependabot alerts for the selected repository. No alerts are dismissed or changed here.').pack(anchor='w')
        security_actions = ttk.Frame(security); security_actions.pack(fill='x', pady=(10, 4))
        self.security_refresh = ttk.Button(security_actions, text='Load open alerts', command=self.load_dependabot_alerts)
        self.security_refresh.pack(side='left')
        self.security_open = ttk.Button(security_actions, text='Open GitHub security page', command=self.open_security_page)
        self.security_open.pack(side='left', padx=8)
        self.security_status = tk.StringVar(value='Connect to GitHub and select a repository, then load its open Dependabot alerts.')
        ttk.Label(security, textvariable=self.security_status, wraplength=850).pack(anchor='w', pady=(4, 8))
        alert_columns = ('severity', 'package', 'patched', 'manifest')
        self.security_alerts = ttk.Treeview(security, columns=alert_columns, show='headings', height=14)
        for key, title, width in (
            ('severity', 'SEVERITY', 100),
            ('package', 'PACKAGE', 220),
            ('patched', 'FIRST FIXED VERSION', 180),
            ('manifest', 'MANIFEST', 360),
        ):
            self.security_alerts.heading(key, text=title)
            self.security_alerts.column(key, width=width, minwidth=90, stretch=(key == 'manifest'))
        alert_scroll = ttk.Scrollbar(security, orient='vertical', command=self.security_alerts.yview)
        self.security_alerts.configure(yscrollcommand=alert_scroll.set)
        self.security_alerts.pack(side='left', fill='both', expand=True)
        alert_scroll.pack(side='right', fill='y')
        self.security_alert_repo = None

        ttk.Label(local_git, text='Inspect the selected local Git repository without contacting GitHub or changing files. URL credentials are redacted from the report.').pack(anchor='w')
        local_git_form = ttk.Frame(local_git); local_git_form.pack(fill='x', pady=8)
        self.git_root = field(local_git_form, 'Repository folder', str(Path.home()), 0)
        git_actions = ttk.Frame(local_git); git_actions.pack(fill='x')
        ttk.Button(git_actions, text='Choose repository…', command=self.choose_git_root).pack(side='left')
        ttk.Button(git_actions, text='Inspect local Git', command=self.inspect_local_git).pack(side='left', padx=8)
        self.git_status = tk.StringVar(value='No repository inspection has run.')
        ttk.Label(local_git, textvariable=self.git_status, wraplength=850).pack(anchor='w', pady=6)
        self._make_report_controls(local_git, 'git')
        git_columns = ('status', 'check', 'detail')
        self.git_report = ttk.Treeview(local_git, columns=git_columns, show='headings', height=18)
        for key, title, width in (('status', 'STATUS', 95), ('check', 'CHECK', 245), ('detail', 'DETAIL', 570)):
            self.git_report.heading(key, text=title); self.git_report.column(key, width=width, minwidth=90, stretch=(key == 'detail'))
        git_scroll = ttk.Scrollbar(local_git, orient='vertical', command=self.git_report.yview)
        self.git_report.configure(yscrollcommand=git_scroll.set)
        self.git_report.pack(side='left', fill='both', expand=True); git_scroll.pack(side='right', fill='y')
        self._register_report('git', self.git_report)

        ttk.Label(project, text='Run bounded local project checks for repository metadata, package manifests, file hygiene, and GitHub Actions settings. Project code is never run.').pack(anchor='w')
        project_form = ttk.Frame(project); project_form.pack(fill='x', pady=8)
        self.project_root = field(project_form, 'Project folder', str(Path.home()), 0)
        project_actions = ttk.Frame(project); project_actions.pack(fill='x')
        ttk.Button(project_actions, text='Choose project…', command=self.choose_project_root).pack(side='left')
        ttk.Button(project_actions, text='Audit project', command=self.audit_local_project).pack(side='left', padx=8)
        self.project_status = tk.StringVar(value='No project audit has run.')
        ttk.Label(project, textvariable=self.project_status, wraplength=850).pack(anchor='w', pady=6)
        self._make_report_controls(project, 'project')
        project_columns = ('status', 'check', 'path', 'message')
        self.project_report = ttk.Treeview(project, columns=project_columns, show='headings', height=18)
        for key, title, width in (('status', 'STATUS', 95), ('check', 'CHECK', 190), ('path', 'PATH', 235), ('message', 'RECOMMENDATION', 385)):
            self.project_report.heading(key, text=title); self.project_report.column(key, width=width, minwidth=90, stretch=(key == 'message'))
        project_scroll = ttk.Scrollbar(project, orient='vertical', command=self.project_report.yview)
        self.project_report.configure(yscrollcommand=project_scroll.set)
        self.project_report.pack(side='left', fill='both', expand=True); project_scroll.pack(side='right', fill='y')
        self._register_report('project', self.project_report)

        ttk.Label(artifacts, text='Check a local release directory for artifact names, versions, SHA-256 manifests, ZIP integrity, and package coverage. Nothing is run, extracted, or uploaded.').pack(anchor='w')
        artifact_form = ttk.Frame(artifacts); artifact_form.pack(fill='x', pady=8)
        self.release_folder = field(artifact_form, 'Release folder', str(Path.home()), 0)
        self.release_version = field(artifact_form, 'Expected version (optional)', '', 1)
        artifact_actions = ttk.Frame(artifacts); artifact_actions.pack(fill='x')
        ttk.Button(artifact_actions, text='Choose release folder…', command=self.choose_release_folder).pack(side='left')
        ttk.Button(artifact_actions, text='Audit artifacts', command=self.audit_release_folder).pack(side='left', padx=8)
        ttk.Button(artifact_actions, text='Create SHA-256 manifest…', command=self.create_release_manifest).pack(side='left')
        self.release_audit_status = tk.StringVar(value='No release artifact audit has run.')
        ttk.Label(artifacts, textvariable=self.release_audit_status, wraplength=850).pack(anchor='w', pady=6)
        self._make_report_controls(artifacts, 'release')
        release_columns = ('status', 'check', 'detail')
        self.release_audit_report = ttk.Treeview(artifacts, columns=release_columns, show='headings', height=18)
        for key, title, width in (('status', 'STATUS', 95), ('check', 'CHECK', 250), ('detail', 'DETAIL', 560)):
            self.release_audit_report.heading(key, text=title); self.release_audit_report.column(key, width=width, minwidth=90, stretch=(key == 'detail'))
        release_scroll = ttk.Scrollbar(artifacts, orient='vertical', command=self.release_audit_report.yview)
        self.release_audit_report.configure(yscrollcommand=release_scroll.set)
        self.release_audit_report.pack(side='left', fill='both', expand=True); release_scroll.pack(side='right', fill='y')
        self._register_report('release', self.release_audit_report)

        ttk.Label(workspace, text='Inspect saved OctoShip queue journals and private state folder permissions. The check is read-only and does not resume, edit, or delete queued work.').pack(anchor='w')
        workspace_form = ttk.Frame(workspace); workspace_form.pack(fill='x', pady=8)
        self.workspace_root = field(workspace_form, 'OctoShip state folder', str(Path.home() / '.local/state/octoship'), 0)
        workspace_actions = ttk.Frame(workspace); workspace_actions.pack(fill='x')
        ttk.Button(workspace_actions, text='Audit local workspace', command=self.audit_workspace_state).pack(side='left')
        self.workspace_status = tk.StringVar(value='No workspace audit has run.')
        ttk.Label(workspace, textvariable=self.workspace_status, wraplength=850).pack(anchor='w', pady=6)
        self._make_report_controls(workspace, 'workspace')
        workspace_columns = ('status', 'check', 'detail')
        self.workspace_report = ttk.Treeview(workspace, columns=workspace_columns, show='headings', height=18)
        for key, title, width in (('status', 'STATUS', 95), ('check', 'CHECK', 245), ('detail', 'DETAIL', 565)):
            self.workspace_report.heading(key, text=title); self.workspace_report.column(key, width=width, minwidth=90, stretch=(key == 'detail'))
        workspace_scroll = ttk.Scrollbar(workspace, orient='vertical', command=self.workspace_report.yview)
        self.workspace_report.configure(yscrollcommand=workspace_scroll.set)
        self.workspace_report.pack(side='left', fill='both', expand=True); workspace_scroll.pack(side='right', fill='y')
        self._register_report('workspace', self.workspace_report)

        ttk.Label(recipes, text=f'Create one of {len(project_recipes.RECIPES)} project files. Preview the exact path and content first. Existing files are never overwritten; review and customize starter content before using it.').pack(anchor='w')
        recipe_form = ttk.Frame(recipes); recipe_form.pack(fill='x', pady=8)
        self.recipe_root = field(recipe_form, 'Project folder', str(Path.home()), 0)
        recipe_select = ttk.Frame(recipes); recipe_select.pack(fill='x')
        ttk.Label(recipe_select, text='Recipe').pack(side='left')
        self.recipe_key = tk.StringVar(value=next(iter(project_recipes.RECIPES)))
        ttk.Combobox(recipe_select, textvariable=self.recipe_key, values=tuple(project_recipes.RECIPES), state='readonly', width=28).pack(side='left', padx=8)
        self.recipe_project = tk.StringVar(value='My Project')
        ttk.Label(recipe_select, text='Project name').pack(side='left')
        ttk.Entry(recipe_select, textvariable=self.recipe_project, width=24).pack(side='left', padx=8)
        self.recipe_summary = tk.StringVar(value='Project description.')
        recipe_details = ttk.Frame(recipes); recipe_details.pack(fill='x', pady=6)
        ttk.Label(recipe_details, text='Summary').pack(side='left')
        ttk.Entry(recipe_details, textvariable=self.recipe_summary).pack(side='left', fill='x', expand=True, padx=8)
        ttk.Button(recipe_details, text='Choose folder…', command=self.choose_recipe_root).pack(side='left')
        recipe_actions = ttk.Frame(recipes); recipe_actions.pack(fill='x')
        ttk.Button(recipe_actions, text='Preview', command=self.preview_recipe).pack(side='left')
        ttk.Button(recipe_actions, text='Create file…', command=self.create_project_recipe).pack(side='left', padx=8)
        self.recipe_status = tk.StringVar(value='No project recipe selected for preview.')
        ttk.Label(recipes, textvariable=self.recipe_status, wraplength=850).pack(anchor='w', pady=6)
        self.recipe_preview = text_box(recipes, 18)
        self.recipe_preview.configure(state='disabled')

    def _build_editor_panel(self, parent):
        canvas = tk.Canvas(parent, highlightthickness=0, borderwidth=0)
        scroll = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        content = ttk.Frame(canvas, padding=(4, 4))
        content_id = canvas.create_window((0, 0), window=content, anchor='nw')
        content.bind('<Configure>', lambda _event: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(content_id, width=event.width))
        canvas.bind('<MouseWheel>', lambda event: canvas.yview_scroll(int(-event.delta / 120), 'units'))
        canvas.bind('<Button-4>', lambda _event: canvas.yview_scroll(-1, 'units'))
        canvas.bind('<Button-5>', lambda _event: canvas.yview_scroll(1, 'units'))
        parent = content
        ttk.Label(parent, text='Editor profiles, accessibility controls, and workspace context are local. CLI actions are launched without a shell.').pack(anchor='w')
        row = ttk.Frame(parent); row.pack(fill='x', pady=8)
        ttk.Label(row, text='Editor').pack(side='left')
        self.editor_id = tk.StringVar(value='code')
        ttk.Combobox(row, textvariable=self.editor_id, values=tuple(editorflow.EDITORS), state='readonly', width=18).pack(side='left', padx=8)
        ttk.Button(row, text='Detect installed editors', command=self.detect_editors).pack(side='left')
        workspace_row = ttk.Frame(parent); workspace_row.pack(fill='x', pady=4)
        self.editor_workspace_root = field(workspace_row, 'Workspace folder', str(Path.home()), 0)
        data_dir = ttk.Frame(parent); data_dir.pack(fill='x', pady=(0, 6))
        self.editor_data_root = tk.StringVar(value=str(Path.home() / '.local/share/octoship/editor-data'))
        ttk.Label(data_dir, text='Isolated editor data/extensions folder').pack(side='left')
        ttk.Entry(data_dir, textvariable=self.editor_data_root).pack(side='left', fill='x', expand=True, padx=8)
        ttk.Button(data_dir, text='Choose existing folder…', command=self.choose_editor_data_root).pack(side='left')
        actions = ttk.Frame(parent); actions.pack(fill='x', pady=4)
        self.editor_action = tk.StringVar(value='open')
        action_names = editorflow.EDITOR_COMMAND_FEATURES
        ttk.Label(actions, text='Editor action').pack(side='left')
        ttk.Combobox(actions, textvariable=self.editor_action, values=action_names, state='readonly', width=27).pack(side='left', padx=8)
        self.editor_extension = tk.StringVar()
        ttk.Label(actions, text='Extension ID').pack(side='left')
        ttk.Entry(actions, textvariable=self.editor_extension, width=24).pack(side='left', padx=4)
        self.editor_action_value = tk.StringVar()
        ttk.Label(actions, text='Profile / value').pack(side='left')
        ttk.Entry(actions, textvariable=self.editor_action_value, width=20).pack(side='left', padx=4)
        self.editor_action_paths = []
        ttk.Button(actions, text='Choose file(s)…', command=self.choose_editor_action_paths).pack(side='left', padx=4)
        ttk.Button(actions, text='Run action…', command=self.run_editor_action).pack(side='left', padx=4)
        profiles = ttk.Frame(parent); profiles.pack(fill='x', pady=4)
        self.editor_profile = tk.StringVar()
        ttk.Label(profiles, text='Local profile').pack(side='left')
        ttk.Entry(profiles, textvariable=self.editor_profile, width=24).pack(side='left', padx=8)
        ttk.Button(profiles, text='Save current', command=self.save_editor_profile).pack(side='left')
        ttk.Button(profiles, text='List', command=self.list_editor_profiles).pack(side='left', padx=4)
        ttk.Button(profiles, text='Preview', command=self.preview_editor_profile).pack(side='left')
        ttk.Button(profiles, text='Activate…', command=self.activate_editor_profile).pack(side='left', padx=4)
        ttk.Button(profiles, text='Remove…', command=self.remove_editor_profile).pack(side='left')
        local = ttk.Frame(parent); local.pack(fill='x', pady=4)
        ttk.Button(local, text='Inspect workspace metadata', command=self.inspect_editor_workspace).pack(side='left')
        ttk.Button(local, text='Back up settings', command=self.backup_editor_settings).pack(side='left', padx=6)
        ttk.Button(local, text='Restore settings backup…', command=self.restore_editor_settings).pack(side='left')
        ttk.Button(local, text='Export portable settings…', command=self.export_editor_snapshot).pack(side='left', padx=6)
        ttk.Button(local, text='Import portable settings…', command=self.import_editor_snapshot).pack(side='left')
        ttk.Button(local, text='Preview accessibility preset', command=self.preview_editor_accessibility).pack(side='left')
        ttk.Button(local, text='Apply accessibility preset…', command=self.apply_editor_accessibility).pack(side='left', padx=6)
        configs = ttk.Frame(parent); configs.pack(fill='x', pady=4)
        ttk.Label(configs, text='Workspace config').pack(side='left')
        self.workspace_config_kind = tk.StringVar(value='settings')
        ttk.Combobox(configs, textvariable=self.workspace_config_kind, values=tuple(editorflow.WORKSPACE_CONFIGS) + ('code-workspace',), state='readonly', width=20).pack(side='left', padx=8)
        ttk.Button(configs, text='Validate selected config', command=self.validate_editor_workspace_config).pack(side='left')
        ttk.Button(configs, text='Open config in editor', command=self.open_editor_workspace_config).pack(side='left', padx=6)
        shell = ttk.Frame(parent); shell.pack(fill='x', pady=4)
        ttk.Button(shell, text='Detect terminal shells', command=self.detect_terminal_shells).pack(side='left')
        self.terminal_shell = tk.StringVar()
        self.terminal_shell_picker = ttk.Combobox(shell, textvariable=self.terminal_shell, state='readonly', width=24)
        self.terminal_shell_picker.pack(side='left', padx=8)
        self.terminal_default = tk.BooleanVar(value=False)
        ttk.Checkbutton(shell, text='Set as default', variable=self.terminal_default).pack(side='left')
        ttk.Button(shell, text='Preview terminal profile', command=self.preview_terminal_profile).pack(side='left', padx=6)
        ttk.Button(shell, text='Add profile…', command=self.add_terminal_profile).pack(side='left')
        ttk.Button(shell, text='Remove profile…', command=self.remove_terminal_profile).pack(side='left', padx=6)
        ttk.Button(shell, text='Set default…', command=self.set_default_terminal).pack(side='left')
        extensions = ttk.Frame(parent); extensions.pack(fill='x', pady=4)
        ttk.Button(extensions, text='Compare workspace recommendations', command=self.compare_editor_recommendations).pack(side='left')
        self.recommended_extension = tk.StringVar()
        ttk.Entry(extensions, textvariable=self.recommended_extension, width=30).pack(side='left', padx=6)
        ttk.Button(extensions, text='Install recommended…', command=self.install_editor_recommendation).pack(side='left')
        ttk.Label(parent, text='Accessibility settings available: ' + ', '.join(x.label for x in editorflow.ACCESSIBILITY_OPTIONS), wraplength=880).pack(anchor='w', pady=5)
        accessibility = ttk.Frame(parent); accessibility.pack(fill='x', pady=3)
        self.editor_accessibility_key = tk.StringVar(value=editorflow.ACCESSIBILITY_OPTIONS[0].key)
        ttk.Label(accessibility, text='Single setting').pack(side='left')
        ttk.Combobox(accessibility, textvariable=self.editor_accessibility_key, values=tuple(x.key for x in editorflow.ACCESSIBILITY_OPTIONS), state='readonly', width=42).pack(side='left', padx=8)
        ttk.Button(accessibility, text='Enable setting', command=lambda: self.set_editor_accessibility(True)).pack(side='left')
        ttk.Button(accessibility, text='Reset setting', command=lambda: self.set_editor_accessibility(False)).pack(side='left', padx=5)
        self.editor_status = tk.StringVar(value='No editor action has run.')
        ttk.Label(parent, textvariable=self.editor_status, wraplength=880).pack(anchor='w', pady=4)
        self.editor_report = text_box(parent, 12)

    def _editor_report(self, value):
        self.editor_report.configure(state='normal'); self.editor_report.delete('1.0','end')
        self.editor_report.insert('1.0', value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False, default=str))
        self.editor_report.configure(state='disabled')

    def detect_editors(self):
        found = editorflow.installed_editors()
        self.editor_status.set(f'Detected {len(found)} installed editor(s).')
        self._editor_report(found)

    def choose_editor_data_root(self):
        folder = filedialog.askdirectory(parent=self.app.root, initialdir=str(Path(self.editor_data_root.get()).expanduser().parent))
        if folder: self.editor_data_root.set(folder)

    def run_editor_action(self):
        action = self.editor_action.get(); path = self.editor_workspace_root.get().strip()
        if action in ('new-instance', 'extensions-dir'):
            path = self.editor_data_root.get().strip()
        folder_actions = ('open','new-window','reuse-window','wait','disable-gpu','log-startup','add-folder','new-instance','extensions-dir','skip-recent','profile-create','profile-open')
        paths = [path] if path and Path(path).exists() and action in folder_actions else []
        if action in ('diff','merge','goto'): paths = list(self.editor_action_paths)
        extension = self.editor_extension.get().strip() or None
        extra = (self.editor_action_value.get().strip(),) if self.editor_action_value.get().strip() else ()
        if action in ('install-extension','uninstall-extension','extensions-update') and not messagebox.askyesno('Confirm extension change', f'{action.replace("-", " ").title()} {extension or "the selected extension set"}? This contacts the editor extension service.', parent=self.app.root): return
        try:
            if action == 'extensions-list':
                profile = self.editor_action_value.get().strip() or None
                self.app.run('Reading installed editor extensions…', lambda: editorflow.extension_list(self.editor_id.get(), profile, False), lambda result: self._show_editor_cli_report(action, '\n'.join(result)))
                return
            if action == 'extensions-list-versions':
                profile = self.editor_action_value.get().strip() or None
                self.app.run('Reading installed editor extension versions…', lambda: editorflow.extension_list(self.editor_id.get(), profile, True), lambda result: self._show_editor_cli_report(action, '\n'.join(result)))
                return
            if action in ('install-extension','uninstall-extension'):
                profile = self.editor_action_value.get().strip() or None
                if action == 'install-extension' and extension and extension.lower().endswith('.vsix'):
                    argv = editorflow.install_local_vsix(extension, self.editor_id.get(), profile)
                else:
                    argv = editorflow.extension_cli_plan(action, extension, self.editor_id.get(), profile)
                process = subprocess.Popen(argv, shell=False, close_fds=True)
                self.editor_status.set(f'Started {action} (process {process.pid}).')
                return
            if action in ('profile-list','show-versions','show-help','status'):
                self.app.run(f'Reading editor {action}…', lambda: editorflow.editor_cli_report(self.editor_id.get(), action), lambda result: self._show_editor_cli_report(action, result))
                return
            process = editorflow.run_editor_action(self.editor_id.get(), action, paths=paths, extension=extension, extra=extra)
            self.editor_status.set(f'Started {action} for {self.editor_id.get()} (process {process.pid}).')
            self._editor_report({'command_started': action, 'editor': self.editor_id.get(), 'pid': process.pid})
        except Exception as exc: messagebox.showerror('Editor action failed', str(exc), parent=self.app.root)

    def choose_editor_action_paths(self):
        action = self.editor_action.get()
        if action not in ('diff', 'merge', 'goto'):
            self.editor_status.set('Choose Diff, Merge, or Go-to-line to pick action files.')
            return
        selected = filedialog.askopenfilenames(parent=self.app.root, title=f'Choose file(s) for {action}', initialdir=self.editor_workspace_root.get())
        if selected:
            self.editor_action_paths = list(selected)
            required = {'diff': 2, 'merge': 4, 'goto': 1}[action]
            self.editor_status.set(f'Selected {len(selected)} file(s); {action} requires {required}.')

    def _show_editor_cli_report(self, action, output):
        self.editor_status.set(f'Editor {action} result.')
        self._editor_report(output or '(No results.)')

    def save_editor_profile(self):
        try:
            path = editorflow.save_profile(self.editor_profile.get(), self.editor_id.get())
            self.editor_status.set('Saved settings profile: ' + str(path))
        except Exception as exc: messagebox.showerror('Profile save failed', str(exc), parent=self.app.root)

    def list_editor_profiles(self):
        rows = [p.name for p in editorflow.list_profiles()]
        self.editor_status.set(f'{len(rows)} local profile(s).'); self._editor_report(rows)

    def preview_editor_profile(self):
        try:
            settings, diff = editorflow.preview_profile(self.editor_profile.get(), self.editor_id.get())
            self.editor_status.set('Profile preview only; settings have not changed.'); self._editor_report(diff or json.dumps(settings, indent=2))
        except Exception as exc: messagebox.showerror('Profile preview failed', str(exc), parent=self.app.root)

    def activate_editor_profile(self):
        if not messagebox.askyesno('Activate editor profile', 'Replace this editor’s current settings with the selected local profile?', parent=self.app.root): return
        try:
            path = editorflow.activate_profile(self.editor_profile.get(), self.editor_id.get())
            self.editor_status.set('Activated profile. Current settings path: ' + str(path))
        except Exception as exc: messagebox.showerror('Profile activation failed', str(exc), parent=self.app.root)

    def remove_editor_profile(self):
        if not messagebox.askyesno('Remove local profile', 'Permanently remove the selected local settings snapshot?', parent=self.app.root): return
        try: self.editor_status.set('Removed: ' + str(editorflow.remove_profile(self.editor_profile.get())))
        except Exception as exc: messagebox.showerror('Profile removal failed', str(exc), parent=self.app.root)

    def inspect_editor_workspace(self):
        try:
            data = editorflow.workspace_metadata(self.editor_workspace_root.get())
            self.editor_status.set(f'Inspected {len(data)} workspace editor file(s); none were executed.')
            self._editor_report(data)
        except Exception as exc: messagebox.showerror('Workspace inspection failed', str(exc), parent=self.app.root)

    def validate_editor_workspace_config(self):
        try:
            report = editorflow.validate_workspace_config(self.editor_workspace_root.get(), self.workspace_config_kind.get())
            self.editor_status.set('Workspace config is valid; it was read without executing tasks.')
            self._editor_report(report)
        except Exception as exc: messagebox.showerror('Workspace config validation failed', str(exc), parent=self.app.root)

    def open_editor_workspace_config(self):
        try:
            process = editorflow.open_workspace_config(self.editor_workspace_root.get(), self.workspace_config_kind.get(), self.editor_id.get())
            self.editor_status.set(f'Opened workspace config in {self.editor_id.get()} (process {process.pid}).')
        except Exception as exc: messagebox.showerror('Could not open workspace config', str(exc), parent=self.app.root)

    def backup_editor_settings(self):
        try: self.editor_status.set('Settings backup saved: ' + str(editorflow.backup_settings(self.editor_id.get())))
        except Exception as exc: messagebox.showerror('Settings backup failed', str(exc), parent=self.app.root)

    def restore_editor_settings(self):
        path = filedialog.askopenfilename(parent=self.app.root, title='Choose settings backup', filetypes=[('JSON settings', '*.json'), ('All files', '*')])
        if not path: return
        if not messagebox.askyesno('Restore editor settings', 'Replace current editor settings with this backup?', parent=self.app.root): return
        try: self.editor_status.set('Restored settings: ' + str(editorflow.restore_settings(self.editor_id.get(), path)))
        except Exception as exc: messagebox.showerror('Settings restore failed', str(exc), parent=self.app.root)

    def export_editor_snapshot(self):
        path = filedialog.asksaveasfilename(parent=self.app.root, title='Export portable editor settings', defaultextension='.json', filetypes=[('OctoShip editor settings', '*.json')])
        if not path: return
        try:
            snapshot = editorflow.settings_snapshot(self.editor_id.get())
            target = Path(path)
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(snapshot, stream, ensure_ascii=False, indent=2); stream.write('\n')
            self.editor_status.set('Exported credential-filtered settings: ' + str(target))
        except Exception as exc: messagebox.showerror('Settings export failed', str(exc), parent=self.app.root)

    def import_editor_snapshot(self):
        path = filedialog.askopenfilename(parent=self.app.root, title='Choose portable editor settings', filetypes=[('OctoShip editor settings', '*.json'), ('All files', '*')])
        if not path: return
        try:
            with open(path, 'r', encoding='utf-8') as stream: snapshot = json.load(stream)
            if not isinstance(snapshot, dict) or not isinstance(snapshot.get('files'), dict): raise ValueError('File is not an OctoShip settings export.')
            if not messagebox.askyesno('Import portable settings', f'Import {len(snapshot["files"])} editor configuration file(s)? Existing files with matching names will be replaced.', parent=self.app.root): return
            imported = editorflow.import_settings_snapshot(self.editor_id.get(), snapshot)
            self.editor_status.set('Imported files: ' + ', '.join(imported))
        except Exception as exc: messagebox.showerror('Settings import failed', str(exc), parent=self.app.root)

    def preview_editor_accessibility(self):
        try:
            _, _, diff = editorflow.accessibility_preview(self.editor_id.get())
            self.editor_status.set('Accessibility preset preview only; settings have not changed.')
            self._editor_report(diff or 'All supported accessibility settings are already enabled.')
        except Exception as exc: messagebox.showerror('Accessibility preview failed', str(exc), parent=self.app.root)

    def apply_editor_accessibility(self):
        if not messagebox.askyesno('Apply accessibility settings', 'Apply the listed settings to this editor? Existing unrelated settings are preserved.', parent=self.app.root): return
        try: self.editor_status.set('Applied accessibility preferences: ' + str(editorflow.apply_accessibility_preset(self.editor_id.get())))
        except Exception as exc: messagebox.showerror('Accessibility update failed', str(exc), parent=self.app.root)

    def set_editor_accessibility(self, enabled):
        try:
            path = editorflow.set_accessibility_option(self.editor_id.get(), self.editor_accessibility_key.get(), enabled)
            self.editor_status.set(('Enabled ' if enabled else 'Reset ') + self.editor_accessibility_key.get() + ': ' + str(path))
        except Exception as exc: messagebox.showerror('Accessibility setting failed', str(exc), parent=self.app.root)

    def detect_terminal_shells(self):
        profiles = editorflow.available_terminal_profiles()
        self.terminal_profiles = {row['name']: row for row in profiles}
        self.terminal_shell_picker.configure(values=tuple(self.terminal_profiles))
        if profiles and self.terminal_shell.get() not in self.terminal_profiles:
            self.terminal_shell.set(profiles[0]['name'])
        self.editor_status.set(f'Detected {len(profiles)} supported terminal shell(s).')
        self._editor_report(profiles)

    def preview_terminal_profile(self):
        profile = getattr(self, 'terminal_profiles', {}).get(self.terminal_shell.get())
        if not profile:
            self.editor_status.set('Detect installed terminal shells and select one first.')
            return
        try:
            _, settings = editorflow.read_settings(self.editor_id.get())
            preview = dict(settings)
            editorflow.add_terminal_profile(preview, profile, self.terminal_default.get())
            self.editor_status.set('Terminal profile preview only; settings have not changed.')
            self._editor_report(editorflow.settings_diff(settings, preview))
        except Exception as exc: messagebox.showerror('Terminal profile preview failed', str(exc), parent=self.app.root)

    def add_terminal_profile(self):
        profile = getattr(self, 'terminal_profiles', {}).get(self.terminal_shell.get())
        if not profile:
            self.editor_status.set('Detect installed terminal shells and select one first.')
            return
        if not messagebox.askyesno('Add terminal profile', 'Add this detected shell to editor settings?' + (' Set it as the default terminal?' if self.terminal_default.get() else ''), parent=self.app.root): return
        try:
            _, settings = editorflow.read_settings(self.editor_id.get())
            editorflow.add_terminal_profile(settings, profile, self.terminal_default.get())
            path = editorflow.write_settings(self.editor_id.get(), settings)
            self.editor_status.set('Added terminal profile: ' + str(path))
        except Exception as exc: messagebox.showerror('Terminal profile update failed', str(exc), parent=self.app.root)

    def remove_terminal_profile(self):
        try:
            _, settings = editorflow.read_settings(self.editor_id.get())
            profiles = settings.get('terminal.integrated.profiles.linux', {})
            if not isinstance(profiles, dict) or not profiles:
                self.editor_status.set('No terminal profiles are configured.')
                return
            name = self.terminal_shell.get()
            if name not in profiles:
                name = next(iter(profiles))
            if not messagebox.askyesno('Remove terminal profile', f'Remove {name} from editor settings?', parent=self.app.root): return
            editorflow.remove_terminal_profile(settings, name)
            path = editorflow.write_settings(self.editor_id.get(), settings)
            self.editor_status.set('Removed terminal profile: ' + str(path))
        except Exception as exc: messagebox.showerror('Terminal profile removal failed', str(exc), parent=self.app.root)

    def set_default_terminal(self):
        try:
            _, settings = editorflow.read_settings(self.editor_id.get())
            profiles = settings.get('terminal.integrated.profiles.linux', {})
            if not isinstance(profiles, dict) or not profiles:
                self.editor_status.set('Add a terminal profile before setting a default.')
                return
            name = self.terminal_shell.get()
            if name not in profiles:
                name = next(iter(profiles))
            if not messagebox.askyesno('Set default terminal', f'Use {name} for new integrated terminals?', parent=self.app.root): return
            editorflow.set_default_terminal_profile(settings, name)
            path = editorflow.write_settings(self.editor_id.get(), settings)
            self.editor_status.set(f'Default terminal is now {name}: {path}')
        except Exception as exc: messagebox.showerror('Default terminal update failed', str(exc), parent=self.app.root)

    def compare_editor_recommendations(self):
        root = self.editor_workspace_root.get()
        profile = self.editor_action_value.get().strip() or None
        def work():
            installed = editorflow.extension_list(self.editor_id.get(), profile, False)
            return editorflow.compare_workspace_extensions(root, installed)
        self.app.run('Comparing workspace extension recommendations…', work,
                     lambda result: (self.editor_status.set(f'{len(result["missing"])} recommended extension(s) are missing.'), self._editor_report(result)))

    def install_editor_recommendation(self):
        identifier = self.recommended_extension.get().strip()
        if not identifier:
            self.editor_status.set('Enter one exact recommendation ID first.')
            return
        if not messagebox.askyesno('Install recommended extension', f'Install {identifier} from the editor extension service?', parent=self.app.root): return
        try:
            process = editorflow.install_recommended_extension(self.editor_workspace_root.get(), identifier, self.editor_id.get(), self.editor_action_value.get().strip() or None)
            self.editor_status.set(f'Started installation of {identifier} (process {process.pid}).')
        except Exception as exc: messagebox.showerror('Could not install recommended extension', str(exc), parent=self.app.root)

    def choose_git_root(self):
        folder = filedialog.askdirectory(parent=self.app.root, initialdir=self.git_root.get())
        if folder:
            self.git_root.set(folder)

    def choose_recipe_root(self):
        folder = filedialog.askdirectory(parent=self.app.root, initialdir=self.recipe_root.get())
        if folder:
            self.recipe_root.set(folder)

    def preview_recipe(self):
        try:
            relative, data = project_recipes.render_recipe(self.recipe_key.get(), self.recipe_project.get(), self.recipe_summary.get())
            self.recipe_preview.configure(state='normal')
            self.recipe_preview.delete('1.0', 'end')
            self.recipe_preview.insert('1.0', data.decode('utf-8'))
            self.recipe_preview.configure(state='disabled')
            self.recipe_status.set('Preview: ' + str(Path(self.recipe_root.get()).expanduser() / relative))
        except Exception as exc:
            messagebox.showerror('Recipe preview failed', str(exc), parent=self.app.root)

    def create_project_recipe(self):
        try:
            target = project_recipes.create_recipe(self.recipe_root.get(), self.recipe_key.get(), self.recipe_project.get(), self.recipe_summary.get())
            self.recipe_status.set('Created: ' + str(target))
            self.preview_recipe()
            self.recipe_status.set('Created: ' + str(target))
        except Exception as exc:
            messagebox.showerror('Could not create recipe', str(exc), parent=self.app.root)

    def _make_report_controls(self, parent, key):
        row = ttk.Frame(parent); row.pack(fill='x', pady=(2, 6))
        query = tk.StringVar()
        severity = tk.StringVar(value='All')
        ttk.Label(row, text='Filter').pack(side='left')
        ttk.Entry(row, textvariable=query).pack(side='left', fill='x', expand=True, padx=6)
        ttk.Combobox(row, textvariable=severity, values=('All', 'Problems', 'Error', 'Review', 'OK', 'Info'), state='readonly', width=12).pack(side='left')
        ttk.Button(row, text='Copy selected row', command=lambda k=key: self._copy_report_row(k)).pack(side='left', padx=6)
        ttk.Button(row, text='Save JSON…', command=lambda k=key: self._save_report_json(k)).pack(side='left')
        query.trace_add('write', lambda *_args, k=key: self._filter_report(k))
        severity.trace_add('write', lambda *_args, k=key: self._filter_report(k))
        self._report_controls[key] = (query, severity)
        self._report_rows[key] = []

    def _register_report(self, key, tree):
        self._report_trees[key] = tree
        for column in tree['columns']:
            tree.heading(column, command=lambda k=key, c=column: self._sort_report(k, c))

    def _filter_report(self, key):
        tree = self._report_trees.get(key)
        if tree is None:
            return
        query, severity = self._report_controls[key]
        needle = query.get().strip().casefold()
        for item in tree.get_children():
            tree.delete(item)
        for row in self._report_rows.get(key, []):
            if key == 'git':
                values = (row.status.upper(), row.title, row.detail)
            elif key == 'project':
                values = ('REVIEW', row.code, row.path, row.message)
            elif key == 'release':
                values = (row.status.upper(), row.title, row.detail)
            else:
                values = (row.status.upper(), row.code, row.detail)
            searchable = [str(value) for value in values]
            searchable.append(str(getattr(row, 'key', getattr(row, 'code', ''))))
            if needle and needle not in ' '.join(searchable).casefold():
                continue
            status = str(values[0]).upper()
            selected = severity.get()
            if selected == 'Problems' and status not in ('ERROR', 'REVIEW', 'WARNING'):
                continue
            if selected in ('Error', 'Review', 'OK', 'Info') and status != selected.upper():
                continue
            tree.insert('', 'end', values=values)

    def _sort_report(self, key, column):
        tree = self._report_trees[key]
        reverse = self._sort_reverse.get((key, column), False)
        rows = [(tree.set(iid, column), iid) for iid in tree.get_children('')]
        for index, (_value, iid) in enumerate(sorted(rows, key=lambda row: row[0].casefold(), reverse=reverse)):
            tree.move(iid, '', index)
        self._sort_reverse[(key, column)] = not reverse

    def _copy_report_row(self, key):
        tree = self._report_trees[key]
        selected = tree.selection()
        if not selected:
            messagebox.showinfo('Select a report row', 'Choose a report row before copying it.', parent=self.app.root)
            return
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append('\t'.join(str(x) for x in tree.item(selected[0], 'values')))
        self.app.record('Copied the selected local diagnostic row to the clipboard.')

    def _save_report_json(self, key):
        rows = self._report_rows.get(key, [])
        if not rows:
            messagebox.showinfo('No report yet', 'Run this audit before saving a report.', parent=self.app.root)
            return
        if not messagebox.askyesno('Save local report?', 'This report may contain local paths, filenames, and repository metadata. Review it before sharing.', parent=self.app.root, default='no'):
            return
        target = filedialog.asksaveasfilename(parent=self.app.root, title='Save diagnostics report',
                                              defaultextension='.json', filetypes=[('JSON report', '*.json')])
        if not target:
            return
        try:
            Path(target).write_text(json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        except OSError as exc:
            messagebox.showerror('Report could not be saved', str(exc), parent=self.app.root)
            return
        self.app.record('Saved diagnostics JSON report: ' + str(target))

    def inspect_local_git(self):
        root = self.git_root.get().strip()
        if not root:
            messagebox.showinfo('Choose a repository', 'Select a local Git working tree first.', parent=self.app.root)
            return
        for item in self.git_report.get_children():
            self.git_report.delete(item)
        self.git_status.set('Inspecting local Git metadata. No network requests are made…')

        def done(rows):
            self._report_rows['git'] = rows
            self._filter_report('git')
            self.git_status.set(f'{len(rows)} local checks completed. Review working-tree, sensitive-name, and conflict findings before publishing.')

        def error(message):
            self.git_status.set('Inspection incomplete: ' + str(message))

        self.app.run('Inspecting local Git…', lambda: git_insights.inspect_repository(root), done, error)

    def choose_project_root(self):
        folder = filedialog.askdirectory(parent=self.app.root, initialdir=self.project_root.get())
        if folder:
            self.project_root.set(folder)

    def audit_local_project(self):
        root = self.project_root.get().strip()
        if not root:
            messagebox.showinfo('Choose a project', 'Select a local project folder first.', parent=self.app.root)
            return
        for item in self.project_report.get_children():
            self.project_report.delete(item)
        self.project_status.set('Auditing up to 10,000 files and 8 MiB of text. No code is executed…')

        def done(rows):
            self._report_rows['project'] = rows
            self._filter_report('project')
            self.project_status.set(f'{len(rows)} finding(s). A clean report covers only supported checks and bounded file content.')

        def error(message):
            self.project_status.set('Audit incomplete: ' + str(message))

        self.app.run('Auditing project…', lambda: project_audit.audit_project(root), done, error)

    def choose_release_folder(self):
        folder = filedialog.askdirectory(parent=self.app.root, initialdir=self.release_folder.get())
        if folder:
            self.release_folder.set(folder)

    def audit_release_folder(self):
        folder = self.release_folder.get().strip()
        if not folder:
            messagebox.showinfo('Choose a folder', 'Select a release artifact folder first.', parent=self.app.root)
            return
        for item in self.release_audit_report.get_children(): self.release_audit_report.delete(item)
        version = self.release_version.get().strip()
        self.release_audit_status.set('Checking up to 500 regular artifacts. No files are executed or extracted…')

        def done(rows):
            self._report_rows['release'] = rows
            self._filter_report('release')
            self.release_audit_status.set(f'{len(rows)} artifact checks completed. Checksums establish byte agreement, not publisher identity or trust.')

        def error(message): self.release_audit_status.set('Audit incomplete: ' + str(message))
        self.app.run('Auditing release artifacts…', lambda: release_audit.audit_release(folder, version), done, error)

    def create_release_manifest(self):
        folder = self.release_folder.get().strip()
        if not folder:
            messagebox.showinfo('Choose a folder', 'Select a release artifact folder first.', parent=self.app.root)
            return
        target = filedialog.asksaveasfilename(parent=self.app.root, title='Create SHA-256 manifest',
                                              initialdir=folder, initialfile='SHA256SUMS.txt',
                                              defaultextension='.txt', filetypes=[('SHA-256 manifest', '*.txt *.sha256')])
        if not target:
            return
        if Path(target).exists() and not messagebox.askyesno('Replace manifest?', f'Replace this checksum manifest?\n{target}', parent=self.app.root, default='no'):
            return

        def done(result):
            path, count = result
            self.release_audit_status.set(f'Wrote {count} artifact checksum(s) to {path}. Run Audit artifacts to verify them.')
            self.app.record(f'Created release checksum manifest: {path}')

        def error(message): self.release_audit_status.set('Manifest was not created: ' + str(message))
        self.app.run('Creating checksum manifest…', lambda: release_audit.create_checksum_manifest(folder, target), done, error)

    def audit_workspace_state(self):
        folder = self.workspace_root.get().strip()
        if not folder:
            messagebox.showinfo('Choose a folder', 'Select the OctoShip state folder first.', parent=self.app.root)
            return
        for item in self.workspace_report.get_children(): self.workspace_report.delete(item)
        self.workspace_status.set('Inspecting saved local queue state; no queued work will be resumed…')

        def done(rows):
            self._report_rows['workspace'] = rows
            self._filter_report('workspace')
            self.workspace_status.set(f'{len(rows)} local state checks completed. Review flagged rows before deleting or sharing state files.')

        def error(message): self.workspace_status.set('Audit incomplete: ' + str(message))
        self.app.run('Auditing OctoShip workspace…', lambda: workspace_audit.audit_workspace(folder), done, error)

    def load_dependabot_alerts(self):
        context = self.context()
        if not context:
            return
        api, repo, _branch = context
        self.security_alert_repo = repo
        self.security_status.set(f'Loading open Dependabot alerts for {repo}…')
        for item in self.security_alerts.get_children():
            self.security_alerts.delete(item)

        def done(alerts):
            for alert in alerts:
                vulnerability = alert.get('security_vulnerability') or {}
                dependency = alert.get('dependency') or {}
                package = dependency.get('package') or {}
                fixed = (vulnerability.get('first_patched_version') or {}).get('identifier') or 'No fix listed'
                self.security_alerts.insert('', 'end', values=(
                    str(vulnerability.get('severity') or 'unknown').title(),
                    str(package.get('name') or 'Unknown package'),
                    str(fixed),
                    str(dependency.get('manifest_path') or 'Unknown manifest'),
                ))
            if alerts:
                self.security_status.set(f'{len(alerts)} open alert(s) returned by GitHub for {repo}. Select an alert and open GitHub for full advisory details.')
            else:
                self.security_status.set(f'GitHub returned no open Dependabot alerts for {repo}.')

        def error(message):
            self.security_status.set('Could not load alerts. If GitHub returned 403 or 404, check Dependabot alerts availability and read permission.')

        self.app.run('Loading Dependabot alerts…', lambda: api.dependabot_alerts(repo), done, error)

    def open_security_page(self):
        repo = self.security_alert_repo or self.app.repo.get().strip()
        try:
            path = self.app.api.repo_path(repo) if self.app.api else None
            if not path:
                raise OctoShipError('Connect to GitHub first.')
        except OctoShipError as exc:
            messagebox.showerror('Repository', str(exc), parent=self.app.root)
            return
        webbrowser.open('https://github.com/' + repo + '/security/dependabot')

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
