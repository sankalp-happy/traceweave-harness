"""pytest plugin for the live demo, loaded with `-p tw_live` (only by `tw.py ui`).

Writes one JSON object per line to the file descriptor named in TW_EVENTS_FD.
pytest captures fds 1 and 2 around every test; this one it leaves alone, so
events arrive while the suite is still running.

With TW_TRACE=<path>::<qualname> it also reports who calls that one function,
through sys.monitoring (Python 3.12+): every other code object turns its own
event off the first time it starts, so the suite runs at close to full speed.
"""
import json
import os
import re
import sys
import time

_out = os.fdopen(int(os.environ["TW_EVENTS_FD"]), "w", buffering=1)
_counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
_state = {"test": None, "file": None, "calls": 0, "sites": 0, "last": 0.0}
# Comprehension and generator scopes fold into their enclosing function, as in build_bundle.py.
_SYNTHETIC = re.compile(r"\.<(genexpr|listcomp|dictcomp|setcomp)>")


def _emit(**event):
    _out.write(json.dumps(event) + "\n")


def _trace(target):
    path, qualname = target.split("::", 1)
    root, seen, mon = os.getcwd() + os.sep, set(), sys.monitoring
    tool = mon.PROFILER_ID
    mon.use_tool_id(tool, "traceweave-live")

    def on_start(code, offset):
        if code.co_qualname.replace(".<locals>", "") != qualname or not code.co_filename.endswith(path):
            return mon.DISABLE
        _state["calls"] += 1
        caller = sys._getframe(2)  # 0 is this callback, 1 the target's own frame
        where = (caller.f_code.co_filename, caller.f_code.co_qualname, caller.f_lineno)
        if where not in seen:
            seen.add(where)
            _emit(type="call", path=where[0].removeprefix(root),
                  qualname=_SYNTHETIC.sub("", where[1].replace(".<locals>", "")),
                  line=where[2], test=_state["test"])

    mon.register_callback(tool, mon.events.PY_START, on_start)
    mon.set_events(tool, mon.events.PY_START)


def _trace_all(package, tests, out_path):
    """Every call into the package, with the line it came from, and every
    package line that ran. Calls that pass through library code (a callback
    handed to the standard library) are charged to the nearest package or
    test frame below them, and flagged."""
    root, mon = os.getcwd() + os.sep, sys.monitoring
    tool = mon.PROFILER_ID
    mon.use_tool_id(tool, "traceweave-all")
    edges, lines = {}, set()
    norm = lambda q: q.replace(".<locals>", "")
    rel = lambda f: f.removeprefix(root)

    def on_start(code, offset):
        if not code.co_filename.startswith(package):
            return mon.DISABLE
        f, via = sys._getframe(2), False
        while f is not None and not f.f_code.co_filename.startswith((package, tests)):
            f, via = f.f_back, True
        caller = (rel(f.f_code.co_filename), norm(f.f_code.co_qualname), f.f_lineno) if f else ("<external>", "", 0)
        key = caller + (rel(code.co_filename), norm(code.co_qualname), code.co_firstlineno, via)
        edges[key] = edges.get(key, 0) + 1
        _state["calls"] += 1
        _state["sites"] = len(edges)

    def on_line(code, line):
        if code.co_filename.startswith(package):
            lines.add((rel(code.co_filename), line))
        return mon.DISABLE

    def dump():
        mon.set_events(tool, 0)
        by_file = {}
        for path, n in lines:
            by_file.setdefault(path, []).append(n)
        with open(out_path, "w") as fh:
            json.dump({"edges": [list(k) + [n] for k, n in edges.items()],
                       "lines": {p: sorted(v) for p, v in by_file.items()}}, fh)

    mon.register_callback(tool, mon.events.PY_START, on_start)
    mon.register_callback(tool, mon.events.LINE, on_line)
    mon.set_events(tool, mon.events.PY_START | mon.events.LINE)
    return dump


if os.environ.get("TW_TRACE"):
    _trace(os.environ["TW_TRACE"])
_dump_all = (_trace_all(os.environ["TW_TRACE_ALL"], os.environ["TW_TESTS"], os.environ["TW_TRACE_OUT"])
             if os.environ.get("TW_TRACE_ALL") else None)


def _progress(force=False):
    now = time.monotonic()
    if force or now - _state["last"] > 0.05:
        _state["last"] = now
        _emit(type="progress", calls=_state["calls"], sites=_state["sites"], **_counts)


def pytest_collection_finish(session):
    _emit(type="collected", total=len(session.items))


def pytest_runtest_logstart(nodeid, location):
    _state["test"] = nodeid
    path = nodeid.split("::", 1)[0]
    if path != _state["file"]:
        _state["file"] = path
        _emit(type="file", path=path)


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        kind = {"passed": "passed", "skipped": "skipped"}.get(
            report.outcome, "failed" if report.when == "call" else "errors")
        _counts[kind] += 1
        _progress()


def pytest_sessionfinish(session):
    _progress(force=True)
    if _dump_all:
        _dump_all()
