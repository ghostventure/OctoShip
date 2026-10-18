"""Offline project-lifecycle planner with a curated, trackable playbook.

The catalog describes work to perform; it does not create project files, run
project code, contact GitHub, or deploy anything.
"""
from __future__ import annotations

import csv
import copy
from datetime import date
from datetime import timedelta
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Iterable

from .core import OctoShipError


# Each entry is an independently selectable project task with an actionable
# instruction. Kept separate from project_recipes: these track work rather
# than generating starter files.
_PHASES = [
    ("onboarding", "Project onboarding", [
        ("Define project purpose", "Write the user problem and the outcome the project should deliver."),
        ("Identify primary users", "Name the main user groups and what each needs from the project."),
        ("Name project decision maker", "Record who can resolve scope and priority disagreements."),
        ("Set communication channel", "Choose the channel for routine updates and urgent decisions."),
        ("Agree working hours", "Record collaboration hours, time zones, and response expectations."),
        ("Collect access requirements", "List accounts and permissions each contributor needs; never record secrets."),
        ("Verify contributor access", "Have each contributor confirm the minimum required access works."),
        ("Set project vocabulary", "Define domain terms and abbreviations used in issues and reviews."),
        ("Record project constraints", "Capture budget, platform, policy, and schedule constraints."),
        ("Confirm onboarding complete", "Review access, communication, purpose, and constraints with the team."),
    ]),
    ("planning", "Scope and planning", [
        ("Write project outcome", "Describe the measurable result that marks project success."),
        ("Define in-scope work", "List the capabilities and systems included in this delivery."),
        ("Define out-of-scope work", "Record tempting adjacent work that this delivery will not include."),
        ("Rank user needs", "Order user needs by value and urgency, with a reason for the ranking."),
        ("Set acceptance measures", "Choose observable measures for deciding whether the outcome was reached."),
        ("Map project dependencies", "List external teams, systems, and decisions that can block progress."),
        ("Estimate delivery capacity", "Estimate available contributor time and known interruptions."),
        ("Set milestone boundaries", "Define what evidence is required to complete each milestone."),
        ("Record planning assumptions", "Write assumptions that could change scope, cost, or delivery timing."),
        ("Review plan with stakeholders", "Get feedback from affected stakeholders and record decisions."),
    ]),
    ("discovery", "Research and discovery", [
        ("Interview representative users", "Ask representative users about current work and unmet needs."),
        ("Observe current workflow", "Document the current workflow, including handoffs and failure points."),
        ("Review existing solutions", "Compare existing tools or services against the identified user needs."),
        ("Validate highest-risk assumption", "Run the smallest research activity that could disprove the riskiest assumption."),
        ("Document research consent", "Record how participants were informed and how their data is handled."),
        ("Summarize user findings", "Separate observed evidence from interpretation and open questions."),
        ("Create user journey map", "Map user steps, decisions, waits, and pain points for the target workflow."),
        ("Identify accessibility needs", "Identify assistive technology, language, and interaction needs to support."),
        ("Review competitor constraints", "Record relevant interoperability or migration expectations from alternatives."),
        ("Close discovery questions", "Assign owners and next steps for unresolved high-impact research questions."),
    ]),
    ("design", "Product and technical design", [
        ("Sketch key user flows", "Show the screens or interactions needed for the primary user journeys."),
        ("Review navigation structure", "Check that users can find the main tasks and recover from a wrong turn."),
        ("Specify interaction states", "Define loading, empty, success, error, disabled, and retry states."),
        ("Check keyboard interaction", "Verify that core flows can be completed with keyboard-only input."),
        ("Review responsive layouts", "Specify how key screens adapt to narrow, medium, and wide viewports."),
        ("Choose system boundaries", "Document component responsibilities and how they communicate."),
        ("Define data ownership", "Record the source of truth and write authority for each important data object."),
        ("Plan failure recovery", "Specify how users and operators recover from expected service failures."),
        ("Review design with users", "Validate the proposed flow with representative users before implementation."),
        ("Approve design decisions", "Record the accepted design, unresolved tradeoffs, and decision owners."),
    ]),
    ("implementation", "Implementation workflow", [
        ("Break work into reviewable tasks", "Split the implementation into changes that can be reviewed independently."),
        ("Assign task owners", "Give each active task one accountable owner and a clear handoff path."),
        ("Set review expectations", "Agree on review response times and what a useful review should check."),
        ("Keep changes focused", "Separate unrelated changes so that each review has a clear purpose."),
        ("Track implementation decisions", "Record decisions that affect interfaces, data, security, or maintenance."),
        ("Review dependency additions", "Check each new dependency for need, license, maintenance, and update path."),
        ("Document local setup", "Confirm a new contributor can reproduce the supported local setup."),
        ("Check error handling", "Ensure failures provide actionable context and do not silently lose user work."),
        ("Check instrumentation", "Confirm key events and failures can be diagnosed without collecting unnecessary data."),
        ("Close implementation tasks", "Link each completed task to its review and validation evidence."),
    ]),
    ("quality", "Quality and validation", [
        ("Choose validation strategy", "Match unit, integration, and end-to-end checks to the failure risks."),
        ("Verify core user journey", "Exercise the primary user journey from entry through successful completion."),
        ("Verify empty states", "Check first-use and no-results states with clear next steps."),
        ("Verify recovery paths", "Cause expected failures and confirm retry, undo, or support guidance works."),
        ("Check accessibility behavior", "Review names, focus order, contrast, announcements, and reduced motion."),
        ("Check supported platforms", "Run the agreed checks on each supported operating system and runtime."),
        ("Review performance budget", "Measure representative flows against agreed load and response budgets."),
        ("Review privacy behavior", "Confirm data collection, retention, and user controls match the stated policy."),
        ("Triage validation findings", "Rank findings by user impact, assign owners, and record accepted risks."),
        ("Capture validation evidence", "Record exact versions, commands, environment, and observed results."),
    ]),
    ("release", "Release readiness", [
        ("Choose release scope", "Confirm the exact changes and known limitations included in this release."),
        ("Confirm version and compatibility", "Check version numbers, supported upgrade paths, and compatibility promises."),
        ("Review release notes", "Summarize user-visible changes, fixes, migration steps, and limitations."),
        ("Check release artifacts", "Confirm expected packages exist and match the intended architecture and version."),
        ("Verify artifact integrity", "Recompute published checksums from the final release artifacts."),
        ("Review rollout plan", "Specify rollout order, monitoring, pause criteria, and responsible operator."),
        ("Prepare rollback steps", "Write and review a practical rollback procedure before rollout begins."),
        ("Confirm support readiness", "Give support staff known issues, escalation routes, and user-facing guidance."),
        ("Approve release go or no-go", "Review readiness evidence and record the explicit release decision."),
        ("Record release completion", "Record deployed version, time, operator, and post-release status."),
    ]),
    ("operations", "Operations and maintenance", [
        ("Assign service ownership", "Name the team responsible for operation and ongoing maintenance."),
        ("Set service objectives", "Define user-facing availability or latency goals for the service."),
        ("Review alert usefulness", "Ensure each alert has a meaningful threshold, owner, and response instruction."),
        ("Practice incident escalation", "Walk through who is contacted and how service decisions are made during an incident."),
        ("Document routine operations", "Record recurring maintenance steps and expected results."),
        ("Set backup expectations", "Document what is backed up, retention, ownership, and recovery objective."),
        ("Exercise restore procedure", "Restore a representative backup and record whether the recovery target was met."),
        ("Review capacity trends", "Check usage trends and identify when capacity needs action."),
        ("Schedule dependency maintenance", "Assign a recurring review for supported runtimes and critical dependencies."),
        ("Review operational runbooks", "Confirm runbooks match the current service and can be followed by a second operator."),
    ]),
    ("security", "Security and privacy governance", [
        ("Identify sensitive data", "List sensitive data handled, its purpose, and its permitted locations."),
        ("Map trust boundaries", "Document where untrusted input crosses into privileged components."),
        ("Review account permissions", "Remove unused access and confirm each remaining permission has an owner and purpose."),
        ("Set secret handling process", "Document approved secret storage, access, rotation, and revocation procedures."),
        ("Review threat scenarios", "Prioritize realistic abuse and failure scenarios for the project."),
        ("Plan security response", "Record private reporting, triage ownership, and coordinated disclosure steps."),
        ("Review data retention", "Set retention periods and deletion responsibilities for collected information."),
        ("Check third-party data flows", "Identify what data is shared with vendors and under what controls."),
        ("Schedule access review", "Set a repeat date and accountable owner for project access review."),
        ("Record accepted security risks", "Document risk rationale, compensating controls, approver, and review date."),
    ]),
    ("handoff", "Handoff and sustainability", [
        ("Prepare maintainer overview", "Explain the architecture, critical paths, and places new maintainers should start."),
        ("List current known issues", "Record unresolved issues, impact, workarounds, and owners."),
        ("Transfer operational access", "Transfer service ownership through approved account controls and verify receipt."),
        ("Walk through support workflow", "Demonstrate how to triage common user reports and collect useful evidence."),
        ("Review documentation freshness", "Check instructions against the current interface and supported versions."),
        ("Confirm ownership coverage", "Ensure critical responsibilities have a primary and backup owner."),
        ("Set maintenance funding", "Record expected time or budget for routine care and external services."),
        ("Capture deferred decisions", "List deferred decisions with the trigger that should reopen each one."),
        ("Collect stakeholder acceptance", "Record acceptance from stakeholders who own downstream workflows."),
        ("Complete formal handoff", "Confirm artifacts, access, support, and maintenance ownership with the receiving team."),
    ]),
    ("improvement", "Learning and improvement", [
        ("Review outcome measures", "Compare observed results with the success measures selected during planning."),
        ("Gather user feedback", "Collect user feedback through an appropriate, privacy-aware channel."),
        ("Review support themes", "Group support reports into repeated friction points and root causes."),
        ("Analyze project delays", "Identify causes of schedule changes without assigning blame to individuals."),
        ("Run team retrospective", "Record what helped, what hindered, and one change to try next time."),
        ("Prioritize improvement ideas", "Rank improvement ideas by user value, cost, and risk reduction."),
        ("Close learning actions", "Assign owners and due dates to the selected improvement actions."),
        ("Review project risks", "Reassess open risks against current evidence and record changed likelihood or impact."),
        ("Archive obsolete project material", "Identify outdated material and archive it without removing required records."),
        ("Schedule next review", "Set a date to revisit project health, ownership, and maintenance needs."),
    ]),
]


