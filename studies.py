"""What the pages show, aggregated from bundles/ and results/; nothing here is
computed that a `tw.py` command does not also print.

  truth_summary   the ground truth: what the test run recorded, and how much
                  of it the static call graphs hold
  study1          who can find the calls: static analysers, three LLMs and the
                  learned combiner, on the same items (bench.py, resolve.py, ml.py)
  study1_fn       one function: its code, every candidate and every answer
  study2          can an AI agent make a same-name rename (agent.py)
  study2_task     one task: the lines that name it, which are right, every run
"""
from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache

import agent
import bench
import resolve
import sandbox
import truth as truth_mod
from context import own_lines
from graph import ENTRY, HERE, Bundle

REPOS = ("click", "toolz")
LEARNED = HERE / "results" / "resolve" / "learned.json"
LABEL = {"groq:openai/gpt-oss-20b": "gpt-oss-20b", "groq:openai/gpt-oss-120b": "gpt-oss-120b",
         "groq:qwen/qwen3.8-27b": "qwen3.8-27b", "regex": "regex", "oracle": "exact rename"}


@lru_cache(maxsize=None)
def items(repo: str) -> list[dict]:
    return bench.items(Bundle(repo))


def learned() -> dict:
    return json.loads(LEARNED.read_text()) if LEARNED.exists() else {}


def truth_summary() -> list[dict]:
    out = []
    for repo in REPOS:
        b = Bundle(repo)
        try:
            t = truth_mod.load(b)
        except SystemExit:
            continue
        calls = [e for e in t["edges"] if e[0] != ENTRY]
        pairs = {(e[0], e[1]) for e in calls if e[0] != e[1] and b.nodes[e[1]]["kind"] in ("function", "method")}
        union = b.static
        found = lambda s: sum(1 for p in pairs if p in s)
        callees = {x for _, x in pairs}
        out.append({
            "repo": repo, "about": b.repo.get("about", ""), "tests": t["suite"]["passed"], "seconds": t["suite"]["seconds"],
            "calls": sum(e[4] for e in calls), "sites": len(calls), "pairs": len(pairs),
            "lines": sum(len(v) for v in t["lines"].values()), "generated": t["generated_utc"],
            "static": {"PyCG": found(b.static_by_tool.get("pycg", set())), "Pyright": found(b.static_by_tool.get("pyright", set())),
                       "PyCG ∪ Pyright": found(union)},
            "no_static_caller": sum(1 for x in callees if not any((c, x) in union for c, _ in pairs if _ == x)),
            "called_functions": len(callees),
        })
    return out


