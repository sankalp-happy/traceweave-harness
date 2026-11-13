"""Call-resolution benchmark: who can tell which functions a piece of code really calls?

An item is a (caller, candidate) pair. The candidate's name is written in a
line of the caller that ran under the project's own tests: as a call `f(`, as a
reference without a call (`obj.prop`, a callback handed on), or as a class
name (a constructor reaches that class's __init__). The label is whether the
call happened (truth.json). Every resolver answers the same items:

  name match          every candidate is a call: what a grep sees
  PyCG, Pyright       the static call graphs in graph.json, and their union
  LLMs                the caller's code plus the candidates' definitions (resolve.py)

Two numbers matter. Precision: of the calls a resolver claims, how many
happened. Recall: of the calls that happened, how many it found. Calls whose
target is never named in the caller (a callback invoked under another name)
cannot be items; they are counted apart as "unnamed" so nobody's recall
hides them.
"""
from __future__ import annotations

import ast
import io
import re
import tokenize
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import sandbox
import truth as truth_mod
from context import own_lines
from graph import ENTRY, Bundle

DUNDER = re.compile(r"^__\w+__$")


def short(qualname: str) -> str:
    return qualname.rsplit(".", 1)[-1]


@lru_cache(maxsize=None)
def tokens(path: Path) -> list[tuple[int, int, str, str]]:
    """(first line of its logical line, last line of it, name, style) for each NAME token."""
    toks = list(tokenize.generate_tokens(io.StringIO(path.read_text()).readline))
    out, start = [], None
    names = []
    for i, t in enumerate(toks):
        if start is None and t.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT):
            start = t.start[0]
        if t.type == tokenize.NAME:
            nxt = next((u for u in toks[i + 1:] if u.type not in (tokenize.NL, tokenize.COMMENT)), None)
            names.append((t.start[0], t.string, "call" if nxt and nxt.string == "(" else "reference"))
        if t.type == tokenize.NEWLINE:
            out += [(start, t.start[0], ln, name, style) for ln, name, style in names]
            names, start = [], None
    return [(first, last, ln, name, style) for first, last, ln, name, style in out]


@lru_cache(maxsize=None)
def signatures(path: Path) -> set[int]:
    """Lines that hold a def's decorators and signature: names there are not calls in the body."""
    out = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = min([d.lineno for d in node.decorator_list] + [node.lineno])
            out.update(range(first, node.body[0].lineno))
    return out


@lru_cache(maxsize=None)
def class_bases(path: Path) -> dict[str, list[str]]:
    """Class name -> base class names, for every class in a file."""
    def name(b: ast.expr) -> str:   # Base, mod.Base, Base[T]
        return b.id if isinstance(b, ast.Name) else b.attr if isinstance(b, ast.Attribute) \
            else name(b.value) if isinstance(b, ast.Subscript) else ""
    return {node.name: [name(b) for b in node.bases]
            for node in ast.walk(ast.parse(path.read_text())) if isinstance(node, ast.ClassDef)}


def items(bundle: Bundle) -> list[dict]:
    t = truth_mod.load(bundle)
    root = sandbox.root(bundle.repo)
    ran = {p: set(v) for p, v in t["lines"].items()}
    called = defaultdict(set)                       # (caller, callee) -> call lines
    for caller, callee, c_path, c_line, n, via in t["edges"]:
        if caller != ENTRY:
            called[(caller, callee)].add(c_line)

    by_name = defaultdict(list)                     # short name -> callable nodes
    classes = defaultdict(list)                     # class name -> its __init__ (own or inherited)
    bases = {}
    for k, n in bundle.nodes.items():
        if n["kind"] in ("function", "method") and not DUNDER.match(short(n["qualname"])):
            by_name[short(n["qualname"])].append(k)
        if n["kind"] == "module":
            bases.update(class_bases(root / n["path"]))
    inits = {n["qualname"].rsplit(".", 1)[0]: k for k, n in bundle.nodes.items() if n["qualname"].endswith(".__init__")}
    for cls in bases:
        seen, todo = set(), [cls]
        while todo:                                 # the first class up the bases that defines __init__
            c = todo.pop(0)
            if c in seen:
                continue
            seen.add(c)
            if c in inits:
                classes[cls].append(inits[c])
                break
            todo += bases.get(c, [])

    out = {}
    for caller, n in bundle.nodes.items():
        if n["kind"] == "lambda":
            continue
        mine = own_lines(bundle, caller) - signatures(root / n["path"])
        executed = ran.get(n["path"], set())
        for first, last, ln, name, style in tokens(root / n["path"]):
            if ln not in mine or not any(x in executed for x in range(first, last + 1)):
                continue
            targets = [(k, style) for k in by_name.get(name, [])] + [(k, "constructor") for k in classes.get(name, [])]
            for callee, how in targets:
                key = (caller, callee)
                it = out.setdefault(key, {"caller": caller, "callee": callee, "name": name, "lines": [],
                                          "style": how, "shared": len(by_name.get(name, [])) + len(classes.get(name, []))})
                it["lines"].append(ln)
                if how == "call":
                    it["style"] = "call"            # a call anywhere outranks a bare reference
    for key, it in out.items():
        it["lines"] = sorted(set(it["lines"]))
        it["label"] = key in called
        it["pycg"] = key in bundle.static_by_tool.get("pycg", set())
        it["pyright"] = key in bundle.static_by_tool.get("pyright", set())
    return sorted(out.values(), key=lambda i: (i["caller"], i["callee"]))


def unnamed(bundle: Bundle, its: list[dict]) -> list[tuple[str, str]]:
    """Calls that happened but whose target is never named in the caller."""
    t = truth_mod.load(bundle)
    have = {(i["caller"], i["callee"]) for i in its}
    real = {(c, x) for c, x, *_ in t["edges"] if c != ENTRY and c != x
            and bundle.nodes[x]["kind"] in ("function", "method")}
    return sorted(real - have)


def score(its: list[dict], predicted) -> dict:
    tp = sum(1 for i in its if predicted(i) and i["label"])
    fp = sum(1 for i in its if predicted(i) and not i["label"])
    fn = sum(1 for i in its if not predicted(i) and i["label"])
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 3), "recall": round(r, 3),
            "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}


BASELINES = {
    "name match": lambda i: True,
    "PyCG": lambda i: i["pycg"],
    "Pyright": lambda i: i["pyright"],
    "PyCG ∪ Pyright": lambda i: i["pycg"] or i["pyright"],
}


def categories(i: dict) -> list[str]:
    return ["all", "shared name" if i["shared"] > 1 else "unique name", i["style"]]