def _make_catalog():
    result = []
    phase_counts = {}
    for source_phase_id, source_phase, tasks in _PHASES:
        # Discovery is an early planning activity, kept under the planning
        # phase so the playbook stays at ten lifecycle stages.
        phase_id, phase = (("planning", "Scope and planning") if source_phase_id == "discovery"
                           else (source_phase_id, source_phase))
        if source_phase_id in ("planning", "discovery"):
            tasks = tasks[:5]
        for title, guidance in tasks:
            phase_counts[phase_id] = phase_counts.get(phase_id, 0) + 1
            index = phase_counts[phase_id]
            result.append({
                "id": f"{phase_id}-{index:02d}",
                "phase_id": phase_id,
                "phase": phase,
                "title": title,
                "guidance": guidance,
            })
    return tuple(result)


PLAYBOOK = _make_catalog()
BY_ID = {item["id"]: item for item in PLAYBOOK}
STATUSES = ("todo", "doing", "blocked", "done", "skipped")
PRIORITIES = ("low", "normal", "high", "critical")


def search_tasks(query="", phase=""):
    """Return catalog tasks matching a case-insensitive query and phase."""
    needle = str(query).strip().casefold()
    phase = str(phase).strip().casefold()
    return [item for item in PLAYBOOK
            if (not phase or item["phase_id"].casefold() == phase or item["phase"].casefold() == phase)
            and (not needle or needle in " ".join(item.values()).casefold())]


def new_plan(name, task_ids: Iterable[str] | None = None):
    """Create a versioned plan from selected catalog IDs (all by default)."""
    name = str(name).strip()
    if not name or len(name) > 160:
        raise OctoShipError("Plan name must contain 1 to 160 characters.")
    ids = list(BY_ID) if task_ids is None else list(dict.fromkeys(map(str, task_ids)))
    unknown = sorted(set(ids) - BY_ID.keys())
    if unknown:
        raise OctoShipError("Unknown lifecycle task: " + ", ".join(unknown))
    return {"version": 1, "name": name, "tasks": [
        {**BY_ID[task_id], "status": "todo", "priority": "normal", "owner": "",
         "start": "", "due": "", "duration": 1, "depends_on": [],
         "blocked_reason": "", "notes": "", "evidence": "", "archived": False}
        for task_id in ids
    ], "milestones": [], "risks": [], "baselines": [], "phase_state": {},
        "decisions": [], "issues": [], "metrics": [], "lessons": [], "effort_logs": [],
        "status": "active", "risk_sequence": 0, "milestone_sequence": 0,
        "decision_sequence": 0, "issue_sequence": 0, "metric_sequence": 0,
        "lesson_sequence": 0, "effort_sequence": 0}


def update_task(plan, task_id, **changes):
    """Update one plan task with validated status, priority, and metadata."""
    allowed = {"status", "priority", "owner", "start", "due", "duration", "depends_on",
               "blocked_reason", "notes", "evidence", "archived"}
    if not set(changes) <= allowed:
        raise OctoShipError("Unsupported task field.")
    task = next((task for task in plan.get("tasks", []) if task.get("id") == task_id), None)
    if task is None:
        raise OctoShipError("Task is not part of this plan.")
    if "status" in changes and changes["status"] not in STATUSES:
        raise OctoShipError("Choose a supported task status.")
    if "priority" in changes and changes["priority"] not in PRIORITIES:
        raise OctoShipError("Choose a supported priority.")
    if "due" in changes and changes["due"]:
        try:
            date.fromisoformat(str(changes["due"]))
        except ValueError as exc:
            raise OctoShipError("Due date must use YYYY-MM-DD.") from exc
    if "start" in changes and changes["start"]:
        try:
            date.fromisoformat(str(changes["start"]))
        except ValueError as exc:
            raise OctoShipError("Start date must use YYYY-MM-DD.") from exc
    if "duration" in changes:
        try:
            duration = int(changes["duration"])
        except (TypeError, ValueError) as exc:
            raise OctoShipError("Duration must be a whole number of days.") from exc
        if not 1 <= duration <= 3650:
            raise OctoShipError("Duration must be between 1 and 3650 days.")
        changes["duration"] = duration
    if "depends_on" in changes:
        dependencies = list(dict.fromkeys(map(str, changes["depends_on"])))
        if task_id in dependencies or any(dep not in {item["id"] for item in plan["tasks"]} for dep in dependencies):
            raise OctoShipError("Dependencies must reference other tasks in this plan.")
        candidate = {item["id"]: list(item.get("depends_on", [])) for item in plan["tasks"]}
        candidate[task_id] = dependencies
        _ensure_acyclic(candidate)
        changes["depends_on"] = dependencies
    for key, value in changes.items():
        if key == "archived":
            if not isinstance(value, bool):
                raise OctoShipError("Archived must be true or false.")
            task[key] = value
            continue
        if key == "duration":
            task[key] = int(value)
            continue
        if key == "depends_on":
            task[key] = list(value)
            continue
        value = str(value).strip()
        if len(value) > 4000:
            raise OctoShipError(f"{key.title()} must be 4000 characters or fewer.")
        task[key] = value
    return task


def plan_summary(plan, today=None):
    """Return stable counts and overdue task IDs without mutating the plan."""
    today = today or date.today()
    tasks = [task for task in plan.get("tasks", []) if not task.get("archived")]
    counts = {status: sum(task.get("status") == status for task in tasks) for status in STATUSES}
    overdue = []
    for task in tasks:
        if task.get("status") not in ("done", "skipped") and task.get("due"):
            try:
                if date.fromisoformat(task["due"]) < today:
                    overdue.append(task["id"])
            except ValueError:
                continue
    return {"total": len(tasks), "counts": counts, "overdue": overdue,
            "completion_percent": round(100 * counts["done"] / len(tasks)) if tasks else 0}


