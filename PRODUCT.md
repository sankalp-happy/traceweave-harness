# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Plain HTML, CSS and JavaScript served by Python's standard-library HTTP server
(`tw.py ui`). No build step, no npm, no new runtime dependencies: the UI must run
anywhere the harness runs, offline.

## Users

Faculty jury and examiners at a department research expo, reviewing a final-year
research project. Technical readers who will question the method and the numbers.
The presenter drives the UI on a laptop screen while the examiner leans in.

## Product Purpose

The TraceWeave harness runs one controlled experiment: does giving an LLM runtime
call-graph context change whether its repo-wide edits work? The UI exists to make
that experiment inspectable in front of an examiner: the result, then any single
task's two arms side by side, then a live re-run on demand. Success is an examiner
who can check a claim against the evidence without the presenter narrating it.

## Positioning

A measured, falsifiable result with a placebo control and a test-suite oracle, not
an explainer or an animation. Every number on screen traces to a results file and a
command that regenerates it.

## Operating Context

- Shown at a booth on the presenter's laptop; examiners lean in to a 13–15 inch screen.
- Network and API credentials may be absent: recorded results must render fully offline.
- A live run takes seconds (click's suite is ~5 s per arm); the UI must show that it is running.
- Examiners may ask "show me the prompt", "which lines couldn't it see", "why did this fail".

## Capabilities and Constraints

- Data sources: `bundles/<repo>/{repo.json,graph.json,tasks.json}`, `results/*.jsonl`,
  checkouts under `work/<repo>` (created by `tw.py fetch`).
- Two arms per task: **static** (PyCG ∪ Pyright callers) and **fused** (plus runtime-only callers).
- Two task groups: **treatment** (≥1 runtime-only caller) and **placebo** (none; prompts identical).
- Models: `oracle` (ceiling), `claude:<id>` (needs key), `replay:<file>`.
- Verdict: same passing-test count as baseline and no new failures.
- Terminology to keep exact: arm, treatment, placebo, oracle, runtime-only caller,
  reference lines, verdict.

## Evidence on Hand

- `results/click.oracle.jsonl`, `results/toolz.oracle.jsonl`: oracle runs, 140 tasks × 2 arms.
- Headline (oracle ceiling): treatment static 1/17 vs fused 9/17, exact p ≈ 0.008;
  placebo 108/123 in both arms.
- No LLM results exist yet. The UI must not imply that they do.

## Product Principles

1. Evidence over assertion: every claim on screen links to the rows that produce it.
2. The difference between arms is the subject; everything held equal recedes.
3. Honest about absence: missing runs, ceilings and limits are stated, not hidden.
4. Works offline on a modest laptop, first time, every time.
