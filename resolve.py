"""LLMs as call resolvers: given one function's code and the project functions
named in it, which does it really call? Scored by bench.py against execution.

One prompt per caller. The model sees the caller's own lines (numbered), every
candidate's definition (with decorators and its class's bases), and the class
hierarchy among the classes involved. It answers with candidate ids; the
schema lists the ids, so it cannot name anything else.

The free tier allows ~200K tokens a day per model, so the LLMs answer a fixed
sample (sample()): the callers with at least one hard item -- a name shared by
several functions, a bare reference, or a pair where static analysis is wrong --
drawn with a fixed seed, capped in size so one prompt fits a minute's budget.
Every resolver, static ones included, is scored on the same sample; the static
tools are also scored on everything.

  python3 tw.py resolve click --model groq:openai/gpt-oss-20b   # resumable
"""
from __future__ import annotations

import json
import random
import time
from collections import defaultdict
from pathlib import Path

import bench
import sandbox
from context import own_lines
from graph import HERE, Bundle

OUT = HERE / "results" / "resolve"
SAMPLE = {"click": 140, "toolz": 60}     # callers per repo in the LLM sample
SAMPLE_DEFAULT = 25                      # corpus repos: 20 x 25 calls x 3 models fits a week of free tier
MAX_TOKENS = 3500                        # one prompt must fit the 8K tokens/minute budget with its answer
SEED = 20261016

PROMPT = """\
You are reading code from the Python project `{repo}`.

## The function
{where}
```python
{code}
```

## Project functions named in it
Several may share a name; each id is one definition.
{candidates}
{hierarchy}
## Question
Which of these candidates does running the function above call? A candidate
counts when executing this function invokes it: a direct call, a method call on
any object, reading a @property, or creating an instance of a class (which runs
that class's __init__). A candidate that is only passed along or stored as a
value does not count here, because it is called later somewhere else. When a
name is shared, decide which definition each line actually reaches from the
types involved. Return the ids of the candidates that are called, or an empty
list.
"""


def hard(i: dict) -> bool:
    static = i["pycg"] or i["pyright"]
    return i["shared"] > 1 or i["style"] == "reference" or static != i["label"]


def decorated_def(src: list[str], line: int) -> str:
    """The def line, with the decorators written above it."""
    out, k = [src[line - 1].strip()], line - 2
    while k >= 0 and src[k].strip().startswith("@"):
        out.insert(0, src[k].strip())
        k -= 1
    return " ".join(out)


def build(bundle: Bundle, caller: str, its: list[dict], root: Path) -> tuple[str, dict[str, str]]:
    n = bundle.nodes[caller]
    src = (root / n["path"]).read_text().splitlines()
    lines, rows, prev = sorted(own_lines(bundle, caller)), [], None
    for ln in lines:
        if prev is not None and ln != prev + 1:
            rows.append("      ...")
        rows.append(f"{ln:>5}| {src[ln - 1]}")
        prev = ln
    ids, cands, classes = {}, [], set()
    if "." in n["qualname"] and n["kind"] == "method":
        classes.add(n["qualname"].split(".")[0])
    for k, it in enumerate(sorted(its, key=lambda i: (i["name"], i["callee"])), 1):
        c = bundle.nodes[it["callee"]]
        cid = f"C{k}"
        ids[cid] = it["callee"]
        csrc = (root / c["path"]).read_text().splitlines()
        owner = c["qualname"].rsplit(".", 1)[0] if c["kind"] == "method" else None
        if owner:
            classes.add(owner.split(".")[0])
        cands.append(f"- {cid}: `{c['qualname']}` ({c['path']}:{c['line']}"
                     f"{', a method of class ' + owner if owner else ''}): `{decorated_def(csrc, c['line'])}`")
    bases = {}
    for k, m in bundle.nodes.items():
        if m["kind"] == "module":
            bases.update(bench.class_bases(root / m["path"]))
    seen, todo, chain = set(), sorted(classes), []
    while todo:
        c = todo.pop(0)
        if c in seen or c not in bases:
            continue
        seen.add(c)
        chain.append(f"- class {c}({', '.join(b for b in bases[c] if b) or 'object'})")
        todo += [b for b in bases[c] if b in bases]
    hierarchy = ("\n## Classes involved\n" + "\n".join(chain) + "\n") if chain else ""
    prompt = PROMPT.format(repo=bundle.name, where=f"`{n['qualname']}` in {n['path']}",
                           code="\n".join(rows), candidates="\n".join(cands), hierarchy=hierarchy)
    return prompt, ids