def _validate_plan(plan):
    if not isinstance(plan, dict) or plan.get("version") != 1 or not isinstance(plan.get("tasks"), list):
        raise OctoShipError("Unsupported lifecycle plan format.")
    if len(plan["tasks"]) > len(PLAYBOOK):
        raise OctoShipError("Lifecycle plan contains too many tasks.")
    seen = set()
    for task in plan["tasks"]:
        if not isinstance(task, dict) or task.get("id") not in BY_ID or task["id"] in seen:
            raise OctoShipError("Lifecycle plan contains an invalid or duplicate task.")
        seen.add(task["id"])
        if task.get("status") not in STATUSES or task.get("priority") not in PRIORITIES:
            raise OctoShipError("Lifecycle plan contains an invalid status or priority.")
        for key in ("owner", "start", "due", "blocked_reason", "notes", "evidence"):
            if not isinstance(task.get(key, ""), str) or len(task.get(key, "")) > 4000:
                raise OctoShipError("Lifecycle task metadata is invalid.")
        if task.get("due"):
            try:
                date.fromisoformat(task["due"])
            except ValueError as exc:
                raise OctoShipError("Lifecycle task date must use YYYY-MM-DD.") from exc
        if task.get("start"):
            try:
                date.fromisoformat(task["start"])
            except ValueError as exc:
                raise OctoShipError("Lifecycle task start date must use YYYY-MM-DD.") from exc
        if not isinstance(task.get("duration", 1), int) or not 1 <= task.get("duration", 1) <= 3650:
            raise OctoShipError("Lifecycle task duration is invalid.")
        if not isinstance(task.get("archived", False), bool):
            raise OctoShipError("Lifecycle task archive state is invalid.")
        if not isinstance(task.get("depends_on", []), list):
            raise OctoShipError("Lifecycle task dependencies are invalid.")
    _ensure_acyclic({task["id"]: task.get("depends_on", []) for task in plan["tasks"]})
    for task in plan["tasks"]:
        if any(dep not in seen for dep in task.get("depends_on", [])):
            raise OctoShipError("Lifecycle plan contains a dependency outside the plan.")
    for key in ("milestones", "risks", "baselines", "decisions", "issues", "metrics", "lessons", "effort_logs"):
        if not isinstance(plan.get(key, []), list) or len(plan.get(key, [])) > 500:
            raise OctoShipError(f"Lifecycle {key} list is invalid.")
    for milestone in plan.get("milestones", []):
        if (not isinstance(milestone, dict) or not isinstance(milestone.get("name"), str)
                or not milestone.get("name") or not isinstance(milestone.get("task_ids"), list)
                or any(task_id not in seen for task_id in milestone.get("task_ids", []))):
            raise OctoShipError("Lifecycle milestone data is invalid.")
    for risk in plan.get("risks", []):
        if (not isinstance(risk, dict) or not isinstance(risk.get("title"), str) or not risk.get("title")
                or type(risk.get("probability")) is not int or risk["probability"] not in range(1, 6)
                or type(risk.get("impact")) is not int or risk["impact"] not in range(1, 6)
                or risk.get("status") not in ("open", "mitigating", "accepted", "closed")):
            raise OctoShipError("Lifecycle risk data is invalid.")
        risk["score"] = risk["probability"] * risk["impact"]
    for decision in plan["decisions"]:
        if (not isinstance(decision, dict) or not decision.get("title") or not decision.get("decision")
                or decision.get("status") not in ("proposed", "accepted", "reversed", "superseded")):
            raise OctoShipError("Lifecycle decision data is invalid.")
    for issue in plan["issues"]:
        if (not isinstance(issue, dict) or not issue.get("title")
                or issue.get("severity") not in ("blocker", "high", "medium", "low")
                or issue.get("status") not in ("open", "triaged", "in_progress", "resolved", "wont_fix")):
            raise OctoShipError("Lifecycle issue data is invalid.")
        if issue.get("linked_task") and issue["linked_task"] not in seen: raise OctoShipError("Issue references an unknown task.")
        if issue.get("due"):
            try: date.fromisoformat(issue["due"])
            except ValueError as exc: raise OctoShipError("Issue due date must use YYYY-MM-DD.") from exc
    for metric in plan["metrics"]:
        if not isinstance(metric, dict) or metric.get("direction") not in ("increase", "decrease"):
            raise OctoShipError("Lifecycle outcome metric is invalid.")
        for key in ("baseline", "target", "actual"): _finite_number(metric.get(key))
        if metric["baseline"] == metric["target"]: raise OctoShipError("Metric baseline and target must differ.")
    for lesson in plan["lessons"]:
        if (not isinstance(lesson, dict) or not lesson.get("title") or not lesson.get("observation")
                or not lesson.get("recommendation") or lesson.get("status") not in ("open", "applied")
                or any(task_id not in seen for task_id in lesson.get("task_ids", []))):
            raise OctoShipError("Lifecycle lesson data is invalid.")
    for entry in plan["effort_logs"]:
        if not isinstance(entry, dict) or entry.get("task_id") not in seen or not entry.get("owner"):
            raise OctoShipError("Lifecycle effort entry is invalid.")
        try: date.fromisoformat(entry["date"])
        except (ValueError, TypeError, KeyError) as exc: raise OctoShipError("Effort entry date is invalid.") from exc
        hours = _finite_number(entry.get("hours"))
        if not 0 < hours <= 24: raise OctoShipError("Effort entry hours are invalid.")
    for baseline in plan.get("baselines", []):
        if (not isinstance(baseline, dict) or not isinstance(baseline.get("name"), str)
                or not isinstance(baseline.get("tasks"), dict)
                or any(task_id not in BY_ID for task_id in baseline.get("tasks", {}))):
            raise OctoShipError("Lifecycle baseline data is invalid.")
    plan.setdefault("milestones", [])
    plan.setdefault("risks", [])
    plan.setdefault("baselines", [])
    plan.setdefault("decisions", []); plan.setdefault("issues", []); plan.setdefault("metrics", [])
    plan.setdefault("lessons", []); plan.setdefault("effort_logs", [])
    plan.setdefault("phase_state", {})
    if plan.get("status", "active") not in ("planning", "active", "paused", "closed"):
        raise OctoShipError("Lifecycle plan status is invalid.")
    if not isinstance(plan["phase_state"], dict) or any(key not in {item[0] for item in _PHASES if item[0] != "discovery"} or value not in ("planned", "active", "closed") for key, value in plan["phase_state"].items()):
        raise OctoShipError("Lifecycle phase status data is invalid.")
    if not isinstance(plan.get("phase_closures", {}), dict):
        raise OctoShipError("Lifecycle phase closeout records are invalid.")
    if not isinstance(plan.get("status_note", ""), str) or len(plan.get("status_note", "")) > 1000:
        raise OctoShipError("Lifecycle plan status note is invalid.")
    for sequence_name, prefix, collection in (("risk_sequence", "risk", plan["risks"]), ("milestone_sequence", "milestone", plan["milestones"])):
        inferred = max((int(item["id"].split("-")[-1]) for item in collection if str(item.get("id", "")).startswith(prefix + "-") and item["id"].split("-")[-1].isdigit()), default=0)
        sequence = plan.get(sequence_name, inferred)
        if type(sequence) is not int or sequence < inferred:
            raise OctoShipError("Lifecycle sequence counter is invalid.")
        plan[sequence_name] = sequence
    for sequence_name, prefix, collection in (("decision_sequence", "decision", plan["decisions"]),
                                              ("issue_sequence", "issue", plan["issues"]),
                                              ("metric_sequence", "metric", plan["metrics"]),
                                              ("lesson_sequence", "lesson", plan["lessons"]),
                                              ("effort_sequence", "effort", plan["effort_logs"])):
        inferred = max((int(item["id"].split("-")[-1]) for item in collection if isinstance(item, dict) and str(item.get("id", "")).startswith(prefix + "-") and item["id"].split("-")[-1].isdigit()), default=0)
        sequence = plan.get(sequence_name, inferred)
        if type(sequence) is not int or sequence < inferred:
            raise OctoShipError("Lifecycle record counter is invalid.")
        plan[sequence_name] = sequence
    for task in plan["tasks"]:
        task.setdefault("start", "")
        task.setdefault("duration", 1)
        task.setdefault("depends_on", [])
        task.setdefault("blocked_reason", "")
        task.setdefault("archived", False)
    if not isinstance(plan.get("name"), str) or not plan["name"].strip() or len(plan["name"]) > 160:
        raise OctoShipError("Lifecycle plan name is invalid.")
    return plan


def save_plan(path, plan):
    """Atomically save a validated local plan with private file permissions."""
    _validate_plan(plan)
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".octoship-lifecycle-", dir=target.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(plan, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, target)
        os.chmod(target, 0o600)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return target


def load_plan(path):
    """Load a bounded local plan and validate every task before use."""
    target = Path(path).expanduser()
    if target.stat().st_size > 2_000_000:
        raise OctoShipError("Lifecycle plan exceeds the 2 MB limit.")
    return load_plan_from_text(target.read_text(encoding="utf-8"))


def load_plan_from_text(text):
    """Parse and validate plan text supplied by a local file transfer."""
    if len(text.encode("utf-8")) > 2_000_000:
        raise OctoShipError("Lifecycle plan exceeds the 2 MB limit.")
    try:
        value = json.loads(text)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OctoShipError("Lifecycle plan is not valid UTF-8 JSON.") from exc
    return _validate_plan(value)


