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
    ])
    assert result == {"applied": 1, "rejected": 4}
    assert (tmp_path / "r" / "a.py").read_text() == "x = 1\ny = 3\n"


def test_verdict_needs_same_passes_and_no_new_failures():
    base = {"rc": 1, "passed": 180, "bad": ["t::known"]}
    assert sandbox.verdict({"rc": 1, "passed": 180, "bad": ["t::known"]}, base)
    assert not sandbox.verdict({"rc": 1, "passed": 179, "bad": ["t::known", "t::new"]}, base)
    assert not sandbox.verdict({"rc": 2, "passed": 0, "bad": []}, base)   # collection error
    assert not sandbox.verdict({"rc": 0, "passed": 170, "bad": []}, base)  # tests vanished
