"""Who performs the rename.

  oracle              No model. Renames the target's name on every line the
                      context shows, and nothing else. It is the ceiling a
                      perfect editor could reach with that context, so it
                      separates "the context was missing the site" from
                      "the model fumbled a site it could see". Free, offline.
  claude:<model-id>   Claude via the official Anthropic SDK, structured JSON
                      output. Needs `pip install anthropic` and credentials.
  groq:<model-id>     An open-weight model on Groq, e.g. groq:openai/gpt-oss-20b,
                      with schema-enforced JSON output. Standard library only;
                      reads GROQ_API_KEY from the environment or `.env`.
  replay:<file>       Re-applies the responses recorded in a results file, so
                      a run can be re-scored on a machine with no network or key.

Every model returns (edits, meta). `meta` is written into the results row
verbatim: raw response, served-by model, stop reason, token usage.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from context import EDITS_SCHEMA, Context
from graph import HERE, word


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


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def dotenv() -> dict:
    f = HERE / ".env"
    if not f.exists():
        return {}
    pairs = (ln.removeprefix("export ").split("=", 1) for ln in f.read_text().splitlines()
             if "=" in ln and not ln.lstrip().startswith("#"))
    return {k.strip(): v.strip().strip("'\"") for k, v in pairs}


def _groq_post(body: bytes, waits=(5, 10, 20, 40, 60, 60)) -> dict:
    key = os.environ.get("GROQ_API_KEY") or dotenv().get("GROQ_API_KEY")
    if not key:
        raise SystemExit("GROQ_API_KEY is not set: export it or put it in .env")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
               "User-Agent": "traceweave-harness"}  # the default urllib agent is blocked
    for wait in waits:
        try:
            req = urllib.request.Request(GROQ_URL, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:500].decode(errors="replace")
            if exc.code == 400 and ("json_validate_failed" in detail or "output_parse_failed" in detail):
                return {"error": f"output failed the schema: {detail}"}
            if exc.code != 429 and exc.code < 500:
                raise SystemExit(f"Groq said HTTP {exc.code}: {detail}")
            pause = float(exc.headers.get("retry-after") or wait)
            if pause > 300:  # a daily cap, not a per-minute one
                raise SystemExit(f"Groq's free-tier daily limit for this model is used up; it frees up in about "
                                 f"{max(1, round(pause / 60))} minutes. Try another model, or try again then.")
            time.sleep(pause)
        except OSError:  # timeouts, resets, DNS: the same request is sent again
            time.sleep(wait)
    # Never record an outage as a model failure; the run resumes where it stopped.
    raise SystemExit("Groq is still rate-limiting or failing; rerun the same command later")


def groq_json(model: str, prompt: str, schema: dict, effort: str = "medium",
              patient: bool = True) -> tuple[dict | None, dict]:
    """One JSON answer from a Groq model, at temperature 0. gpt-oss models get
    the schema enforced (strict JSON-schema output); others get JSON mode with
    the schema in a system message, so the user prompt is the same bytes for
    every model. A reply Groq cannot parse is asked for again, up to three
    tries in all; after that the answer is None and `meta` says why."""
    strict = "gpt-oss" in model
    body = json.dumps({
        "model": model, "temperature": 0, "seed": 0, "max_tokens": 8192,
        "response_format": {"type": "json_schema", "json_schema": {"name": "answer", "strict": True, "schema": schema}}
        if strict else {"type": "json_object"},
        **({"reasoning_effort": effort} if strict else {}),
        "messages": ([] if strict else [{"role": "system", "content":
                     "Reply with one JSON object that matches this JSON Schema, and nothing else:\n" + json.dumps(schema)}])
        + [{"role": "user", "content": prompt}],
    }).encode()
    # A batch run waits out rate limits; a live demo must not keep a room waiting for minutes.
    waits = (5, 10, 20, 40, 60, 60) if patient else (3, 6)
    for attempts in (1, 2, 3):
        try:
            data = _groq_post(body, waits)
        except SystemExit as exc:
            if patient:
                raise
            raise SystemExit(str(exc) if "daily limit" in str(exc)
                             else "Groq is busy right now (its per-minute limit); try again in a minute, or pick another model.")
        if "error" not in data:
            break
    if "error" in data:
        return None, data | {"attempts": attempts}
    choice, usage = data["choices"][0], data.get("usage", {})
    text = choice["message"].get("content") or ""
    meta = {"served_by": data.get("model"), "stop_reason": choice.get("finish_reason"),
            "usage": {"input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens")},
            "raw": text, "reasoning": choice["message"].get("reasoning"), "attempts": attempts}
    try:
        obj = json.loads(re.sub(r"^```(?:json)?|```$", "", text.strip()).strip())
        return (obj, meta) if isinstance(obj, dict) else (None, meta | {"error": "not a JSON object"})
    except json.JSONDecodeError as exc:
        return None, meta | {"error": f"unparseable: {exc}"}


def groq(model: str, effort: str, patient: bool = True):
    """The rename editor on Groq: one JSON list of {path, line, old, new} edits."""
    def run(task: dict, ctx: Context, root: Path) -> tuple[list[dict], dict]:
        obj, meta = groq_json(model, ctx.prompt, EDITS_SCHEMA, effort, patient)
        edits = (obj or {}).get("edits")
        if obj is not None and not isinstance(edits, list):
            return [], meta | {"error": "edits is not a list"}
        return edits or [], meta

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


def load(spec: str, effort: str = "medium", patient: bool = True):
    kind, _, arg = spec.partition(":")
    if kind == "oracle":
        return oracle
    if kind == "claude":
        return claude(arg or "claude-opus-5-5", effort)
    if kind == "groq":
        return groq(arg or "openai/gpt-oss-20b", effort, patient)
    if kind == "replay":
        return replay(Path(arg))
    raise SystemExit(f"unknown model {spec!r}: use oracle, claude:<model-id>, groq:<model-id> or replay:<results.jsonl>")
