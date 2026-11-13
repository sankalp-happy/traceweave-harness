# TraceWeave harness

**Static analysis misses about a third of the calls a Python program really
makes. Can AI find them, and can an AI agent edit code safely with what it finds?**

Everything here is scored against what the program did: the project's own
test suite runs under a tracer (Python 3.12 `sys.monitoring`) and records every
call, with the line it came from. Nothing is labelled by hand or by a model.

| | What it asks | Who answers | Result so far |
|---|---|---|---|
| **Ground truth** | What did click's 1,939 passing tests actually call? | the tracer (`tw.py truth`) | 704 caller-to-callee paths; PyCG ∪ Pyright hold 69% |
| **Study 1** | Does this line of code call that function? (2,381 items) | PyCG, Pyright, gpt-oss-20b, gpt-oss-120b, qwen3.8-27b, a learned combiner | static P 0.94 / R 0.78; best AI R 0.96 but P 0.74; combiner F1 0.87, the best |
| **Study 2** | Rename a function whose name another function shares | regex, an AI agent with grep / static / runtime context | regex 0 of 9; exact rename 9 of 9; AI agent runs in `results/agent/` |

The AI models were run on Groq at temperature 0. The learned combiner is a
logistic regression over static flags, each model's answer and how the name is
written, scored out-of-fold (5-fold, grouped by function). In click, AI finds the
calls static analysis is blind to (shared names, properties); in toolz, where
static analysis is already near perfect, the models mostly add false claims,
and the combiner learns to lean on static analysis there.

It is the downstream half of TraceWeave-Core, the research repo (not yet published).
Core builds the static call graphs; the bundles here carry them, so running
everything needs Python 3.12+, git and pytest, and nothing else (plus a Groq key in
`.env` for the AI runs).

### The studies, from the command line

```bash
python3 tw.py truth click                        # record the ground truth (about 6 s)
python3 tw.py bench click toolz                  # Study 1: every resolver, scored
python3 tw.py resolve click --model groq:openai/gpt-oss-120b   # ask a model (resumable)
python3 tw.py learn click toolz                  # train and cross-validate the combiner
python3 tw.py agent-tasks click --validate       # Study 2: find and validate the tasks
python3 tw.py agent click --model groq:openai/gpt-oss-120b     # run the agent (resumable)
python3 tw.py ui                                 # the demo: http://127.0.0.1:8765/
```

| file | what it does |
|---|---|
| `truth.py` | ground truth from one traced test run: every call, its line, every line that ran |
| `bench.py` | Study 1 items (a function names a project function in code that ran) and scoring |
| `resolve.py` | the AI resolver prompt, the fixed sample (seed in `results/resolve/*.sample.json`), the runs |
| `ml.py` | the learned combiner: logistic regression written out, grouped cross-validation |
| `agent.py` | Study 2: same-name rename tasks, their validation, the agent and its three contexts |
| `studies.py` | what the pages show, aggregated from the files above |

The rest of this README describes the **pilot study** that came first: renames of
functions with unique names, where a regex would also have worked. Its pages are
kept under Method → Earlier pilot.

---

## Pilot study: the experiment

| | |
|---|---|
| **Task** | Rename one function or method repo-wide. It has one unambiguous right answer and a free oracle. |
| **Static arm** | The model sees the target's definition plus every caller that **PyCG ∪ Pyright** report, as line-numbered excerpts. The static arm gets the union of both tools, the strongest static graph available. |
| **Fused arm** | Identical, plus the callers observed while the repo's own test suite ran under `sys.setprofile`. |
| **Held equal** | Prompt template, slicer, excerpt window, token budget, model, effort. `tests/test_harness.py` checks on every task that the two prompts differ only in the caller list and the excerpts those callers pull in. |
| **Slicer** | The retrieval unit is a caller *function*, as in code-graph RAG. For each caller the model sees ±2 lines around every line of that function's own body that names the target, plus, for a runtime-only edge, the line the tracer saw make the call. |
| **Oracle** | Apply the edits, run the full suite. A task passes only if the same number of tests pass as on the untouched checkout and no new test fails. |
| **Models** | `oracle` (the ceiling: a perfect editor limited to what the context shows), `groq:<model-id>` (open-weight models on Groq; the first LLM run is `groq:openai/gpt-oss-20b`) and `claude:<model-id>`. Every response is recorded, so `replay:` re-scores a run offline. |

