"""`tw.py ui`: the results page and its JSON, served by the standard library.

Everything the page shows comes from three places, all on disk: the bundles,
the recorded results in `results/`, and the pinned checkouts in `work/`.
Nothing is computed for display that `tw.py report` / `show` would not print.

  GET  /api/report[?model=]       outcomes, attrition, the task roster
  GET  /api/task?id=...[&model=]  one task: callers, both arms' excerpts, prompt, recorded result
  POST /api/run?id=...            re-run the oracle on both arms now (one run at a time)
  GET  /api/editors               who can edit live: the rename script, and the LLM when a key is set
  GET  /api/live?stage=...&id=... the live demo, one stage at a time, as server-sent events:
                                  trace (the suite under a tracer), edit (&editor=), test

`model` is any model with rows in `results/`; it defaults to the first LLM,
or the oracle when no LLM has run.
"""
from __future__ import annotations

import json
import mimetypes
import os
import queue
import socket
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import context
import models
import sandbox
from graph import CONDITIONS, ENTRY, HERE, Bundle, word
from tw import attempt, sign_test

UI = HERE / "ui"
RESULTS = HERE / "results"
RUN_LOCK = threading.Lock()  # ponytail: one live run at a time, the checkout is shared
LLM = "groq:openai/gpt-oss-20b"
LLMS = {"groq:openai/gpt-oss-20b": "gpt-oss-20b", "groq:openai/gpt-oss-120b": "gpt-oss-120b",
        "groq:qwen/qwen3.8-27b": "qwen3.8-27b"}
PENDING: dict[str, dict] = {}  # task id -> the edits its last edit stage produced, for the test stage


def bundles() -> list[Bundle]:
    return [Bundle(p.parent.name) for p in sorted((HERE / "bundles").glob("*/tasks.json"))]


def all_rows() -> list[dict]:
    return [json.loads(line) | {"file": f.name}
            for f in sorted(RESULTS.glob("*.jsonl")) for line in f.read_text().splitlines()]


def models_run() -> list[str]:
    """LLMs first, the oracle last: the oracle is the ceiling they are read against."""
    return sorted({r["model"] for r in all_rows()}, key=lambda m: (m == "oracle", m))


def pick(model: str | None) -> str:
    have = models_run()
    if model and model not in have:
        raise LookupError(f"No saved results for {model}. Saved: {', '.join(have) or 'none'}.")
    return model or (have[0] if have else "oracle")


def recorded(model: str) -> dict[tuple[str, str], dict]:
    return {(r["task"], r["condition"]): r for r in all_rows() if r["model"] == model}


def arm_summary(r: dict | None) -> dict | None:
    if r is None:
        return None
    t = r["tests"]
    return {"pass": r["pass"], "refs_shown": r["refs_shown"], "passed": t["passed"],
            "failed": t["failed"], "errors": t["errors"], "rc": t["rc"]}


