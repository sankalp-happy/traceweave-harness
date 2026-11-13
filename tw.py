#!/usr/bin/env python3
"""TraceWeave harness: does runtime call-graph context change how well an LLM edits code?

    python3 tw.py fetch click                      pinned checkout + baseline test run
    python3 tw.py tasks click --validate           select rename tasks, prove each is gradeable
    python3 tw.py run click --model oracle         both arms, every task, scored by the suite
    python3 tw.py run click --model claude:claude-opus-5-5
    python3 tw.py run click --model groq:openai/gpt-oss-20b   GROQ_API_KEY from env or .env
    python3 tw.py report results/*.jsonl           the results table
    python3 tw.py show click:Context._make_sub_context [--results FILE]   one task, both arms
    python3 tw.py prompt click:<qualname> static   the exact prompt an arm receives
    python3 tw.py ui                               the results page on http://127.0.0.1:8765/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import context
import models
import sandbox
from graph import CONDITIONS, Bundle, candidates, word

HERE = Path(__file__).resolve().parent


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def find_task(task_id: str) -> tuple[Bundle, dict]:
    bundle = Bundle(task_id.split(":", 1)[0])
    for t in json.loads((bundle.dir / "tasks.json").read_text())["tasks"]:
        if t["id"] == task_id:
            return bundle, t
    raise SystemExit(f"no task {task_id!r}; see bundles/{bundle.name}/tasks.json")


def attempt(bundle: Bundle, edits: list[dict], base: dict, on_event=None) -> dict:
    with sandbox.lock(bundle.repo):
        sandbox.reset(bundle.repo)
        applied = sandbox.apply(bundle.repo, edits)
        tests = sandbox.run_tests(bundle.repo, on_event)
        sandbox.reset(bundle.repo)
    return {"apply": applied, "tests": tests, "pass": sandbox.verdict(tests, base)}


def rename_lines(root: Path, task: dict, lines) -> list[dict]:
    pat, edits = word(task["name"]), []
    for path, ln in lines:
        text = (root / path).read_text().splitlines()[ln - 1]
        edits.append({"path": path, "line": ln, "text": pat.sub(task["new_name"], text)})
    return edits


# ---------------------------------------------------------------- commands

def cmd_fetch(args) -> int:
    bundle = Bundle(args.repo)
    root = sandbox.fetch(bundle.repo)
    base = sandbox.baseline(bundle.repo, refresh=True)
    print(f"{bundle.name} @ {bundle.repo['sha'][:12]} in {root}")
    print(f"baseline: {base['passed']} passed, {base['failed']} failed, {base['errors']} errors "
          f"in {base['seconds']}s")
    return 0


def cmd_tasks(args) -> int:
    """Task selection. Validation proves each task is gradeable, in BOTH directions:
    the complete rename (every line naming the symbol) must pass, and renaming
    only the definition must fail. A task failing either check cannot tell a
    right answer from a wrong one, so it is dropped -- before any model runs,
    and without looking at which arm sees what."""
    bundle = Bundle(args.repo)
    root = sandbox.fetch(bundle.repo)
    tasks, attrition = candidates(bundle, root)
    # Validation depends only on the checkout and the symbol's name, never on the
    # graph, so results survive a bundle rebuild and are reused rather than re-run.
    old = bundle.dir / "tasks.json"
    cached = {t["id"]: t for t in json.loads(old.read_text())["tasks"]
              if "validation" in t} if old.exists() else {}
    if args.validate:
        base = sandbox.baseline(bundle.repo)
        for i, t in enumerate(tasks, 1):
            if t["id"] in cached and cached[t["id"]]["new_name"] == t["new_name"]:
                t["validation"], t["valid"] = cached[t["id"]]["validation"], cached[t["id"]]["valid"]
                continue
            target = bundle.nodes[t["target"]]
            full = attempt(bundle, rename_lines(root, t, t["reference_lines"]), base)
            only_def = attempt(bundle, rename_lines(root, t, [(target["path"], target["line"])]), base)
            t["valid"] = full["pass"] and not only_def["pass"]
            t["validation"] = {"complete_rename_passes": full["pass"],
                               "definition_only_fails": not only_def["pass"]}
            print(f"[{i}/{len(tasks)}] {t['id']:60s} {t['arm']:9s} "
                  f"{'valid' if t['valid'] else 'dropped'}", flush=True)
    treatment = [t for t in tasks if t["arm"] == "treatment"]
    attrition["dropped by validation"] = sum(not t.get("valid", True) for t in treatment)
    payload = {"repo": bundle.name, "sha": bundle.repo["sha"], "generated_utc": now(),
               "validated": args.validate, "attrition": attrition, "tasks": tasks}
    (bundle.dir / "tasks.json").write_text(json.dumps(payload, indent=1) + "\n")
    kept = [t for t in tasks if t.get("valid", True)]
    for arm in ("treatment", "placebo"):
        print(f"{arm:9s}: {sum(t['arm'] == arm for t in kept)} tasks")
    return 0


def cmd_run(args) -> int:
    bundle = Bundle(args.repo)
    root = sandbox.fetch(bundle.repo)
    base = sandbox.baseline(bundle.repo)
    model = models.load(args.model, args.effort)
    out = Path(args.out or HERE / "results" / f"{bundle.name}.{args.model.replace(':', '_').replace('/', '_')}.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        done = {(r["task"], r["condition"]) for r in map(json.loads, out.read_text().splitlines())}
    tasks = [t for t in bundle.tasks() if args.arm in ("all", t["arm"])]
    if args.only:
        tasks = [t for t in tasks if t["id"] in args.only]
    tasks = tasks[: args.limit] if args.limit else tasks
    with out.open("a") as f:
        for i, task in enumerate(tasks, 1):
            for condition in CONDITIONS:
                if (task["id"], condition) in done:
                    continue
                ctx = context.build(bundle, task, condition, root, args.budget)
                edits, meta = model(task, ctx, root)
                res = attempt(bundle, edits, base)
                refs = task["reference_lines"]
                row = {
                    "task": task["id"], "repo": bundle.name, "arm": task["arm"],
                    "condition": condition, "model": args.model, "effort": args.effort,
                    "budget_tokens": args.budget, "ts": now(),
                    "prompt_sha256": hashlib.sha256(ctx.prompt.encode()).hexdigest(),
                    "callers_shown": len(ctx.callers),
                    "dynamic_only_shown": len(set(ctx.callers) & set(task["dynamic_only_callers"])),
                    "truncated": ctx.truncated,
                    "refs_total": len(refs),
                    "refs_shown": sum(ctx.shows(p, ln) for p, ln in refs),
                    "edits": edits, "model_meta": meta, **res,
                }
                f.write(json.dumps(row) + "\n")
                f.flush()
                print(f"[{i}/{len(tasks)}] {task['id']:55s} {condition:6s} "
                      f"{'PASS' if res['pass'] else 'fail'}  refs {row['refs_shown']}/{row['refs_total']}",
                      flush=True)
    print(f"-> {out}")
    return 0


def sign_test(b: int, c: int) -> float:
    """Exact two-sided McNemar (binomial on discordant pairs)."""
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n)


def cmd_report(args) -> int:
    rows = [json.loads(l) for f in args.files for l in Path(f).read_text().splitlines()]
    cells, pairs = defaultdict(list), defaultdict(dict)
    for r in rows:
        cells[(r["model"], r["repo"], r["arm"], r["condition"])].append(r)
        pairs[(r["model"], r["repo"], r["arm"])].setdefault(r["task"], {})[r["condition"]] = r["pass"]

    print(f"{'model':28s} {'repo':6s} {'arm':9s} {'cond':6s} {'n':>4s} {'pass':>5s} {'rate':>6s} {'ref cover':>9s}")
    for key in sorted(cells):
        rs = cells[key]
        p = sum(r["pass"] for r in rs)
        cover = sum(r["refs_shown"] / r["refs_total"] for r in rs if r["refs_total"]) / len(rs)
        print(f"{key[0]:28s} {key[1]:6s} {key[2]:9s} {key[3]:6s} {len(rs):4d} {p:5d} {p / len(rs):6.1%} {cover:9.1%}")

    print("\npaired by task (only tasks run under both arms):")
    print(f"{'model':28s} {'repo':6s} {'arm':9s} {'both':>5s} {'fused only':>10s} {'static only':>11s} {'neither':>7s} {'p (exact)':>9s}")
    for key in sorted(pairs):
        both = [v for v in pairs[key].values() if len(v) == 2]
        a = sum(v["static"] and v["fused"] for v in both)
        b = sum(v["fused"] and not v["static"] for v in both)
        c = sum(v["static"] and not v["fused"] for v in both)
        d = len(both) - a - b - c
        print(f"{key[0]:28s} {key[1]:6s} {key[2]:9s} {a:5d} {b:10d} {c:11d} {d:7d} {sign_test(b, c):9.3g}")
    return 0


def cmd_show(args) -> int:
    """One task, both arms, side by side: the view to put on the screen."""
    bundle, task = find_task(args.task)
    root = sandbox.fetch(bundle.repo)
    target = bundle.nodes[task["target"]]
    print(f"\n  {task['id']}   ({task['arm']})")
    print(f"  rename {target['qualname']} -> {task['new_name']}   {target['path']}:{target['line']}")
    print(f"  callers: {task['static_callers']} static, {task['runtime_callers']} observed at runtime, "
          f"{len(task['dynamic_only_callers'])} visible ONLY at runtime\n")
    for c in task["dynamic_only_callers"]:
        site = bundle.runtime_site.get((c, task["target"]))
        line = (root / site[0]).read_text().splitlines()[site[1] - 1].strip() if site else ""
        where = f"{site[0]}:{site[1]}" if site else bundle.nodes[c]["path"]
        print(f"    runtime-only  {bundle.nodes[c]['qualname']}\n                  {where}  {line}")

    recorded = {}
    if args.results:
        for r in map(json.loads, Path(args.results).read_text().splitlines()):
            if r["task"] == task["id"]:
                recorded[r["condition"]] = r
    refs = task["reference_lines"]
    print()
    for condition in CONDITIONS:
        ctx = context.build(bundle, task, condition, root, args.budget)
        unseen = [(p, ln) for p, ln in refs if not ctx.shows(p, ln)]
        print(f"  [{condition.upper()}]  {len(ctx.callers)} callers in context, "
              f"sees {len(refs) - len(unseen)}/{len(refs)} lines that name the symbol")
        for p, ln in unseen:
            print(f"      cannot see  {p}:{ln}  {(root / p).read_text().splitlines()[ln - 1].strip()}")
        r = recorded.get(condition)
        if r is None and args.live:
            edits, _ = models.load(args.live)(task, ctx, root)
            r = attempt(bundle, edits, sandbox.baseline(bundle.repo)) | {"edits": edits, "model": args.live}
        if r:
            t = r["tests"]
            print(f"      {r['model']}: {len(r['edits'])} edits -> "
                  f"{'PASS' if r['pass'] else 'FAIL'}  ({t['passed']} passed, {t['failed']} failed, "
                  f"{t['errors']} errors)")
            for name in t["bad"][:3]:
                print(f"        {name}")
        print()
    return 0


def cmd_prompt(args) -> int:
    bundle, task = find_task(args.task)
    print(context.build(bundle, task, args.condition, sandbox.fetch(bundle.repo), args.budget).prompt)
    return 0


def cmd_truth(args) -> int:
    import truth
    bundle = Bundle(args.repo)
    t = truth.build(bundle)
    (bundle.dir / "truth.json").write_text(json.dumps(t, separators=(",", ":")) + "\n")
    calls = [e for e in t["edges"] if e[0] != "<entry>"]
    print(f"{bundle.name}: {len(calls)} in-package call sites, {len({(e[0], e[1]) for e in calls})} caller->callee pairs, "
          f"{sum(len(v) for v in t['lines'].values())} package lines ran; suite {t['suite']['passed']} passed "
          f"in {t['suite']['seconds']} s -> bundles/{bundle.name}/truth.json")
    return 0


def cmd_resolve(args) -> int:
    import resolve
    out = resolve.run(Bundle(args.repo), args.model, args.effort, args.limit)
    print(f"-> {out}")
    return 0


def cmd_bench(args) -> int:
    import bench, resolve
    for name in args.repos:
        b = Bundle(name)
        its = bench.items(b)
        llm = resolve.answers(b)
        sample = set(resolve.sample(b, its))
        sub = [i for i in its if i["caller"] in sample]
        print(f"\n{name}: {len(its)} items, {sum(i['label'] for i in its)} real calls; "
              f"{len(bench.unnamed(b, its))} real calls whose target is never named")
        print(f"  {'resolver':28s} {'on':>8s} {'prec':>6s} {'recall':>6s} {'F1':>6s}   shared-name recall")
        rows = [(k, f, its, "all") for k, f in bench.BASELINES.items()] + [(k, f, sub, "sample") for k, f in bench.BASELINES.items()]
        for model, got in llm.items():
            done = [i for i in sub if i["caller"] in got]
            rows.append((model, lambda i, got=got: i["callee"] in got.get(i["caller"], ()), done, f"{len({i['caller'] for i in done})} fn"))
        for k, f, pool, on in rows:
            sc, sh = bench.score(pool, f), bench.score([i for i in pool if i["shared"] > 1], f)
            print(f"  {k:28s} {on:>8s} {sc['precision']:6.2f} {sc['recall']:6.2f} {sc['f1']:6.2f}   {sh['recall']:.2f}")
    return 0


def cmd_agent_tasks(args) -> int:
    import agent
    bundle = Bundle(args.repo)
    found, attrition = agent.candidates(bundle)
    print(f"{bundle.name}: {len(found)} candidates; left out: {attrition}")
    if args.validate:
        agent.validate(bundle, found)
        attrition["dropped by validation"] = sum(not t["valid"] for t in found)
    (bundle.dir / "agent_tasks.json").write_text(json.dumps(
        {"repo": bundle.name, "sha": bundle.repo["sha"], "generated_utc": now(), "attrition": attrition,
         "validated": args.validate, "tasks": found}, indent=1) + "\n")
    print(f"{sum(t.get('valid', False) for t in found)} tasks kept -> bundles/{bundle.name}/agent_tasks.json")
    return 0


def cmd_agent(args) -> int:
    import agent
    print(f"-> {agent.run(Bundle(args.repo), args.model, args.effort)}")
    return 0


def cmd_learn(args) -> int:
    import ml
    r = ml.report(args.repos)
    out = HERE / "results" / "resolve" / "learned.json"
    out.write_text(json.dumps(r, indent=1) + "\n")
    print(f"{r['items']} items from {r['callers']} functions ({r['real']} real calls), 5-fold out-of-fold scores:")
    for k, sc in r["scores"].items():
        print(f"  {k:26s} precision {sc['precision']:.2f}  recall {sc['recall']:.2f}  F1 {sc['f1']:.2f}")
    print(f"-> {out}")
    return 0


def cmd_ui(args) -> int:
    import server
    server.serve(args.port, args.host)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fetch"); p.add_argument("repo"); p.set_defaults(fn=cmd_fetch)
    p = sub.add_parser("tasks"); p.add_argument("repo"); p.add_argument("--validate", action="store_true")
    p.set_defaults(fn=cmd_tasks)
    p = sub.add_parser("run"); p.add_argument("repo"); p.add_argument("--model", default="oracle")
    p.add_argument("--effort", default="medium"); p.add_argument("--arm", default="all",
                                                                 choices=("all", "treatment", "placebo"))
    p.add_argument("--budget", type=int, default=context.BUDGET_TOKENS)
    p.add_argument("--limit", type=int); p.add_argument("--only", nargs="*"); p.add_argument("--out")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("report"); p.add_argument("files", nargs="+"); p.set_defaults(fn=cmd_report)
    p = sub.add_parser("show"); p.add_argument("task"); p.add_argument("--results")
    p.add_argument("--live", help="score both arms now with this model, e.g. oracle")
    p.add_argument("--budget", type=int, default=context.BUDGET_TOKENS); p.set_defaults(fn=cmd_show)
    p = sub.add_parser("prompt"); p.add_argument("task"); p.add_argument("condition", choices=CONDITIONS)
    p.add_argument("--budget", type=int, default=context.BUDGET_TOKENS); p.set_defaults(fn=cmd_prompt)
    p = sub.add_parser("truth"); p.add_argument("repo"); p.set_defaults(fn=cmd_truth)
    p = sub.add_parser("resolve"); p.add_argument("repo"); p.add_argument("--model", required=True)
    p.add_argument("--effort", default="low"); p.add_argument("--limit", type=int); p.set_defaults(fn=cmd_resolve)
    p = sub.add_parser("bench"); p.add_argument("repos", nargs="+"); p.set_defaults(fn=cmd_bench)
    p = sub.add_parser("learn"); p.add_argument("repos", nargs="+"); p.set_defaults(fn=cmd_learn)
    p = sub.add_parser("agent-tasks"); p.add_argument("repo"); p.add_argument("--validate", action="store_true")
    p.set_defaults(fn=cmd_agent_tasks)
    p = sub.add_parser("agent"); p.add_argument("repo"); p.add_argument("--model", required=True)
    p.add_argument("--effort", default="low"); p.set_defaults(fn=cmd_agent)
    p = sub.add_parser("ui"); p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default=os.environ.get("TW_HOST", "127.0.0.1")); p.set_defaults(fn=cmd_ui)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
