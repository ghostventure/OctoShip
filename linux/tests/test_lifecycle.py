import csv
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from octoship import lifecycle
from octoship.core import OctoShipError


class LifecycleTests(unittest.TestCase):
    def test_playbook_has_100_distinct_actionable_activities_across_ten_phases(self):
        self.assertEqual(len(lifecycle.PLAYBOOK), 100)
        self.assertEqual(len({item["id"] for item in lifecycle.PLAYBOOK}), 100)
        self.assertEqual(len({item["title"] for item in lifecycle.PLAYBOOK}), 100)
        self.assertEqual(len({item["guidance"] for item in lifecycle.PLAYBOOK}), 100)
        self.assertEqual(len({item["phase_id"] for item in lifecycle.PLAYBOOK}), 10)
        self.assertTrue(all(len(item["guidance"]) > 40 for item in lifecycle.PLAYBOOK))

    def test_search_and_phase_filter_compose(self):
        results = lifecycle.search_tasks("account", "security")
        self.assertEqual([item["id"] for item in results], ["security-03", "security-09"])
        self.assertEqual(lifecycle.search_tasks("backup", "operations")[0]["id"], "operations-06")
        self.assertEqual(lifecycle.search_tasks("not present"), [])

    def test_new_plan_all_and_selected(self):
        full = lifecycle.new_plan("Annual plan")
        selected = lifecycle.new_plan("Small plan", ["planning-01", "release-01", "planning-01"])
        self.assertEqual(len(full["tasks"]), 100)
        self.assertEqual([task["id"] for task in selected["tasks"]], ["planning-01", "release-01"])
        with self.assertRaises(OctoShipError):
            lifecycle.new_plan("bad", ["missing"])
        with self.assertRaises(OctoShipError):
            lifecycle.new_plan(" ")

    def test_update_fields_and_validate_dates(self):
        plan = lifecycle.new_plan("Update test", ["planning-01"])
        task = lifecycle.update_task(plan, "planning-01", status="doing", priority="high", owner="A", due="2026-11-01", notes="Scope", evidence="decision link")
        self.assertEqual((task["status"], task["priority"], task["owner"], task["due"]), ("doing", "high", "A", "2026-11-01"))
        with self.assertRaises(OctoShipError): lifecycle.update_task(plan, "planning-01", status="unknown")
        with self.assertRaises(OctoShipError): lifecycle.update_task(plan, "planning-01", priority="urgent")
        with self.assertRaises(OctoShipError): lifecycle.update_task(plan, "planning-01", due="tomorrow")
        with self.assertRaises(OctoShipError): lifecycle.update_task(plan, "release-01", status="done")
        with self.assertRaises(OctoShipError): lifecycle.update_task(plan, "planning-01", made_up="x")

    def test_summary_and_overdue_exclude_finished_tasks(self):
        plan = lifecycle.new_plan("Due test", ["planning-01", "planning-02", "planning-03"])
        lifecycle.update_task(plan, "planning-01", due="2026-01-01")
        lifecycle.update_task(plan, "planning-02", due="2026-01-01", status="done")
        lifecycle.update_task(plan, "planning-03", due="2026-12-01", status="skipped")
        summary = lifecycle.plan_summary(plan, today=date(2026, 6, 1))
        self.assertEqual(summary["overdue"], ["planning-01"])
        self.assertEqual(summary["completion_percent"], 33)
        self.assertEqual(summary["counts"]["skipped"], 1)

    def test_atomic_private_save_and_load_round_trip(self):
        plan = lifecycle.new_plan("Private plan", ["onboarding-01"])
        lifecycle.update_task(plan, "onboarding-01", notes="Do not lose this")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nested" / "plan.json"
            lifecycle.save_plan(path, plan)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(lifecycle.load_plan(path), plan)
            self.assertEqual(list(path.parent.glob(".octoship-lifecycle-*")), [])

    def test_load_rejects_corrupt_or_invalid_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            path.write_text("not json", encoding="utf-8")
            with self.assertRaises(OctoShipError): lifecycle.load_plan(path)
            path.write_text(json.dumps({"version": 1, "name": "X", "tasks": [{"id": "x"}]}), encoding="utf-8")
            with self.assertRaises(OctoShipError): lifecycle.load_plan(path)

    def test_markdown_export_includes_progress_and_escapes_newlines(self):
        plan = lifecycle.new_plan("Review & ship", ["release-01"])
        lifecycle.update_task(plan, "release-01", status="done", notes="ready\nextra")
        content = lifecycle.export_markdown(plan)
        self.assertIn("# Review & ship", content)
        self.assertIn("Completion: 100% (1/1 tasks)", content)
        self.assertIn("Notes: ready extra", content)

    def test_csv_export_is_parseable_and_keeps_user_text_as_one_cell(self):
        plan = lifecycle.new_plan("CSV", ["handoff-01"])
        lifecycle.update_task(plan, "handoff-01", notes='text, with "quotes"')
        rows = list(csv.DictReader(lifecycle.export_csv(plan).splitlines()))
        self.assertEqual(rows[0]["notes"], 'text, with "quotes"')
        self.assertEqual(rows[0]["id"], "handoff-01")

    def test_external_plan_cannot_exceed_catalog_or_duplicate_ids(self):
        plan = lifecycle.new_plan("Duplicate test", ["onboarding-01"])
        plan["tasks"].append(dict(plan["tasks"][0]))
        with self.assertRaises(OctoShipError): lifecycle.export_csv(plan)

    def test_dependencies_readiness_and_cycles(self):
        plan = lifecycle.new_plan("Dependency plan", ["planning-01", "planning-02", "planning-03"])
        lifecycle.add_dependency(plan, "planning-02", "planning-01")
        lifecycle.add_dependency(plan, "planning-03", "planning-02")
        self.assertEqual([task["id"] for task in lifecycle.ready_tasks(plan)], ["planning-01"])
        self.assertEqual([task["id"] for task in lifecycle.blocked_tasks(plan)], ["planning-02", "planning-03"])
        lifecycle.update_task(plan, "planning-01", status="done")
        self.assertEqual([task["id"] for task in lifecycle.ready_tasks(plan)], ["planning-02"])
        self.assertTrue(lifecycle.remove_dependency(plan, "planning-02", "planning-01"))
        self.assertFalse(lifecycle.remove_dependency(plan, "planning-02", "planning-01"))
        with self.assertRaises(OctoShipError): lifecycle.add_dependency(plan, "planning-02", "planning-03")

    def test_schedule_respects_dependencies_duration_and_weekends(self):
        plan = lifecycle.new_plan("Schedule", ["planning-01", "planning-02", "planning-03"])
        lifecycle.update_task(plan, "planning-01", duration=2)
        lifecycle.update_task(plan, "planning-03", duration=2)
        lifecycle.add_dependency(plan, "planning-02", "planning-01")
        lifecycle.add_dependency(plan, "planning-03", "planning-02")
        lifecycle.schedule_plan(plan, "2026-10-16", weekdays_only=True)
        tasks = {task["id"]: task for task in plan["tasks"]}
        self.assertEqual(tasks["planning-01"]["start"], "2026-10-16")
        self.assertEqual(tasks["planning-01"]["due"], "2026-10-19")
        self.assertEqual(tasks["planning-02"]["start"], "2026-10-20")
        self.assertEqual(tasks["planning-03"]["due"], "2026-10-22")
        with self.assertRaises(OctoShipError): lifecycle.schedule_plan(plan, "not-a-date")

    def test_rollups_and_priority_dependency_ranking(self):
        plan = lifecycle.new_plan("Rollup", ["planning-01", "planning-02", "release-01"])
        lifecycle.update_task(plan, "planning-01", due="2026-01-01", priority="normal")
        lifecycle.update_task(plan, "planning-02", priority="critical")
        lifecycle.add_dependency(plan, "planning-02", "planning-01")
        lifecycle.update_task(plan, "release-01", status="done", priority="high")
        rollup = lifecycle.phase_rollup(plan, today=date(2026, 6, 1))
        self.assertEqual(rollup["planning"]["overdue"], 1)
        self.assertEqual(rollup["release"]["completion_percent"], 100)
        self.assertEqual(lifecycle.critical_tasks(plan)[0]["id"], "planning-02")

    def test_risk_register_scores_updates_filters_and_summarizes(self):
        plan = lifecycle.new_plan("Risks", [])
        low = lifecycle.add_risk(plan, "Minor schedule slip", 2, 2, "A", "Monitor")
        high = lifecycle.add_risk(plan, "Provider outage", 4, 5, "B", "Prepare fallback")
        self.assertEqual(lifecycle.risk_register(plan)[0]["id"], high["id"])
        self.assertEqual(lifecycle.risk_summary(plan), {"total": 2, "open": 2, "high_exposure": 1, "max_score": 20})
        lifecycle.update_risk(plan, low["id"], probability=5, status="mitigating")
        self.assertEqual(lifecycle.risk_register(plan, "mitigating")[0]["score"], 10)
        with self.assertRaises(OctoShipError): lifecycle.add_risk(plan, "Bad", 0, 5)
        with self.assertRaises(OctoShipError): lifecycle.update_risk(plan, low["id"], status="invalid")

    def test_milestone_progress_and_validation(self):
        plan = lifecycle.new_plan("Milestones", ["planning-01", "planning-02"])
        milestone = lifecycle.add_milestone(plan, "Discovery exit", ["planning-01", "planning-02"])
        self.assertEqual(lifecycle.milestone_progress(plan, milestone["id"])["completion_percent"], 0)
        lifecycle.update_task(plan, "planning-01", status="done")
        self.assertEqual(lifecycle.milestone_progress(plan, milestone["id"])["completion_percent"], 50)
        with self.assertRaises(OctoShipError): lifecycle.add_milestone(plan, "bad", ["unknown"])

    def test_plan_compare_and_merge_strategies(self):
        left = lifecycle.new_plan("Left", ["planning-01", "planning-02"])
        right = lifecycle.new_plan("Right", ["planning-01", "release-01"])
        lifecycle.update_task(left, "planning-01", status="doing", owner="Left owner")
        lifecycle.update_task(right, "planning-01", status="done", owner="Right owner")
        delta = lifecycle.compare_plans(left, right)
        self.assertEqual(delta["added"], ["release-01"])
        self.assertEqual(delta["removed"], ["planning-02"])
        self.assertEqual(delta["changed"][0]["fields"]["status"], ("doing", "done"))
        result = lifecycle.merge_plans(left, right, "prefer-latest-status")
        self.assertIn("release-01", result["added"])
        self.assertEqual(next(t for t in left["tasks"] if t["id"] == "planning-01")["owner"], "Right owner")
        with self.assertRaises(OctoShipError): lifecycle.merge_plans(left, right, "guess")

    def test_merge_keep_target_and_take_incoming_conflicts(self):
        target = lifecycle.new_plan("Target", ["planning-01"])
        incoming = lifecycle.new_plan("Incoming", ["planning-01"])
        lifecycle.update_task(target, "planning-01", owner="Target owner", status="doing")
        lifecycle.update_task(incoming, "planning-01", owner="Incoming owner", status="done")
        keep = lifecycle.duplicate_plan(target, "Target")
        lifecycle.merge_plans(keep, incoming, "keep-target")
        self.assertEqual(keep["tasks"][0]["owner"], "Target owner")
        take = lifecycle.duplicate_plan(target, "Target")
        lifecycle.merge_plans(take, incoming, "take-incoming")
        self.assertEqual((take["tasks"][0]["owner"], take["tasks"][0]["status"]), ("Incoming owner", "done"))

    def test_archive_restore_and_active_rollups(self):
        plan = lifecycle.new_plan("Archive", ["planning-01", "planning-02"])
        self.assertEqual(lifecycle.archive_tasks(plan, ["planning-01"]), ["planning-01"])
        self.assertEqual([task["id"] for task in lifecycle.ready_tasks(plan)], ["planning-02"])
        lifecycle.restore_tasks(plan, ["planning-01"])
        self.assertEqual({task["id"] for task in lifecycle.ready_tasks(plan)}, {"planning-01", "planning-02"})

    def test_json_and_csv_transfer_round_trips(self):
        plan = lifecycle.new_plan("Transfer", ["planning-01", "release-01"])
        lifecycle.update_task(plan, "release-01", status="doing", owner="Reviewer")
        lifecycle.add_dependency(plan, "release-01", "planning-01")
        exported_json = lifecycle.export_json(plan)
        self.assertEqual(lifecycle.load_plan_from_text(exported_json), plan)
        imported_csv = lifecycle.import_csv(lifecycle.export_csv(plan), "CSV transfer")
        result = {task["id"]: task for task in imported_csv["tasks"]}["release-01"]
        self.assertEqual(result["depends_on"], ["planning-01"])
        self.assertEqual(result["owner"], "Reviewer")

    def test_task_transition_requires_dependencies_and_block_reason(self):
        plan = lifecycle.new_plan("Transitions", ["planning-01", "planning-02"])
        lifecycle.add_dependency(plan, "planning-02", "planning-01")
        with self.assertRaises(OctoShipError): lifecycle.transition_task(plan, "planning-02", "done")
        with self.assertRaises(OctoShipError): lifecycle.transition_task(plan, "planning-02", "blocked")
        lifecycle.transition_task(plan, "planning-02", "blocked", "Waiting for review")
        self.assertEqual(plan["tasks"][1]["blocked_reason"], "Waiting for review")
        lifecycle.transition_task(plan, "planning-01", "done")
        lifecycle.transition_task(plan, "planning-02", "done")

    def test_task_editor_update_is_atomic_when_metadata_or_transition_fails(self):
        plan = lifecycle.new_plan("Atomic editor", ["planning-01", "planning-02"])
        lifecycle.add_dependency(plan, "planning-02", "planning-01")
        task = plan["tasks"][1]
        before = dict(task)

        with self.assertRaises(OctoShipError):
            lifecycle.update_task_workflow(plan, "planning-02", "doing", due="not-a-date")
        self.assertEqual(task, before)

        with self.assertRaises(OctoShipError):
            lifecycle.update_task_workflow(plan, "planning-02", "done", owner="Pat")
        self.assertEqual(task, before)

        result = lifecycle.update_task_workflow(plan, "planning-02", "blocked", "Waiting on review", owner="Pat")
        self.assertEqual((result["status"], result["blocked_reason"], result["owner"]), ("blocked", "Waiting on review", "Pat"))

    def test_bulk_updates_validate_before_mutation(self):
        plan = lifecycle.new_plan("Bulk", ["planning-01", "planning-02"])
        self.assertEqual(lifecycle.bulk_update_tasks(plan, ["planning-01", "planning-02"], owner="Pat"), ["planning-01", "planning-02"])
        with self.assertRaises(OctoShipError): lifecycle.bulk_update_tasks(plan, ["planning-01"], status="nonsense")
        with self.assertRaises(OctoShipError): lifecycle.bulk_update_tasks(plan, ["unknown"], owner="X")
        self.assertEqual(plan["tasks"][0]["owner"], "Pat")

    def test_task_filters_and_safe_delete_references(self):
        plan = lifecycle.new_plan("Filter", ["planning-01", "planning-02", "release-01"])
        lifecycle.update_task(plan, "planning-01", owner="Pat", priority="high", due="2026-01-01")
        lifecycle.update_task(plan, "planning-02", owner="Pat", priority="low", status="done")
        self.assertEqual([task["id"] for task in lifecycle.filter_tasks(plan, owner="pat", priority="high", overdue_before="2026-05-01")], ["planning-01"])
        lifecycle.add_dependency(plan, "release-01", "planning-01")
        with self.assertRaises(OctoShipError): lifecycle.delete_task(plan, "planning-01")
        lifecycle.remove_dependency(plan, "release-01", "planning-01")
        milestone = lifecycle.add_milestone(plan, "M", ["planning-01"])
        with self.assertRaises(OctoShipError): lifecycle.delete_task(plan, "planning-01")
        plan["milestones"].remove(milestone)
        self.assertEqual(lifecycle.delete_task(plan, "planning-01"), "planning-01")

    def test_dependency_waves_critical_path_and_independent_schedule(self):
        plan = lifecycle.new_plan("Graph", ["planning-01", "planning-02", "planning-03", "release-01"])
        lifecycle.update_task(plan, "planning-01", duration=2)
        lifecycle.update_task(plan, "planning-02", duration=4)
        lifecycle.update_task(plan, "planning-03", duration=3)
        lifecycle.add_dependency(plan, "planning-03", "planning-01")
        lifecycle.add_dependency(plan, "release-01", "planning-03")
        waves = lifecycle.dependency_levels(plan)
        self.assertEqual(set(waves[0]), {"planning-01", "planning-02"})
        self.assertEqual(lifecycle.critical_path(plan), (6, ["planning-01", "planning-03", "release-01"]))
        lifecycle.schedule_plan(plan, "2026-01-05")
        tasks = {task["id"]: task for task in plan["tasks"]}
        self.assertEqual(tasks["planning-01"]["start"], tasks["planning-02"]["start"])

    def test_capacity_conflicts_forecast_and_health_report(self):
        plan = lifecycle.new_plan("Health", ["planning-01", "planning-02", "planning-03"])
        lifecycle.update_task(plan, "planning-01", owner="Pat", start="2026-01-05", due="2026-01-07", duration=3, priority="critical")
        lifecycle.update_task(plan, "planning-02", owner="pat", start="2026-01-06", due="2026-01-08", duration=3)
        lifecycle.update_task(plan, "planning-03", due="2026-01-10")
        lifecycle.add_dependency(plan, "planning-02", "planning-01")
        lifecycle.add_dependency(plan, "planning-03", "planning-02")
        self.assertEqual(len(lifecycle.schedule_conflicts(plan)), 1)
        self.assertEqual(lifecycle.owner_capacity(plan)["pat"]["estimated_days"], 6)
        self.assertEqual([item["id"] for item in lifecycle.forecast_slip(plan, "planning-01", 2)], ["planning-01", "planning-02", "planning-03"])
        report = lifecycle.health_report(plan, today=date(2026, 1, 9))
        self.assertEqual(report["progress"]["total"], 3)
        with self.assertRaises(OctoShipError): lifecycle.forecast_slip(plan, "planning-01", -1)

    def test_risk_heatmap_removal_and_nonreused_ids(self):
        plan = lifecycle.new_plan("Risk map", [])
        risk = lifecycle.add_risk(plan, "R1", 4, 5)
        self.assertEqual(lifecycle.risk_heatmap(plan)[4][5], 1)
        self.assertTrue(lifecycle.remove_risk(plan, risk["id"]))
        self.assertFalse(lifecycle.remove_risk(plan, risk["id"]))
        another = lifecycle.add_risk(plan, "R2", 1, 1)
        self.assertNotEqual(risk["id"], another["id"])

    def test_duplicate_plan_is_independent(self):
        plan = lifecycle.new_plan("Original", ["planning-01"])
        lifecycle.add_risk(plan, "Risk", 2, 4)
        clone = lifecycle.duplicate_plan(plan, "Copy")
        lifecycle.update_task(clone, "planning-01", owner="Copy owner")
        self.assertNotEqual(plan["tasks"][0]["owner"], clone["tasks"][0]["owner"])
        self.assertEqual(clone["name"], "Copy")

    def test_baseline_capture_and_variance_report(self):
        plan = lifecycle.new_plan("Baseline", ["planning-01", "planning-02"])
        lifecycle.update_task(plan, "planning-01", start="2026-10-01", due="2026-10-05", owner="A")
        baseline = lifecycle.capture_baseline(plan, "Approved plan")
        lifecycle.update_task(plan, "planning-01", due="2026-10-08", owner="B")
        lifecycle.delete_task(plan, "planning-02")
        report = lifecycle.compare_baseline(plan, baseline["id"])
        self.assertEqual(report["removed"], ["planning-02"])
        self.assertEqual(report["changed"][0]["fields"]["due"]["delta_days"], 3)
        with self.assertRaises(OctoShipError): lifecycle.compare_baseline(plan, "missing")

    def test_schedule_validator_calendar_and_owner_balancing(self):
        plan = lifecycle.new_plan("Calendar", ["planning-01", "planning-02", "release-01"])
        lifecycle.update_task(plan, "planning-01", start="2026-10-10", due="2026-10-05", duration=5)
        lifecycle.update_task(plan, "planning-02", due="2026-10-15", duration=3)
        lifecycle.add_dependency(plan, "planning-02", "planning-01")
        issues = lifecycle.validate_schedule(plan)
        self.assertEqual(issues[0]["issue"], "due-before-start")
        calendar = lifecycle.due_calendar(plan, "2026-10-01", "2026-10-31")
        self.assertIn("planning-02", calendar["2026-10-15"])
        result = lifecycle.assign_unowned_tasks(plan, ["Pat", "Lee"])
        self.assertEqual(len(result["assigned"]), 3)
        self.assertNotEqual(plan["tasks"][0]["owner"], "")
        self.assertEqual(abs(result["workloads"]["Pat"] - result["workloads"]["Lee"]), 1)
        with self.assertRaises(OctoShipError): lifecycle.assign_unowned_tasks(plan, [])

    def test_milestone_reschedule_and_remove(self):
        plan = lifecycle.new_plan("Milestone edit", ["release-01"])
        milestone = lifecycle.add_milestone(plan, "Release", ["release-01"])
        lifecycle.update_milestone(plan, milestone["id"], name="Launch", due="2026-12-01")
        self.assertEqual(plan["milestones"][0]["name"], "Launch")
        self.assertEqual(plan["milestones"][0]["due"], "2026-12-01")
        self.assertTrue(lifecycle.remove_milestone(plan, milestone["id"]))
        self.assertFalse(lifecycle.remove_milestone(plan, milestone["id"]))

    def test_phase_readiness_gated_closeout_and_reopen(self):
        plan = lifecycle.new_plan("Gate", ["planning-01", "planning-02"])
        self.assertFalse(lifecycle.phase_readiness(plan, "planning")["ready_to_close"])
        with self.assertRaises(OctoShipError): lifecycle.close_phase(plan, "planning")
        lifecycle.update_task(plan, "planning-01", status="done")
        lifecycle.update_task(plan, "planning-02", status="skipped")
        self.assertTrue(lifecycle.close_phase(plan, "planning")["closed"])
        self.assertEqual(lifecycle.set_phase_active(plan, "planning"), "planning")

    def test_phase_and_plan_closeout_require_rationale_or_resolved_work(self):
        plan = lifecycle.new_plan("Closeout", ["planning-01", "release-01"])
        with self.assertRaises(OctoShipError): lifecycle.set_plan_status(plan, "closed")
        with self.assertRaises(OctoShipError): lifecycle.close_phase(plan, "planning", allow_open=True)
        lifecycle.close_phase(plan, "planning", allow_open=True, rationale="Stakeholder accepted remaining work")
        lifecycle.update_task(plan, "planning-01", status="done")
        lifecycle.update_task(plan, "release-01", status="done")
        self.assertEqual(lifecycle.set_plan_status(plan, "closed", "Delivered"), "closed")
        self.assertEqual(lifecycle.set_plan_status(plan, "active"), "active")

    def test_carry_forward_preserves_context_and_resets_progress(self):
        source = lifecycle.new_plan("Current", ["planning-01", "planning-02", "release-01"])
        lifecycle.update_task(source, "planning-01", status="done")
        lifecycle.update_task(source, "planning-02", status="doing", priority="high", owner="Pat", notes="Waiting")
        lifecycle.add_dependency(source, "release-01", "planning-02")
        followup = lifecycle.carry_forward_tasks(source, "Next release")
        tasks = {task["id"]: task for task in followup["tasks"]}
        self.assertNotIn("planning-01", tasks)
        self.assertEqual(tasks["planning-02"]["status"], "todo")
        self.assertEqual(tasks["planning-02"]["owner"], "Pat")
        self.assertEqual(tasks["release-01"]["depends_on"], ["planning-02"])

    def test_decision_register_supersession_and_summary(self):
        plan = lifecycle.new_plan("Decision log", [])
        old = lifecycle.add_decision(plan, "Choose database", "Use SQLite", context="Single-user app", owner="Pat")
        replacement = lifecycle.add_decision(plan, "Choose database v2", "Use PostgreSQL", owner="Lee")
        lifecycle.supersede_decision(plan, old["id"], replacement["id"])
        self.assertEqual(lifecycle.decision_register(plan, status="superseded", query="SQLite")[0]["id"], old["id"])
        self.assertEqual(lifecycle.decision_register(plan, owner="Lee")[0]["id"], replacement["id"])
        lifecycle.update_decision(plan, replacement["id"], outcome="Migration completed")
        self.assertEqual(replacement["outcome"], "Migration completed")
        self.assertEqual(lifecycle.decision_summary(plan), {"total": 2, "proposed": 0, "accepted": 1, "reversed": 0, "superseded": 1})
        with self.assertRaises(OctoShipError): lifecycle.supersede_decision(plan, replacement["id"], old["id"])

    def test_issue_tracking_resolution_and_overdue_reporting(self):
        plan = lifecycle.new_plan("Issue log", ["planning-01"])
        issue = lifecycle.add_issue(plan, "Blocked API access", "blocker", owner="Pat", due="2026-01-01", linked_task="planning-01", next_action="Ask admin")
        self.assertEqual(lifecycle.issue_register(plan, severity="blocker", overdue_before="2026-02-01")[0]["id"], issue["id"])
        self.assertEqual(lifecycle.issue_register(plan, status="open", owner="pat")[0]["id"], issue["id"])
        self.assertEqual(lifecycle.issue_summary(plan, today=date(2026, 2, 1))["overdue"], 1)
        with self.assertRaises(OctoShipError): lifecycle.update_issue(plan, issue["id"], status="resolved")
        lifecycle.update_issue(plan, issue["id"], status="in_progress", next_action="Escalate")
        lifecycle.update_issue(plan, issue["id"], status="resolved", resolution="Access granted")
        self.assertEqual(lifecycle.issue_summary(plan)["open"], 0)
        with self.assertRaises(OctoShipError): lifecycle.add_issue(plan, "bad", "urgent")

    def test_outcome_metrics_track_increasing_and_decreasing_targets(self):
        plan = lifecycle.new_plan("Metrics", [])
        uptime = lifecycle.add_metric(plan, "Availability", "%", 90, 99)
        latency = lifecycle.add_metric(plan, "Latency", "ms", 500, 200, direction="decrease")
        self.assertEqual(lifecycle.update_metric_actual(plan, uptime["id"], 99)["status"], "achieved")
        self.assertEqual(lifecycle.update_metric_actual(plan, latency["id"], 350)["progress_percent"], 50.0)
        self.assertEqual(lifecycle.metric_rollup(plan)["achieved"], 1)
        with self.assertRaises(OctoShipError): lifecycle.update_metric_actual(plan, uptime["id"], float("inf"))
        with self.assertRaises(OctoShipError): lifecycle.add_metric(plan, "Bad", "", 1, 1)

    def test_retrospective_lessons_link_to_followup_work(self):
        plan = lifecycle.new_plan("Lessons", ["improvement-01", "improvement-02"])
        lesson = lifecycle.add_lesson(plan, "Review was late", "Reviews waited until Friday", "Request reviews daily", category="process")
        self.assertEqual(lifecycle.lesson_register(plan, category="process", status="open")[0]["id"], lesson["id"])
        lifecycle.apply_lesson(plan, lesson["id"], ["improvement-01", "improvement-02"])
        self.assertEqual(lifecycle.lesson_summary(plan)["applied"], 1)
        with self.assertRaises(OctoShipError): lifecycle.apply_lesson(plan, lesson["id"], ["unknown"])

    def test_effort_estimates_timesheet_grouping_and_variance(self):
        plan = lifecycle.new_plan("Effort", ["implementation-01"])
        task_id = "implementation-01"
        lifecycle.set_effort_estimate(plan, task_id, 8)
        first = lifecycle.log_effort(plan, task_id, "Pat", "2026-10-12", 3.5, "Implementation")
        lifecycle.log_effort(plan, task_id, "Pat", "2026-10-13", 5, "Rework")
        self.assertEqual(lifecycle.effort_report(plan, group_by="owner")["totals"]["Pat"], 8.5)
        self.assertEqual(lifecycle.effort_report(plan, group_by="task")["totals"][task_id], 8.5)
        self.assertEqual(lifecycle.effort_report(plan, group_by="date")["totals"]["2026-10-12"], 3.5)
        self.assertEqual(lifecycle.effort_report(plan, start_date="2026-10-13", end_date="2026-10-13")["hours"], 5)
        self.assertEqual(lifecycle.effort_variance(plan, task_id)["variance_hours"], 0.5)
        self.assertTrue(lifecycle.remove_effort_log(plan, first["id"]))
        self.assertFalse(lifecycle.remove_effort_log(plan, first["id"]))
        with self.assertRaises(OctoShipError): lifecycle.log_effort(plan, task_id, "Pat", "2026-10-12", 25)
        with self.assertRaises(OctoShipError): lifecycle.log_effort(plan, task_id, "Pat", "2026-10-12", 0)
        with self.assertRaises(OctoShipError): lifecycle.log_effort(plan, task_id, "Pat", "bad date", 1)

    def test_project_records_survive_json_transfer_with_counters(self):
        plan = lifecycle.new_plan("All records", ["planning-01"])
        lifecycle.add_decision(plan, "Protocol", "Use HTTPS", owner="Pat")
        lifecycle.add_issue(plan, "Review policy", "high", linked_task="planning-01")
        lifecycle.add_metric(plan, "Adoption", "users", 0, 10)
        lifecycle.add_lesson(plan, "Ask earlier", "Approval was late", "Request signoff at kickoff")
        lifecycle.log_effort(plan, "planning-01", "Pat", "2026-10-12", 2)
        imported = lifecycle.load_plan_from_text(lifecycle.export_json(plan))
        self.assertEqual(len(imported["decisions"]), 1)
        self.assertEqual(len(imported["issues"]), 1)
        self.assertEqual(len(imported["metrics"]), 1)
        self.assertEqual(len(imported["lessons"]), 1)
        self.assertEqual(len(imported["effort_logs"]), 1)
        self.assertEqual(lifecycle.add_decision(imported, "Next", "Use HSTS")["id"], "decision-002")


if __name__ == "__main__":
    unittest.main()
