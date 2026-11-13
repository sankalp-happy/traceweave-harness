"""Ground truth from execution: every call the test suite makes into the package.

`python3 tw.py truth click` runs the repo's own suite once under the
whole-package tracer (live/tw_live.py, sys.monitoring) and writes
bundles/click/truth.json:

  edges  [caller, callee, call_path, call_line, count, via_library]
         caller and callee are graph node keys. A caller that is a test, or
         anything outside the package, is "<entry>"; call_path still says
         where the call came from. via_library marks a call that passed
         through library code (a callback handed to the standard library) and
         is charged to the nearest package or test frame.
  lines  {path: [package lines that ran]}

These are the labels for the call-resolution benchmark (bench.py) and the
call sites for the same-name rename tasks (agent.py). Nothing here is
predicted or inferred: a pair is a call because the call happened.
"""
from __future__ import annotations

import json
import platform
import re
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import sandbox
from graph import ENTRY, Bundle

# Generator scopes are not nodes of their own; they fold into their function (build_bundle.py).
SYNTHETIC = re.compile(r"\.<(genexpr|listcomp|dictcomp|setcomp)>")


def build(bundle: Bundle, on_event=None) -> dict:
    repo, root = bundle.repo, sandbox.fetch(bundle.repo)
    package, tests = str(root / repo["package"]), str(root / repo["tests"])
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "trace.json"
        sandbox.reset(repo)
        suite = sandbox.run_tests(repo, on_event=on_event or (lambda e: None), extra_env={
            "TW_TRACE_ALL": package, "TW_TESTS": tests, "TW_TRACE_OUT": str(out)})
        raw = json.loads(out.read_text())
    base = sandbox.baseline(repo)
    if not sandbox.verdict(suite, base):
        raise SystemExit(f"{repo['name']}: the suite behaved differently under the tracer; not writing truth")

    in_tests = lambda p: p.startswith(repo["tests"].rstrip("/") + "/")
    edges = defaultdict(int)
    for c_path, c_qual, c_line, t_path, t_qual, t_first, via, n in raw["edges"]:
        callee = bundle.node_at(t_path, SYNTHETIC.sub("", t_qual), t_first)
        if callee == ENTRY:
            continue
        caller = ENTRY if c_path == "<external>" or in_tests(c_path) else bundle.node_at(c_path, SYNTHETIC.sub("", c_qual), c_line)
        if caller == callee and (SYNTHETIC.search(c_qual) or SYNTHETIC.search(t_qual)):
            continue  # a comprehension folded into its own function, not recursion
        edges[(caller, callee, c_path, c_line, via)] += n
    return {
        "repo": repo["name"], "sha": repo["sha"],
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": platform.python_version(), "host_arch": platform.machine(),
        "suite": {k: suite[k] for k in ("passed", "failed", "seconds")},
        "edges": sorted([list(k[:4]) + [n, k[4]] for k, n in edges.items()]),
        "lines": raw["lines"],
    }


def load(bundle: Bundle) -> dict:
    f = bundle.dir / "truth.json"
    if not f.exists():
        raise SystemExit(f"no {f}; run python3 tw.py truth {bundle.name}")
    return json.loads(f.read_text())
