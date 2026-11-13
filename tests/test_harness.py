"""Self-checks. `python3 -m pytest tests` (needs a fetched repo for the prompt checks).

The prompt check is the one that matters: if the two arms' prompts ever differ
outside the caller list and the excerpts, the experiment no longer isolates
the effect of runtime edges, and every number it produces is uninterpretable.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import context  # noqa: E402
import sandbox  # noqa: E402
from graph import HERE, Bundle  # noqa: E402
from tw import sign_test  # noqa: E402

FETCHED = [p.parent.name for p in (HERE / "bundles").glob("*/tasks.json")
           if (sandbox.WORK / p.parent.name / ".git").exists()]


def strip_varying(prompt: str) -> str:
    head, _, rest = prompt.partition("## Callers of")
    _, _, tail = rest.partition("## Output")
    return head + tail


@pytest.mark.parametrize("repo", FETCHED)
def test_arms_differ_only_in_callers_and_excerpts(repo):
    bundle = Bundle(repo)
    root = sandbox.root(bundle.repo)
    for task in bundle.tasks():
        s = context.build(bundle, task, "static", root)
        f = context.build(bundle, task, "fused", root)
        assert strip_varying(s.prompt) == strip_varying(f.prompt), task["id"]
        if task["arm"] == "placebo":
            assert s.prompt == f.prompt, f"placebo arms must be identical: {task['id']}"
        if not f.truncated:
            for path, lines in s.shown.items():
                assert lines <= f.shown.get(path, set()), task["id"]
            assert set(s.callers) <= set(f.callers), task["id"]


@pytest.mark.parametrize("repo", FETCHED)
def test_treatment_tasks_really_hide_a_caller_from_the_static_arm(repo):
    bundle = Bundle(repo)
    for task in bundle.tasks():
        hidden = set(task["dynamic_only_callers"])
        assert (task["arm"] == "treatment") == bool(hidden)
        assert not hidden & bundle.callers(task["target"], "static"), task["id"]
        assert hidden <= bundle.callers(task["target"], "fused"), task["id"]


def test_sign_test():
    assert sign_test(0, 0) == 1.0
    assert sign_test(2, 0) == 0.5
    assert sign_test(10, 0) == pytest.approx(2 / 1024)
    assert sign_test(5, 5) == 1.0


def test_apply_rejects_malformed_edits(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "WORK", tmp_path)
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "a.py").write_text("x = 1\ny = 2\n")
    repo = {"name": "r"}
    result = sandbox.apply(repo, [
        {"path": "a.py", "line": 2, "text": "y = 3"},
        {"path": "a.py", "line": 9, "text": "z"},            # no such line
        {"path": "../escape.py", "line": 1, "text": "z"},    # outside the repo
        {"path": "a.py", "line": 1, "text": "x = 1\nimport os"},  # smuggles a second line
        {"path": "a.py", "line": 1},                         # no text at all
        "a.py:1",                                            # not an edit object
    ])
    assert result == {"applied": 1, "rejected": 5}
    assert (tmp_path / "r" / "a.py").read_text() == "x = 1\ny = 3\n"
    renamed = sandbox.apply(repo, [{"path": "a.py", "line": 2, "old": "y", "new": "why"},   # LLM shape
                                   {"path": "a.py", "line": 1, "old": "zz", "new": "q"}])    # old not on the line
    assert renamed == {"applied": 1, "rejected": 1}
    assert (tmp_path / "r" / "a.py").read_text() == "x = 1\nwhy = 3\n"
    broken = sandbox.apply(repo, [{"path": "a.py", "line": 2, "text": "  y = 4"}])
    assert broken["syntax_error"].startswith("IndentationError") and "line 2" in broken["syntax_error"]


def test_verdict_needs_same_passes_and_no_new_failures():
    base = {"rc": 1, "passed": 180, "bad": ["t::known"]}
    assert sandbox.verdict({"rc": 1, "passed": 180, "bad": ["t::known"]}, base)
    assert not sandbox.verdict({"rc": 1, "passed": 179, "bad": ["t::known", "t::new"]}, base)
    assert not sandbox.verdict({"rc": 2, "passed": 0, "bad": []}, base)   # collection error
    assert not sandbox.verdict({"rc": 0, "passed": 170, "bad": []}, base)  # tests vanished


def test_report_pooled_rows_are_the_sum_of_their_repos():
    import server
    table = server.report()["table"]
    for group in ("treatment", "placebo"):
        rows = [r for r in table if r["group"] == group]
        pooled = [r for r in rows if r["repo"] == "pooled"]
        if not pooled:
            continue
        for k in ("tasks", "static", "fused", "fused_only", "static_only"):
            assert pooled[0][k] == sum(r[k] for r in rows if r["repo"] != "pooled"), (group, k)


@pytest.mark.skipif("toolz" not in FETCHED, reason="needs python3 tw.py fetch toolz")
def test_live_trace_finds_the_recorded_hidden_caller():
    """The live demo's tracer, end to end: the real suite under sys.monitoring
    must find the same hidden caller the recorded trace holds."""
    import server
    events = list(server.live_events("trace", {"id": "toolz:thread_first.evalform_front"}))
    done = next(e for e in events if e["type"] == "done")
    assert done["hidden_found"] == ["toolz/functoolz.py::thread_first"] and not done["hidden_missed"]
    assert any(e["type"] == "progress" for e in events)


def test_benchmark_labels_come_from_the_trace_and_the_combiner_is_out_of_fold():
    """Items are labelled by recorded calls only, and the learned combiner's
    folds never put one function's items on both sides."""
    import bench
    import ml
    from graph import ENTRY
    import truth
    b = Bundle("toolz")
    real = {(e[0], e[1]) for e in truth.load(b)["edges"] if e[0] != ENTRY}
    its = bench.items(b)
    assert its and all(i["label"] == ((i["caller"], i["callee"]) in real) for i in its)
    rows = [{"group": g, "x": [1.0, x], "y": y} for g, x, y in
            [("a", 0.0, 0.0), ("a", 1.0, 1.0), ("b", 0.0, 0.0), ("b", 1.0, 1.0), ("c", 1.0, 1.0), ("c", 0.0, 0.0)]]
    w = ml.fit(rows, epochs=500)
    assert ml.predict(w, [1.0, 1.0]) > 0.5 > ml.predict(w, [1.0, 0.0])