def study1() -> dict:
    ln = learned()
    prob = {(p["repo"], p["caller"], p["callee"]): p["p"] for p in ln.get("predictions", [])}
    llm = {repo: resolve.answers(Bundle(repo)) for repo in REPOS}
    resolvers = ["name match", "PyCG", "Pyright", "PyCG ∪ Pyright", "gpt-oss-20b", "gpt-oss-120b", "qwen3.8-27b",
                 "majority of the 3 LLMs", "learned combiner"]
    models = {v: k for k, v in LABEL.items() if k.startswith("groq:")}

    def says(repo: str, i: dict, r: str) -> bool | None:
        if r in bench.BASELINES:
            return bench.BASELINES[r](i)
        if r in models:
            got = llm[repo].get(models[r], {}).get(i["caller"])
            return None if got is None else i["callee"] in got
        if r == "majority of the 3 LLMs":
            v = [says(repo, i, m) for m in models]
            return None if None in v else sum(v) >= 2
        p = prob.get((repo, i["caller"], i["callee"]))
        return None if p is None else p >= 0.5

    sample = [(repo, i) for repo in REPOS for i in items(repo) if (repo, i["caller"], i["callee"]) in prob]
    every = [(repo, i) for repo in REPOS for i in items(repo)]
    cats = ("unique name", "shared name", "call", "reference", "constructor")

    def board(pool, rs):
        return {r: bench.score([i for _, i in pool], lambda i, r=r, pool=pool: bool(says(next(rp for rp, j in pool if j is i), i, r)))
                for r in rs}

    # Index once: scoring by identity over a list is slow.
    def score(pool, r):
        tp = fp = fn = 0
        for repo, i in pool:
            s = says(repo, i, r)
            tp += bool(s) and i["label"]
            fp += bool(s) and not i["label"]
            fn += (not s) and i["label"]
        p_, r_ = (tp / (tp + fp) if tp + fp else 0.0), (tp / (tp + fn) if tp + fn else 0.0)
        return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p_, 3), "recall": round(r_, 3),
                "f1": round(2 * p_ * r_ / (p_ + r_), 3) if p_ + r_ else 0.0}

    functions = defaultdict(list)
    for repo, i in sample:
        functions[(repo, i["caller"])].append(i)
    fn_rows = []
    for (repo, caller), its in sorted(functions.items()):
        b = Bundle(repo)
        n = b.nodes[caller]
        fn_rows.append({"repo": repo, "caller": caller, "qualname": n["qualname"], "items": len(its),
                        "real": sum(i["label"] for i in its), "shared": sum(i["shared"] > 1 for i in its),
                        "static_missed": sum(1 for i in its if i["label"] and not (i["pycg"] or i["pyright"])),
                        "length": n["end"] - n["line"] + 1,
                        "right": {r: sum(1 for i in its if bool(says(repo, i, r)) == i["label"]) for r in resolvers[1:]}})
    # The "try it live" function: static analysis misses a real call that shares its name with
    # another function, every AI model and the combiner get it right, and it is short enough to read.
    perfect = lambda f: all(f["right"][r] == f["items"] for r in ("gpt-oss-120b", "learned combiner"))
    pool = [f for f in fn_rows if f["static_missed"] and f["shared"] and perfect(f) and 3 <= f["items"] <= 8 and f["length"] <= 30]
    featured = min(pool, key=lambda f: (-f["static_missed"], f["length"])) if pool else (fn_rows[0] if fn_rows else None)
    return {
        "sample": {"items": len(sample), "functions": len(functions), "real": sum(i["label"] for _, i in sample)},
        "all": {"items": len(every), "real": sum(i["label"] for _, i in every),
                "unnamed": sum(len(bench.unnamed(Bundle(r), items(r))) for r in REPOS)},
        "resolvers": resolvers,
        "leaderboard": {r: score(sample, r) for r in resolvers},
        "by_repo": {repo: {"items": sum(1 for rp, _ in sample if rp == repo),
                           "scores": {r: score([(rp, i) for rp, i in sample if rp == repo], r) for r in resolvers}}
                    for repo in REPOS},
        "static_on_all": {r: score(every, r) for r in ("name match", "PyCG", "Pyright", "PyCG ∪ Pyright")},
        "categories": {c: {"items": sum(1 for _, i in sample if c in bench.categories(i)),
                           "real": sum(i["label"] for _, i in sample if c in bench.categories(i)),
                           "scores": {r: score([(rp, i) for rp, i in sample if c in bench.categories(i)], r) for r in resolvers}}
                       for c in cats},
        "weights": ln.get("weights", {}), "folds": ln.get("folds"),
        "functions": fn_rows, "featured": featured and {"repo": featured["repo"], "caller": featured["caller"]},
    }


def study1_fn(repo: str, caller: str) -> dict:
    b = Bundle(repo)
    if caller not in b.nodes:
        raise LookupError(f"no function {caller} in {repo}")
    root = sandbox.root(b.repo)
    its = [i for i in items(repo) if i["caller"] == caller]
    n = b.nodes[caller]
    src = (root / n["path"]).read_text().splitlines()
    lines = sorted(own_lines(b, caller))
    llm = resolve.answers(b)
    prob = {(p["caller"], p["callee"]): p["p"] for p in learned().get("predictions", []) if p["repo"] == repo}
    prompt = resolve.build(b, caller, its, root)[0] if its else ""
    return {
        "repo": repo, "caller": caller, "qualname": n["qualname"], "path": n["path"],
        "code": [{"n": ln, "text": src[ln - 1]} for ln in lines],
        "candidates": [{"callee": i["callee"], "qualname": b.nodes[i["callee"]]["qualname"], "name": i["name"],
                        "lines": i["lines"], "style": i["style"], "shared": i["shared"], "real": i["label"],
                        "pycg": i["pycg"], "pyright": i["pyright"], "learned": prob.get((caller, i["callee"])),
                        "llm": {LABEL[m]: (i["callee"] in got[caller]) if caller in got else None for m, got in llm.items()}}
                       for i in its],
        "prompt": prompt,
    }


