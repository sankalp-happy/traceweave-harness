# TraceWeave harness

**Does giving an LLM runtime call-graph context change whether its code edits work?**

The harness runs one controlled experiment. The same model, the same prompt and
the same token budget are used on two arms, and the only thing that changes
between them is whether the model is told about callers that **only runtime
tracing can see**. The judge is the project's own test suite, not an LLM.

It is the downstream half of TraceWeave-Core, the research repo (not yet published).
Core measures how many runtime call edges static analysis misses. This repo asks
whether those misses matter when an AI edits code. Everything heavy (PyCG,
Pyright, Docker, tracing) happened once in Core, and the results are bundled
here. Running the experiment needs Python 3.11+, git and pytest, and nothing else.

---

## The experiment

| | |
|---|---|
| **Task** | Rename one function or method repo-wide. It has one unambiguous right answer and a free oracle. |
| **Static arm** | The model sees the target's definition plus every caller that **PyCG ∪ Pyright** report, as line-numbered excerpts. The static arm gets the union of both tools, the strongest static graph available. |
| **Fused arm** | Identical, plus the callers observed while the repo's own test suite ran under `sys.setprofile`. |
| **Held equal** | Prompt template, slicer, excerpt window, token budget, model, effort. `tests/test_harness.py` checks on every task that the two prompts differ only in the caller list and the excerpts those callers pull in. |
| **Slicer** | The retrieval unit is a caller *function*, as in code-graph RAG. For each caller the model sees ±2 lines around every line of that function's own body that names the target, plus, for a runtime-only edge, the line the tracer saw make the call. |
| **Oracle** | Apply the edits, run the full suite. A task passes only if the same number of tests pass as on the untouched checkout and no new test fails. |
| **Models** | `oracle` (the ceiling: a perfect editor limited to what the context shows) and `claude:<model-id>`. Every response is recorded, so `replay:` re-scores a run offline. |

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
python3 tw.py run click --model claude:claude-opus-5-5 --effort medium
python3 tw.py report results/click.claude_claude-opus-5-5.jsonl
```

Runs append to `results/<repo>.<model>.jsonl`, one row per task × arm, and resume
where they stopped. Each row records the prompt's SHA-256, the callers shown,
how many of the symbol's reference lines the context covered, every edit, the
full test outcome, and the served-by model. Claude requests opt into server-side
refusal fallback (`fallbacks: "default"`). If a fallback model ever answers, it
shows in `model_meta.served_by` and can be excluded.

`python3 tw.py prompt <task> static|fused` prints the exact prompt an arm receives.

### On the expo screen

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
- **Model-generated code is executed.** The suite runs on edited source. Edits are whole-line replacements, confined to the checkout and checked before writing, but run this somewhere disposable if that matters.

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
| `models.py` | `oracle`, `claude:`, `replay:` |
| `sandbox.py` | pinned checkout, reset, edit application, the test-suite oracle |
| `build_bundle.py` | TraceWeave-Core outputs → `bundles/<repo>/graph.json` |
| `tests/test_harness.py` | prompt invariance across arms, task arms, edit safety, verdict, the sign test |
