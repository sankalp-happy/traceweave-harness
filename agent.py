"""Same-name renames: the edit a regex cannot do.

Rename one function whose name other functions share (`ParamType.fail`, but
not `Context.fail`). Every call that reaches it must change; every call that
reaches a namesake must not. The project's own tests judge, as before.

A task is kept only if all three hold, each checked by running the suite:
  - the right rename passes: its definition, plus every line the test run saw
    call it (truth.json);
  - renaming every whole-word occurrence of the name (the regex rename) fails;
  - renaming the definition alone fails.

The agent (an LLM) gets the same instructions under each condition. Only the
lines it is shown differ, i.e. how its context was retrieved:

  grep      every line in the package that contains the name (what an agent's
            search tool returns); the agent must work out which ones are ours
  static    the definition, plus the lines in callers PyCG or Pyright report
  runtime   the definition, plus the lines the test run saw call it

Two edits without a model bound the result: `regex` (rename every occurrence;
fails by construction) and `oracle` (the right rename; passes by construction).

  python3 tw.py agent-tasks click --validate
  python3 tw.py agent click --model groq:openai/gpt-oss-120b
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import bench
import sandbox
import truth as truth_mod
from graph import ENTRY, HERE, Bundle, word

CONDITIONS = ("grep", "static", "runtime")
WINDOW = 2
OUT = HERE / "results" / "agent"

PROMPT = """\
You are editing the Python repository `{repo}`.

Task: rename `{qualname}` (defined in {path}, line {line}) to `{new}`.
Other functions in this project are also named `{name}`:
{namesakes}
They keep their names. Change every place that calls or refers to `{qualname}`,
and nothing that calls one of the others, so the project's test suite still
passes.

You can see only the line-numbered excerpts below, and you may only edit lines
shown in them.

