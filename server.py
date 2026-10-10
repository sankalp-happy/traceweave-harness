"""`tw.py ui`: the results page and its JSON, served by the standard library.

Everything the page shows comes from three places, all on disk: the bundles,
the recorded results in `results/`, and the pinned checkouts in `work/`.
Nothing is computed for display that `tw.py report` / `show` would not print.

  GET  /api/report          outcomes, attrition, the task roster
  GET  /api/task?id=...      one task: callers, both arms' excerpts, prompt, recorded result
  POST /api/run?id=...       re-run the oracle on both arms now (one run at a time)
"""
from __future__ import annotations

import json
import mimetypes
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import context
import models
import sandbox
from graph import CONDITIONS, HERE, Bundle, word
from tw import attempt, sign_test

UI = HERE / "ui"
RESULTS = HERE / "results"
MODEL = "oracle"   # the only model with recorded results so far; see README
RUN_LOCK = threading.Lock()  # ponytail: one live run at a time, the checkout is shared


def bundles() -> list[Bundle]:
    return [Bundle(p.parent.name) for p in sorted((HERE / "bundles").glob("*/tasks.json"))]


def recorded() -> dict[tuple[str, str], dict]:
    rows = {}
    for f in sorted(RESULTS.glob("*.jsonl")):
        for line in f.read_text().splitlines():
            r = json.loads(line)
            if r["model"] == MODEL:
                rows[(r["task"], r["condition"])] = r | {"file": f.name}
    return rows


def arm_summary(r: dict | None) -> dict | None:
    if r is None:
        return None
    t = r["tests"]
    return {"pass": r["pass"], "refs_shown": r["refs_shown"], "passed": t["passed"],
            "failed": t["failed"], "errors": t["errors"], "rc": t["rc"]}


def report() -> dict:
    rows = recorded()
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
    return {"model": MODEL, "repos": repos, "table": table, "attrition": dict(attrition),
            "tasks": tasks,
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


def task_detail(task_id: str) -> dict:
    from tw import find_task
    bundle, task = find_task(task_id)
    root = sandbox.root(bundle.repo)
    target = bundle.nodes[task["target"]]
    base = {"id": task["id"], "repo": bundle.name, "group": task["arm"], "name": task["name"],
            "new_name": task["new_name"], "qualname": target["qualname"], "path": target["path"],
            "line": target["line"], "static_callers": task["static_callers"],
            "runtime_callers": task["runtime_callers"], "refs_total": len(task["reference_lines"])}
    if not (root / ".git").exists():
        return base | {"fetched": False, "fetch_command": f"python3 tw.py fetch {bundle.name}"}

    rows = recorded()
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
                   "prompt_sha256": r["prompt_sha256"]}
        arms[c] = {"callers": [{"qualname": bundle.nodes[k]["qualname"], "path": bundle.nodes[k]["path"],
                                "runtime_only": k in task["dynamic_only_callers"]} for k in ctx.callers],
                   "excerpts": excerpts(ctx, root, task["name"], added if c == "fused" else {}, edits),
                   "refs_shown": len(task["reference_lines"]) - len(unseen), "unseen": unseen,
                   "truncated": ctx.truncated, "prompt": ctx.prompt, "recorded": rec}
    baseline = sandbox.baseline(bundle.repo)
    return base | {"fetched": True, "runtime_only": runtime_only, "arms": arms,
                   "baseline": {"passed": baseline["passed"], "failed": baseline["failed"]}}


def run_live(task_id: str) -> dict:
    from tw import find_task
    bundle, task = find_task(task_id)
    root = sandbox.root(bundle.repo)
    if not (root / ".git").exists():
        raise LookupError(f"{bundle.name} is not on this machine: run python3 tw.py fetch {bundle.name}")
    if not RUN_LOCK.acquire(blocking=False):
        raise RuntimeError("another live run is still in progress")
    try:
        base = sandbox.baseline(bundle.repo)
        out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": MODEL}
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

    def do_GET(self) -> None:
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if url.path == "/api/report":
            return self.api(report)
        if url.path == "/api/task":
            return self.api(task_detail, q.get("id", [""])[0])
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


def serve(port: int) -> None:
    mimetypes.add_type("font/woff2", ".woff2")
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"TraceWeave harness UI on http://127.0.0.1:{port}/  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
