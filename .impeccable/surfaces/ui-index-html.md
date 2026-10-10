---
version: 1
slug: "ui-index-html"
primary_target: "ui/index.html"
related_targets: []
---

# Surface: harness UI (ui/index.html)

Mode: Operate. Audience: faculty jury and examiners, leaning in to the presenter's laptop.
Job: check the result against its evidence: read the outcome, open any task's two arms, re-run it live.
Constraints: offline, stdlib server (`tw.py ui`), self-hosted fonts, oracle-only live runs, no LLM results implied.
States that matter: recorded vs live result, repo not fetched, run in progress, run failed, placebo arms identical.

## Direction contract

THESIS: Report the experiment the way a clinical trial is reported: allocation, paired arms, placebo, outcome, with every figure traceable to rows. Refuses the KPI-tile dashboard and the stat-card hero.

OWN-WORLD: Journal white ground, ink #1b1b1b, journal blue #0b4f8a for the fused (intervention) arm and links, slate for the static arm, red #b23a2e only for failure and unseen lines, mist #e9eef3 for pooled rows and selection. Source Serif 4 for titles, table captions and figures; Source Sans 3 for UI; system mono only for code. Three-rule tables, small-caps arm labels, CONSORT boxes in 1.5px ink.

STORY: The examiner sees the study's title, the CONSORT allocation from 196 targets to 17 paired tasks, and Table 1 at once; believes the effect because the placebo arm is identical; opens a task and sees exactly which line the static arm could not see and what the suite said; re-runs it live and watches the live entry match the record.

FIRST VIEWPORT: Header bar (serif product name, Report/Tasks/Method tabs, run status right). Left 600px: study title, one-line lede, CONSORT flow ending in two arm boxes (1 of 17, 9 of 17). Right: Table 1 outcomes by group with pooled row in mist, exact p column, note on value references. Task roster starts below the fold.

FORM: Clinical-trial report (medical journal CONSORT + results table), candidate 1 of 7 on the grounded list (chosen as IMPECCABLE'S PICK over the roll); seed key 39ae3f0a. Signature move: the CONSORT flow is the live navigation into the evidence, and live re-runs append a dated entry beside the recorded one.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