def export_markdown(plan):
    """Render a portable Markdown status report, escaping user text safely."""
    _validate_plan(plan)
    summary = plan_summary(plan)
    lines = [f"# {plan['name']}", "", f"Completion: {summary['completion_percent']}% ({summary['counts']['done']}/{summary['total']} tasks)", ""]
    for phase_id, phase, _ in _PHASES:
        if phase_id == "discovery":
            continue
        tasks = [task for task in plan["tasks"] if task["phase_id"] == phase_id]
        if not tasks:
            continue
        lines.extend([f"## {phase}", ""])
        for task in tasks:
            marker = "x" if task["status"] == "done" else " "
            due = f" · due {task['due']}" if task.get("due") else ""
            owner = f" · {task['owner']}" if task.get("owner") else ""
            lines.append(f"- [{marker}] **{task['title']}** ({task['status']}, {task['priority']}{owner}{due})")
            lines.append(f"  - {task['guidance']}")
            if task.get("notes"):
                lines.append("  - Notes: " + task["notes"].replace("\n", " "))
            if task.get("evidence"):
                lines.append("  - Evidence: " + task["evidence"].replace("\n", " "))
        lines.append("")
    return "\n".join(lines)


def export_csv(plan):
    """Return CSV suitable for a spreadsheet without writing to disk."""
    _validate_plan(plan)
    from io import StringIO
    output = StringIO(newline="")
    fields = ("id", "phase", "title", "guidance", "status", "priority", "owner", "start", "due", "duration", "depends_on", "blocked_reason", "notes", "evidence", "archived")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for task in plan["tasks"]:
        writer.writerow({**task, "depends_on": ";".join(task.get("depends_on", []))})
    return output.getvalue()


def _ensure_acyclic(graph):
    """Reject unknown edges and dependency cycles using depth-first traversal."""
    visiting, visited = set(), set()
    def visit(node):
        if node in visiting:
            raise OctoShipError("Task dependencies contain a cycle.")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph.get(node, []):
            if dependency not in graph:
                raise OctoShipError("Task dependency references an unknown task.")
            visit(dependency)
        visiting.remove(node)
        visited.add(node)
    for node in graph:
        visit(node)


def dependencies_of(plan, task_id):
    task = _find_task(plan, task_id)
    return list(task.get("depends_on", []))


def _find_task(plan, task_id):
    task = next((item for item in plan.get("tasks", []) if item.get("id") == task_id), None)
    if task is None:
        raise OctoShipError("Task is not part of this plan.")
    return task


def add_dependency(plan, task_id, depends_on):
    """Make one task depend on another, rejecting cycles and self-links."""
    task = _find_task(plan, task_id)
    if task_id == depends_on:
        raise OctoShipError("A task cannot depend on itself.")
    dependency = _find_task(plan, depends_on)
    edges = list(task.get("depends_on", []))
    if depends_on not in edges:
        edges.append(depends_on)
    update_task(plan, task_id, depends_on=edges)
    return dependency


def remove_dependency(plan, task_id, depends_on):
    task = _find_task(plan, task_id)
    if depends_on not in task.get("depends_on", []):
        return False
    update_task(plan, task_id, depends_on=[item for item in task["depends_on"] if item != depends_on])
    return True


def ready_tasks(plan):
    """Return non-archived tasks whose dependencies are all complete."""
    tasks = {task["id"]: task for task in plan.get("tasks", [])}
    return [task for task in tasks.values() if not task.get("archived") and not task.get("blocked_reason") and task.get("status") not in ("done", "skipped", "blocked")
            and all(tasks.get(dep, {}).get("status") == "done" for dep in task.get("depends_on", []))]


def blocked_tasks(plan):
    """Return open tasks with incomplete dependencies or a recorded block reason."""
    tasks = {task["id"]: task for task in plan.get("tasks", [])}
    return [task for task in tasks.values() if not task.get("archived") and task.get("status") not in ("done", "skipped")
            and (task.get("status") == "blocked" or task.get("blocked_reason") or any(tasks.get(dep, {}).get("status") != "done" for dep in task.get("depends_on", [])))]


def schedule_plan(plan, start_date, weekdays_only=False):
    """Assign start and due dates in topological order using task durations."""
    try:
        cursor = date.fromisoformat(str(start_date))
    except ValueError as exc:
        raise OctoShipError("Schedule start date must use YYYY-MM-DD.") from exc
    _validate_plan(plan)
    tasks = {task["id"]: task for task in plan["tasks"] if not task.get("archived")}
    order, visited = [], set()
    def visit(task_id):
        if task_id in visited or task_id not in tasks:
            return
        for dep in tasks[task_id].get("depends_on", []): visit(dep)
        visited.add(task_id); order.append(task_id)
    for task_id in tasks: visit(task_id)
    finishes = {}
    for task_id in order:
        task = tasks[task_id]
        earliest = max([cursor, *[finishes[dep] for dep in task.get("depends_on", []) if dep in finishes]])
        while weekdays_only and earliest.weekday() >= 5:
            earliest += timedelta(days=1)
        finish = earliest
        if weekdays_only:
            remaining = task.get("duration", 1) - 1
            while remaining:
                finish += timedelta(days=1)
                if finish.weekday() < 5: remaining -= 1
        else:
            finish += timedelta(days=task.get("duration", 1) - 1)
        task["start"], task["due"] = earliest.isoformat(), finish.isoformat()
        finishes[task_id] = finish + timedelta(days=1)
    return plan


def phase_rollup(plan, today=None):
    """Return per-phase status, priority, overdue, and completion metrics."""
    today = today or date.today()
    result = {}
    for task in plan.get("tasks", []):
        if task.get("archived"): continue
        row = result.setdefault(task["phase_id"], {"phase": task["phase"], "total": 0, "done": 0, "overdue": 0, "priorities": {key: 0 for key in PRIORITIES}})
        row["total"] += 1
        row["done"] += task.get("status") == "done"
        row["priorities"][task.get("priority", "normal")] += 1
        if task.get("due") and task.get("status") not in ("done", "skipped"):
            try: row["overdue"] += date.fromisoformat(task["due"]) < today
            except ValueError: pass
    for row in result.values(): row["completion_percent"] = round(row["done"] * 100 / row["total"]) if row["total"] else 0
    return result


def critical_tasks(plan):
    """Rank active tasks by priority, then overdue status and dependency impact."""
    weights = {"critical": 4, "high": 3, "normal": 2, "low": 1}
    dependents = {task["id"]: 0 for task in plan.get("tasks", [])}
    for task in plan.get("tasks", []):
        for dep in task.get("depends_on", []):
            if dep in dependents: dependents[dep] += 1
    return sorted([task for task in plan.get("tasks", []) if not task.get("archived") and task.get("status") not in ("done", "skipped")],
                  key=lambda task: (-weights.get(task.get("priority"), 0), -dependents.get(task["id"], 0), task.get("due") or "9999-99-99"))


def filter_tasks(plan, *, status=None, priority=None, owner=None, phase=None, overdue_before=None, include_archived=False):
    """Filter task views by state, ownership, lifecycle stage, and due date."""
    cutoff = date.fromisoformat(overdue_before) if overdue_before else None
    result = []
    for task in plan.get("tasks", []):
        if not include_archived and task.get("archived"): continue
        if status and task.get("status") != status: continue
        if priority and task.get("priority") != priority: continue
        if owner and task.get("owner", "").casefold() != owner.casefold(): continue
        if phase and task.get("phase_id") != phase: continue
        if cutoff:
            try:
                if task.get("status") in ("done", "skipped") or not task.get("due") or date.fromisoformat(task["due"]) >= cutoff: continue
            except ValueError: continue
        result.append(task)
    return result


def delete_task(plan, task_id):
    """Delete a task only when no dependency or milestone references it."""
    _find_task(plan, task_id)
    dependents = [task["id"] for task in plan["tasks"] if task_id in task.get("depends_on", [])]
    milestone_refs = [milestone["name"] for milestone in plan.get("milestones", []) if task_id in milestone.get("task_ids", [])]
    if dependents or milestone_refs:
        raise OctoShipError("Task is referenced by dependencies or milestones; remove those references first.")
    plan["tasks"] = [task for task in plan["tasks"] if task["id"] != task_id]
    return task_id


def transition_task(plan, task_id, status, reason=""):
    """Apply guarded task state transitions and enforce dependency completion."""
    task = _find_task(plan, task_id)
    if status not in STATUSES: raise OctoShipError("Choose a supported task status.")
    if status == "blocked" and not str(reason).strip(): raise OctoShipError("Record a reason when blocking a task.")
    if status == "done":
        incomplete = [dep for dep in task.get("depends_on", []) if _find_task(plan, dep).get("status") != "done"]
        if incomplete: raise OctoShipError("Complete dependencies first: " + ", ".join(incomplete))
    update_task(plan, task_id, status=status, blocked_reason=reason if status == "blocked" else "")
    return task


def update_task_workflow(plan, task_id, status, reason="", **changes):
    """Atomically save task details and apply its guarded status transition.

    The desktop editor changes metadata and status together. Validate both on a
    private candidate first so a rejected date, duration, or dependency check
    cannot leave the task half-updated in memory.
    """
    if "status" in changes:
        raise OctoShipError("Set task status through the status argument.")
    candidate = copy.deepcopy(plan)
    transition_task(candidate, task_id, status, reason)
    update_task(candidate, task_id, **changes)
    updated = _find_task(candidate, task_id)
    original = _find_task(plan, task_id)
    original.clear()
    original.update(updated)
    return original