def study2() -> dict:
    rows = []
    for f in sorted((HERE / "results" / "agent").glob("*.jsonl")):
        rows += [json.loads(l) for l in f.read_text().splitlines()]
    tasks_ = []
    for repo in REPOS:
        b = Bundle(repo)
        try:
            for t in agent.tasks(b):
                n = b.nodes[t["target"]]
                tasks_.append({"id": t["id"], "repo": repo, "qualname": n["qualname"], "name": t["name"],
                               "new_name": t["new_name"], "right": len(t["right_lines"]),
                               "named": len(agent.name_lines(b, t["name"])),
                               "namesakes": [b.nodes[k]["qualname"] for k in t["namesakes"]]})
        except SystemExit:
            continue
    by = defaultdict(dict)
    for r in rows:
        by[(LABEL.get(r["model"], r["model"]), r["condition"])][r["task"]] = {
            "pass": r["pass"], "right_edited": r["right_edited"], "wrong_edited": r["wrong_edited"]}
    cells = [{"editor": e, "condition": c, "runs": len(v), "passed": sum(x["pass"] for x in v.values()), "tasks": v}
             for (e, c), v in sorted(by.items())]
    attrition = {}
    for repo in REPOS:
        f = Bundle(repo).dir / "agent_tasks.json"
        if f.exists():
            for k, v in json.loads(f.read_text()).get("attrition", {}).items():
                attrition[k] = attrition.get(k, 0) + v
    return {"tasks": tasks_, "cells": cells, "attrition": attrition, "conditions": list(agent.CONDITIONS)}


def study2_task(task_id: str) -> dict:
    repo = task_id.split(":", 1)[0]
    b = Bundle(repo)
    t = next((x for x in agent.tasks(b) if x["id"] == task_id), None)
    if t is None:
        raise LookupError(f"no agent task {task_id}")
    root = sandbox.root(b.repo)
    right = {tuple(x) for x in t["right_lines"]}
    static = set(agent.shown_lines(b, t, "static"))
    named = []
    for path, ln in agent.name_lines(b, t["name"]):
        owner = b.node_at(path, "", ln)
        named.append({"path": path, "n": ln, "text": (root / path).read_text().splitlines()[ln - 1].strip(),
                      "in": b.nodes[owner]["qualname"] if owner in b.nodes else "", "right": (path, ln) in right,
                      "static": (path, ln) in static})
    runs = []
    for f in sorted((HERE / "results" / "agent").glob(f"{repo}.*.jsonl")):
        for r in map(json.loads, f.read_text().splitlines()):
            if r["task"] == task_id:
                runs.append({"editor": LABEL.get(r["model"], r["model"]), "condition": r["condition"], "pass": r["pass"],
                             "right_edited": r["right_edited"], "wrong_edited": r["wrong_edited"],
                             "edits": [(e.get("path"), e.get("line")) for e in r["edits"] if isinstance(e, dict)],
                             "passed": r["tests"]["passed"], "failed": r["tests"]["failed"] + r["tests"]["errors"]})
    n = b.nodes[t["target"]]
    return {"id": task_id, "repo": repo, "qualname": n["qualname"], "path": n["path"], "line": n["line"],
            "name": t["name"], "new_name": t["new_name"], "namesakes": [b.nodes[k]["qualname"] for k in t["namesakes"]],
            "named": named, "right": len(right), "runs": runs, "baseline": sandbox.baseline(b.repo)["passed"]}