### Two arms of tasks

- **Treatment**: the target has at least one caller that only the runtime trace sees. The static arm cannot see that call site at all.
- **Placebo**: the target has no runtime-only callers, so the two arms receive **byte-identical prompts**. Any difference between arms on placebo tasks is the model's own run-to-run noise, which gives the noise floor that treatment results have to clear.

### Pre-registered predictions (written 2026-10-10, before any LLM run)

1. **Treatment:** the fused arm passes more tasks than the static arm. Test: exact two-sided McNemar on discordant pairs (`tw.py report`).
2. **Placebo:** no difference between arms beyond model noise. Its prompts are identical by construction.

The oracle ran before these were written. Its numbers below are the ceiling
the LLM runs are read against, not a test of these predictions.

Banned as in TraceWeave-Core's plan: LLM-as-judge in any headline metric, and pooled means without the per-arm split.

### How tasks are chosen, and what that costs

`tw.py tasks` keeps a symbol only if:

- it is a function or method with a plain name of four or more characters: not a dunder, a lambda, an overload stub or a numbered redefinition;
- its name is **unique** in the package, because otherwise "rename it" means "rename an override family", which is a different task;
- its name **never appears in the test suite**, because the unmodified suite is the oracle;
- at least one in-package caller **ran** under the suite.

Then `--validate` proves each task can be graded, in both directions: renaming every line that names the symbol must **pass**, and renaming only the definition must **fail**. Tasks that fail either check are dropped. None of these filters looks at which arm sees what.

The filters are strict, and the attrition is a result in its own right:

| click | targets |
|---|---|
| all targets with ≥1 runtime-only caller | 166 |
| dropped: name shared with another node (override families) | 82 |
| dropped: dunder (`__init__`, protocol methods) | 31 |
| dropped: named in the test suite | 30 |
| dropped: lambda | 4 |
| dropped: name under four characters | 2 |
| candidates | 17 |
| dropped by validation (the suite cannot tell right from wrong) | 2 |
| **treatment tasks** | **15** |

toolz contributes 2 treatment tasks (30 runtime-only targets; most of the rest are dunders or named in its tests).

Half of the calls static analysis misses in click land on methods that share a name across a class hierarchy. That is exactly where runtime information should matter most, and exactly the case this v1 task cannot grade. Renaming a whole override family is the obvious next task.

---


## Quick start (any laptop)

```bash
pip install -r requirements.txt          # pytest; anthropic only for claude runs
python3 tw.py fetch toolz                # shallow-clones the pinned commit into work/, runs the baseline
python3 tw.py show toolz:thread_first.evalform_front --live oracle
python3 tw.py report results/*.jsonl
```

`tw.py fetch` clones at the exact commit TraceWeave-Core analysed and refuses
to run on any other.

### Running a model

```bash
python3 tw.py run toolz --model oracle
python3 tw.py run click --model groq:openai/gpt-oss-20b
python3 tw.py run click --model claude:claude-opus-5-5 --effort medium
python3 tw.py report results/click.groq_openai_gpt-oss-20b.jsonl
```

Runs append to `results/<repo>.<model>.jsonl`, one row per task × arm, and resume
where they stopped. Each row records the prompt's SHA-256, the callers shown,
how many of the symbol's reference lines the context covered, every edit, the
full test outcome, and the served-by model. Claude requests opt into server-side
refusal fallback (`fallbacks: "default"`). If a fallback model ever answers, it
shows in `model_meta.served_by` and can be excluded.

Groq runs use only the standard library and read `GROQ_API_KEY` from the
environment or from a `.env` file next to `tw.py` (gitignored). Requests ask
for strict JSON-schema output at temperature 0 and seed 0, with `--effort` passed
as gpt-oss's reasoning effort. The user prompt is the same bytes every model
gets. When Groq cannot parse an answer, the request is sent again, up to three
tries in all (`model_meta.attempts`). After that the run is scored a fail. Groq
rate limits (HTTP 429) are waited out and never scored. Each row also records
the model's reasoning text. When an edit leaves a file Python cannot parse, the row
records the error under `apply.syntax_error`.