def bulk_update_tasks(plan, task_ids, **changes):
    """Validate and apply one status/owner/priority change to selected tasks."""
    allowed = {"status", "priority", "owner"}
    if not changes or not set(changes) <= allowed: raise OctoShipError("Bulk updates support status, priority, and owner.")
    tasks = [_find_task(plan, task_id) for task_id in list(dict.fromkeys(task_ids))]
    for key, value in changes.items():
        if key == "status" and value not in STATUSES: raise OctoShipError("Choose a supported task status.")
        if key == "priority" and value not in PRIORITIES: raise OctoShipError("Choose a supported priority.")
    for task in tasks: update_task(plan, task["id"], **changes)
    return [task["id"] for task in tasks]


def dependency_levels(plan):
    """Group tasks into parallelizable waves based on prerequisite depth."""
    _validate_plan(plan)
    tasks = {task["id"]: task for task in plan["tasks"] if not task.get("archived")}
    levels = {}
    def level(task_id):
        if task_id in levels: return levels[task_id]
        deps = [dep for dep in tasks[task_id].get("depends_on", []) if dep in tasks]
        levels[task_id] = 0 if not deps else 1 + max(level(dep) for dep in deps)
        return levels[task_id]
    for task_id in tasks: level(task_id)
    return [[task_id for task_id in tasks if levels[task_id] == depth] for depth in range(max(levels.values(), default=-1) + 1)]


def critical_path(plan):
    """Calculate the longest dependency chain by estimated task duration."""
    _validate_plan(plan)
    tasks = {task["id"]: task for task in plan["tasks"] if not task.get("archived")}
    best = {}
    def finish(task_id):
        if task_id in best: return best[task_id]
        task = tasks[task_id]
        parents = [dep for dep in task.get("depends_on", []) if dep in tasks]
        parent_path = max((finish(dep) for dep in parents), key=lambda item: item[0], default=(0, []))
        best[task_id] = (parent_path[0] + task.get("duration", 1), parent_path[1] + [task_id])
        return best[task_id]
    return max((finish(task_id) for task_id in tasks), key=lambda item: item[0], default=(0, []))


def owner_capacity(plan):
    """Summarize estimated active task-days and open items per owner."""
    result = {}
    for task in plan.get("tasks", []):
        if task.get("archived") or task.get("status") in ("done", "skipped"): continue
        owner = task.get("owner") or "Unassigned"
        row = result.setdefault(owner.casefold(), {"owner": owner, "tasks": 0, "estimated_days": 0, "blocked": 0})
        row["tasks"] += 1; row["estimated_days"] += task.get("duration", 1)
        row["blocked"] += task.get("status") == "blocked" or bool(task.get("blocked_reason"))
    return result


def schedule_conflicts(plan):
    """Report overlapping dated work assigned to the same owner."""
    by_owner = {}
    for task in plan.get("tasks", []):
        if task.get("archived") or task.get("status") in ("done", "skipped") or not task.get("owner") or not task.get("start") or not task.get("due"): continue
        by_owner.setdefault(task["owner"].casefold(), []).append(task)
    conflicts = []
    for owner, tasks in by_owner.items():
        tasks.sort(key=lambda item: item["start"])
        for index, left in enumerate(tasks):
            for right in tasks[index + 1:]:
                if right["start"] <= left["due"] and left["start"] <= right["due"]:
                    conflicts.append({"owner": owner, "tasks": [left["id"], right["id"]], "overlap": [max(left["start"], right["start"]), min(left["due"], right["due"])]})
    return conflicts


def forecast_slip(plan, task_id, delay_days):
    """Estimate direct downstream due-date movement without mutating the plan."""
    _find_task(plan, task_id)
    try: delay_days = int(delay_days)
    except (TypeError, ValueError) as exc: raise OctoShipError("Delay must be a whole number of days.") from exc
    if not 0 <= delay_days <= 3650: raise OctoShipError("Delay must be between 0 and 3650 days.")
    affected, changed = {task_id}, True
    while changed:
        changed = False
        for task in plan["tasks"]:
            if task["id"] not in affected and set(task.get("depends_on", [])) & affected:
                affected.add(task["id"]); changed = True
    forecast = []
    for task in plan["tasks"]:
        if task["id"] not in affected or not task.get("due"): continue
        due = date.fromisoformat(task["due"]) + timedelta(days=delay_days)
        forecast.append({"id": task["id"], "current_due": task["due"], "forecast_due": due.isoformat()})
    return forecast


def health_report(plan, today=None):
    """Combine completion, overdue, blocked, critical-path, and risk signals."""
    return {"plan": plan["name"], "progress": plan_summary(plan, today),
            "phases": phase_rollup(plan, today), "blocked": [item["id"] for item in blocked_tasks(plan)],
            "ready": [item["id"] for item in ready_tasks(plan)], "critical_path": critical_path(plan),
            "risk": risk_summary(plan), "schedule_conflicts": schedule_conflicts(plan)}


def risk_heatmap(plan):
    """Count open risks in each probability-impact cell of a 5x5 matrix."""
    matrix = {probability: {impact: 0 for impact in range(1, 6)} for probability in range(1, 6)}
    for risk in plan.get("risks", []):
        if risk.get("status") != "closed": matrix[risk["probability"]][risk["impact"]] += 1
    return matrix


def remove_risk(plan, risk_id):
    before = len(plan.get("risks", []))
    plan["risks"] = [risk for risk in plan.get("risks", []) if risk.get("id") != risk_id]
    return len(plan["risks"]) != before


def duplicate_plan(plan, name):
    """Create an independent copy of a plan, its risks, milestones, and task state."""
    _validate_plan(plan)
    if not str(name).strip() or len(str(name)) > 160: raise OctoShipError("Plan name must contain 1 to 160 characters.")
    duplicate = json.loads(json.dumps(plan))
    duplicate["name"] = str(name).strip()
    return duplicate


def capture_baseline(plan, name):
    """Record a named, immutable snapshot of task schedule and status fields."""
    _validate_plan(plan)
    name = str(name).strip()
    if not name or len(name) > 120: raise OctoShipError("Baseline name must contain 1 to 120 characters.")
    baseline = {"id": f"baseline-{len(plan['baselines']) + 1:03d}", "name": name, "captured": date.today().isoformat(),
                "tasks": {task["id"]: {key: task.get(key, "") for key in ("status", "start", "due", "owner", "duration")}
                          for task in plan["tasks"]}}
    plan["baselines"].append(baseline)
    return baseline


def compare_baseline(plan, baseline_id):
    """Report task additions/removals and schedule, status, owner, and duration variance."""
    _validate_plan(plan)
    baseline = next((item for item in plan["baselines"] if item["id"] == baseline_id), None)
    if baseline is None: raise OctoShipError("Baseline is not in this plan.")
    current = {task["id"]: task for task in plan["tasks"]}
    before = baseline["tasks"]
    changed = []
    for task_id in sorted(current.keys() & before.keys()):
        fields = {}
        for key in ("status", "start", "due", "owner", "duration"):
            old, new = before[task_id].get(key, ""), current[task_id].get(key, "")
            if old != new:
                delta = None
                if key == "due" and old and new:
                    delta = (date.fromisoformat(new) - date.fromisoformat(old)).days
                fields[key] = {"baseline": old, "current": new, "delta_days": delta}
        if fields: changed.append({"id": task_id, "fields": fields})
    return {"baseline": baseline["name"], "added": sorted(current.keys() - before.keys()),
            "removed": sorted(before.keys() - current.keys()), "changed": changed}


def validate_schedule(plan):
    """Find invalid date order, missing dependency dates, and prerequisite violations."""
    _validate_plan(plan)
    tasks = {task["id"]: task for task in plan["tasks"]}
    issues = []
    for task in plan["tasks"]:
        start, due = task.get("start"), task.get("due")
        if start and due and date.fromisoformat(due) < date.fromisoformat(start):
            issues.append({"task": task["id"], "issue": "due-before-start"})
        for dep_id in task.get("depends_on", []):
            dep = tasks[dep_id]
            if dep.get("due") and start and date.fromisoformat(start) <= date.fromisoformat(dep["due"]):
                issues.append({"task": task["id"], "dependency": dep_id, "issue": "starts-before-dependency-finishes"})
            elif dep.get("due") and not start:
                issues.append({"task": task["id"], "dependency": dep_id, "issue": "missing-start-date"})
    return issues