def report(model: str | None = None) -> dict:
    model = pick(model)
    rows = recorded(model)
    tasks, groups, attrition = [], defaultdict(lambda: [0, 0, 0, 0, 0]), defaultdict(int)
    repos = []
    for b in bundles():
        meta = json.loads((b.dir / "tasks.json").read_text())
        for reason, n in meta.get("attrition", {}).items():
            attrition[reason] += n
        repos.append({"name": b.name, "sha": b.repo["sha"], "url": b.repo["url"],
                      "fetched": (sandbox.root(b.repo) / ".git").exists()})
        for t in b.tasks():
            s, f = rows.get((t["id"], "static")), rows.get((t["id"], "fused"))
            tasks.append({"id": t["id"], "repo": b.name, "group": t["arm"],
                          "qualname": b.nodes[t["target"]]["qualname"],
                          "runtime_only": len(t["dynamic_only_callers"]),
                          "static_callers": t["static_callers"], "refs_total": len(t["reference_lines"]),
                          "static": arm_summary(s), "fused": arm_summary(f)})
            if s and f:
                for key in ((b.name, t["arm"]), ("pooled", t["arm"])):
                    g = groups[key]
                    g[0] += 1
                    g[1] += s["pass"]
                    g[2] += f["pass"]
                    g[3] += f["pass"] and not s["pass"]
                    g[4] += s["pass"] and not f["pass"]
    table = [{"repo": repo, "group": group, "tasks": g[0], "static": g[1], "fused": g[2],
              "fused_only": g[3], "static_only": g[4], "p": sign_test(g[3], g[4])}
             for (repo, group), g in groups.items()]
    files = sorted({r["file"] for r in rows.values()})
    stamps = sorted(r["ts"] for r in rows.values())
    ceiling = None if model == "oracle" else [
        x for x in report("oracle")["table"] if x["repo"] == "pooled"] if "oracle" in models_run() else None
    return {"model": model, "models": models_run(), "ceiling": ceiling,
            "repos": repos, "table": table, "attrition": dict(attrition), "tasks": tasks,
            "provenance": {"command": "python3 tw.py report " + " ".join(f"results/{f}" for f in files),
                           "rows": len(rows), "files": files,
                           "first": stamps[0] if stamps else None, "last": stamps[-1] if stamps else None}}


def excerpts(ctx: context.Context, root: Path, name: str, added: dict[str, set[int]],
             edits: dict[tuple[str, int], str]) -> list[dict]:
    pat, out = word(name), []
    for path in sorted(ctx.shown):
        src = (root / path).read_text().splitlines()
        lines = []
        for n in sorted(ctx.shown[path]):
            lines.append({"n": n, "text": src[n - 1], "names": bool(pat.search(src[n - 1])),
                          "added": n in added.get(path, ()), "edit": edits.get((path, n))})
        out.append({"path": path, "lines": lines})
    return out


def task_detail(task_id: str, model: str | None = None) -> dict:
    from tw import find_task
    bundle, task = find_task(task_id)
    root = sandbox.root(bundle.repo)
    target = bundle.nodes[task["target"]]
    base = {"id": task["id"], "repo": bundle.name, "group": task["arm"], "name": task["name"],
            "new_name": task["new_name"], "qualname": target["qualname"], "path": target["path"],
            "line": target["line"], "static_callers": task["static_callers"],
            "runtime_callers": task["runtime_callers"], "refs_total": len(task["reference_lines"]),
            "about": bundle.repo.get("about", "")}
    if not (root / ".git").exists():
        return base | {"fetched": False, "fetch_command": f"python3 tw.py fetch {bundle.name}"}

    model = pick(model)
    rows = recorded(model)
    ctxs = {c: context.build(bundle, task, c, root) for c in CONDITIONS}
    added = {p: lines - ctxs["static"].shown.get(p, set()) for p, lines in ctxs["fused"].shown.items()}
    runtime_only = []
    for c in task["dynamic_only_callers"]:
        site = bundle.runtime_site.get((c, task["target"]))
        text = (root / site[0]).read_text().splitlines()[site[1] - 1].strip() if site else None
        runtime_only.append({"qualname": bundle.nodes[c]["qualname"],
                             "path": site[0] if site else bundle.nodes[c]["path"],
                             "line": site[1] if site else None, "text": text})
    arms = {}
    for c, ctx in ctxs.items():
        r = rows.get((task["id"], c))
        edits = {(e["path"], e["line"]): e["text"] for e in (r["edits"] if r else [])}
        unseen = [{"path": p, "n": n, "text": (root / p).read_text().splitlines()[n - 1].strip()}
                  for p, n in task["reference_lines"] if not ctx.shows(p, n)]
        rec = None
        if r:
            t = r["tests"]
            rec = {"pass": r["pass"], "rc": t["rc"], "note": t.get("note"),
                   "passed": t["passed"], "failed": t["failed"], "errors": t["errors"],
                   "bad": t["bad"][:6], "bad_count": len(t["bad"]), "seconds": t["seconds"],
                   "edits": len(r["edits"]), "ts": r["ts"], "file": r["file"],
                   "prompt_sha256": r["prompt_sha256"], "error": r["model_meta"].get("error"),
                   "syntax_error": r["apply"].get("syntax_error"),
                   "reasoning": r["model_meta"].get("reasoning")}
        arms[c] = {"callers": [{"qualname": bundle.nodes[k]["qualname"], "path": bundle.nodes[k]["path"],
                                "runtime_only": k in task["dynamic_only_callers"]} for k in ctx.callers],
                   "excerpts": excerpts(ctx, root, task["name"], added if c == "fused" else {}, edits),
                   "refs_shown": len(task["reference_lines"]) - len(unseen), "unseen": unseen,
                   "truncated": ctx.truncated, "prompt": ctx.prompt, "recorded": rec}
    baseline = sandbox.baseline(bundle.repo)
    t = task["target"]
    graph = {"static": [{"key": k, "qualname": bundle.nodes[k]["qualname"], "path": bundle.nodes[k]["path"],
                         "tools": [tool for tool, edges in bundle.static_by_tool.items() if (k, t) in edges]}
                        for k in sorted(bundle.static_in.get(t, ()))],
             "hidden": [{"key": k, "qualname": bundle.nodes[k]["qualname"]} for k in task["dynamic_only_callers"]],
             "target": t,
             "provenance": {k: bundle.provenance["static"].get(k) for k in ("pycg_pin", "pyright_pin", "recorded_utc")}}
    refs = [{"path": p, "n": n, "text": source_line(root, p, n)} for p, n in task["reference_lines"]]
    return base | {"fetched": True, "model": model, "graph": graph, "refs": refs, "runtime_only": runtime_only, "arms": arms,
                   "baseline": {"passed": baseline["passed"], "failed": baseline["failed"]}}


