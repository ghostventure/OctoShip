# Project lifecycle workbench

The **Project lifecycle** page in the Shipping workbench provides an offline,
searchable playbook of 100 activities across ten project stages. Select a
subset or start with the full plan, then track status, priority, owner, due
date, notes, and evidence. Plans are private local JSON files; reports export
to Markdown, CSV, or JSON. Planning operations include dependency-aware
weekday scheduling, risk and milestone tracking, owner balancing, baseline
variance, plan comparison and merge, archive and restore, phase gates, and
follow-on plans. No activity runs project code, calls GitHub, or deploys.

Implementation is in `linux/octoship/lifecycle.py` and
`linux/octoship/lifecycle_ui.py`. Focused coverage is in
`linux/tests/test_lifecycle.py`.