def due_calendar(plan, start_date, end_date):
    """Group tasks due in an inclusive date window, excluding archived work."""
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except ValueError as exc: raise OctoShipError("Calendar dates must use YYYY-MM-DD.") from exc
    if end < start: raise OctoShipError("Calendar end date must not precede its start date.")
    result = {}
    for task in plan.get("tasks", []):
        if task.get("archived") or not task.get("due"): continue
        due = date.fromisoformat(task["due"])
        if start <= due <= end: result.setdefault(due.isoformat(), []).append(task["id"])
    return dict(sorted(result.items()))


def assign_unowned_tasks(plan, owners):
    """Balance unowned active work across owners using estimated task-days."""
    owners = list(dict.fromkeys(str(owner).strip() for owner in owners if str(owner).strip()))
    if not owners: raise OctoShipError("Add at least one owner before balancing work.")
    workloads = {owner: sum(task.get("duration", 1) for task in plan.get("tasks", []) if task.get("owner", "").casefold() == owner.casefold() and not task.get("archived") and task.get("status") not in ("done", "skipped")) for owner in owners}
    pending = [task for task in plan.get("tasks", []) if not task.get("owner") and not task.get("archived") and task.get("status") not in ("done", "skipped")]
    for task in sorted(pending, key=lambda item: (-item.get("duration", 1), item["id"])):
        owner = min(owners, key=lambda person: (workloads[person], person.casefold()))
        task["owner"] = owner
        workloads[owner] += task.get("duration", 1)
    return {"assigned": [task["id"] for task in pending], "workloads": workloads}


def update_milestone(plan, milestone_id, *, name=None, due=None):
    """Rename or reschedule an existing milestone without changing task links."""
    milestone = next((item for item in plan.get("milestones", []) if item.get("id") == milestone_id), None)
    if milestone is None: raise OctoShipError("Milestone is not in this plan.")
    if name is not None:
        name = str(name).strip()
        if not name or len(name) > 120: raise OctoShipError("Milestone name must contain 1 to 120 characters.")
        milestone["name"] = name
    if due is not None:
        try: date.fromisoformat(due)
        except ValueError as exc: raise OctoShipError("Milestone due date must use YYYY-MM-DD.") from exc
        milestone["due"] = due
    return milestone


def remove_milestone(plan, milestone_id):
    before = len(plan.get("milestones", []))
    plan["milestones"] = [item for item in plan.get("milestones", []) if item.get("id") != milestone_id]
    return len(plan["milestones"]) != before


def phase_readiness(plan, phase_id, today=None):
    """Check open, blocked, overdue, and high-priority work before phase closeout."""
    if phase_id not in {task["phase_id"] for task in PLAYBOOK}: raise OctoShipError("Choose a known lifecycle phase.")
    tasks = [task for task in plan.get("tasks", []) if task["phase_id"] == phase_id and not task.get("archived")]
    open_tasks = [task["id"] for task in tasks if task.get("status") not in ("done", "skipped")]
    blocked = [task["id"] for task in blocked_tasks(plan) if task["phase_id"] == phase_id]
    overdue = [task["id"] for task in filter_tasks(plan, phase=phase_id, overdue_before=(today or date.today()).isoformat())]
    critical = [task["id"] for task in tasks if task.get("priority") == "critical" and task.get("status") not in ("done", "skipped")]
    return {"phase": phase_id, "total": len(tasks), "open": open_tasks, "blocked": blocked,
            "overdue": overdue, "critical_open": critical, "ready_to_close": bool(tasks) and not open_tasks}


def close_phase(plan, phase_id, *, allow_open=False, rationale=""):
    """Close a project phase only after readiness, or record an explicit exception."""
    readiness = phase_readiness(plan, phase_id)
    if not readiness["total"]: raise OctoShipError("Add phase tasks before closing the phase.")
    if not readiness["ready_to_close"] and (not allow_open or not str(rationale).strip()):
        raise OctoShipError("Resolve open work or record a rationale for closing with open items.")
    plan.setdefault("phase_state", {})[phase_id] = "closed"
    plan.setdefault("phase_closures", {})[phase_id] = {"date": date.today().isoformat(), "rationale": str(rationale).strip()}
    return {**readiness, "closed": True}


def set_phase_active(plan, phase_id):
    if phase_id not in {task["phase_id"] for task in PLAYBOOK}: raise OctoShipError("Choose a known lifecycle phase.")
    plan.setdefault("phase_state", {})[phase_id] = "active"
    plan.setdefault("phase_closures", {}).pop(phase_id, None)
    return phase_id


def set_plan_status(plan, status, note=""):
    """Pause, resume, or close the plan; closure requires all active work resolved."""
    if status not in ("planning", "active", "paused", "closed"): raise OctoShipError("Choose a supported plan status.")
    if status == "closed":
        open_tasks = [task["id"] for task in plan.get("tasks", []) if not task.get("archived") and task.get("status") not in ("done", "skipped")]
        if open_tasks: raise OctoShipError("Resolve or archive open tasks before closing the plan.")
    plan["status"] = status
    if note: plan["status_note"] = str(note).strip()[:1000]
    return status


def carry_forward_tasks(source, name, task_ids=None):
    """Start a follow-on plan from unresolved tasks while retaining their context."""
    _validate_plan(source)
    selected = set(task_ids) if task_ids is not None else {task["id"] for task in source["tasks"] if task.get("status") not in ("done", "skipped") and not task.get("archived")}
    originals = {task["id"]: task for task in source["tasks"]}
    if not selected or not selected <= originals.keys(): raise OctoShipError("Choose existing source tasks to carry forward.")
    plan = new_plan(name, sorted(selected))
    copied = {task["id"]: task for task in plan["tasks"]}
    for task_id in selected:
        old, new = originals[task_id], copied[task_id]
        for key in ("priority", "owner", "notes", "evidence", "duration"):
            new[key] = old.get(key, new.get(key))
        new["depends_on"] = [dependency for dependency in old.get("depends_on", []) if dependency in selected]
    return plan


def add_risk(plan, title, probability, impact, owner="", response=""):
    """Add a project risk scored on a 1-5 likelihood and impact scale."""
    title = str(title).strip()
    if not title or len(title) > 240: raise OctoShipError("Risk title must contain 1 to 240 characters.")
    if type(probability) is not int or probability not in range(1, 6) or type(impact) is not int or impact not in range(1, 6): raise OctoShipError("Risk probability and impact must be 1 to 5.")
    risks = plan.setdefault("risks", [])
    plan["risk_sequence"] = max(plan.get("risk_sequence", 0), max((int(item["id"].split("-")[-1]) for item in risks if str(item.get("id", "")).startswith("risk-") and item["id"].split("-")[-1].isdigit()), default=0)) + 1
    next_id = plan["risk_sequence"]
    risk = {"id": f"risk-{next_id:03d}", "title": title,
            "probability": probability, "impact": impact, "score": probability * impact,
            "owner": str(owner).strip(), "response": str(response).strip(), "status": "open"}
    plan["risks"].append(risk)
    return risk


def update_risk(plan, risk_id, **changes):
    allowed = {"title", "probability", "impact", "owner", "response", "status"}
    if not set(changes) <= allowed: raise OctoShipError("Unsupported risk field.")
    risk = next((item for item in plan.get("risks", []) if item.get("id") == risk_id), None)
    if risk is None: raise OctoShipError("Risk is not in this plan.")
    for key, value in changes.items():
        if key in ("probability", "impact") and (type(value) is not int or value not in range(1, 6)):
            raise OctoShipError("Risk probability and impact must be 1 to 5.")
        if key == "status" and value not in ("open", "mitigating", "accepted", "closed"):
            raise OctoShipError("Choose a supported risk status.")
        risk[key] = str(value).strip() if key not in ("probability", "impact") else value
    risk["score"] = risk["probability"] * risk["impact"]
    return risk


def risk_register(plan, status=None):
    """List risks from highest exposure to lowest, optionally filtered."""
    risks = [item for item in plan.get("risks", []) if status is None or item.get("status") == status]
    return sorted(risks, key=lambda item: (-item.get("score", 0), item.get("title", "").casefold()))


def risk_summary(plan):
    risks = plan.get("risks", [])
    return {"total": len(risks), "open": sum(item.get("status") == "open" for item in risks),
            "high_exposure": sum(item.get("score", 0) >= 15 and item.get("status") != "closed" for item in risks),
            "max_score": max((item.get("score", 0) for item in risks), default=0)}


def add_milestone(plan, name, task_ids):
    """Save a reusable named group of plan task IDs as a milestone."""
    name = str(name).strip()
    ids = list(dict.fromkeys(map(str, task_ids)))
    available = {task["id"] for task in plan.get("tasks", [])}
    if not name or len(name) > 120: raise OctoShipError("Milestone name must contain 1 to 120 characters.")
    if not ids or not set(ids) <= available: raise OctoShipError("Milestone must reference tasks in this plan.")
    milestones = plan.setdefault("milestones", [])
    plan["milestone_sequence"] = max(plan.get("milestone_sequence", 0), max((int(item["id"].split("-")[-1]) for item in milestones if str(item.get("id", "")).startswith("milestone-") and item["id"].split("-")[-1].isdigit()), default=0)) + 1
    next_id = plan["milestone_sequence"]
    milestone = {"id": f"milestone-{next_id:03d}", "name": name, "task_ids": ids}
    plan["milestones"].append(milestone)
    return milestone


