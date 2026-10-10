"""A bundle's call graph, and the rename tasks drawn from it.

Two edge sets per repo, over one node set:

  static   PyCG ∪ Pyright. The union, not either tool alone: the static arm
           gets the strongest static graph we can build, so a gap that
           survives it is not "you picked a weak tool".
  runtime  calls observed while the repo's own test suite ran.

A task is "rename symbol T". Its inbound callers split three ways, and the
split is the experiment:

  static callers     S(T)        the static arm sees these
  runtime callers    R(T)        observed; tests reach T through them
  dynamic-only       D = R − S   only the fused arm sees these

Treatment tasks have |D| >= 1. Placebo tasks have |D| = 0 and |S| >= 1, so
both arms receive identical context -- any difference there is noise, and the
prediction (no difference) is pre-registered in README.md.
"""
from __future__ import annotations

import json
import re
from functools import cached_property
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENTRY = "<entry>"
CONDITIONS = ("static", "fused")


class Bundle:
    def __init__(self, name: str):
        self.dir = HERE / "bundles" / name
        self.repo = json.loads((self.dir / "repo.json").read_text())
        g = json.loads((self.dir / "graph.json").read_text())
        self.nodes: dict[str, dict] = g["nodes"]
        self.provenance = g["provenance"]
        self.static = {tuple(e) for tool in g["static_edges"].values() for e in tool}
        self.runtime = [tuple(e) for e in g["runtime_edges"]]

    @property
    def name(self) -> str:
        return self.repo["name"]

    @cached_property
    def static_in(self) -> dict[str, set[str]]:
        inbound: dict[str, set[str]] = {}
        for caller, callee in self.static:
            inbound.setdefault(callee, set()).add(caller)
        return inbound

    @cached_property
    def runtime_in(self) -> dict[str, set[str]]:
        inbound: dict[str, set[str]] = {}
        for caller, callee, _, _ in self.runtime:
            if caller != ENTRY:
                inbound.setdefault(callee, set()).add(caller)
        return inbound

    @cached_property
    def runtime_site(self) -> dict[tuple[str, str], tuple[str, int]]:
        """(caller, callee) -> the call line the tracer saw, for dynamic-only edges."""
        return {(c, t): (p, ln) for c, t, p, ln in self.runtime if p and ln}

    def callers(self, target: str, condition: str) -> set[str]:
        s = self.static_in.get(target, set())
        return s if condition == "static" else s | self.runtime_in.get(target, set())

    def dynamic_only(self, target: str) -> set[str]:
        return self.runtime_in.get(target, set()) - self.static_in.get(target, set())

    def tasks(self) -> list[dict]:
        tasks = json.loads((self.dir / "tasks.json").read_text())["tasks"]
        return [t for t in tasks if t.get("valid", True)]


def short(qualname: str) -> str:
    return qualname.rsplit(".", 1)[-1]


def word(name: str) -> re.Pattern:
    return re.compile(rf"(?<![\w]){re.escape(name)}(?![\w])")


def package_files(root: Path, repo: dict) -> list[Path]:
    tests = (root / repo["tests"]).resolve()
    return sorted(p for p in (root / repo["package"]).rglob("*.py")
                  if tests not in p.resolve().parents)


def reference_lines(root: Path, repo: dict, name: str) -> list[tuple[str, int]]:
    """Every package line naming `name`: the ground truth a complete rename touches."""
    pat, out = word(name), []
    for f in package_files(root, repo):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if pat.search(line):
                out.append((str(f.relative_to(root)), i))
    return out


def candidates(bundle: Bundle, root: Path) -> list[dict]:
    """Rename targets with a well-defined answer, before any test is run.

    Filters, all independent of which arm will see what:
      * a function or method with a plain identifier for a name: not a dunder,
        not synthetic, not an overload stub or a numbered redefinition
      * its bare name is unique among the package's nodes -- otherwise
        "rename it" silently means "rename an override family", a different task
      * its name never appears in the test suite -- the unmodified suite is the
        oracle, so a correct rename must not require editing a test
      * at least one in-package caller ran under the suite (R non-empty), or a
        broken rename could pass simply because nothing exercises it
    """
    repo = bundle.repo
    counts: dict[str, int] = {}
    for n in bundle.nodes.values():
        counts[short(n["qualname"])] = counts.get(short(n["qualname"]), 0) + 1
    test_text = "\n".join(p.read_text(errors="replace")
                          for p in (root / repo["tests"]).rglob("*.py"))
    package_text = "\n".join(p.read_text() for p in package_files(root, repo))

    out = []
    for key, n in sorted(bundle.nodes.items()):
        name = short(n["qualname"])
        if (n["kind"] not in ("function", "method") or not name.isidentifier()
                or re.fullmatch(r"__\w+__", name) or "<overload" in n["qualname"]
                or counts[name] != 1 or len(name) < 4):
            continue
        if word(name).search(test_text) or not bundle.runtime_in.get(key):
            continue
        new = f"{name}_v2"
        if word(new).search(package_text):
            continue
        d = bundle.dynamic_only(key)
        s = bundle.static_in.get(key, set())
        if not d and not s:
            continue
        out.append({
            "id": f"{bundle.name}:{n['qualname']}",
            "target": key,
            "name": name,
            "new_name": new,
            "arm": "treatment" if d else "placebo",
            "static_callers": len(s),
            "runtime_callers": len(bundle.runtime_in[key]),
            "dynamic_only_callers": sorted(d),
            "reference_lines": reference_lines(root, repo, name),
        })
    return out