def run_live(task_id: str) -> dict:
    from tw import find_task
    bundle, task = find_task(task_id)
    root = sandbox.root(bundle.repo)
    if not (root / ".git").exists():
        raise LookupError(f"The code for {bundle.name} is not on this computer. Run python3 tw.py fetch {bundle.name}, then try again.")
    if not RUN_LOCK.acquire(blocking=False):
        raise RuntimeError("Another run is still going. Try again when it finishes.")
    try:
        base = sandbox.baseline(bundle.repo)
        out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": "oracle"}
        for c in CONDITIONS:
            ctx = context.build(bundle, task, c, root)
            edits, _ = models.oracle(task, ctx, root)
            res = attempt(bundle, edits, base)
            t = res["tests"]
            out[c] = {"pass": res["pass"], "rc": t["rc"], "note": t.get("note"),
                      "passed": t["passed"], "failed": t["failed"],
                      "errors": t["errors"], "seconds": t["seconds"], "edits": len(edits)}
        return out
    finally:
        RUN_LOCK.release()


def editors() -> list[dict]:
    why = None
    if not (os.environ.get("GROQ_API_KEY") or models.dotenv().get("GROQ_API_KEY")):
        why = "set GROQ_API_KEY in .env to use it."
    else:
        try:  # an offline laptop would otherwise sit in the Groq retry loop for minutes
            socket.create_connection(("api.groq.com", 443), timeout=1.5).close()
        except OSError:
            why = "no network, and it runs through Groq."
    return [{"id": "oracle", "name": "Rename script", "ready": True}] + [
        {"id": m, "name": name, "ready": why is None, "why": why} for m, name in LLMS.items()]


def source_line(root: Path, path: str, n: int) -> str:
    try:
        return (root / path).read_text().splitlines()[n - 1].strip()
    except (OSError, IndexError):
        return ""


def live_task(task_id: str):
    from tw import find_task
    bundle, task = find_task(task_id)
    root = sandbox.root(bundle.repo)
    if not (root / ".git").exists():
        raise LookupError(f"The code for {bundle.name} is not on this computer. Run python3 tw.py fetch {bundle.name}, then try again.")
    return bundle, task, root