def milestone_progress(plan, milestone_id):
    milestone = next((item for item in plan.get("milestones", []) if item.get("id") == milestone_id), None)
    if milestone is None: raise OctoShipError("Milestone is not in this plan.")
    tasks = [_find_task(plan, task_id) for task_id in milestone["task_ids"]]
    done = sum(task.get("status") == "done" for task in tasks)
    return {"name": milestone["name"], "total": len(tasks), "done": done,
            "completion_percent": round(100 * done / len(tasks)) if tasks else 0,
            "complete": bool(tasks) and done == len(tasks)}


def compare_plans(left, right):
    """Compare task state by catalog ID, reporting additions, removals and changes."""
    _validate_plan(left); _validate_plan(right)
    a = {task["id"]: task for task in left["tasks"]}; b = {task["id"]: task for task in right["tasks"]}
    fields = ("status", "priority", "owner", "start", "due", "duration", "depends_on", "notes", "evidence", "archived")
    changed = [{"id": task_id, "fields": {key: (a[task_id].get(key), b[task_id].get(key)) for key in fields if a[task_id].get(key) != b[task_id].get(key)}}
               for task_id in sorted(a.keys() & b.keys())]
    changed = [entry for entry in changed if entry["fields"]]
    return {"added": sorted(b.keys() - a.keys()), "removed": sorted(a.keys() - b.keys()), "changed": changed}


def merge_plans(target, incoming, strategy="keep-target"):
    """Merge plans by task ID with explicit conflict resolution strategy."""
    _validate_plan(target); _validate_plan(incoming)
    if strategy not in ("keep-target", "take-incoming", "prefer-latest-status"):
        raise OctoShipError("Choose a supported merge strategy.")
    merged = duplicate_plan(target, target["name"])
    by_id = {task["id"]: task for task in merged["tasks"]}
    added, replaced = [], []
    for task in incoming["tasks"]:
        old = by_id.get(task["id"])
        if old is None:
            merged["tasks"].append(dict(task)); by_id[task["id"]] = merged["tasks"][-1]; added.append(task["id"])
        elif strategy == "take-incoming":
            old.update(task); replaced.append(task["id"])
        elif strategy == "prefer-latest-status" and old.get("status") != "done" and task.get("status") == "done":
            old.update(task); replaced.append(task["id"])
    _validate_plan(merged)
    target.clear(); target.update(merged)
    return {"added": added, "replaced": replaced, "strategy": strategy}


def archive_tasks(plan, task_ids):
    """Archive selected tasks without deleting their history."""
    tasks = [_find_task(plan, task_id) for task_id in task_ids]
    for task in tasks: task["archived"] = True
    return [task["id"] for task in tasks]


def restore_tasks(plan, task_ids):
    """Restore selected archived tasks to active plan views."""
    tasks = [_find_task(plan, task_id) for task_id in task_ids]
    for task in tasks: task["archived"] = False
    return [task["id"] for task in tasks]


def export_json(plan):
    """Return validated plan JSON for backup or transfer."""
    _validate_plan(plan)
    return json.dumps(plan, ensure_ascii=False, indent=2) + "\n"


def import_csv(text, name="Imported lifecycle plan"):
    """Import a bounded CSV status export, accepting only known task IDs and fields."""
    if len(text) > 2_000_000: raise OctoShipError("Lifecycle CSV exceeds the 2 MB limit.")
    try: rows = list(csv.DictReader(text.splitlines()))
    except csv.Error as exc: raise OctoShipError("Lifecycle CSV is invalid.") from exc
    ids = [row.get("id", "") for row in rows]
    plan = new_plan(name, ids)
    by_id = {task["id"]: task for task in plan["tasks"]}
    for row in rows:
        task_id = row.get("id", "")
        for key in ("status", "priority", "owner", "start", "due", "notes", "evidence", "blocked_reason"):
            if row.get(key) is not None: update_task(plan, task_id, **{key: row[key]})
        if row.get("duration"):
            update_task(plan, task_id, duration=row["duration"])
        if row.get("archived"):
            update_task(plan, task_id, archived=row["archived"].strip().casefold() in ("true", "1", "yes"))
    for row in rows:
        if row.get("depends_on"):
            deps = [item for item in row["depends_on"].split(";") if item]
            update_task(plan, row["id"], depends_on=deps)
    return _validate_plan(plan)


def _record_id(plan, sequence_key, prefix):
    plan[sequence_key] = plan.get(sequence_key, 0) + 1
    return f"{prefix}-{plan[sequence_key]:03d}"


def _record(plan, collection, record_id):
    item = next((entry for entry in plan.get(collection, []) if entry.get("id") == record_id), None)
    if item is None: raise OctoShipError(f"{collection[:-1].title()} record was not found.")
    return item


def add_decision(plan, title, decision, *, context="", owner=""):
    """Record a project decision with context, accountable owner, and lifecycle status."""
    title, decision = str(title).strip(), str(decision).strip()
    if not title or len(title) > 240 or not decision or len(decision) > 4000:
        raise OctoShipError("Decision title and decision text are required and bounded.")
    item = {"id": _record_id(plan, "decision_sequence", "decision"), "title": title,
            "decision": decision, "context": str(context).strip()[:4000], "owner": str(owner).strip()[:200],
            "status": "accepted", "created": date.today().isoformat(), "outcome": "", "superseded_by": ""}
    plan.setdefault("decisions", []).append(item)
    return item


def update_decision(plan, decision_id, *, status=None, outcome=None):
    """Revise a decision's lifecycle state or record its measured outcome."""
    item = _record(plan, "decisions", decision_id)
    if status is not None:
        if status not in ("proposed", "accepted", "reversed", "superseded"):
            raise OctoShipError("Choose proposed, accepted, reversed, or superseded.")
        item["status"] = status
    if outcome is not None: item["outcome"] = str(outcome).strip()[:4000]
    return item


def supersede_decision(plan, old_id, replacement_id):
    """Link an older decision to its accepted replacement."""
    old, replacement = _record(plan, "decisions", old_id), _record(plan, "decisions", replacement_id)
    if old_id == replacement_id: raise OctoShipError("A decision cannot supersede itself.")
    if replacement.get("status") != "accepted": raise OctoShipError("Accept the replacement decision first.")
    old["status"], old["superseded_by"] = "superseded", replacement_id
    return old


def decision_register(plan, *, status=None, owner=None, query=""):
    """Search/filter project decisions by status, owner, and decision text."""
    query = str(query).casefold().strip()
    return [item for item in plan.get("decisions", [])
            if (not status or item["status"] == status)
            and (not owner or item.get("owner", "").casefold() == owner.casefold())
            and (not query or query in " ".join(str(value) for value in item.values()).casefold())]


def decision_summary(plan):
    """Count proposed, accepted, reversed, and superseded decisions."""
    decisions = plan.get("decisions", [])
    return {"total": len(decisions), **{status: sum(item.get("status") == status for item in decisions)
                                      for status in ("proposed", "accepted", "reversed", "superseded")}}


def add_issue(plan, title, severity, *, owner="", due="", linked_task="", next_action=""):
    """Create a tracked project issue with severity, owner, due date, and next action."""
    title = str(title).strip()
    if not title or len(title) > 240: raise OctoShipError("Issue title must contain 1 to 240 characters.")
    if severity not in ("blocker", "high", "medium", "low"): raise OctoShipError("Choose blocker, high, medium, or low severity.")
    if due:
        try: date.fromisoformat(due)
        except ValueError as exc: raise OctoShipError("Issue due date must use YYYY-MM-DD.") from exc
    if linked_task: _find_task(plan, linked_task)
    item = {"id": _record_id(plan, "issue_sequence", "issue"), "title": title, "severity": severity,
            "owner": str(owner).strip()[:200], "due": due, "linked_task": linked_task,
            "next_action": str(next_action).strip()[:2000], "status": "open", "resolution": ""}
    plan.setdefault("issues", []).append(item)
    return item


