"""Local UI for building and tracking a project-lifecycle plan."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import lifecycle


class LifecyclePanel:
    def __init__(self, app, parent):
        self.app = app
        self.plan = None
        self.catalog_rows = {}
        self.row_tasks = {}
        self.tabs = ttk.Notebook(parent)
        self.tabs.pack(fill="both", expand=True)
        guide = ttk.Frame(self.tabs, padding=12)
        tracker = ttk.Frame(self.tabs, padding=12)
        operations = ttk.Frame(self.tabs, padding=12)
        records = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(guide, text="Lifecycle playbook")
        self.tabs.add(tracker, text="Project task plan")
        self.tabs.add(operations, text="Planning operations")
        self.tabs.add(records, text="Project records")

        ttk.Label(guide, text="Select useful project activities and add them to a local task plan. This playbook tracks work; it does not generate files, execute project code, contact GitHub, or deploy.", wraplength=850).pack(anchor="w")
        controls = ttk.Frame(guide); controls.pack(fill="x", pady=8)
        self.query = tk.StringVar()
        self.phase = tk.StringVar(value="All phases")
        ttk.Label(controls, text="Search").pack(side="left")
        search = ttk.Entry(controls, textvariable=self.query, width=28); search.pack(side="left", padx=6)
        ttk.Label(controls, text="Phase").pack(side="left", padx=(8, 0))
        phases = [phase[1] for phase in lifecycle._PHASES]
        ttk.Combobox(controls, textvariable=self.phase, values=["All phases", *phases], state="readonly", width=24).pack(side="left", padx=6)
        self.catalog = ttk.Treeview(guide, columns=("phase", "task", "guidance"), show="headings", selectmode="extended", height=17)
        for key, title, width in (("phase", "PHASE", 175), ("task", "ACTIVITY", 250), ("guidance", "WHAT TO DO", 520)):
            self.catalog.heading(key, text=title); self.catalog.column(key, width=width, minwidth=90, stretch=key == "guidance")
        scroll = ttk.Scrollbar(guide, orient="vertical", command=self.catalog.yview)
        self.catalog.configure(yscrollcommand=scroll.set)
        self.catalog.pack(side="left", fill="both", expand=True); scroll.pack(side="right", fill="y")
        buttons = ttk.Frame(guide); buttons.pack(fill="x", pady=8)
        ttk.Button(buttons, text="Add selected to plan", command=self.add_selected).pack(side="left")
        ttk.Button(buttons, text="Start with all activities", command=self.add_all).pack(side="left", padx=6)
        self.catalog_count = tk.StringVar()
        ttk.Label(buttons, textvariable=self.catalog_count).pack(side="right")
        self.query.trace_add("write", lambda *_: self.refresh_catalog())
        self.phase.trace_add("write", lambda *_: self.refresh_catalog())
        self.refresh_catalog()

        header = ttk.Frame(tracker); header.pack(fill="x")
        self.plan_name = tk.StringVar(value="Project lifecycle plan")
        ttk.Label(header, text="Plan name").pack(side="left")
        ttk.Entry(header, textvariable=self.plan_name, width=40).pack(side="left", padx=6)
        ttk.Button(header, text="New plan from selected", command=self.add_selected).pack(side="left")
        ttk.Button(header, text="Open plan…", command=self.open_plan).pack(side="left", padx=6)
        self.summary = tk.StringVar(value="No plan loaded.")
        ttk.Label(tracker, textvariable=self.summary, wraplength=850).pack(anchor="w", pady=6)
        self.tasks = ttk.Treeview(tracker, columns=("phase", "task", "status", "priority", "owner", "due"), show="headings", selectmode="browse", height=12)
        for key, title, width in (("phase", "PHASE", 145), ("task", "ACTIVITY", 260), ("status", "STATUS", 80), ("priority", "PRIORITY", 80), ("owner", "OWNER", 140), ("due", "DUE", 100)):
            self.tasks.heading(key, text=title); self.tasks.column(key, width=width, minwidth=65, stretch=key == "task")
        task_scroll = ttk.Scrollbar(tracker, orient="vertical", command=self.tasks.yview)
        self.tasks.configure(yscrollcommand=task_scroll.set)
        self.tasks.pack(side="left", fill="both", expand=True); task_scroll.pack(side="right", fill="y")
        self.tasks.bind("<<TreeviewSelect>>", lambda _event: self.load_task_fields())
        edit = ttk.LabelFrame(tracker, text="Selected task", padding=8); edit.pack(fill="x", pady=8)
        self.status = tk.StringVar(value="todo"); self.priority = tk.StringVar(value="normal")
        self.owner = tk.StringVar(); self.start = tk.StringVar(); self.due = tk.StringVar(); self.duration = tk.StringVar(value="1")
        self.blocked_reason = tk.StringVar(); self.notes = tk.StringVar(); self.evidence = tk.StringVar()
        for label, variable, choices in (("Status", self.status, lifecycle.STATUSES), ("Priority", self.priority, lifecycle.PRIORITIES)):
            ttk.Label(edit, text=label).pack(side="left")
            ttk.Combobox(edit, textvariable=variable, values=choices, state="readonly", width=12).pack(side="left", padx=(4, 12))
        for label, variable, width in (("Owner", self.owner, 18), ("Start YYYY-MM-DD", self.start, 14), ("Due YYYY-MM-DD", self.due, 14), ("Days", self.duration, 5), ("Blocked reason", self.blocked_reason, 20), ("Notes", self.notes, 26), ("Evidence", self.evidence, 26)):
            ttk.Label(edit, text=label).pack(side="left")
            ttk.Entry(edit, textvariable=variable, width=width).pack(side="left", padx=(4, 10))
        actions = ttk.Frame(tracker); actions.pack(fill="x")
        ttk.Button(actions, text="Update selected task", command=self.update_selected).pack(side="left")
        ttk.Button(actions, text="Remove selected task", command=self.remove_selected).pack(side="left", padx=6)
        ttk.Button(actions, text="Save plan…", command=self.save_plan).pack(side="left")
        ttk.Button(actions, text="Export Markdown…", command=lambda: self.export("md")).pack(side="left", padx=6)
        ttk.Button(actions, text="Export CSV…", command=lambda: self.export("csv")).pack(side="left")

        ttk.Label(operations, text="Dependencies, schedule, risks, milestones, plan comparison, merge, archive, and transfer tools operate only on the current local plan.", wraplength=850).pack(anchor="w")
        dependency = ttk.LabelFrame(operations, text="Dependencies and readiness", padding=8); dependency.pack(fill="x", pady=5)
        self.dependency_task = tk.StringVar(); self.dependency_parent = tk.StringVar()
        ttk.Label(dependency, text="Task ID").pack(side="left"); ttk.Entry(dependency, textvariable=self.dependency_task, width=20).pack(side="left", padx=4)
        ttk.Label(dependency, text="Depends on ID").pack(side="left"); ttk.Entry(dependency, textvariable=self.dependency_parent, width=20).pack(side="left", padx=4)
        ttk.Button(dependency, text="Add dependency", command=lambda: self.dependency_action(True)).pack(side="left", padx=4)
        ttk.Button(dependency, text="Remove dependency", command=lambda: self.dependency_action(False)).pack(side="left")
        ttk.Button(dependency, text="Show ready / blocked", command=self.show_readiness).pack(side="left", padx=4)

        scheduling = ttk.LabelFrame(operations, text="Schedule", padding=8); scheduling.pack(fill="x", pady=5)
        self.schedule_start = tk.StringVar(); self.weekdays_only = tk.BooleanVar(value=True)
        ttk.Label(scheduling, text="Start YYYY-MM-DD").pack(side="left"); ttk.Entry(scheduling, textvariable=self.schedule_start, width=16).pack(side="left", padx=4)
        ttk.Checkbutton(scheduling, text="Weekdays only", variable=self.weekdays_only).pack(side="left", padx=4)
        ttk.Button(scheduling, text="Schedule dependencies", command=self.schedule).pack(side="left", padx=4)
        ttk.Button(scheduling, text="Show phase rollup", command=self.show_rollup).pack(side="left")
        ttk.Button(scheduling, text="Validate schedule", command=self.show_schedule_issues).pack(side="left", padx=4)

        baseline_row = ttk.LabelFrame(operations, text="Baseline, calendar, and workload", padding=8); baseline_row.pack(fill="x", pady=5)
        self.baseline_name = tk.StringVar(value="Approved baseline"); self.baseline_id = tk.StringVar()
        ttk.Label(baseline_row, text="Baseline name").pack(side="left"); ttk.Entry(baseline_row, textvariable=self.baseline_name, width=18).pack(side="left", padx=3)
        ttk.Button(baseline_row, text="Capture baseline", command=self.capture_baseline).pack(side="left", padx=3)
        ttk.Label(baseline_row, text="Baseline ID").pack(side="left"); ttk.Entry(baseline_row, textvariable=self.baseline_id, width=14).pack(side="left", padx=3)
        ttk.Button(baseline_row, text="Compare baseline", command=self.compare_baseline).pack(side="left", padx=3)
        self.calendar_start = tk.StringVar(); self.calendar_end = tk.StringVar(); self.owner_names = tk.StringVar()
        ttk.Label(baseline_row, text="Due window").pack(side="left")
        ttk.Entry(baseline_row, textvariable=self.calendar_start, width=12).pack(side="left", padx=2)
        ttk.Entry(baseline_row, textvariable=self.calendar_end, width=12).pack(side="left", padx=2)
        ttk.Button(baseline_row, text="Show calendar", command=self.show_calendar).pack(side="left", padx=3)
        ttk.Label(baseline_row, text="Owners (comma separated)").pack(side="left")
        ttk.Entry(baseline_row, textvariable=self.owner_names, width=24).pack(side="left", padx=3)
        ttk.Button(baseline_row, text="Balance unassigned", command=self.balance_work).pack(side="left", padx=3)

        risk = ttk.LabelFrame(operations, text="Risk register", padding=8); risk.pack(fill="x", pady=5)
        self.risk_title = tk.StringVar(); self.risk_probability = tk.IntVar(value=3); self.risk_impact = tk.IntVar(value=3); self.risk_owner = tk.StringVar(); self.risk_response = tk.StringVar()
        for label, variable, width in (("Risk", self.risk_title, 22), ("Likelihood 1–5", self.risk_probability, 7), ("Impact 1–5", self.risk_impact, 7), ("Owner", self.risk_owner, 14), ("Response", self.risk_response, 20)):
            ttk.Label(risk, text=label).pack(side="left"); ttk.Entry(risk, textvariable=variable, width=width).pack(side="left", padx=3)
        ttk.Button(risk, text="Add risk", command=self.add_risk).pack(side="left", padx=4)
        ttk.Button(risk, text="Show risk ranking", command=self.show_risks).pack(side="left")

        misc = ttk.LabelFrame(operations, text="Milestones, plan comparison, archive and transfer", padding=8); misc.pack(fill="x", pady=5)
        self.milestone_name = tk.StringVar(); self.milestone_ids = tk.StringVar()
        ttk.Label(misc, text="Milestone").pack(side="left"); ttk.Entry(misc, textvariable=self.milestone_name, width=18).pack(side="left", padx=3)
        ttk.Label(misc, text="Task IDs (comma separated)").pack(side="left"); ttk.Entry(misc, textvariable=self.milestone_ids, width=28).pack(side="left", padx=3)
        ttk.Button(misc, text="Add milestone", command=self.add_milestone).pack(side="left", padx=3)
        ttk.Button(misc, text="Compare plan…", command=self.compare_plan).pack(side="left", padx=3)
        self.merge_strategy = tk.StringVar(value="keep-target")
        ttk.Combobox(misc, textvariable=self.merge_strategy, values=("keep-target", "take-incoming", "prefer-latest-status"), state="readonly", width=21).pack(side="left")
        ttk.Button(misc, text="Merge plan…", command=self.merge_plan).pack(side="left", padx=3)
        self.archive_ids = tk.StringVar()
        ttk.Label(misc, text="IDs").pack(side="left"); ttk.Entry(misc, textvariable=self.archive_ids, width=22).pack(side="left", padx=3)
        ttk.Button(misc, text="Archive", command=lambda: self.archive_action(True)).pack(side="left", padx=2)
        ttk.Button(misc, text="Restore", command=lambda: self.archive_action(False)).pack(side="left", padx=2)
        ttk.Button(misc, text="Import CSV…", command=self.import_csv).pack(side="left", padx=3)
        ttk.Button(misc, text="Export JSON…", command=lambda: self.export("json")).pack(side="left")
        governance = ttk.LabelFrame(operations, text="Phase gates and project status", padding=8); governance.pack(fill="x", pady=5)
        self.gate_phase = tk.StringVar(value="planning")
        phase_ids = tuple(dict.fromkeys(item["phase_id"] for item in lifecycle.PLAYBOOK))
        ttk.Label(governance, text="Phase").pack(side="left")
        ttk.Combobox(governance, textvariable=self.gate_phase, values=phase_ids, state="readonly", width=18).pack(side="left", padx=3)
        ttk.Button(governance, text="Check readiness", command=self.show_phase_readiness).pack(side="left", padx=3)
        self.close_rationale = tk.StringVar()
        ttk.Entry(governance, textvariable=self.close_rationale, width=32).pack(side="left", padx=3)
        ttk.Button(governance, text="Close phase…", command=self.close_phase).pack(side="left", padx=3)
        ttk.Button(governance, text="Reopen phase", command=self.reopen_phase).pack(side="left", padx=3)
        self.plan_status = tk.StringVar(value="active"); self.plan_status_note = tk.StringVar()
        ttk.Combobox(governance, textvariable=self.plan_status, values=("planning", "active", "paused", "closed"), state="readonly", width=12).pack(side="left", padx=3)
        ttk.Entry(governance, textvariable=self.plan_status_note, width=24).pack(side="left", padx=3)
        ttk.Button(governance, text="Set plan status", command=self.set_plan_status).pack(side="left", padx=3)
        self.followup_name = tk.StringVar(value="Follow-up plan")
        ttk.Entry(governance, textvariable=self.followup_name, width=22).pack(side="left", padx=3)
        ttk.Button(governance, text="Carry open tasks forward", command=self.carry_forward).pack(side="left", padx=3)
        self.operations_output = tk.Text(operations, height=11, wrap="word", font=("Monospace", 9), state="disabled")
        self.operations_output.pack(fill="both", expand=True, pady=5)

        record_tabs = ttk.Notebook(records); record_tabs.pack(fill="both", expand=True)
        self.record_vars = {}
        decision_page, issue_page, metric_page, lesson_page, effort_page = [ttk.Frame(record_tabs, padding=12) for _ in range(5)]
        for page, title in zip((decision_page, issue_page, metric_page, lesson_page, effort_page), ("Decisions", "Issues", "Outcomes", "Lessons", "Effort")):
            record_tabs.add(page, text=title)

        def entry_row(parent, key, label, row, width=36, values=None):
            variable = tk.StringVar()
            self.record_vars[key] = variable
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
            widget = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly" if values else "normal", width=width) if values else ttk.Entry(parent, textvariable=variable, width=width)
            widget.grid(row=row, column=1, sticky="ew", padx=6, pady=4)
            parent.columnconfigure(1, weight=1)
            return variable

        entry_row(decision_page, "decision_title", "Decision title", 0)
        entry_row(decision_page, "decision_text", "Decision", 1)
        entry_row(decision_page, "decision_context", "Context", 2)
        entry_row(decision_page, "decision_owner", "Owner", 3)
        entry_row(decision_page, "decision_id", "Decision ID", 4)
        entry_row(decision_page, "decision_status", "Status", 5, values=("proposed", "accepted", "reversed", "superseded"))
        entry_row(decision_page, "decision_outcome", "Outcome", 6)
        entry_row(decision_page, "decision_replacement", "Replacement decision ID", 7)
        self.record_buttons(decision_page, [("Add decision", self.add_decision_ui), ("Update decision", self.update_decision_ui), ("Supersede decision", self.supersede_decision_ui), ("Show decision log", self.show_decisions_ui)])

        entry_row(issue_page, "issue_title", "Issue title", 0)
        entry_row(issue_page, "issue_severity", "Severity", 1, values=("blocker", "high", "medium", "low"))
        entry_row(issue_page, "issue_owner", "Owner", 2)
        entry_row(issue_page, "issue_due", "Due YYYY-MM-DD", 3)
        entry_row(issue_page, "issue_task", "Linked task ID", 4)
        entry_row(issue_page, "issue_action", "Next action", 5)
        entry_row(issue_page, "issue_id", "Issue ID to update", 6)
        entry_row(issue_page, "issue_status", "Status", 7, values=("open", "triaged", "in_progress", "resolved", "wont_fix"))
        entry_row(issue_page, "issue_resolution", "Resolution", 8)
        self.record_buttons(issue_page, [("Add issue", self.add_issue_ui), ("Update issue", self.update_issue_ui), ("Show issue register", self.show_issues_ui)])

        entry_row(metric_page, "metric_name", "Metric name", 0)
        entry_row(metric_page, "metric_unit", "Unit", 1)
        entry_row(metric_page, "metric_baseline", "Baseline", 2)
        entry_row(metric_page, "metric_target", "Target", 3)
        entry_row(metric_page, "metric_direction", "Direction", 4, values=("increase", "decrease"))
        entry_row(metric_page, "metric_id", "Metric ID", 5)
        entry_row(metric_page, "metric_actual", "Latest actual", 6)
        self.record_buttons(metric_page, [("Add outcome metric", self.add_metric_ui), ("Update actual", self.update_metric_ui), ("Show outcome report", self.show_metrics_ui)])

        entry_row(lesson_page, "lesson_title", "Lesson title", 0)
        entry_row(lesson_page, "lesson_observation", "Observation", 1)
        entry_row(lesson_page, "lesson_recommendation", "Recommendation", 2)
        entry_row(lesson_page, "lesson_category", "Category", 3, values=("process", "product", "quality", "operations", "team", "general"))
        entry_row(lesson_page, "lesson_id", "Lesson ID", 4)
        entry_row(lesson_page, "lesson_tasks", "Follow-up task IDs (comma separated)", 5)
        self.record_buttons(lesson_page, [("Capture lesson", self.add_lesson_ui), ("Apply to tasks", self.apply_lesson_ui), ("Show lessons", self.show_lessons_ui)])

        entry_row(effort_page, "effort_task", "Task ID", 0)
        entry_row(effort_page, "effort_owner", "Owner", 1)
        entry_row(effort_page, "effort_date", "Work date YYYY-MM-DD", 2)
        entry_row(effort_page, "effort_hours", "Hours", 3)
        entry_row(effort_page, "effort_note", "Note", 4)
        entry_row(effort_page, "effort_estimate", "Estimated hours", 5)
        entry_row(effort_page, "effort_group", "Group report by", 6, values=("owner", "task", "date", "entry"))
        entry_row(effort_page, "effort_start", "Report start date", 7)
        entry_row(effort_page, "effort_end", "Report end date", 8)
        entry_row(effort_page, "effort_log_id", "Effort entry ID to remove", 9)
        self.record_buttons(effort_page, [("Set estimate", self.set_effort_estimate_ui), ("Log effort", self.log_effort_ui), ("Show effort report", self.show_effort_ui), ("Show task variance", self.show_effort_variance_ui), ("Remove effort entry", self.remove_effort_ui)])

        self.records_output = tk.Text(records, height=7, wrap="word", font=("Monospace", 9), state="disabled")
        self.records_output.pack(fill="x", pady=(8, 0))

    def record_buttons(self, parent, buttons):
        row = ttk.Frame(parent); row.grid(row=100, column=0, columnspan=2, sticky="ew", pady=8)
        for title, action in buttons:
            ttk.Button(row, text=title, command=action).pack(side="left", padx=(0, 6))

    def record_value(self, key):
        return self.record_vars[key].get().strip()

    def record_report(self, result):
        import json
        self.records_output.configure(state="normal"); self.records_output.delete("1.0", "end")
        self.records_output.insert("1.0", result if isinstance(result, str) else json.dumps(result, indent=2, ensure_ascii=False, default=str))
        self.records_output.configure(state="disabled")

    def run_record(self, operation):
        try:
            result = operation(self.require_plan())
            self.record_report(result)
            self.refresh_tasks()
        except Exception as exc: messagebox.showerror("Project records", str(exc), parent=self.app.root)

    def add_decision_ui(self):
        self.run_record(lambda plan: lifecycle.add_decision(plan, self.record_value("decision_title"), self.record_value("decision_text"), context=self.record_value("decision_context"), owner=self.record_value("decision_owner")))

    def update_decision_ui(self):
        self.run_record(lambda plan: lifecycle.update_decision(plan, self.record_value("decision_id"), status=self.record_value("decision_status") or None, outcome=self.record_value("decision_outcome") or None))

    def supersede_decision_ui(self):
        self.run_record(lambda plan: lifecycle.supersede_decision(plan, self.record_value("decision_id"), self.record_value("decision_replacement")))

    def show_decisions_ui(self):
        self.run_record(lambda plan: {"summary": lifecycle.decision_summary(plan), "decisions": lifecycle.decision_register(plan, status=self.record_value("decision_status") or None, owner=self.record_value("decision_owner") or None, query=self.record_value("decision_title"))})

    def add_issue_ui(self):
        self.run_record(lambda plan: lifecycle.add_issue(plan, self.record_value("issue_title"), self.record_value("issue_severity"), owner=self.record_value("issue_owner"), due=self.record_value("issue_due"), linked_task=self.record_value("issue_task"), next_action=self.record_value("issue_action")))

    def update_issue_ui(self):
        self.run_record(lambda plan: lifecycle.update_issue(plan, self.record_value("issue_id"), status=self.record_value("issue_status") or None, resolution=self.record_value("issue_resolution") or None))

    def show_issues_ui(self):
        self.run_record(lambda plan: {"summary": lifecycle.issue_summary(plan), "issues": lifecycle.issue_register(plan, status=self.record_value("issue_status") or None, severity=self.record_value("issue_severity") or None, owner=self.record_value("issue_owner") or None)})

    def add_metric_ui(self):
        self.run_record(lambda plan: lifecycle.add_metric(plan, self.record_value("metric_name"), self.record_value("metric_unit"), self.record_value("metric_baseline"), self.record_value("metric_target"), direction=self.record_value("metric_direction")))

    def update_metric_ui(self):
        self.run_record(lambda plan: lifecycle.update_metric_actual(plan, self.record_value("metric_id"), self.record_value("metric_actual")))

    def show_metrics_ui(self):
        self.run_record(lifecycle.metric_rollup)

    def add_lesson_ui(self):
        self.run_record(lambda plan: lifecycle.add_lesson(plan, self.record_value("lesson_title"), self.record_value("lesson_observation"), self.record_value("lesson_recommendation"), category=self.record_value("lesson_category")))

    def apply_lesson_ui(self):
        ids = [item.strip() for item in self.record_value("lesson_tasks").split(",") if item.strip()]
        self.run_record(lambda plan: lifecycle.apply_lesson(plan, self.record_value("lesson_id"), ids))

    def show_lessons_ui(self):
        self.run_record(lambda plan: {"summary": lifecycle.lesson_summary(plan), "lessons": lifecycle.lesson_register(plan, category=self.record_value("lesson_category") or None)})

    def set_effort_estimate_ui(self):
        self.run_record(lambda plan: {"estimate_hours": lifecycle.set_effort_estimate(plan, self.record_value("effort_task"), self.record_value("effort_estimate"))})

    def log_effort_ui(self):
        self.run_record(lambda plan: lifecycle.log_effort(plan, self.record_value("effort_task"), self.record_value("effort_owner"), self.record_value("effort_date"), self.record_value("effort_hours"), self.record_value("effort_note")))

    def show_effort_ui(self):
        start, end = self.record_value("effort_start"), self.record_value("effort_end")
        self.run_record(lambda plan: lifecycle.effort_report(plan, start_date=start or None, end_date=end or None, group_by=self.record_value("effort_group") or "owner"))

    def show_effort_variance_ui(self):
        self.run_record(lambda plan: lifecycle.effort_variance(plan, self.record_value("effort_task")))

    def remove_effort_ui(self):
        self.run_record(lambda plan: {"removed": lifecycle.remove_effort_log(plan, self.record_value("effort_log_id"))})

    def operation_report(self, value):
        import json
        self.operations_output.configure(state="normal")
        self.operations_output.delete("1.0", "end")
        self.operations_output.insert("1.0", value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False, default=str))
        self.operations_output.configure(state="disabled")

    def require_plan(self):
        if not self.plan: raise ValueError("Create or open a lifecycle plan first.")
        return self.plan

    def safe_operation(self, action):
        try:
            action()
            self.refresh_tasks()
        except Exception as exc:
            messagebox.showerror("Lifecycle operation", str(exc), parent=self.app.root)

    def dependency_action(self, add):
        def run():
            plan = self.require_plan()
            result = lifecycle.add_dependency(plan, self.dependency_task.get().strip(), self.dependency_parent.get().strip()) if add else lifecycle.remove_dependency(plan, self.dependency_task.get().strip(), self.dependency_parent.get().strip())
            self.operation_report({"updated": bool(result), "dependencies": lifecycle.dependencies_of(plan, self.dependency_task.get().strip())})
        self.safe_operation(run)

    def show_readiness(self):
        try:
            plan = self.require_plan()
            self.operation_report({"ready": [item["id"] for item in lifecycle.ready_tasks(plan)], "blocked": [item["id"] for item in lifecycle.blocked_tasks(plan)]})
        except Exception as exc: messagebox.showerror("Lifecycle operation", str(exc), parent=self.app.root)

    def schedule(self):
        self.safe_operation(lambda: (lifecycle.schedule_plan(self.require_plan(), self.schedule_start.get(), self.weekdays_only.get()), self.operation_report("Schedule updated. Review task start and due dates in the plan.")))

    def show_rollup(self):
        try: self.operation_report(lifecycle.phase_rollup(self.require_plan()))
        except Exception as exc: messagebox.showerror("Lifecycle operation", str(exc), parent=self.app.root)

    def show_schedule_issues(self):
        try: self.operation_report(lifecycle.validate_schedule(self.require_plan()))
        except Exception as exc: messagebox.showerror("Lifecycle operation", str(exc), parent=self.app.root)

    def capture_baseline(self):
        def run():
            baseline = lifecycle.capture_baseline(self.require_plan(), self.baseline_name.get())
            self.baseline_id.set(baseline["id"])
            self.operation_report({"captured": baseline["id"], "name": baseline["name"]})
        self.safe_operation(run)

    def compare_baseline(self):
        try: self.operation_report(lifecycle.compare_baseline(self.require_plan(), self.baseline_id.get().strip()))
        except Exception as exc: messagebox.showerror("Compare baseline", str(exc), parent=self.app.root)

    def show_calendar(self):
        try: self.operation_report(lifecycle.due_calendar(self.require_plan(), self.calendar_start.get(), self.calendar_end.get()))
        except Exception as exc: messagebox.showerror("Due calendar", str(exc), parent=self.app.root)

    def balance_work(self):
        owners = [name.strip() for name in self.owner_names.get().split(",") if name.strip()]
        self.safe_operation(lambda: self.operation_report(lifecycle.assign_unowned_tasks(self.require_plan(), owners)))

    def show_phase_readiness(self):
        try: self.operation_report(lifecycle.phase_readiness(self.require_plan(), self.gate_phase.get()))
        except Exception as exc: messagebox.showerror("Phase readiness", str(exc), parent=self.app.root)

    def close_phase(self):
        rationale = self.close_rationale.get().strip()
        self.safe_operation(lambda: self.operation_report(lifecycle.close_phase(self.require_plan(), self.gate_phase.get(), allow_open=bool(rationale), rationale=rationale)))

    def reopen_phase(self):
        self.safe_operation(lambda: self.operation_report({"reopened": lifecycle.set_phase_active(self.require_plan(), self.gate_phase.get())}))

    def set_plan_status(self):
        self.safe_operation(lambda: self.operation_report({"status": lifecycle.set_plan_status(self.require_plan(), self.plan_status.get(), self.plan_status_note.get())}))

    def carry_forward(self):
        self.safe_operation(lambda: self._install_plan(lifecycle.carry_forward_tasks(self.require_plan(), self.followup_name.get())))

    def _install_plan(self, plan):
        self.plan = plan
        self.plan_name.set(plan["name"])
        self.refresh_tasks()
        self.operation_report(f"Started {plan['name']} with {len(plan['tasks'])} carried tasks. Save it as a new JSON plan.")

    def add_risk(self):
        def run():
            risk = lifecycle.add_risk(self.require_plan(), self.risk_title.get(), self.risk_probability.get(), self.risk_impact.get(), self.risk_owner.get(), self.risk_response.get())
            self.operation_report(risk)
        self.safe_operation(run)

    def show_risks(self):
        try: self.operation_report({"summary": lifecycle.risk_summary(self.require_plan()), "risks": lifecycle.risk_register(self.plan)})
        except Exception as exc: messagebox.showerror("Lifecycle operation", str(exc), parent=self.app.root)

    def add_milestone(self):
        def run():
            ids = [item.strip() for item in self.milestone_ids.get().split(",") if item.strip()]
            milestone = lifecycle.add_milestone(self.require_plan(), self.milestone_name.get(), ids)
            self.operation_report({"milestone": milestone, "progress": lifecycle.milestone_progress(self.plan, milestone["id"])})
        self.safe_operation(run)

    def compare_plan(self):
        path = filedialog.askopenfilename(parent=self.app.root, filetypes=[("Lifecycle plan", "*.json")])
        if not path: return
        try: self.operation_report(lifecycle.compare_plans(self.require_plan(), lifecycle.load_plan(path)))
        except Exception as exc: messagebox.showerror("Compare plans", str(exc), parent=self.app.root)

    def merge_plan(self):
        path = filedialog.askopenfilename(parent=self.app.root, filetypes=[("Lifecycle plan", "*.json")])
        if not path: return
        self.safe_operation(lambda: self.operation_report(lifecycle.merge_plans(self.require_plan(), lifecycle.load_plan(path), self.merge_strategy.get())))

    def archive_action(self, archive):
        def run():
            ids = [item.strip() for item in self.archive_ids.get().split(",") if item.strip()]
            result = lifecycle.archive_tasks(self.require_plan(), ids) if archive else lifecycle.restore_tasks(self.require_plan(), ids)
            self.operation_report({"updated": result})
        self.safe_operation(run)

    def import_csv(self):
        path = filedialog.askopenfilename(parent=self.app.root, filetypes=[("Lifecycle CSV", "*.csv")])
        if not path: return
        try:
            if Path(path).stat().st_size > 2_000_000: raise ValueError("Lifecycle CSV exceeds the 2 MB limit.")
            self.plan = lifecycle.import_csv(Path(path).read_text(encoding="utf-8"), self.plan_name.get())
            self.refresh_tasks()
            self.operation_report("CSV plan imported and validated.")
        except Exception as exc: messagebox.showerror("Import CSV", str(exc), parent=self.app.root)

    def refresh_catalog(self):
        self.catalog.delete(*self.catalog.get_children())
        selected_phase = self.phase.get()
        phase_id = next((key for key, label, _ in lifecycle._PHASES if label == selected_phase), "")
        rows = lifecycle.search_tasks(self.query.get(), phase_id)
        for item in rows:
            self.catalog.insert("", "end", iid=item["id"], values=(item["phase"], item["title"], item["guidance"]))
        self.catalog_count.set(f"{len(rows)} activities")

    def add_selected(self):
        if not self.plan:
            try:
                self.plan = lifecycle.new_plan(self.plan_name.get(), [])
            except Exception as exc:
                messagebox.showerror("Lifecycle plan", str(exc), parent=self.app.root); return
        selected = self.catalog.selection()
        for task_id in selected:
            if not any(task["id"] == task_id for task in self.plan["tasks"]):
                self.plan["tasks"].append(lifecycle.new_plan(self.plan["name"], [task_id])["tasks"][0])
        self.refresh_tasks()

    def add_all(self):
        self.plan = lifecycle.new_plan(self.plan_name.get())
        self.refresh_tasks()

    def refresh_tasks(self):
        self.tasks.delete(*self.tasks.get_children())
        for task in self.plan.get("tasks", []) if self.plan else []:
            self.tasks.insert("", "end", iid=task["id"], values=(task["phase"], task["title"], task["status"], task["priority"], task["owner"], task["due"]))
        info = lifecycle.plan_summary(self.plan) if self.plan else None
        self.summary.set(f"{self.plan['name']} · {info['total']} tasks · {info['completion_percent']}% done · {len(info['overdue'])} overdue" if info else "No plan loaded.")

    def load_task_fields(self):
        if not self.plan or not self.tasks.selection(): return
        task_id = self.tasks.selection()[0]
        task = next((item for item in self.plan["tasks"] if item["id"] == task_id), None)
        if not task: return
        for variable, key in ((self.status, "status"), (self.priority, "priority"), (self.owner, "owner"), (self.start, "start"), (self.due, "due"), (self.duration, "duration"), (self.blocked_reason, "blocked_reason"), (self.notes, "notes"), (self.evidence, "evidence")):
            variable.set(task[key])

    def update_selected(self):
        if not self.plan or not self.tasks.selection(): return
        try:
            task_id = self.tasks.selection()[0]
            lifecycle.update_task_workflow(self.plan, task_id, self.status.get(), self.blocked_reason.get(), priority=self.priority.get(), owner=self.owner.get(), start=self.start.get(), due=self.due.get(), duration=self.duration.get(), notes=self.notes.get(), evidence=self.evidence.get())
            self.refresh_tasks()
        except Exception as exc:
            messagebox.showerror("Update task", str(exc), parent=self.app.root)

    def remove_selected(self):
        if not self.plan or not self.tasks.selection(): return
        task_id = self.tasks.selection()[0]
        try:
            lifecycle.delete_task(self.plan, task_id)
            self.refresh_tasks()
        except Exception as exc:
            messagebox.showerror("Remove task", str(exc), parent=self.app.root)

    def save_plan(self):
        if not self.plan: return
        path = filedialog.asksaveasfilename(parent=self.app.root, defaultextension=".json", filetypes=[("OctoShip lifecycle plan", "*.json")])
        if not path: return
        try:
            lifecycle.save_plan(path, self.plan)
        except Exception as exc:
            messagebox.showerror("Save plan", str(exc), parent=self.app.root)

    def open_plan(self):
        path = filedialog.askopenfilename(parent=self.app.root, filetypes=[("OctoShip lifecycle plan", "*.json")])
        if not path: return
        try:
            self.plan = lifecycle.load_plan(path)
            self.plan_name.set(self.plan["name"])
            self.refresh_tasks()
        except Exception as exc:
            messagebox.showerror("Open plan", str(exc), parent=self.app.root)

    def export(self, kind):
        if not self.plan: return
        extension = {"md": ".md", "csv": ".csv", "json": ".json"}[kind]
        label = {"md": "Markdown", "csv": "CSV", "json": "JSON"}[kind]
        path = filedialog.asksaveasfilename(parent=self.app.root, defaultextension=extension, filetypes=[(label, "*" + extension)])
        if not path: return
        content = lifecycle.export_markdown(self.plan) if kind == "md" else lifecycle.export_csv(self.plan) if kind == "csv" else lifecycle.export_json(self.plan)
        try:
            Path(path).write_text(content, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Export plan", str(exc), parent=self.app.root)