def live_trace(emit, task_id: str) -> None:
    bundle, task, root = live_task(task_id)
    target = task["target"]
    static, recorded = bundle.static_in.get(target, set()), bundle.runtime_in.get(target, set())
    found, tests = {}, set()

    def on_event(e: dict) -> None:
        if e["type"] != "call":
            return emit(e)
        key = bundle.node_at(e["path"], e["qualname"], e["line"])
        if key == ENTRY or e["path"].startswith(bundle.repo["tests"].rstrip("/") + "/"):
            if not tests:
                emit({"type": "direct", "test": e["test"]})
            tests.add(e["test"])
            return
        if key in found:
            return
        kind = "static" if key in static else "hidden" if key in recorded else "new"
        found[key] = kind
        emit({"type": "caller", "key": key, "kind": kind, "qualname": bundle.nodes[key]["qualname"],
              "path": e["path"], "line": e["line"], "text": source_line(root, e["path"], e["line"]),
              "test": e["test"]})

    with sandbox.lock(bundle.repo):
        sandbox.reset(bundle.repo)
        res = sandbox.run_tests(bundle.repo, on_event, trace=target)
    emit({"type": "done", "rc": res["rc"], "passed": res["passed"], "failed": res["failed"],
          "seconds": res["seconds"], "direct_tests": len(tests),
          "hidden_found": sorted(k for k, v in found.items() if v == "hidden"),
          "hidden_missed": [bundle.nodes[k]["qualname"] for k in sorted(recorded - static - set(found))],
          "static_unseen": [bundle.nodes[k]["qualname"] for k in sorted(static - set(found))]})


def live_edit(emit, task_id: str, editor: str) -> None:
    bundle, task, root = live_task(task_id)
    if editor not in {e["id"] for e in editors() if e["ready"]}:
        raise LookupError(f"{editor} is not available here.")
    model = models.load(editor, patient=False)
    sandbox.reset(bundle.repo)
    out = {}
    for c in CONDITIONS:
        ctx = context.build(bundle, task, c, root)
        unseen = [{"path": p, "n": n, "text": source_line(root, p, n)}
                  for p, n in task["reference_lines"] if not ctx.shows(p, n)]
        emit({"type": "asking", "arm": c, "callers": len(ctx.callers),
              "refs_shown": len(task["reference_lines"]) - len(unseen), "refs_total": len(task["reference_lines"])})
        t0 = time.monotonic()
        edits, meta = model(task, ctx, root)
        change = sandbox.preview(bundle.repo, edits)
        out[c] = edits
        emit({"type": "edits", "arm": c, "seconds": round(time.monotonic() - t0, 1), **change,
              "unseen": unseen, "error": meta.get("error"), "reasoning": meta.get("reasoning"),
              "usage": meta.get("usage")})
    PENDING[task_id] = {"editor": editor, "edits": out, "repo": bundle.name}


def live_test(emit, task_id: str) -> None:
    from tw import attempt
    if task_id not in PENDING:
        raise LookupError("Run the edit step for this task first.")
    p = PENDING[task_id]
    bundle = Bundle(p["repo"])
    base = sandbox.baseline(bundle.repo)
    saved = recorded("oracle") if p["editor"] == "oracle" and "oracle" in models_run() else {}
    for c, edits in p["edits"].items():
        emit({"type": "start", "arm": c, "baseline": base["passed"]})
        res = attempt(bundle, edits, base, on_event=lambda e, c=c: emit(e | {"arm": c}))
        t, was = res["tests"], saved.get((task_id, c))
        emit({"type": "verdict", "arm": c, "pass": res["pass"], "rc": t["rc"], "passed": t["passed"],
              "failed": t["failed"], "errors": t["errors"], "seconds": t["seconds"], "note": t.get("note"),
              "syntax_error": res["apply"].get("syntax_error"), "bad": t["bad"][:5], "bad_count": len(t["bad"]),
              "baseline": base["passed"], "saved": was["pass"] if was else None})


