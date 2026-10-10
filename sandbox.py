"""The working copy, the edits, and the oracle: the repo's own test suite.

One pinned checkout per repo under `work/`. Every attempt starts from a
`git checkout` + `git clean` reset, so no attempt can see another's edits.

A task passes when the suite, after the edit, gives the same result as the
untouched checkout: the same number of passing tests, and no failure or error
that the baseline did not already have. Exit code alone is not enough -- a
rename that breaks an import can turn 1,939 passes into one collection error,
and some suites (toolz here) already fail a test at baseline.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
TIMEOUT = 600


def root(repo: dict) -> Path:
    return WORK / repo["name"]


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def fetch(repo: dict) -> Path:
    """Shallow-fetch exactly the pinned commit. Idempotent."""
    r = root(repo)
    if not (r / ".git").exists():
        r.mkdir(parents=True, exist_ok=True)
        git(r, "init", "-q")
        git(r, "remote", "add", "origin", repo["url"])
        git(r, "fetch", "-q", "--depth", "1", "origin", repo["sha"])
        git(r, "checkout", "-q", "FETCH_HEAD")
    head = git(r, "rev-parse", "HEAD").strip()
    if head != repo["sha"]:
        raise SystemExit(f"{r} is at {head[:12]}, bundle is pinned to {repo['sha'][:12]}")
    return r


def reset(repo: dict) -> None:
    git(root(repo), "checkout", "-q", "--", ".")
    git(root(repo), "clean", "-qfd")


def apply(repo: dict, edits: list[dict]) -> dict:
    """Whole-line replacements. Anything malformed is rejected, never guessed at."""
    r, files, applied, rejected = root(repo), {}, 0, []
    for e in edits:
        path = (r / str(e.get("path", ""))).resolve()
        line = e.get("line")
        if r.resolve() not in path.parents or not path.is_file() or not isinstance(line, int):
            rejected.append(e)
            continue
        lines = files.setdefault(path, path.read_text().splitlines(keepends=True))
        text = e.get("text")
        if not 1 <= line <= len(lines) or not isinstance(text, str) or "\n" in text.rstrip("\n"):
            rejected.append(e)
            continue
        ending = "\n" if lines[line - 1].endswith("\n") else ""
        lines[line - 1] = text.rstrip("\n") + ending
        applied += 1
    for path, lines in files.items():
        path.write_text("".join(lines))
    return {"applied": applied, "rejected": len(rejected)}


SUMMARY = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|deselected)")


def run_tests(repo: dict) -> dict:
    r = root(repo)
    env = os.environ | {
        "PYTHONPATH": str(r / repo["src_root"]),
        # Bytecode caches are keyed on mtime+size; an edit and its revert in the
        # same second could otherwise run stale bytecode.
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=no", "-rfE",
             repo["tests"]],
            cwd=r, env=env, capture_output=True, text=True, timeout=TIMEOUT)
        out, rc = proc.stdout, proc.returncode
    except subprocess.TimeoutExpired:
        out, rc = "", -1
    counts = {"passed": 0, "failed": 0, "errors": 0}
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    for n, kind in SUMMARY.findall(tail):
        counts["errors" if kind.startswith("error") else kind] = int(n)
    bad = sorted({ln.split(" ", 1)[1].split(" - ")[0] for ln in out.splitlines()
                  if ln.startswith(("FAILED ", "ERROR "))})
    result = {"rc": rc, **{k: counts.get(k, 0) for k in ("passed", "failed", "errors")},
              "bad": bad, "seconds": round(time.monotonic() - t0, 2)}
    if rc not in (0, 1):  # the suite never ran: keep pytest's own last word on why
        lines = [ln for ln in (out + proc.stderr if rc != -1 else "").splitlines() if ln.strip()]
        result["note"] = lines[-1][:300] if lines else ("timed out" if rc == -1 else "")
    return result


def baseline(repo: dict, refresh: bool = False) -> dict:
    f = WORK / f"{repo['name']}.baseline.json"
    if f.exists() and not refresh:
        return json.loads(f.read_text())
    reset(repo)
    result = run_tests(repo)
    if result["rc"] not in (0, 1) or not result["passed"]:
        raise SystemExit(f"{repo['name']}: the untouched suite does not run "
                         f"(rc={result['rc']}); fix the environment before scoring anything")
    f.write_text(json.dumps(result, indent=1))
    return result


def verdict(result: dict, base: dict) -> bool:
    return (result["rc"] in (0, 1) and result["passed"] == base["passed"]
            and set(result["bad"]) <= set(base["bad"]))
