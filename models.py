"""Who performs the rename.

  oracle              No model. Renames the target's name on every line the
                      context shows, and nothing else. It is the ceiling a
                      perfect editor could reach with that context, so it
                      separates "the context was missing the site" from
                      "the model fumbled a site it could see". Free, offline.
  claude:<model-id>   Claude via the official Anthropic SDK, structured JSON
                      output. Needs `pip install anthropic` and credentials.
  replay:<file>       Re-applies the responses recorded in a results file, so
                      a run can be re-scored on a machine with no network or key.

Every model returns (edits, meta). `meta` is written into the results row
verbatim: raw response, served-by model, stop reason, token usage.
"""
from __future__ import annotations

import json
from pathlib import Path

from context import EDITS_SCHEMA, Context
from graph import word


def oracle(task: dict, ctx: Context, root: Path) -> tuple[list[dict], dict]:
    pat, edits = word(task["name"]), []
    for path, lines in sorted(ctx.shown.items()):
        src = (root / path).read_text().splitlines()
        for ln in sorted(lines):
            if pat.search(src[ln - 1]):
                edits.append({"path": path, "line": ln, "text": pat.sub(task["new_name"], src[ln - 1])})
    return edits, {}


def claude(model: str, effort: str):
    import anthropic  # imported here so oracle and replay runs need no SDK

    client = anthropic.Anthropic()

    def run(task: dict, ctx: Context, root: Path) -> tuple[list[dict], dict]:
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            # A refusal would otherwise end the task; the served-by model is
            # recorded below so any row a fallback answered is visible, not mixed in.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": effort,
                           "format": {"type": "json_schema", "schema": EDITS_SCHEMA}},
            messages=[{"role": "user", "content": ctx.prompt}],
        )
        meta = {
            "served_by": response.model,
            "stop_reason": response.stop_reason,
            "usage": {"input_tokens": response.usage.input_tokens,
                      "output_tokens": response.usage.output_tokens},
        }
        if response.stop_reason == "refusal":
            return [], meta | {"error": "refusal"}
        text = next((b.text for b in response.content if b.type == "text"), "")
        meta["raw"] = text
        try:
            return json.loads(text)["edits"], meta
        except (json.JSONDecodeError, KeyError) as exc:
            return [], meta | {"error": f"unparseable: {exc}"}

    return run


def replay(path: Path):
    recorded = {}
    for line in path.read_text().splitlines():
        row = json.loads(line)
        recorded[(row["task"], row["condition"])] = row

    def run(task: dict, ctx: Context, root: Path) -> tuple[list[dict], dict]:
        row = recorded.get((task["id"], ctx.condition))
        if row is None:
            return [], {"error": "not in replay file"}
        return row["edits"], row.get("model_meta", {}) | {"replayed_from": row["model"]}

    return run


def load(spec: str, effort: str = "medium"):
    kind, _, arg = spec.partition(":")
    if kind == "oracle":
        return oracle
    if kind == "claude":
        return claude(arg or "claude-opus-5-5", effort)
    if kind == "replay":
        return replay(Path(arg))
    raise SystemExit(f"unknown model {spec!r}: use oracle, claude:<model-id> or replay:<results.jsonl>")