def live_truth(emit, repo: str) -> None:
    """Record the ground truth again, now: the whole suite under the tracer."""
    import truth as truth_mod
    bundle = Bundle(repo)
    with sandbox.lock(bundle.repo):
        t = truth_mod.build(bundle, on_event=emit)
    pairs = {(e[0], e[1]) for e in t["edges"] if e[0] != ENTRY and e[0] != e[1]
             and bundle.nodes[e[1]]["kind"] in ("function", "method")}
    saved = {(e[0], e[1]) for e in truth_mod.load(bundle)["edges"] if e[0] != ENTRY and e[0] != e[1]
             and bundle.nodes[e[1]]["kind"] in ("function", "method")}
    emit({"type": "done", "pairs": len(pairs), "sites": sum(1 for e in t["edges"] if e[0] != ENTRY),
          "lines": sum(len(v) for v in t["lines"].values()), "tests": t["suite"]["passed"], "seconds": t["suite"]["seconds"],
          "same_as_saved": len(pairs & saved), "saved": len(saved),
          "static": {"PyCG ∪ Pyright": sum(1 for x in pairs if x in bundle.static)}})


def live_resolve(emit, repo: str, caller: str, model: str) -> None:
    """Ask one LLM, now, which candidates one function calls; score it against the truth."""
    import resolve
    import studies
    from models import groq_json
    if model not in {e["id"] for e in editors() if e["ready"] and e["id"] != "oracle"}:
        raise LookupError(f"{model} is not available here.")
    bundle, root = Bundle(repo), sandbox.root(Bundle(repo).repo)
    its = [i for i in studies.items(repo) if i["caller"] == caller]
    if not its:
        raise LookupError("This function names no candidate functions.")
    prompt, ids = resolve.build(bundle, caller, its, root)
    emit({"type": "asking", "model": LLMS[model], "candidates": len(ids)})
    t0 = time.monotonic()
    obj, meta = groq_json(model.removeprefix("groq:"), prompt, resolve.schema(ids), "low", patient=False)
    called = {ids[c] for c in (obj or {}).get("called", []) if c in ids}
    emit({"type": "answer", "model": LLMS[model], "seconds": round(time.monotonic() - t0, 1), "error": meta.get("error"),
          "usage": meta.get("usage"), "reasoning": meta.get("reasoning"),
          "answers": [{"callee": i["callee"], "says": i["callee"] in called, "real": i["label"]} for i in its]})


def live_agent(emit, task_id: str, model: str) -> None:
    """The agent study's edit step, now: one model, all three kinds of context."""
    import agent
    from models import groq_json
    if model not in {e["id"] for e in editors() if e["ready"] and e["id"] != "oracle"}:
        raise LookupError(f"{model} is not available here.")
    bundle = Bundle(task_id.split(":", 1)[0])
    task = next((t for t in agent.tasks(bundle) if t["id"] == task_id), None)
    if task is None:
        raise LookupError(f"no agent task {task_id}")
    right, out = {tuple(x) for x in task["right_lines"]}, {}
    for c in agent.CONDITIONS:
        prompt, shown = agent.build(bundle, task, c)
        emit({"type": "asking", "arm": c, "shown": sum(len(v) for v in shown.values()),
              "right_shown": sum(1 for p, ln in right if ln in shown.get(p, ()))})
        t0 = time.monotonic()
        obj, meta = groq_json(model.removeprefix("groq:"), prompt, agent.EDITS_SCHEMA, "low", patient=False)
        edits = (obj or {}).get("edits") or []
        with sandbox.lock(bundle.repo):
            change = sandbox.preview(bundle.repo, edits)
        for line in change["lines"]:
            line["right"] = (line["path"], line["line"]) in right
        out[c] = edits
        emit({"type": "edits", "arm": c, "seconds": round(time.monotonic() - t0, 1), **change,
              "missed": len(right - {(l["path"], l["line"]) for l in change["lines"]}),
              "error": meta.get("error"), "reasoning": meta.get("reasoning")})
    PENDING[task_id] = {"editor": model, "edits": out, "repo": bundle.name}


