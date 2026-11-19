"""Step 4's checks, only what changed: tools/check.py runs them; retrodev decides which and remembers results.

    check                    the fast checks whose inputs changed since their last pass on this branch, plus the
                             real-engine run and the clean install when the branch changed what they cover
    check unit lint          just these        check --again    ignore earlier passes
    check --full             the fast checks, scaffold, acceptance and the clean install
    check --watch            run again on every file change or commit (Ctrl+C stops; watch.py)

Each check's inputs (policy.toml [checks.inputs]) are digested; a pass is kept per branch against that digest
and prints "ok (cached)" while nothing it reads changed. When every check the branch needs has passed on the
current tree, that tree's digest is recorded with the names of those checks: ship pushes only a tree that passed
everything the policy requires of it now. Times are printed against the budgets in policy.toml (measured cold
runs); a check over its budget twice in a row on the branch (each run's time is recorded) gets a warning that it
is slower than usual, never a failure: one slow run is load or a cold cache, not news.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

from . import repo, state
from .output import Failure

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


def known(ctx) -> list[str]:
    return list(ctx.policy["checks"]["inputs"])


def triggered(ctx) -> dict[str, str]:
    """{check: why} for the checks the branch's changes call for beyond the fast ones."""
    changed = repo.changed_files(ctx.top, ctx.remote_base)
    if changed is None:
        return {}
    found = {}
    for name, patterns in ctx.policy["checks"]["triggers"].items():
        hits = [path for path in changed if repo.matches(path, patterns)]
        if hits:
            found[name] = f"changed {hits[0]}" + (f" and {len(hits) - 1} more" if len(hits) > 1 else "")
    if "clean_install" in found:
        moved = repo.moved_or_deleted(ctx.top, ctx.remote_base)
        if moved:
            found["update"] = f"moved or deleted {moved[0]}" + (f" and {len(moved) - 1} more" if len(moved) > 1 else "")
    return found


def required(ctx) -> dict[str, str]:
    """What must pass on a tree before it may be shipped: the fast checks plus the triggered ones."""
    return {name: "fast" for name in ctx.policy["checks"]["fast"]} | triggered(ctx)


def select(ctx, names: list[str], full: bool, need: dict[str, str] | None = None) -> dict[str, str]:
    if names:
        unknown = [name for name in names if name not in known(ctx)]
        if unknown:
            raise Failure(f"unknown check: {', '.join(unknown)}", "use one of: " + ", ".join(known(ctx)))
        return {name: "asked" for name in names}
    wanted = dict(need if need is not None else required(ctx))
    if full:
        wanted |= {"scaffold": "--full", "acceptance": "--full", "clean_install": "--full"}
    return wanted


def budget(ctx, name: str) -> float:
    budgets = ctx.policy["checks"]["budgets"]
    return float(budgets.get(name, budgets["default"]))