def schema(ids: dict[str, str]) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["called"],
            "properties": {"called": {"type": "array", "items": {"type": "string", "enum": sorted(ids)}}}}


def by_caller(its: list[dict]) -> dict[str, list[dict]]:
    out = defaultdict(list)
    for i in its:
        out[i["caller"]].append(i)
    return out


def sample(bundle: Bundle, its: list[dict]) -> list[str]:
    f = OUT / f"{bundle.name}.sample.json"
    if f.exists():
        return json.loads(f.read_text())["callers"]
    root = sandbox.root(bundle.repo)
    groups = by_caller(its)
    pool = sorted(c for c, v in groups.items()
                  if any(hard(i) for i in v) and len(build(bundle, c, v, root)[0]) // 4 <= MAX_TOKENS)
    chosen = sorted(random.Random(SEED).sample(pool, min(SAMPLE.get(bundle.name, SAMPLE_DEFAULT), len(pool))))
    OUT.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"repo": bundle.name, "seed": SEED, "pool": len(pool), "callers": chosen,
                             "rule": "callers with >=1 hard item (shared name, bare reference, or static analysis wrong), "
                                     f"prompt <= {MAX_TOKENS} tokens, random sample with the seed above"}, indent=1))
    return chosen


def run(bundle: Bundle, model: str, effort: str = "low", limit: int | None = None) -> Path:
    from models import groq_json
    its = bench.items(bundle)
    groups, root = by_caller(its), sandbox.root(bundle.repo)
    out = OUT / f"{bundle.name}.{model.replace(':', '_').replace('/', '_')}.jsonl"
    done = {json.loads(l)["caller"] for l in out.read_text().splitlines()} if out.exists() else set()
    todo = [c for c in sample(bundle, its) if c not in done][:limit]
    with out.open("a") as fh:
        for k, caller in enumerate(todo, 1):
            prompt, ids = build(bundle, caller, groups[caller], root)
            t0 = time.monotonic()
            obj, meta = groq_json(model.removeprefix("groq:"), prompt, schema(ids), effort)
            called = [ids[c] for c in (obj or {}).get("called", []) if c in ids]
            fh.write(json.dumps({"caller": caller, "model": model, "effort": effort, "called": called,
                                 "ids": ids, "seconds": round(time.monotonic() - t0, 2),
                                 "usage": meta.get("usage"), "error": meta.get("error"),
                                 "reasoning": meta.get("reasoning"), "raw": meta.get("raw")}) + "\n")
            fh.flush()
            print(f"[{k}/{len(todo)}] {bundle.nodes[caller]['qualname']:50s} {len(called)}/{len(ids)} called"
                  f"{'  ERROR ' + str(meta.get('error'))[:60] if meta.get('error') else ''}", flush=True)
    return out


def answers(bundle: Bundle) -> dict[str, dict[str, set[str]]]:
    """model -> caller -> the callees it says are called, from every results file."""
    out = defaultdict(dict)
    for f in sorted(OUT.glob(f"{bundle.name}.*.jsonl")):
        for line in f.read_text().splitlines():
            r = json.loads(line)
            if not r.get("error"):
                out[r["model"]][r["caller"]] = set(r["called"])
    return out
