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

TraceWeave asks whether AI can recover the calls static analysis misses, and
whether an AI agent edits code safely with that context. Ground truth is recorded
from execution (the project's test suite under a tracer). Study 1 scores static
analysers, three LLMs and a learned combiner on "does this code call that
function?"; Study 2 runs an AI agent on renames a regex cannot do. The UI makes
both inspectable in front of an examiner: the precision-recall plane first, then
any item or task, then a live run on demand.

## Positioning

A measured, falsifiable result with a placebo control and a test-suite oracle, not
an explainer or an animation. Every number on screen traces to a results file and a
command that regenerates it.

## Operating Context

- Shown at a booth on the presenter's laptop; examiners lean in to a 13–15 inch screen.
- Network and API credentials may be absent: recorded results must render fully offline.
- A live run takes seconds (click's suite is ~5 s per arm); the UI must show that it is running.
- The live demo (`#/live`, the default view) runs the experiment on screen: the suite under a
  tracer (sys.monitoring, Python 3.12+), an editor, and the suite again per arm, streamed as
  server-sent events. gpt-oss-20b needs a Groq key in `.env` and a network; everything else runs offline.
- Examiners may ask "show me the prompt", "which lines couldn't it see", "why did this fail".

## Capabilities and Constraints

- Data sources: `bundles/<repo>/{repo.json,graph.json,tasks.json}`, `results/*.jsonl`,
  checkouts under `work/<repo>` (created by `tw.py fetch`).
- Two arms per task: **static** (PyCG ∪ Pyright callers) and **fused** (plus runtime-only callers).
- Two task groups: **treatment** (≥1 runtime-only caller) and **placebo** (none; prompts identical).
- Models: `oracle` (ceiling), `groq:<id>` (gpt-oss-20b live; needs key and network), `claude:<id>` (needs key), `replay:<file>`.
- LLM edits are `{path, line, old, new}`, so a model never retypes indentation; the oracle and recorded rows use whole lines.
- Verdict: same passing-test count as baseline and no new failures.
- Terminology to keep exact: arm, treatment, placebo, oracle, runtime-only caller,
  reference lines, verdict.

## Evidence on Hand

- `results/click.oracle.jsonl`, `results/toolz.oracle.jsonl`: oracle runs, 140 tasks × 2 arms.
- Headline (oracle ceiling): treatment static 1/17 vs fused 9/17, exact p ≈ 0.008;
  placebo 108/123 in both arms.
- No saved LLM results are reported yet: the 78-row gpt-oss-20b pilot (whole-line edits) sits in
  `results/pilot/` and is left out of every page. LLM verdicts on the live page come from that session only, and say so.

## Product Principles

1. Evidence over assertion: every claim on screen links to the rows that produce it.
2. The difference between arms is the subject; everything held equal recedes.
3. Honest about absence: missing runs, ceilings and limits are stated, not hidden.
4. Works offline on a modest laptop, first time, every time.