def update_issue(plan, issue_id, *, status=None, owner=None, due=None, next_action=None, resolution=None, linked_task=None):
    """Update issue ownership, schedule, task link, next action, or resolution."""
    issue = _record(plan, "issues", issue_id)
    if status is not None and status not in ("open", "triaged", "in_progress", "resolved", "wont_fix"):
        raise OctoShipError("Choose a supported issue status.")
    if status == "resolved" and not str(resolution if resolution is not None else issue.get("resolution", "")).strip():
        raise OctoShipError("Record a resolution before closing an issue.")
    if due is not None and due:
        try: date.fromisoformat(due)
        except ValueError as exc: raise OctoShipError("Issue due date must use YYYY-MM-DD.") from exc
    if linked_task is not None and linked_task: _find_task(plan, linked_task)
    for key, value in (("status", status), ("owner", owner), ("due", due), ("next_action", next_action), ("resolution", resolution), ("linked_task", linked_task)):
        if value is not None: issue[key] = str(value).strip()
    return issue


def issue_register(plan, *, status=None, severity=None, owner=None, overdue_before=None):
    """Filter active issue records by state, severity, owner, or overdue cutoff."""
    cutoff = date.fromisoformat(overdue_before) if overdue_before else None
    result = []
    for issue in plan.get("issues", []):
        if status and issue["status"] != status: continue
        if severity and issue["severity"] != severity: continue
        if owner and issue.get("owner", "").casefold() != owner.casefold(): continue
        if cutoff:
            if issue.get("status") in ("resolved", "wont_fix") or not issue.get("due") or date.fromisoformat(issue["due"]) >= cutoff: continue
        result.append(issue)
    return result


def issue_summary(plan, today=None):
    """Summarize open issues by severity, status, and overdue state."""
    today = today or date.today()
    issues = plan.get("issues", [])
    return {"total": len(issues), "open": sum(item["status"] not in ("resolved", "wont_fix") for item in issues),
            "overdue": len(issue_register(plan, overdue_before=today.isoformat())),
            "by_severity": {severity: sum(item["severity"] == severity and item["status"] not in ("resolved", "wont_fix") for item in issues)
                            for severity in ("blocker", "high", "medium", "low")}}


def add_metric(plan, name, unit, baseline, target, *, direction="increase"):
    """Define a numeric outcome metric with baseline, target, and desired direction."""
    name = str(name).strip()
    if not name or len(name) > 160 or not str(unit).strip() or len(str(unit)) > 40: raise OctoShipError("Metric name and unit are required.")
    baseline, target = _finite_number(baseline), _finite_number(target)
    if direction not in ("increase", "decrease"): raise OctoShipError("Metric direction must be increase or decrease.")
    if baseline == target: raise OctoShipError("Metric baseline and target must differ.")
    metric = {"id": _record_id(plan, "metric_sequence", "metric"), "name": name, "unit": str(unit).strip(),
              "baseline": baseline, "target": target, "actual": baseline, "direction": direction}
    plan.setdefault("metrics", []).append(metric)
    return metric


def _finite_number(value):
    try: number = float(value)
    except (TypeError, ValueError) as exc: raise OctoShipError("Metric values must be numeric.") from exc
    if not math.isfinite(number): raise OctoShipError("Metric values must be finite.")
    return number


def update_metric_actual(plan, metric_id, actual):
    """Record the latest measured outcome value for a project metric."""
    metric = _record(plan, "metrics", metric_id)
    metric["actual"] = _finite_number(actual)
    return metric_status(metric)


def metric_status(metric):
    """Calculate target progress, remaining gap, and reached/behind status."""
    baseline, actual, target = metric["baseline"], metric["actual"], metric["target"]
    progress = (actual - baseline) / (target - baseline) * 100 if metric["direction"] == "increase" else (baseline - actual) / (baseline - target) * 100
    achieved = actual >= target if metric["direction"] == "increase" else actual <= target
    return {"id": metric["id"], "name": metric["name"], "unit": metric["unit"], "actual": actual,
            "target": target, "progress_percent": round(progress, 1), "remaining": round(abs(target - actual), 3),
            "achieved": achieved, "status": "achieved" if achieved else "in_progress" if progress > 0 else "behind"}


def metric_rollup(plan):
    """Report all defined outcome metrics and how many targets are achieved."""
    rows = [metric_status(metric) for metric in plan.get("metrics", [])]
    return {"total": len(rows), "achieved": sum(row["achieved"] for row in rows), "metrics": rows}


def add_lesson(plan, title, observation, recommendation, *, category="general"):
    """Capture a retrospective lesson with a concrete recommendation."""
    title, observation, recommendation = map(lambda value: str(value).strip(), (title, observation, recommendation))
    if not title or not observation or not recommendation: raise OctoShipError("Lesson title, observation, and recommendation are required.")
    if category not in ("process", "product", "quality", "operations", "team", "general"):
        raise OctoShipError("Choose a supported lesson category.")
    item = {"id": _record_id(plan, "lesson_sequence", "lesson"), "title": title[:200],
            "observation": observation[:4000], "recommendation": recommendation[:4000],
            "category": category, "status": "open", "task_ids": []}
    plan.setdefault("lessons", []).append(item)
    return item


def apply_lesson(plan, lesson_id, task_ids):
    """Link a retrospective recommendation to follow-up tasks and mark it applied."""
    lesson = _record(plan, "lessons", lesson_id)
    ids = list(dict.fromkeys(map(str, task_ids)))
    if not ids: raise OctoShipError("Link at least one follow-up task.")
    for task_id in ids: _find_task(plan, task_id)
    lesson["task_ids"] = ids
    lesson["status"] = "applied"
    return lesson


def lesson_register(plan, *, category=None, status=None):
    """Filter retrospective lessons by category and follow-up state."""
    return [item for item in plan.get("lessons", []) if (not category or item["category"] == category) and (not status or item["status"] == status)]


def lesson_summary(plan):
    """Count captured and applied retrospective lessons."""
    lessons = plan.get("lessons", [])
    return {"total": len(lessons), "open": sum(item["status"] == "open" for item in lessons),
            "applied": sum(item["status"] == "applied" for item in lessons),
            "by_category": {category: sum(item["category"] == category for item in lessons)
                            for category in ("process", "product", "quality", "operations", "team", "general")}}


def set_effort_estimate(plan, task_id, hours):
    """Set a numeric person-hour estimate independent of calendar-day duration."""
    task = _find_task(plan, task_id)
    hours = _finite_number(hours)
    if not 0 <= hours <= 100000: raise OctoShipError("Effort estimate must be between 0 and 100000 hours.")
    task["effort_estimate_hours"] = hours
    return hours


def log_effort(plan, task_id, owner, work_date, hours, note=""):
    """Append an auditable time entry for one owner, task, and date."""
    _find_task(plan, task_id)
    owner = str(owner).strip()
    if not owner or len(owner) > 200: raise OctoShipError("Effort log owner is required.")
    try: date.fromisoformat(work_date)
    except ValueError as exc: raise OctoShipError("Effort date must use YYYY-MM-DD.") from exc
    hours = _finite_number(hours)
    if not 0 < hours <= 24: raise OctoShipError("Logged effort must be greater than zero and at most 24 hours per day.")
    entry = {"id": _record_id(plan, "effort_sequence", "effort"), "task_id": task_id, "owner": owner,
             "date": work_date, "hours": hours, "note": str(note).strip()[:1000]}
    plan.setdefault("effort_logs", []).append(entry)
    return entry


def effort_report(plan, *, start_date=None, end_date=None, group_by="owner"):
    """Summarize recorded effort by owner, task, date, or log entry."""
    if group_by not in ("owner", "task", "date", "entry"): raise OctoShipError("Choose owner, task, date, or entry grouping.")
    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None
    if start and end and end < start: raise OctoShipError("Effort report end must not precede its start.")
    rows, totals = [], {}
    for entry in plan.get("effort_logs", []):
        work_day = date.fromisoformat(entry["date"])
        if start and work_day < start or end and work_day > end: continue
        key = {"owner": entry["owner"], "task": entry["task_id"], "date": entry["date"], "entry": entry["id"]}[group_by]
        totals[key] = totals.get(key, 0) + entry["hours"]
        rows.append(entry)
    return {"group_by": group_by, "totals": totals, "hours": round(sum(totals.values()), 2), "entries": rows}


def effort_variance(plan, task_id):
    """Compare logged person-hours with the task's effort estimate."""
    task = _find_task(plan, task_id)
    actual = sum(entry["hours"] for entry in plan.get("effort_logs", []) if entry["task_id"] == task_id)
    estimate = task.get("effort_estimate_hours")
    return {"task_id": task_id, "estimate_hours": estimate, "actual_hours": round(actual, 2),
            "variance_hours": round(actual - estimate, 2) if estimate is not None else None,
            "over_estimate": actual > estimate if estimate is not None else None}


def remove_effort_log(plan, entry_id):
    """Remove an incorrect time entry by ID while preserving other records."""
    before = len(plan.get("effort_logs", []))
    plan["effort_logs"] = [entry for entry in plan.get("effort_logs", []) if entry.get("id") != entry_id]
    return len(plan["effort_logs"]) != before