STAGES = {
    "trace": lambda emit, a: live_trace(emit, a["id"]),
    "edit": lambda emit, a: live_edit(emit, a["id"], a.get("editor") or "oracle"),
    "test": lambda emit, a: live_test(emit, a["id"]),
    "truth": lambda emit, a: live_truth(emit, a["repo"]),
    "resolve": lambda emit, a: live_resolve(emit, a["repo"], a["caller"], a.get("editor") or "groq:openai/gpt-oss-120b"),
    "agent": lambda emit, a: live_agent(emit, a["id"], a.get("editor") or "groq:openai/gpt-oss-120b"),
}


def live_events(stage: str, args: dict):
    """Run one stage in a worker thread and yield its events as they happen."""
    q: queue.Queue = queue.Queue()

    def work() -> None:
        if not RUN_LOCK.acquire(blocking=False):
            q.put({"type": "error", "message": "Another run is still going. Try again when it finishes."})
            return q.put(None)
        try:
            STAGES[stage](q.put, args)
        except (Exception, SystemExit) as exc:  # SystemExit: models and find_task speak in it
            q.put({"type": "error", "message": str(exc)})
        finally:
            RUN_LOCK.release()
            q.put(None)

    threading.Thread(target=work, daemon=True).start()
    while (event := q.get()) is not None:
        yield event


def _studies(name):
    def call(*a):
        import studies
        return getattr(studies, name)(*a)
    return call


STUDY = {"/api/truth": _studies("truth_summary"), "/api/study1": _studies("study1"),
         "/api/study1/fn": _studies("study1_fn"), "/api/study2": _studies("study2"),
         "/api/study2/task": _studies("study2_task")}
STUDY_ARGS = {"/api/study1/fn": ("repo", "caller"), "/api/study2/task": ("id",)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet: the terminal is the presenter's
        pass

    def send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def json(self, code: int, payload) -> None:
        self.send(code, json.dumps(payload).encode(), "application/json")

    def api(self, fn, *args) -> None:
        try:
            self.json(200, fn(*args))
        except (LookupError, SystemExit) as exc:
            self.json(404, {"error": str(exc)})
        except RuntimeError as exc:
            self.json(409, {"error": str(exc)})

    def stream(self, events) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            for event in events:
                self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
                self.wfile.flush()
            self.wfile.write(b"event: end\ndata: {}\n\n")
        except (BrokenPipeError, ConnectionResetError):
            pass  # the page went away; the stage still finishes and releases the lock

    def do_GET(self) -> None:
        url = urlparse(self.path)
        q = parse_qs(url.query)
        model = q.get("model", [None])[0]
        if url.path == "/api/report":
            return self.api(report, model)
        if url.path == "/api/task":
            return self.api(task_detail, q.get("id", [""])[0], model)
        if url.path == "/api/editors":
            return self.api(editors)
        if url.path == "/api/live" and q.get("stage", [""])[0] in STAGES:
            return self.stream(live_events(q["stage"][0], {k: v[0] for k, v in q.items()}))
        if url.path in STUDY:
            return self.api(STUDY[url.path], *[q.get(k, [""])[0] for k in STUDY_ARGS.get(url.path, ())])
        path = (UI / url.path.lstrip("/")).resolve() if url.path != "/" else UI / "index.html"
        if UI.resolve() not in path.parents and path != UI / "index.html" or not path.is_file():
            return self.send(404, b"not found", "text/plain")
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send(200, path.read_bytes(), ctype)

    def do_POST(self) -> None:
        url = urlparse(self.path)
        if url.path == "/api/run":
            return self.api(run_live, parse_qs(url.query).get("id", [""])[0])
        self.send(404, b"not found", "text/plain")


def serve(port: int, host: str = "127.0.0.1") -> None:
    mimetypes.add_type("font/woff2", ".woff2")

    def warm() -> None:  # the first page should not wait for every file to be tokenized
        import studies
        for repo in studies.REPOS:
            try:
                studies.items(repo)
            except SystemExit:
                pass
    threading.Thread(target=warm, daemon=True).start()
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"TraceWeave harness UI on http://{host}:{port}/  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