def _stream(ctx, command: list[str], env: dict) -> tuple[int, list[str]]:
    """Run a command, showing its lines as they come (check.py's result rows in retrodev's columns)."""
    lines = []
    with subprocess.Popen(
        command,
        cwd=str(ctx.top),
        env=env,
        text=True,
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


def run_check_py(ctx, names: list[str], env: dict) -> dict[str, dict]:
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


def env_for(name: str) -> dict:
    env = dict(os.environ)
    if name == "acceptance":
        # The broker's socket path must stay short, and the run uses the toolchain setup put in place.
        env["TMPDIR"] = short_tmp()
        env.pop("HERMRETRO_DEPS_ROOT", None)
    return env


def run(ctx, names: list[str], again: bool = False, full: bool = False) -> int:
    branch = repo.branch(ctx.top) or "detached"
    record = state.load_branch(ctx.top, branch) if branch != "detached" else {"branch": branch, "checks": {}}
    record.setdefault("checks", {})
    ids = repo.file_ids(ctx.top)
    tree = repo.digest(ids)
    need = required(ctx)
    wanted = select(ctx, names, full, need)
    digests = {name: repo.digest(ids, ctx.policy["checks"]["inputs"][name]) for name in wanted}
    extra = {name: why for name, why in wanted.items() if why not in ("fast", "asked")}
    for name, why in extra.items():
        ctx.out.say(f"adding {name}: {why}")
    rows, todo = [], []
    for name in wanted:
        last = record["checks"].get(name, {})
        if not again and last.get("state") == "ok" and last.get("digest") == digests[name]:
            rows.append(
                {
                    "name": name,
                    "state": "ok",
                    "seconds": last.get("seconds", 0.0),
                    "cached": True,
                    "detail": "ok (cached)",
                }
            )
            ctx.out.say(_row_text("ok", name, 0.0, "ok (cached)"))
        else:
            todo.append(name)
    started = time.monotonic()
    fast = [name for name in todo if name in CHECK_PY and name != "acceptance"]
    results = run_check_py(ctx, fast, env_for("fast")) if fast else {}
    wall = time.monotonic() - started
    if "acceptance" in todo:
        results |= run_check_py(ctx, ["acceptance"], env_for("acceptance"))
    # The install checks install the committed HEAD: they run only when it is exactly the tree being checked, and
    # their pass is recorded against HEAD's own files (with uncommitted changes they would test other code).
    installs = [name for name in todo if name in SCRIPTS]
    uncommitted = installs if installs and repo.dirty(ctx.top) else []
    committed = repo.head_ids(ctx.top) if installs and not uncommitted else {}
    for name in todo:
        if name in uncommitted:
            detail = "not run: it installs the committed HEAD and this tree has uncommitted changes"
            results[name] = {"state": "skipped", "seconds": 0.0, "detail": detail, "more": []}
            ctx.out.say(_row_text("skipped", name, 0.0, detail))
        elif name in SCRIPTS:
            results[name] = run_script(ctx, name, env_for(name))
            digests[name] = repo.digest(committed, ctx.policy["checks"]["inputs"][name])
    for name in todo:
        result = results[name]
        if name in uncommitted:
            rows.append({"name": name, "cached": False, **result})
            continue
        record["checks"][name] = {
            "state": result["state"],
            "digest": digests[name],
            "seconds": result["seconds"],
            "at": state.now(),
            "detail": result["detail"],
        }
        rows.append(
            {
                "name": name,
                "state": result["state"],
                "seconds": result["seconds"],
                "cached": False,
                "detail": result["detail"],
                "more": result["more"],
            }
        )
    whole_fast = set(fast) >= set(ctx.policy["checks"]["fast"])
    last = record.get("durations") or {}
    warnings = budget_warnings(ctx, rows, wall if fast else None, whole_fast, last)
    record["durations"] = durations(rows, wall if fast and whole_fast else None, last)
    for line in warnings:
        ctx.out.say("warning: " + line)
    record["last_run"] = {
        "at": state.now(),
        "tree": tree,
        "rows": [{k: row[k] for k in ("name", "state", "seconds", "cached")} for row in rows],
        "fast_wall": round(wall, 1) if fast else None,
    }
    may_skip = set(ctx.policy["checks"]["may_skip"])
    all_digests = {name: repo.digest(ids, ctx.policy["checks"]["inputs"][name]) for name in need}
    good = all(
        (last := record["checks"].get(name, {})).get("digest") == all_digests[name]
        and (last.get("state") == "ok" or (last.get("state") == "skipped" and name in may_skip))
        for name in need
    )
    if good:
        record.update(passed_tree=tree, passed_at=state.now(), passed_checks=sorted(need))
    else:  # a pass recorded earlier is taken back: this run shows the tree no longer passes everything it needs
        for key in ("passed_tree", "passed_at", "passed_checks"):
            record.pop(key, None)
    if branch != "detached":
        state.save_branch(ctx.top, record)
    ctx.out.set(
        branch=branch,
        tree=tree,
        checks=rows,
        warnings=warnings,
        tree_passed=good,
        fast_wall=round(wall, 1) if fast else None,
    )
    failed = [row["name"] for row in rows if row["state"] == "FAILED"]
    skipped = [
        row["name"]
        for row in rows
        if row["state"] == "skipped" and row["name"] not in may_skip and row["name"] not in uncommitted
    ]
    if failed:
        raise Failure(
            f"failed: {', '.join(failed)}",
            "read each failure's FIX line above, fix it, run "
            "python tools/retrodev check again (passing checks stay cached)",
        )
    if uncommitted:
        raise Failure(
            f"not run on uncommitted changes: {', '.join(uncommitted)} (an install gets only what is committed)",
            "commit first, then python tools/retrodev check",
        )
    if skipped:
        raise Failure(
            f"skipped (a tool is missing): {', '.join(skipped)}; a skipped check proves nothing",
            "install what each skip names (python tools/retrodev doctor lists it), then check again",
        )
    ran = sum(not row["cached"] for row in rows)
    ctx.out.say(
        f"all {len(rows)} passed ({ran} ran, {len(rows) - ran} cached)"
        + (f", fast checks {wall:.1f} s wall" if fast else "")
        + ("; this tree may ship" if good else "")
    )
    return 0


FAST_TOTAL = "fast_total"


def over(ctx, name: str, seconds: float) -> bool:
    limit = float(ctx.policy["checks"]["budgets"][name]) if name == FAST_TOTAL else budget(ctx, name)
    return seconds > limit


def durations(rows: list[dict], wall: float | None, before: dict) -> dict:
    """{check: seconds} of each check's latest run on the branch (fast_total: the fast checks together, when all
    of them ran). A cached row or a check that did not run keeps its last run's time."""
    found = dict(before)
    for row in rows:
        if not row["cached"]:
            found[row["name"]] = round(float(row["seconds"]), 1)
    if wall is not None:
        found[FAST_TOTAL] = round(wall, 1)
    return found


def budget_warnings(
    ctx, rows: list[dict], wall: float | None, whole_fast: bool, before: dict | None = None
) -> list[str]:
    """A warning for each check over its budget in this run and in its last run on the branch (``before``: the
    recorded durations): a single slow run says nothing (load, a cold cache), two in a row say something got slower."""
    before = before or {}
    found = []
    for row in rows:
        limit = budget(ctx, row["name"])
        if (
            not row["cached"]
            and over(ctx, row["name"], row["seconds"])
            and over(ctx, row["name"], before.get(row["name"], 0.0))
        ):
            found.append(
                f"{row['name']} took {row['seconds']:.1f} s, over its {limit:g} s budget twice in a row: slower than "
                "usual "
                "(machines and load differ; not a failure; if it repeats on an idle machine, find what got slow)"
            )
    total = float(ctx.policy["checks"]["budgets"][FAST_TOTAL])
    if wall is not None and whole_fast and wall > total and before.get(FAST_TOTAL, 0.0) > total:
        found.append(
            f"the fast checks took {wall:.1f} s together, over their {total:g} s budget twice in a row: slower than "
            "usual (machines and load differ)"
        )
    return found
