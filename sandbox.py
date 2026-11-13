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

import contextlib
import fcntl
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
TIMEOUT = int(os.environ.get("TW_TIMEOUT", 600))   # traced corpus suites need longer


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


@contextlib.contextmanager
def lock(repo: dict):
    """One user of a checkout at a time, across processes: a batch run and the
    live demo would otherwise apply edits over each other."""
    WORK.mkdir(parents=True, exist_ok=True)
    with open(WORK / f"{repo['name']}.lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def reset(repo: dict) -> None:
    git(root(repo), "checkout", "-q", "--", ".")
    git(root(repo), "clean", "-qfd")


def plan(repo: dict, edits: list[dict]) -> tuple[dict[Path, list[str]], int, int]:
    """The edited files, in memory. Two edit shapes, both one existing line:

      {path, line, text}       the whole new line (the oracle, and recorded runs)
      {path, line, old, new}   every `old` on that line becomes `new` (the LLM
                               prompt asks for this one, so an LLM never has to
                               retype indentation)

    Anything malformed is rejected, never guessed at."""
    r, files, applied, rejected = root(repo), {}, 0, 0
    for e in edits:
        path = (r / str(e.get("path", ""))).resolve() if isinstance(e, dict) else None
        line = e.get("line") if path else None
        if path is None or r.resolve() not in path.parents or not path.is_file() or not isinstance(line, int):
            rejected += 1
            continue
        lines = files.setdefault(path, path.read_text().splitlines(keepends=True))
        if not 1 <= line <= len(lines):
            rejected += 1
            continue
        current, ending = lines[line - 1].rstrip("\n"), "\n" if lines[line - 1].endswith("\n") else ""
        if "text" in e:
            new_line = e["text"]
        elif isinstance(e.get("old"), str) and e["old"] and e["old"] in current and isinstance(e.get("new"), str):
            new_line = current.replace(e["old"], e["new"])
        else:
            new_line = None
        if not isinstance(new_line, str) or "\n" in new_line.rstrip("\n"):
            rejected += 1
            continue
        lines[line - 1] = new_line.rstrip("\n") + ending
        applied += 1
    return files, applied, rejected


def preview(repo: dict, edits: list[dict]) -> dict:
    """What `apply` would change, line by line, without touching the checkout."""
    files, applied, rejected = plan(repo, edits)
    r, changed = root(repo).resolve(), []
    for path, lines in files.items():
        before = path.read_text().splitlines()
        for n, (old, new) in enumerate(zip(before, (ln.rstrip("\n") for ln in lines)), 1):
            if old != new:
                changed.append({"path": str(path.relative_to(r)), "line": n, "before": old, "after": new})
    return {"applied": applied, "rejected": rejected, "lines": changed}


def apply(repo: dict, edits: list[dict]) -> dict:
    r = root(repo)
    files, applied, rejected = plan(repo, edits)
    broken = None
    for path, lines in files.items():
        path.write_text("".join(lines))
        try:
            compile("".join(lines), str(path.relative_to(r.resolve())), "exec")
        except SyntaxError as exc:  # why the suite will not even collect
            broken = broken or f"{type(exc).__name__}: {exc.msg} ({exc.filename}, line {exc.lineno})"
    return {"applied": applied, "rejected": rejected, **({"syntax_error": broken} if broken else {})}


SUMMARY = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|deselected)")


def run_tests(repo: dict, on_event=None, trace: str | None = None, extra_env: dict | None = None) -> dict:
    """Run the suite once. With `on_event`, the live plugin (live/tw_live.py)
    reports progress while it runs, and `trace` names one function whose
    callers it reports; the verdict is computed the same way either way."""
    r = root(repo)
    env = os.environ | {
        "PYTHONPATH": str(r / repo["src_root"]),
        # Bytecode caches are keyed on mtime+size; an edit and its revert in the
        # same second could otherwise run stale bytecode.
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=no", "-rfE"]
    keep = ()
    if on_event:
        read_fd, write_fd = os.pipe()
        keep = (write_fd,)
        env |= {"PYTHONPATH": env["PYTHONPATH"] + os.pathsep + str(HERE / "live"),
                "TW_EVENTS_FD": str(write_fd), **({"TW_TRACE": trace} if trace else {})}
        cmd += ["-p", "tw_live"]
    env |= extra_env or {}
    t0 = time.monotonic()
    proc = subprocess.Popen(cmd + [repo["tests"]], cwd=r, env=env, pass_fds=keep, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if on_event:
        os.close(write_fd)
        reader = threading.Thread(daemon=True, target=lambda: [
            on_event(json.loads(line)) for line in os.fdopen(read_fd)])
        reader.start()
    try:
        out, err = proc.communicate(timeout=TIMEOUT)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        out, err, rc = "", "", -1
    if on_event:
        reader.join(5)
    counts = {"passed": 0, "failed": 0, "errors": 0}
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    for n, kind in SUMMARY.findall(tail):
        counts["errors" if kind.startswith("error") else kind] = int(n)
    bad = sorted({ln.split(" ", 1)[1].split(" - ")[0] for ln in out.splitlines()
                  if ln.startswith(("FAILED ", "ERROR "))})
    result = {"rc": rc, **{k: counts.get(k, 0) for k in ("passed", "failed", "errors")},
              "bad": bad, "seconds": round(time.monotonic() - t0, 2)}
    if rc not in (0, 1):  # the suite never ran: keep pytest's own last word on why
        lines = [ln for ln in (out or err).splitlines() if ln.strip()]
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
