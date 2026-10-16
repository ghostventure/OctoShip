# Lifecycle workbench implementation map

This is a map of implemented user behaviors, not a count of the 100 playbook
entries. Source: `linux/octoship/lifecycle.py` (data and validation) and
`linux/octoship/lifecycle_ui.py` (Tk UI). Focused evidence: `PYTHONPATH=linux
python -m unittest linux.tests.test_lifecycle -v` passed 10 tests.

| User behavior | Implementation | Test evidence |
| --- | --- | --- |
| Search by text | `search_tasks` and playbook Search field | `test_search_and_phase_filter_compose` |
| Filter by lifecycle phase | `search_tasks`; phase selector | `test_search_and_phase_filter_compose` |
| Start a full plan | `new_plan`; Start with all activities | `test_new_plan_all_and_selected` |
| Start a plan from selected activities | `new_plan`; Add selected to plan | `test_new_plan_all_and_selected` |
| Prevent unknown task IDs | `new_plan` | `test_new_plan_all_and_selected` |
| Update task status with dependency guards | `update_task`, `transition_task`; status selector | `test_update_fields_and_validate_dates`, `test_task_transition_requires_dependencies_and_block_reason` |
| Update task priority | `update_task`; priority selector | `test_update_fields_and_validate_dates` |
| Assign a task owner | `update_task`; owner field | `test_update_fields_and_validate_dates` |
| Set a due date with ISO date validation | `update_task`; due field | `test_update_fields_and_validate_dates` |
| Record task notes | `update_task`; notes field | `test_update_fields_and_validate_dates` |
| Record task evidence | `update_task`; evidence field | `test_update_fields_and_validate_dates` |
| Bulk set task state, owner, or priority | `bulk_update_tasks` | `test_bulk_updates_validate_before_mutation` |
| Filter tasks by owner, priority, state, stage, archive state, and overdue cutoff | `filter_tasks` | `test_task_filters_and_safe_delete_references` |
| Reject a blocked task without a reason | `transition_task` | `test_task_transition_requires_dependencies_and_block_reason` |
| Prevent completion before dependencies finish | `transition_task` | `test_task_transition_requires_dependencies_and_block_reason` |
| Add/remove prerequisite relationships | `add_dependency`, `remove_dependency` | `test_dependencies_readiness_and_cycles` |
| Reject self-dependencies, unknown dependencies, and cycles | `update_task`, `_ensure_acyclic` | `test_dependencies_readiness_and_cycles` |
| Show ready and blocked work | `ready_tasks`, `blocked_tasks` | `test_dependencies_readiness_and_cycles` |
| Show dependency waves for parallel work | `dependency_levels` | `test_dependency_waves_critical_path_and_independent_schedule` |
| Calculate longest duration path | `critical_path` | `test_dependency_waves_critical_path_and_independent_schedule` |
| Schedule tasks using dependency order and duration | `schedule_plan` | `test_schedule_respects_dependencies_duration_and_weekends` |
| Schedule on weekdays only | `schedule_plan(weekdays_only=True)` | `test_schedule_respects_dependencies_duration_and_weekends` |
| Validate due date, start date, and dependency order | `validate_schedule` | `test_schedule_validator_calendar_and_owner_balancing` |
| Browse due dates in a bounded calendar window | `due_calendar` | `test_schedule_validator_calendar_and_owner_balancing` |
| Balance unassigned work by estimated task-days | `assign_unowned_tasks` | `test_schedule_validator_calendar_and_owner_balancing` |
| Identify same-owner schedule overlaps | `schedule_conflicts` | `test_capacity_conflicts_forecast_and_health_report` |
| Summarize owner task-day capacity and blockers | `owner_capacity` | `test_capacity_conflicts_forecast_and_health_report` |
| Forecast downstream date movement from a delay | `forecast_slip` | `test_capacity_conflicts_forecast_and_health_report` |
| Rank open work by priority and dependency impact | `critical_tasks` | `test_rollups_and_priority_dependency_ranking` |
| Summarize progress, overdue work, and statuses | `plan_summary` | `test_summary_and_overdue_exclude_finished_tasks` |
| Summarize stage progress, overdue work, and priority | `phase_rollup` | `test_rollups_and_priority_dependency_ranking` |
| Combine delivery health signals in one report | `health_report` | `test_capacity_conflicts_forecast_and_health_report` |
| Check phase closeout readiness | `phase_readiness` | `test_phase_readiness_gated_closeout_and_reopen` |
| Close phase after all tasks resolve | `close_phase` | `test_phase_readiness_gated_closeout_and_reopen` |
| Close phase with an explicit exception rationale | `close_phase(allow_open=True)` | `test_phase_and_plan_closeout_require_rationale_or_resolved_work` |
| Reopen a closed phase | `set_phase_active` | `test_phase_readiness_gated_closeout_and_reopen` |
| Set plan planning/active/paused/closed status | `set_plan_status` | `test_phase_and_plan_closeout_require_rationale_or_resolved_work` |
| Prevent plan closure while unresolved work remains | `set_plan_status("closed")` | `test_phase_and_plan_closeout_require_rationale_or_resolved_work` |
| Carry unresolved tasks into a follow-on plan | `carry_forward_tasks` | `test_carry_forward_preserves_context_and_resets_progress` |
| Preserve owner, priority, notes, and dependency context when carrying work | `carry_forward_tasks` | `test_carry_forward_preserves_context_and_resets_progress` |
| Add and score risks | `add_risk` | `test_risk_register_scores_updates_filters_and_summarizes` |
| Update risk owner, response, probability, impact, or status | `update_risk` | `test_risk_register_scores_updates_filters_and_summarizes` |
| Rank/filter risk register and summarize exposure | `risk_register`, `risk_summary` | `test_risk_register_scores_updates_filters_and_summarizes` |
| View risk probability-impact heatmap | `risk_heatmap` | `test_risk_heatmap_removal_and_nonreused_ids` |
| Remove risks without reusing their IDs | `remove_risk`, `add_risk` | `test_risk_heatmap_removal_and_nonreused_ids` |
| Create milestones from task groups | `add_milestone` | `test_milestone_progress_and_validation` |
| Track milestone completion percentage | `milestone_progress` | `test_milestone_progress_and_validation` |
| Rename and reschedule milestones | `update_milestone` | `test_milestone_reschedule_and_remove` |
| Remove milestones | `remove_milestone` | `test_milestone_reschedule_and_remove` |
| Capture a named schedule/status baseline | `capture_baseline` | `test_baseline_capture_and_variance_report` |
| Compare current plan against a baseline | `compare_baseline` | `test_baseline_capture_and_variance_report` |
| Calculate due-date variance in calendar days | `compare_baseline` | `test_baseline_capture_and_variance_report` |
| Compare plans for task additions, removals, and changes | `compare_plans` | `test_plan_compare_and_merge_strategies` |
| Merge plans while keeping target values | `merge_plans(strategy="keep-target")` | `test_plan_compare_and_merge_strategies` |
| Merge plans using incoming values | `merge_plans(strategy="take-incoming")` | Strategy validation covered in `test_plan_compare_and_merge_strategies` |
| Merge plans preferring completed incoming status | `merge_plans(strategy="prefer-latest-status")` | `test_plan_compare_and_merge_strategies` |
| Archive and restore task history | `archive_tasks`, `restore_tasks` | `test_archive_restore_and_active_rollups` |
| Delete tasks only when no dependency/milestone references remain | `delete_task` | `test_task_filters_and_safe_delete_references` |
| Clone plans independently | `duplicate_plan` | `test_duplicate_plan_is_independent` |
| Remove a selected task from the UI with reference checks | `LifecyclePanel.remove_selected` | Backend behavior tested by `test_task_filters_and_safe_delete_references`; UI has no automated test |
| Summarize statuses and completion | `plan_summary`; task summary | `test_summary_and_overdue_exclude_finished_tasks` |
| Identify overdue open work | `plan_summary` | `test_summary_and_overdue_exclude_finished_tasks` |
| Save a plan atomically with mode 0600 | `save_plan` | `test_atomic_private_save_and_load_round_trip` |
| Reopen and validate a saved plan | `load_plan` | `test_atomic_private_save_and_load_round_trip`, `test_load_rejects_corrupt_or_invalid_plan` |
| Export plan as Markdown | `export_markdown` | `test_markdown_export_includes_progress_and_escapes_newlines` |
| Export plan as spreadsheet-ready CSV | `export_csv` | `test_csv_export_is_parseable_and_keeps_user_text_as_one_cell` |

