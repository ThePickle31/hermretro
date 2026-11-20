"""How `check` runs tools/check.py and the install scripts (checks.py decides what runs and keeps the results):
check.py's rows shown in retrodev's columns as they come, and scaffold run only once lint passes.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

from . import repo

ROW = re.compile(r"^\s*(ok|skipped|FAILED)  (\S+)\s+([\d.]+) s(?:  (.*))?$")
CHECK_PY = ("unit", "bundle", "lint", "page", "scan", "scaffold", "acceptance")
SCRIPTS = {
    "clean_install": ["tools/ci/clean_install_check.py"],
    "update": ["tools/ci/clean_install_check.py", "--update-from"],
}


def short_tmp() -> str:
    """A temp folder short enough for Unix sockets (macOS allows 104 characters, Linux 108); as tools/check.py."""
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    return runtime if runtime and Path(runtime).is_dir() and len(runtime) < 40 else "/tmp"


def _stream(ctx, command: list[str], env: dict):
    """Run a command, showing its lines as they come (check.py's result rows in retrodev's columns): (exit code,
    lines)."""
    lines = []
    with subprocess.Popen(
        command,
        cwd=str(ctx.top),
        env=env,
        encoding="utf-8",
        errors="replace",  # a tool's line that is not UTF-8 shows with U+FFFD; it never stops the run
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    ) as process:
        assert process.stdout is not None
        for line in process.stdout:
            lines.append(line.rstrip("\n"))
            ctx.out.say(_row_text(*_row(line)) if ROW.match(line) else line.rstrip("\n"))
    return process.returncode, lines


def _row(line: str) -> tuple[str, str, float, str]:
    match = ROW.match(line)
    assert match
    return match.group(1), match.group(2), float(match.group(3)), match.group(4) or ""


def _row_text(status: str, name: str, seconds: float, detail: str) -> str:
    return f"{status:>7}  {name:<13} {seconds:5.1f} s  {detail}"


def check_py(ctx, names: list[str], env: dict) -> dict:
    """One tools/check.py run of ``names`` (together, as check.py runs them): its result per check."""
    code, lines = _stream(ctx, [sys.executable, "tools/check.py", *names], env)
    results, current = {}, None
    for line in lines:
        if ROW.match(line):
            status, name, seconds, detail = _row(line)
            current = results[name] = {"state": status, "seconds": seconds, "detail": detail, "more": []}
        elif current is not None and line.strip():
            current["more"].append(line.strip())
    for name in names:
        if name not in results:
            results[name] = {
                "state": "FAILED",
                "seconds": 0.0,
                "detail": f"tools/check.py exited {code} without a result for {name}",
                "more": lines[-10:],
            }
    return results


def run_check_py(ctx, names: list[str], env: dict, record: dict | None = None, ids: dict | None = None) -> dict:
    """check.py's result per check. With ``record`` and ``ids``, when scaffold is due: lint runs first, by itself,
    and on a tree that fails lint or page (in this run, or as recorded for these very inputs) scaffold is recorded
    as skipped without running (new's generated code is linted and page-tested, so such a failure anywhere fails
    scaffold too, after a minute and more); the other checks run beside scaffold once lint passed. check.py
    scaffold reuses page's row of the same run, and a pass recorded for these inputs goes to it in
    RD_SCAFFOLD_BASE, so the tree's page suite runs once."""
    if record is None or "scaffold" not in names:
        return check_py(ctx, names, env)
    first = ["lint"] if "lint" in names else []
    results = check_py(ctx, first, env) if first else {}
    rest = [name for name in names if name not in first and name != "scaffold"]
    failing = next(
        (name for name in ("lint", "page") if name not in rest and fails(ctx, results, record, ids, name)), ""
    )
    if failing:
        results |= check_py(ctx, rest, env) if rest else {}
        why = LINT_FIRST if failing == "lint" else PAGE_FIRST
        results["scaffold"] = {"state": "skipped", "seconds": 0.0, "detail": why, "more": []}
        ctx.out.say(_row_text("skipped", "scaffold", 0.0, why))
    else:
        known = [name for name in ("page", "unit") if name not in names and passed(ctx, record, ids, name)]
        results |= check_py(ctx, rest + ["scaffold"], {**env, "RD_SCAFFOLD_BASE": ",".join(known)})
    return results


LINT_FIRST = "skipped: the tree fails lint (fix lint first)"
UNIT_FIRST = "skipped: the tree fails unit (fix unit first)"  # tools/check.py scaffold's skip in its nested mode
PAGE_FIRST = "skipped: the tree fails page (fix page first)"  # tools/check.py scaffold's skip: page fails already


def inputs_digest(ctx, ids: dict, name: str) -> str:
    """The digest of what ``name`` reads: the files its [checks.inputs] patterns match, less those its
    [checks.input_ignore] patterns name (files the patterns cover that the check is shown never to read)."""
    policy = ctx.policy["checks"]
    return repo.digest(ids, policy["inputs"][name], policy.get("input_ignore", {}).get(name, []))


def recorded(ctx, record: dict, ids: dict, name: str) -> str:
    """``name``'s recorded state when it was recorded for these very inputs, else ""."""
    last = record.get("checks", {}).get(name, {})
    same = last.get("digest") == inputs_digest(ctx, ids, name)
    return last.get("state", "") if same else ""


def passed(ctx, record: dict, ids: dict, name: str) -> bool:
    return recorded(ctx, record, ids, name) == "ok"


def fails(ctx, results: dict, record: dict, ids: dict, name: str = "lint") -> bool:
    if name in results:
        return results[name]["state"] == "FAILED"
    return recorded(ctx, record, ids, name) == "FAILED"


def run_script(ctx, name: str, env: dict) -> dict:
    command = [sys.executable, *SCRIPTS[name]]
    ctx.out.say(f"running {shlex.join(SCRIPTS[name])} ...")
    started = time.monotonic()
    code, lines = _stream(ctx, command, env)
    seconds = time.monotonic() - started
    tail = [line for line in lines if line.strip()][-1:] or [""]
    result = {"state": "ok" if code == 0 else "FAILED", "seconds": round(seconds, 1), "detail": tail[0], "more": []}
    if code:
        result["more"] = [line for line in lines if line.strip()][-15:]
    ctx.out.say(_row_text(result["state"], name, seconds, result["detail"]))
    return result


def env_for(name: str, extra: dict | None = None) -> dict:
    """A check's process environment: a copy of os.environ plus ``extra`` (os.environ itself is never changed)."""
    env = {**os.environ, **(extra or {})}
    if name == "acceptance":
        # The broker's socket path must stay short, and the run uses the toolchain setup put in place.
        env["TMPDIR"] = short_tmp()
        env.pop("HERMRETRO_DEPS_ROOT", None)
    return env