`python3 tw.py prompt <task> static|fused` prints the exact prompt an arm receives.

### The live demo and the results pages

```bash
python3 tw.py ui        # http://127.0.0.1:8765/  (stdlib server, works offline)
```

The page opens on **Live demo**. It tells one task as a story in plain words,
so a viewer who does not read Python can follow it. The function is used in
N places in the code, and each run shows the editor some of them. The editor
renames what it sees, then the project's tests judge the result. Each step runs
on the real code when you press Next:

1. **Read the code.** The callers PyCG and Pyright found, drawn as a small call graph. They were computed beforehand, from the bundle. A row of squares shows how many of the N places this gives the editor.
2. **Run the tests.** The project's whole test suite runs with a tracer
   (`live/tw_live.py`, a pytest plugin on Python 3.12's `sys.monitoring`). Each
   caller appears on the graph the moment a test calls the function. On click
   this takes about 5 s, and it finds the same hidden callers as the recorded
   trace (checked in `tests/`).
3. **Rename.** The rename script, or gpt-oss-20b live through Groq, edits both runs. Each place square turns solid when that place is renamed, or red when it still has the old name.
4. **Check with the tests.** Each run's edits go onto the checkout and the full suite runs, with its progress shown as it goes, ending in Pass or Fail.

Above the task, a scoreboard shows one square per task for each run, filled
from the recorded results (1 and 9 of 17). Squares run live today get a ring.
**Run all 17 live** repeats steps 3 and 4 for every task. The code itself is
behind **Show the code**. Live verdicts are kept only in the browser tab's
session storage. The stages stream from `GET /api/live?stage=trace|edit|test&id=...`
as server-sent events, one run at a time.

The other three views read from `bundles/` and `results/`. When more than one model
has results, a switch in the header picks the editor; an LLM is shown first,
with the oracle's numbers quoted as its ceiling.

- **Report:** the CONSORT allocation and the outcome tables.
- **Tasks:** a filterable roster of every task.
- **Method:** design, predictions and limits.

Opening a task shows its two arms side by side:

- the runtime-only callers and the lines that made each call;
- the excerpts each arm was shown, with lines only the fused arm saw tinted;
- the lines naming the function that each arm never saw;
- each arm's edits, its test-suite verdict, and its exact prompt.

**Re-run both arms now** re-applies the oracle (never an LLM) and runs the suite live.
Do not use it while `tw.py run` is going on the same repo: the two share one checkout. The live
result is added under the recorded one; it never replaces it. Task views need
`tw.py fetch <repo>` first, and the report does not.

### In the terminal

`show` puts one task's two arms side by side: the runtime-only caller and the
line it calls from, which reference lines each arm could not see, and what the
test suite said.

```
  click:Option.flag_activation_value   (treatment)
  rename Option.flag_activation_value -> flag_activation_value_v2   src/click/core.py:3035
  callers: 1 static, 4 observed at runtime, 4 visible ONLY at runtime

    runtime-only  Option._resolve_lazy_default
                  src/click/core.py:3140  return self.flag_activation_value
    runtime-only  Option.add_to_parser
                  src/click/core.py:3320  const=self.flag_activation_value,
    runtime-only  Option.consume_value
                  src/click/core.py:3606  value = self.flag_activation_value
    runtime-only  Option.to_info_dict
                  src/click/core.py:3182  flag_value=self.flag_activation_value,

  [STATIC]  1 callers in context, sees 1/9 lines that name the symbol
      cannot see  src/click/core.py:3140  return self.flag_activation_value
      ...
      oracle: 1 edits -> FAIL  (764 passed, 1175 failed, 0 errors)

  [FUSED]  5 callers in context, sees 8/9 lines that name the symbol
      cannot see  src/click/core.py:3006  # lazily in :meth:`_resolve_lazy_default` and :attr:`flag_activation_value`.
      oracle: 8 edits -> PASS  (1939 passed, 0 failed, 0 errors)
```

`flag_activation_value` is a property. Static analysis sees no call when
it is read, so the static arm's rename breaks 1,175 of click's 1,939 tests. A
smaller one, in toolz:

```
  toolz:thread_first.evalform_front   (treatment)
  rename thread_first.evalform_front -> evalform_front_v2   toolz/functoolz.py:70
  callers: 1 static, 1 observed at runtime, 1 visible ONLY at runtime

    runtime-only  thread_first
                  toolz/functoolz.py:77  return reduce(evalform_front, forms, val)

  [STATIC]  1 callers in context, sees 1/2 lines that name the symbol
      cannot see  toolz/functoolz.py:77  return reduce(evalform_front, forms, val)
      oracle: 1 edits -> FAIL  (179 passed, 2 failed, 0 errors)
        toolz/tests/test_functoolz.py::test_thread_first

  [FUSED]  2 callers in context, sees 2/2 lines that name the symbol
      oracle: 2 edits -> PASS  (180 passed, 1 failed, 0 errors)
```

(`test_has_version` fails on the untouched toolz checkout too: it needs installed
package metadata. The verdict only counts *new* failures.)

---

## Results so far

**Oracle only, so far.** These numbers are the *ceiling*: what a perfect editor
could do with each arm's context. No LLM has been run yet. The Claude adapter
is wired and was checked against a mocked transport, but a live run needs
credentials. Produced by `python3 tw.py report results/*.jsonl` on 2026-10-10.

| | tasks | static arm passes | fused arm passes | fused only | static only | exact p |
|---|---|---|---|---|---|---|
| **Treatment**, click | 15 | 1 | 7 | 6 | 0 | 0.031 |
| **Treatment**, toolz | 2 | 0 | 2 | 2 | 0 | 0.5 |
| **Treatment**, both | **17** | **1 (6%)** | **9 (53%)** | **8** | **0** | **0.008** |
| Placebo, click | 110 | 95 | 95 | 0 | 0 | 1 |
| Placebo, toolz | 13 | 13 | 13 | 0 | 0 | 1 |

What the ceiling already says:

- **With static context alone, even a perfect editor almost never completes these renames** (1 of 17). It cannot edit a call site it was never shown.
- **Runtime edges recover about half of them** (9 of 17), and no task goes the other way. Reference-line coverage on treatment tasks rises from 53% to 76% (click).
- **The other half is a hard limit of call graphs, not of tracing.** All 8 click treatment tasks the fused arm still fails miss exactly one line, and in every case the function is referenced *as a value* on a line that is not a call: a stream-dispatch dict (`"stdout": get_binary_stdout`), a callback registration (`kwargs.setdefault("callback", show_help)`, `ctx.call_on_close(lf.close_intelligently)`), or a monkeypatch (`pdb.Pdb.__init__ = _patched_pdb_init`). The runtime trace sees the call, but it happens somewhere else entirely. A reference graph, not a call graph, closes that gap.
- **Placebo arms are identical by construction**, and the oracle confirms it: 108 of 123 pass in both. The 15 click placebo failures are references *neither* graph holds (names stored in dicts and default arguments), so they lower both arms equally.

The LLM result to report is how far a real model gets toward each arm's ceiling,
and whether the gap between the arms survives the model's own errors.

---

## Threats to validity

- **Small n.** The pilot has 17 treatment tasks, not hundreds. The paired exact test is reported with its p-value, and a non-significant result is reported as such.
- **A unique name makes `grep` sufficient.** For these tasks a text search would find every site. The experiment measures **call-graph-retrieved context**, the kind code-graph RAG and agent tools supply, not whether renaming is hard. A grep-equipped agent is a different baseline and is not claimed against.
- **Runtime coverage is only as good as the test suite.** A caller the tests never execute is invisible to both arms. It also cannot break the oracle, which is why tasks need an executed caller.
- **Call edges are not references.** A function passed as a value is named on a line that is not a call. When the call happens in a caller that also names it (`reduce(evalform_front, …)`), the fused arm sees it. When the value is stored elsewhere (a dict, a callback registration), neither arm does. That is all 8 of click's fused-arm misses (see results).
- **The slicer was revised once, before any LLM run.** The first version found caller lines through TraceWeave's AST call-site table, which misses attribute reads. The oracle exposed this on a property (`Option.flag_activation_value`), and the slicer now matches the target's name within each retrieved caller's own body. The change applies to both arms identically, and the prompt-invariance check covers it.
- **Context-limited editing.** Models may only edit lines they were shown. This is deliberate: it attributes outcomes to the context rather than to guessing, and the instruction is identical in both arms.
- **Token estimate.** The budget uses characters ÷ 4, not a tokenizer. The same estimate applies to both arms, so it cannot favour one. It only decides when an excerpt list is truncated, and every truncation is recorded per row.
- **Provenance.** click and toolz static graphs were extracted on the arm64 manager host (TraceWeave-Core `MANIFEST` §1 treats those as development output, not corpus records). Both repos are pure Python, so no architecture-dependent wheels enter the graph. They should still be regenerated on the amd64 execution host before anything is published. `graph.json` records host and tool pins.
- **Model-generated code is executed.** The suite runs on edited source. Edits replace text on one existing line, confined to the checkout and checked before writing, but run this somewhere disposable if that matters.
- **The first LLM run is a pilot, not a result.** gpt-oss-20b's first 78 rows (`results/pilot/`) used whole-line edits, and 33 of their 50 failures were files broken by indentation. The prompt now asks for `{path, line, old, new}` edits, and those rows are left out of every report.

---

## Bundles

| repo | commit | tests at baseline | static edges (PyCG / Pyright) | runtime edges | licence |
|---|---|---|---|---|---|
| click | `00e592c` | 1,939 pass | 448 / 567 | 922 (167 from tests) | BSD-3-Clause |
| toolz | `568c2b8` | 180 pass, 1 pre-existing fail | 111 / 121 | 423 (299 from tests) | BSD-3-Clause |

Each `bundles/<repo>/` holds `repo.json` (pin), `graph.json` (nodes, both static
edge sets, runtime edges with their call lines), `trace.json` (the raw tracer output,
kept for provenance) and `tasks.json` (selected and validated tasks). The repos'
source is never committed. `fetch` clones it.

### Adding a repo

Needs TraceWeave-Core and its Docker image, on the execution host:

```bash
# 1. static: inventory, PyCG, Pyright over one shared node set
python3 <core>/traceweave/static/extract.py run --repos-from <list> --clone-dir <dir>
# 2. runtime: the repo's own test suite under the tracer
TW_PYTEST_ARGS=<tests> PYTHONPATH=<src_root> python3 <core>/traceweave/demo/tracer.py trace-package \
    --src-root <src_root> --package <package> --exclude "" \
    --workload <core>/traceweave/dypybench/pytest_workload.py --entry entry \
    --run-id <id> --out trace.json
# 3. here
python3 build_bundle.py <repo> --static ~/traceweave-data/static/<repo> --runtime trace.json
python3 tw.py fetch <repo> && python3 tw.py tasks <repo> --validate
```

---

## Layout

| file | what it does |
|---|---|
| `tw.py` | CLI: fetch, tasks, run, report, show, prompt |
| `graph.py` | bundle loading, the three caller sets, task selection |
| `context.py` | the slicer and the prompt, with the one place the arms differ |
| `models.py` | `oracle`, `groq:`, `claude:`, `replay:` |
| `sandbox.py` | pinned checkout, reset, edit application, the test-suite oracle |
| `build_bundle.py` | TraceWeave-Core outputs → `bundles/<repo>/graph.json` |
| `server.py`, `ui/` | `tw.py ui`: the live demo, the results pages and their JSON/SSE API (stdlib only, fonts self-hosted) |
| `live/tw_live.py` | pytest plugin for the live demo: streamed progress, and who calls one function (`sys.monitoring`) |
| `tests/test_harness.py` | prompt invariance across arms, task arms, edit safety, verdict, the sign test |