The playbook also has a catalog integrity test asserting 100 unique IDs,
titles, and activity instructions across ten stages; these are task templates,
not counted as additional software behaviors.

## Additional record and outcome workflows

| User behavior | Implementation | Test evidence |
| --- | --- | --- |
| Capture an accepted decision with context and owner | `add_decision` | `test_decision_register_supersession_and_summary` |
| Change a decision to proposed, accepted, or reversed | `update_decision` | `test_decision_register_supersession_and_summary` |
| Record the observed outcome of a decision | `update_decision(outcome=...)` | `test_decision_register_supersession_and_summary` |
| Supersede an older decision with an accepted replacement | `supersede_decision` | `test_decision_register_supersession_and_summary` |
| Filter the decision log by lifecycle state | `decision_register(status=...)` | `test_decision_register_supersession_and_summary` |
| Search decisions by text and owner | `decision_register(query=..., owner=...)` | `test_decision_register_supersession_and_summary` |
| Summarize decisions by proposed, accepted, reversed, and superseded state | `decision_summary` | `test_decision_register_supersession_and_summary` |
| Capture issues at blocker, high, medium, or low severity | `add_issue` | `test_issue_tracking_resolution_and_overdue_reporting` |
| Link an issue to a lifecycle task | `add_issue`, `update_issue` | `test_issue_tracking_resolution_and_overdue_reporting` |
| Assign issue ownership, due date, and next action | `add_issue`, `update_issue` | `test_issue_tracking_resolution_and_overdue_reporting` |
| Move issues through open, triaged, active, resolved, and wont-fix states | `update_issue` | `test_issue_tracking_resolution_and_overdue_reporting` |
| Require a resolution note before resolving an issue | `update_issue` | `test_issue_tracking_resolution_and_overdue_reporting` |
| Filter issues by status and severity | `issue_register(status=..., severity=...)` | `test_issue_tracking_resolution_and_overdue_reporting` |
| Filter issues by owner | `issue_register(owner=...)` | `test_issue_tracking_resolution_and_overdue_reporting` |
| Find overdue unresolved issues | `issue_register(overdue_before=...)` | `test_issue_tracking_resolution_and_overdue_reporting` |
| Summarize open issues, overdue issues, and severity counts | `issue_summary` | `test_issue_tracking_resolution_and_overdue_reporting` |
| Define a direction-aware increasing or decreasing outcome target | `add_metric(direction=...)` | `test_outcome_metrics_track_increasing_and_decreasing_targets` |
| Record measured outcome values | `update_metric_actual` | `test_outcome_metrics_track_increasing_and_decreasing_targets` |
| Calculate outcome progress and remaining target gap | `metric_status` | `test_outcome_metrics_track_increasing_and_decreasing_targets` |
| Mark outcome target as achieved, in progress, or behind | `metric_status` | `test_outcome_metrics_track_increasing_and_decreasing_targets` |
| Roll up outcome metrics and achieved target count | `metric_rollup` | `test_outcome_metrics_track_increasing_and_decreasing_targets` |
| Capture retrospective observations and recommendations | `add_lesson` | `test_retrospective_lessons_link_to_followup_work` |
| Filter lessons by category | `lesson_register(category=...)` | `test_retrospective_lessons_link_to_followup_work` |
| Link lessons to follow-up tasks | `apply_lesson` | `test_retrospective_lessons_link_to_followup_work` |
| Summarize open and applied lessons by category | `lesson_summary` | `test_retrospective_lessons_link_to_followup_work` |
| Set person-hour estimates separately from calendar duration | `set_effort_estimate` | `test_effort_estimates_timesheet_grouping_and_variance` |
| Record dated effort entries with owner, task, hours, and note | `log_effort` | `test_effort_estimates_timesheet_grouping_and_variance` |
| Group effort reports by owner | `effort_report(group_by="owner")` | `test_effort_estimates_timesheet_grouping_and_variance` |
| Group effort reports by owner, task, date, or individual entry | `effort_report(group_by=...)` | `test_effort_estimates_timesheet_grouping_and_variance` |
| Restrict effort reports to a date range | `effort_report(start_date=..., end_date=...)` | `test_effort_estimates_timesheet_grouping_and_variance` |
| Compare actual person-hours with task estimate | `effort_variance` | `test_effort_estimates_timesheet_grouping_and_variance` |
| Remove an incorrect effort entry and recalculate totals | `remove_effort_log` | `test_effort_estimates_timesheet_grouping_and_variance` |
| Reject nonpositive or over-24-hour daily effort entries | `log_effort` | `test_effort_estimates_timesheet_grouping_and_variance` |
| Preserve decision, issue, outcome, lesson, and effort records in JSON transfer | `export_json`, `load_plan_from_text` | `test_project_records_survive_json_transfer_with_counters` |
