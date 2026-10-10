#!/usr/bin/env python3
"""Turn TraceWeave-Core's outputs for one repo into a self-contained bundle.

This is the only step that needs the heavy tooling. It runs once, on the
machine that has TraceWeave-Core, PyCG and Pyright; everything downstream
reads only `bundles/<repo>/graph.json` and works on any laptop with Python.

Inputs, all produced by TraceWeave-Core (`traceweave/` in the research repo):

  --static DIR    `static/extract.py` output for the repo: inventory.json,
                  pycg.json, pyright.json, summary.json.
                  One shared node set, both static tools mapped onto it.
  --runtime FILE  `demo/tracer.py trace-package` output: the repo's own test
                  suite run under sys.setprofile, one record per distinct
                  (caller, callee) pair with the line that made the call.

Node identity is TraceWeave's `relative_path::qualified_symbol`. The tracer
names functions PyCG-style (`click.core.Option._parse_decls`); this script
maps those onto node keys by name, falling back to (file, definition line)
for lambdas and decorated functions whose two names disagree.

Calls whose caller is a test file, or outside the package, become `<entry>`:
a test calling the library is not an edge the library's call graph can hold,
and counting it would hand the runtime side free edges.

Usage:
    python3 build_bundle.py click --static ~/traceweave-data/static/click \\
        --runtime /path/to/click_runtime.json
"""
from __future__ import annotations

import argparse
import json
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENTRY = "<entry>"
# Metric spec §1: comprehension and generator scopes are not nodes of their
# own; they fold into the enclosing function. The tracer still reports them.
SYNTHETIC = re.compile(r"\.<(genexpr|listcomp|dictcomp|setcomp)>")


def module_of(path: str, src_root: str) -> str:
    """`src/click/core.py` -> `click.core`, the tracer's (and PyCG's) scheme."""
    rel = Path(path).relative_to(src_root) if src_root not in ("", ".") else Path(path)
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def build(repo: dict, static_dir: Path, runtime: dict) -> dict:
    inv = json.loads((static_dir / "inventory.json").read_text())
    summary = json.loads((static_dir / "summary.json").read_text())
    src_root, tests = repo["src_root"], repo["tests"].rstrip("/") + "/"

    def in_tests(path: str | None) -> bool:
        return path is None or path.startswith(tests)

    nodes, by_dotted, by_line, path_of_module = {}, {}, {}, {}
    for n in inv["nodes"]:
        if in_tests(n["relative_path"]):
            continue
        nodes[n["key"]] = {"path": n["relative_path"], "qualname": n["qualified_symbol"],
                           "kind": n["kind"], "line": n["lineno"], "end": n["end_lineno"]}
        mod = module_of(n["relative_path"], src_root)
        path_of_module[mod] = n["relative_path"]
        if n["qualified_symbol"] == "<module>":
            by_dotted[mod] = n["key"]
        else:
            by_dotted[f"{mod}.{n['qualified_symbol']}"] = n["key"]
        by_line.setdefault((n["relative_path"], n["lineno"]), n["key"])

    static = {}
    for tool in ("pycg", "pyright"):
        f = static_dir / f"{tool}.json"
        pairs = json.loads(f.read_text())["edges"]["in_universe_edges"] if f.exists() else []
        static[tool] = sorted({tuple(p.split("->")) for p in pairs
                               if all(k in nodes for k in p.split("->"))})

    def resolve(dotted: str, module: str | None, def_line: int | None) -> str | None:
        dotted = SYNTHETIC.sub("", dotted)
        key = by_dotted.get(dotted)
        if key is None and module in path_of_module and def_line:
            key = by_line.get((path_of_module[module], def_line))
        return key

    edges, unmapped = set(), []
    for e in runtime["edges"]:
        callee = resolve(e["callee"], e.get("module"), e.get("def_line"))
        if callee is None:
            if not in_tests(path_of_module.get(e.get("module"), tests)):
                unmapped.append(e["callee"])
            continue
        call_path = path_of_module.get(e.get("call_module"))
        caller = ENTRY if e["caller"] == ENTRY else resolve(e["caller"], None, None)
        if caller is None and call_path:
            # Caller's own def line is unknown here; the call line sits inside
            # it, so take the innermost node whose span contains that line.
            spans = [(n["line"], k) for k, n in nodes.items()
                     if n["path"] == call_path and n["line"] <= e["call_line"] <= n["end"]
                     and n["kind"] != "class_body"]
            caller = max(spans)[1] if spans else None
        if caller is None or in_tests(call_path):
            caller = ENTRY
        if caller == callee and (SYNTHETIC.search(e["caller"]) or SYNTHETIC.search(e["callee"])):
            continue  # a comprehension folded into its own function, not recursion
        edges.add((caller, callee, call_path, e.get("call_line")))

    return {
        "repo": repo["name"],
        "sha": repo["sha"],
        "provenance": {
            "static": {k: summary.get(k) for k in
                       ("recorded_utc", "host_arch", "image", "spec_version", "baseline_comparison")}
                      | {"pycg_pin": "pycg==0.0.8", "pyright_pin": "pyright@1.1.411"},
            "runtime": {"workload": runtime.get("workload"), "run_id": runtime.get("run_id"),
                        "python": platform.python_version(), "host_arch": platform.machine(),
                        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
            "unmapped_runtime_callees": len(unmapped),
            "unmapped_examples": sorted(set(unmapped))[:10],
        },
        "nodes": nodes,
        "static_edges": static,
        "runtime_edges": sorted(edges, key=lambda e: (e[0], e[1], e[2] or "", e[3] or 0)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("repo")
    ap.add_argument("--static", type=Path, required=True)
    ap.add_argument("--runtime", type=Path, required=True)
    args = ap.parse_args()
    bundle_dir = HERE / "bundles" / args.repo
    repo = json.loads((bundle_dir / "repo.json").read_text())
    graph = build(repo, args.static, json.loads(args.runtime.read_text()))
    (bundle_dir / "graph.json").write_text(json.dumps(graph, separators=(",", ":")) + "\n")
    p = graph["provenance"]
    print(f"{args.repo}: {len(graph['nodes'])} nodes, "
          f"pycg {len(graph['static_edges']['pycg'])} / pyright {len(graph['static_edges']['pyright'])} "
          f"static edges, {len(graph['runtime_edges'])} runtime edges "
          f"({p['unmapped_runtime_callees']} callees unmapped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
