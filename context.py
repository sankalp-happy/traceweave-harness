"""The slicer: what the model is shown for one task under one condition.

Both arms go through this one function with the same budget. The ONLY input
that differs is the caller set (`Bundle.callers`), so the only sections of
the prompt that can differ are the caller list and the excerpts those callers
pull in. `tests/test_harness.py` checks that on real tasks -- if anything else
ever differs between the arms, the comparison stops being causal.

The retrieval unit is the caller FUNCTION, as in code-graph RAG; excerpts are
windows around the lines of each retrieved caller that name the target. "Lines
of a caller" means its own body, not the bodies of functions nested in it --
otherwise a `<module>` caller would hand over the whole file. A dynamic-only
edge also contributes the line the tracer saw make the call (for a callback
invoked under another name, that line never names the target).

Design note, recorded rather than hidden: the first version located lines
through TraceWeave's AST call-site table. That misses attribute-style uses
(properties read as `x.name`), and the oracle showed it on click before any
model was run. The change applies identically to both arms.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from graph import Bundle, word

WINDOW = 2          # lines of context either side of a call site
DEF_LINES = 4       # lines shown after the target's def line
BUDGET_TOKENS = 6000
CHARS_PER_TOKEN = 4  # ponytail: char estimate, not a tokenizer; identical for both arms so it cannot bias them


@dataclass
class Context:
    prompt: str
    condition: str
    callers: list[str]
    shown: dict[str, set[int]] = field(default_factory=dict)  # path -> line numbers shown
    truncated: bool = False

    def shows(self, path: str, line: int) -> bool:
        return line in self.shown.get(path, ())


def own_lines(bundle: Bundle, key: str) -> set[int]:
    """A node's span minus the spans of nodes nested inside it (lambdas excepted:
    they share their line with the enclosing statement)."""
    n = bundle.nodes[key]
    lines = set(range(n["line"], n["end"] + 1))
    for other, m in bundle.nodes.items():
        if (other != key and m["path"] == n["path"] and m["kind"] != "lambda"
                and n["line"] <= m["line"] and m["end"] <= n["end"]
                and (m["line"], m["end"]) != (n["line"], n["end"])):
            lines -= set(range(m["line"], m["end"] + 1))
    return lines


def caller_sites(bundle: Bundle, caller: str, task: dict, root: Path) -> list[tuple[str, int]]:
    node = bundle.nodes[caller]
    src, pat = (root / node["path"]).read_text().splitlines(), word(task["name"])
    sites = {(node["path"], ln) for ln in own_lines(bundle, caller) if pat.search(src[ln - 1])}
    if caller in task["dynamic_only_callers"] and (caller, task["target"]) in bundle.runtime_site:
        sites.add(bundle.runtime_site[(caller, task["target"])])
    if not sites:  # an edge with no locatable call line: show the caller's head
        sites.add((node["path"], node["line"]))
    return sorted(sites)


def build(bundle: Bundle, task: dict, condition: str, root: Path,
          budget_tokens: int = BUDGET_TOKENS) -> Context:
    target = bundle.nodes[task["target"]]
    files: dict[str, list[str]] = {}

    def source(path: str) -> list[str]:
        if path not in files:
            files[path] = (root / path).read_text().splitlines()
        return files[path]

    def window(path: str, lo: int, hi: int) -> set[int]:
        return set(range(max(1, lo), min(len(source(path)), hi) + 1))

    shown: dict[str, set[int]] = {}
    shown.setdefault(target["path"], set()).update(
        window(target["path"], target["line"], min(target["end"], target["line"] + DEF_LINES)))

    callers = sorted(bundle.callers(task["target"], condition),
                     key=lambda c: (bundle.nodes[c]["path"], bundle.nodes[c]["line"], c))
    included, truncated = [], False
    for caller in callers:
        trial = {p: set(s) for p, s in shown.items()}
        for path, ln in caller_sites(bundle, caller, task, root):
            trial.setdefault(path, set()).update(window(path, ln - WINDOW, ln + WINDOW))
        if len(render_excerpts(trial, source)) > budget_tokens * CHARS_PER_TOKEN:
            truncated = True
            break
        shown, included = trial, included + [caller]

    caller_list = "\n".join(
        f"- {bundle.nodes[c]['qualname']}  ({bundle.nodes[c]['path']})" for c in included
    ) or "- (none found)"
    prompt = PROMPT.format(
        repo=bundle.name, qualname=target["qualname"], path=target["path"],
        line=target["line"], new=task["new_name"], callers=caller_list,
        excerpts=render_excerpts(shown, source),
    )
    return Context(prompt=prompt, condition=condition, callers=included, shown=shown, truncated=truncated)


def render_excerpts(shown: dict[str, set[int]], source) -> str:
    out = []
    for path in sorted(shown):
        lines, src, prev = sorted(shown[path]), source(path), None
        out.append(f"### {path}")
        for ln in lines:
            if prev is not None and ln != prev + 1:
                out.append("      ...")
            out.append(f"{ln:>5}| {src[ln - 1]}")
            prev = ln
        out.append("")
    return "\n".join(out)


PROMPT = """\
You are editing the Python repository `{repo}`.

Task: rename `{qualname}` (defined in {path}, line {line}) to `{new}`.
Update every reference so the project's existing test suite still passes.
Do not change any behaviour, and do not rename anything else.

You cannot see the whole repository. You are given the target's definition
and the functions a call graph reports as its callers, with line-numbered
excerpts. You may only edit lines that appear in the excerpts below.

## Callers of {qualname}, per the call graph
{callers}

## Source excerpts
{excerpts}
## Output
Return the edits as JSON. Each edit replaces one whole existing line, named by
its path and line number exactly as shown above; `text` is the complete new
line, indentation included. Lines you do not list are left unchanged.
"""

EDITS_SCHEMA = {
    "type": "object",
    "properties": {
        "edits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "line": {"type": "integer"},
                    "text": {"type": "string"},
                },
                "required": ["path", "line", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["edits"],
    "additionalProperties": False,
}
