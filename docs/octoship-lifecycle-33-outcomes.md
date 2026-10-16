# OctoShip project lifecycle: 33 implemented outcomes

This inventory counts independently usable offline workflows exposed in the
Linux Shipping workbench. The 100 lifecycle playbook activities are task
templates and are not included in this count. Operations edit local plan data;
they do not execute project code, publish to GitHub, or deploy.

| # | User-visible outcome | Implementation paths |
| ---: | --- | --- |
| 1 | Search the project activity catalog by text and lifecycle stage. | `linux/octoship/lifecycle.py:190`; `linux/octoship/lifecycle_ui.py:430` |
| 2 | Create a project plan from selected catalog activities. | `linux/octoship/lifecycle.py:199`; `linux/octoship/lifecycle_ui.py:439` |
| 3 | Start a plan with the complete catalog. | `linux/octoship/lifecycle.py:199`; `linux/octoship/lifecycle_ui.py:451` |
| 4 | Track task state, priority, owner, dates, duration, notes, evidence, and blocked reason. | `linux/octoship/lifecycle.py:220`; `linux/octoship/lifecycle_ui.py:462` |
| 5 | Bulk change task status, priority, or owner with validation before mutation. | `linux/octoship/lifecycle.py:672` |
| 6 | Filter project tasks by status, priority, owner, stage, archive state, or overdue date. | `linux/octoship/lifecycle.py:631` |
| 7 | Add and remove task prerequisites while rejecting invalid or cyclic dependencies. | `linux/octoship/lifecycle.py:534`; `linux/octoship/lifecycle_ui.py:319` |
| 8 | See which tasks are ready to start and which are waiting on prerequisites. | `linux/octoship/lifecycle.py:555`; `linux/octoship/lifecycle_ui.py:326` |
| 9 | Generate dependency-ordered schedules with task durations and optional weekday-only dates. | `linux/octoship/lifecycle.py:569`; `linux/octoship/lifecycle_ui.py:332` |
| 10 | Validate dates, dependency ordering, and schedule conflicts. | `linux/octoship/lifecycle.py:725`; `linux/octoship/lifecycle.py:826`; `linux/octoship/lifecycle_ui.py:339` |
| 11 | Browse tasks due inside a chosen date window. | `linux/octoship/lifecycle.py:844`; `linux/octoship/lifecycle_ui.py:354` |
| 12 | Assign unowned work across named owners using estimated task duration. | `linux/octoship/lifecycle.py:858`; `linux/octoship/lifecycle_ui.py:358` |
| 13 | Review project progress, overdue work, stage rollups, and combined health signals. | `linux/octoship/lifecycle.py:278`; `linux/octoship/lifecycle.py:603`; `linux/octoship/lifecycle.py:761`; `linux/octoship/lifecycle_ui.py:335` |
| 14 | Identify critical tasks and the longest dependency path. | `linux/octoship/lifecycle.py:620`; `linux/octoship/lifecycle.py:698` |
| 15 | Forecast downstream schedule movement when a task is delayed. | `linux/octoship/lifecycle.py:741` |
| 16 | Add, update, rank, filter, summarize, and remove risks in a local risk register. | `linux/octoship/lifecycle.py:777`; `linux/octoship/lifecycle.py:949`; `linux/octoship/lifecycle.py:964`; `linux/octoship/lifecycle.py:979`; `linux/octoship/lifecycle_ui.py:385` |
| 17 | Create milestones from task groups and track their completion. | `linux/octoship/lifecycle.py:992`; `linux/octoship/lifecycle.py:1007`; `linux/octoship/lifecycle_ui.py:395` |
| 18 | Rename, reschedule, or remove a milestone. | `linux/octoship/lifecycle.py:871`; `linux/octoship/lifecycle.py:886` |
| 19 | Capture a named plan baseline and compare current status and dates against it. | `linux/octoship/lifecycle.py:792`; `linux/octoship/lifecycle.py:804`; `linux/octoship/lifecycle_ui.py:343` |
| 20 | Compare two plans and inspect additions, removals, and changed task data. | `linux/octoship/lifecycle.py:1017`; `linux/octoship/lifecycle_ui.py:402` |
| 21 | Merge a plan using keep-target, take-incoming, or incoming-status preference. | `linux/octoship/lifecycle.py:1028`; `linux/octoship/lifecycle_ui.py:408` |
| 22 | Archive and restore task records without deleting their history. | `linux/octoship/lifecycle.py:1049`; `linux/octoship/lifecycle.py:1056`; `linux/octoship/lifecycle_ui.py:413` |
| 23 | Close a lifecycle stage after readiness review, or record a reason for an exception; reopen it later. | `linux/octoship/lifecycle.py:892`; `linux/octoship/lifecycle.py:904`; `linux/octoship/lifecycle.py:915`; `linux/octoship/lifecycle_ui.py:362` |
| 24 | Set the whole plan to planning, active, paused, or closed with closure checks. | `linux/octoship/lifecycle.py:922`; `linux/octoship/lifecycle_ui.py:373` |
| 25 | Carry unresolved activities and their context into a follow-up plan. | `linux/octoship/lifecycle.py:933`; `linux/octoship/lifecycle_ui.py:376` |
| 26 | Import a validated CSV plan and export a plan as CSV or JSON. | `linux/octoship/lifecycle.py:1063`; `linux/octoship/lifecycle.py:1069`; `linux/octoship/lifecycle_ui.py:420`; `linux/octoship/lifecycle_ui.py:508` |
| 27 | Save plans privately and atomically, reopen them, and export a Markdown status report. | `linux/octoship/lifecycle.py:421`; `linux/octoship/lifecycle.py:445`; `linux/octoship/lifecycle.py:464`; `linux/octoship/lifecycle_ui.py:489` |
| 28 | Capture decisions with context and ownership, update outcomes, search/filter, and supersede decisions. | `linux/octoship/lifecycle.py:1103`; `linux/octoship/lifecycle.py:1115`; `linux/octoship/lifecycle.py:1126`; `linux/octoship/lifecycle.py:1135`; `linux/octoship/lifecycle_ui.py:245` |
| 29 | Track issues with severity, owner, due date, next action, linked task, status, and resolution. | `linux/octoship/lifecycle.py:1151`; `linux/octoship/lifecycle.py:1167`; `linux/octoship/lifecycle_ui.py:257` |
| 30 | Review issue registers, overdue issues, and severity summaries. | `linux/octoship/lifecycle.py:1183`; `linux/octoship/lifecycle.py:1197`; `linux/octoship/lifecycle_ui.py:263` |
| 31 | Define increasing or decreasing outcome targets, record actuals, and review progress. | `linux/octoship/lifecycle.py:1207`; `linux/octoship/lifecycle.py:1227`; `linux/octoship/lifecycle.py:1234`; `linux/octoship/lifecycle_ui.py:266` |
| 32 | Capture retrospective lessons, categorize them, and link them to follow-up tasks. | `linux/octoship/lifecycle.py:1250`; `linux/octoship/lifecycle.py:1263`; `linux/octoship/lifecycle.py:1274`; `linux/octoship/lifecycle_ui.py:275` |
| 33 | Estimate person-hours, log dated effort, report by owner/task/date/entry, compare estimate variance, and remove mistaken entries. | `linux/octoship/lifecycle.py:1288`; `linux/octoship/lifecycle.py:1297`; `linux/octoship/lifecycle.py:1312`; `linux/octoship/lifecycle.py:1328`; `linux/octoship/lifecycle.py:1338`; `linux/octoship/lifecycle_ui.py:285` |

## Partial or unimplemented

- These workflows are local planning and recordkeeping. There is no automatic
  project-code execution, source-control integration, GitHub issue sync,
  deployment, or collaboration service in the lifecycle panel.
- Interactive Tk behavior and these paths were not exercised as part of this
  inventory task. The inventory describes code wiring, not a claim of a new
  runtime or release verification.