## Source excerpts
{excerpts}
## Output
Return the edits as JSON. Each edit changes one existing line, named by its
path and line number exactly as shown above: every occurrence of `old` on that
line is replaced by `new`. `old` must appear on that line exactly as shown.
Lines you do not list are left unchanged.
"""

EDITS_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["edits"],
    "properties": {"edits": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["path", "line", "old", "new"],
        "properties": {"path": {"type": "string"}, "line": {"type": "integer"},
                       "old": {"type": "string"}, "new": {"type": "string"}}}}},
}


def package_files(bundle: Bundle) -> list[str]:
    root = sandbox.root(bundle.repo)
    return sorted(str(p.relative_to(root)) for p in (root / bundle.repo["package"]).rglob("*.py"))


def name_lines(bundle: Bundle, name: str) -> list[tuple[str, int]]:
    """Every package line where `name` appears as a code token (not in strings or comments)."""
    root = sandbox.root(bundle.repo)
    out = []
    for path in package_files(bundle):
        out += sorted({(path, ln) for _, _, ln, nm, _ in bench.tokens(root / path) if nm == name})
    return out


def token_count(bundle: Bundle, path: str, line: int, name: str) -> int:
    return sum(1 for _, _, ln, nm, _ in bench.tokens(sandbox.root(bundle.repo) / path) if ln == line and nm == name)


def site_line(bundle: Bundle, path: str, line: int, name: str) -> int | None:
    """The physical line holding `name` in the logical line a call was recorded on."""
    for first, last, ln, nm, _ in bench.tokens(sandbox.root(bundle.repo) / path):
        if nm == name and first <= line <= last:
            return ln
    return None


def candidates(bundle: Bundle) -> tuple[list[dict], dict]:
    t = truth_mod.load(bundle)
    tests = bundle.repo["tests"].rstrip("/") + "/"
    by_name = defaultdict(list)
    for k, n in bundle.nodes.items():
        if n["kind"] in ("function", "method"):
            by_name[n["qualname"].rsplit(".", 1)[-1]].append(k)
    calls = defaultdict(set)          # callee -> {(path, line)} it was called from, inside the package
    from_tests = set()
    for caller, callee, c_path, c_line, n, via in t["edges"]:
        if caller == ENTRY:
            if c_path.startswith(tests):
                from_tests.add(callee)
        elif not via:
            calls[callee].add((c_path, c_line))
    out, attrition = [], defaultdict(int)
    for name, keys in sorted(by_name.items()):
        if len(keys) < 2 or bench.DUNDER.match(name) or len(name) < 4 or not name.isidentifier():
            continue
        for k in keys:
            n = bundle.nodes[k]
            why = ("no call from package code ran" if not calls.get(k)
                   else "the tests call it directly" if k in from_tests else None)
            sites = set()
            if not why:
                for path, line in calls[k]:
                    ln = site_line(bundle, path, line, name)
                    if ln is None:
                        why = "called on a line that does not name it (a callback)"
                        break
                    sites.add((path, ln))
            right = sorted(sites | {(n["path"], n["line"])})
            if not why and any(token_count(bundle, p, ln, name) != 1 for p, ln in right):
                why = "a line names it twice"
            if not why and set(name_lines(bundle, name)) <= set(right):
                why = "every occurrence is ours, so a regex rename is right"
            if why:
                attrition[why] += 1
                continue
            out.append({"id": f"{bundle.name}:{n['qualname']}", "target": k, "name": name, "new_name": f"{name}_v2",
                        "namesakes": sorted(x for x in keys if x != k), "right_lines": right})
    return out, dict(attrition)


def rename(bundle: Bundle, task: dict, lines) -> list[dict]:
    return [{"path": p, "line": ln, "old": task["name"], "new": task["new_name"]} for p, ln in lines]


def regex_edits(bundle: Bundle, task: dict) -> list[dict]:
    return rename(bundle, task, name_lines(bundle, task["name"]))


def validate(bundle: Bundle, tasks: list[dict]) -> list[dict]:
    from tw import attempt
    base = sandbox.baseline(bundle.repo)
    for t in tasks:
        right = attempt(bundle, rename(bundle, t, t["right_lines"]), base)["pass"]
        regex = attempt(bundle, regex_edits(bundle, t), base)["pass"] if right else None
        definition = [(bundle.nodes[t["target"]]["path"], bundle.nodes[t["target"]]["line"])]
        alone = attempt(bundle, rename(bundle, t, definition), base)["pass"] if right and regex is False else None
        t["validation"] = {"right_passes": right, "regex_fails": regex is False, "definition_only_fails": alone is False}
        t["valid"] = right and regex is False and alone is False
        print(f"  {t['id']:55s} right {'pass' if right else 'FAIL'}  regex {'-' if regex is None else 'pass' if regex else 'fail'}"
              f"  def-only {'-' if alone is None else 'pass' if alone else 'fail'}  -> {'kept' if t['valid'] else 'dropped'}", flush=True)
    return tasks


def tasks(bundle: Bundle) -> list[dict]:
    f = bundle.dir / "agent_tasks.json"
    if not f.exists():
        raise SystemExit(f"no {f}; run python3 tw.py agent-tasks {bundle.name} --validate")
    return [t for t in json.loads(f.read_text())["tasks"] if t.get("valid")]


# ---------------------------------------------------------------- the agent

def shown_lines(bundle: Bundle, task: dict, condition: str) -> list[tuple[str, int]]:
    n = bundle.nodes[task["target"]]
    defn = [(n["path"], n["line"])]
    if condition == "grep":
        return name_lines(bundle, task["name"])
    if condition == "runtime":
        return sorted({tuple(x) for x in task["right_lines"]})
    callers = {c for c, x in bundle.static if x == task["target"]}
    pat, root, out = word(task["name"]), sandbox.root(bundle.repo), set(defn)
    from context import own_lines
    for c in callers:
        src = (root / bundle.nodes[c]["path"]).read_text().splitlines()
        out |= {(bundle.nodes[c]["path"], ln) for ln in own_lines(bundle, c) if pat.search(src[ln - 1])}
    return sorted(out)


def build(bundle: Bundle, task: dict, condition: str) -> tuple[str, dict[str, set[int]]]:
    from context import render_excerpts
    root = sandbox.root(bundle.repo)
    files: dict[str, list[str]] = {}

    def source(path: str) -> list[str]:
        if path not in files:
            files[path] = (root / path).read_text().splitlines()
        return files[path]

    shown: dict[str, set[int]] = defaultdict(set)
    for path, ln in shown_lines(bundle, task, condition):
        shown[path] |= set(range(max(1, ln - WINDOW), min(len(source(path)), ln + WINDOW) + 1))
    n = bundle.nodes[task["target"]]
    namesakes = "\n".join(f"- `{bundle.nodes[k]['qualname']}` ({bundle.nodes[k]['path']}, line {bundle.nodes[k]['line']})"
                          for k in task["namesakes"])
    prompt = PROMPT.format(repo=bundle.name, qualname=n["qualname"], path=n["path"], line=n["line"],
                           new=task["new_name"], name=task["name"], namesakes=namesakes,
                           excerpts=render_excerpts(dict(shown), source))
    return prompt, dict(shown)


def run(bundle: Bundle, model: str, effort: str = "low") -> Path:
    from models import groq_json
    from tw import attempt
    base = sandbox.baseline(bundle.repo)
    out = OUT / f"{bundle.name}.{model.replace(':', '_').replace('/', '_')}.jsonl"
    OUT.mkdir(parents=True, exist_ok=True)
    done = {(r["task"], r["condition"]) for r in map(json.loads, out.read_text().splitlines())} if out.exists() else set()
    todo = [(t, c) for t in tasks(bundle) for c in (CONDITIONS if model.startswith("groq:") else ("-",))
            if (t["id"], c) not in done]
    with out.open("a") as fh:
        for k, (t, cond) in enumerate(todo, 1):
            t0 = time.monotonic()
            if model == "regex":
                edits, meta, prompt, shown = regex_edits(bundle, t), {}, "", {}
            elif model == "oracle":
                edits, meta, prompt, shown = rename(bundle, t, t["right_lines"]), {}, "", {}
            else:
                prompt, shown = build(bundle, t, cond)
                obj, meta = groq_json(model.removeprefix("groq:"), prompt, EDITS_SCHEMA, effort)
                edits = (obj or {}).get("edits") or []
            res = attempt(bundle, edits, base)
            right = {tuple(x) for x in t["right_lines"]}
            touched = {(e.get("path"), e.get("line")) for e in edits if isinstance(e, dict)}
            fh.write(json.dumps({
                "task": t["id"], "repo": bundle.name, "condition": cond, "model": model, "effort": effort,
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest() if prompt else None,
                "right_total": len(right), "right_shown": sum(1 for p, ln in right if ln in shown.get(p, ())),
                "right_edited": len(right & touched), "wrong_edited": len(touched - right),
                "edits": edits, "model_meta": {k: v for k, v in meta.items() if k != "raw"}, **res,
                "seconds": round(time.monotonic() - t0, 1)}) + "\n")
            fh.flush()
            print(f"[{k}/{len(todo)}] {t['id']:50s} {cond:8s} {'PASS' if res['pass'] else 'fail'}  "
                  f"right {len(right & touched)}/{len(right)}  wrong {len(touched - right)}", flush=True)
    return out
