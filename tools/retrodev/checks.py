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

import time

from . import repo, state
from .checks_run import (  # noqa: F401 - the other modules and the tests use them from here
    CHECK_PY,
    LINT_FIRST,
    UNIT_FIRST,
    ROW,
    SCRIPTS,
    _row_text,
    _stream,
    env_for,
    fails_lint,
    run_check_py,
    run_script,
    short_tmp,
)
from .checks_triggers import known, required, select, triggered  # noqa: F401 - as above
from .output import Failure


def budget(ctx, name: str) -> float:
    budgets = ctx.policy["checks"]["budgets"]
    return float(budgets.get(name, budgets["default"]))


def refuse_uncommitted_installs(ctx, todo: list[str], wanted: dict[str, str]) -> None:
    """Before anything runs: an install check is due and the tree has uncommitted changes. It installs the
    committed tree, so it could not pass this one; better said now than after a minute of other checks."""
    installs = [name for name in todo if name in SCRIPTS]
    changes = repo.dirty(ctx.top) if installs else []
    if changes:
        listed = ", ".join(line[3:] for line in changes[:3]) + (" ..." if len(changes) > 3 else "")
        raise Failure(
            f"{', '.join(installs)} must run ({wanted[installs[0]]}) and this tree has {len(changes)} uncommitted "
            f"change(s) ({listed}); nothing was run",
            "commit first: the clean install installs the committed tree (git add -A && git commit -m "
            "'<what changed>'), then python tools/retrodev check",
        )


def run(ctx, names: list[str], again: bool = False, full: bool = False, wait_for_commit: bool = False) -> int:
    """``wait_for_commit`` (check --watch): run the other checks on uncommitted changes and skip the install
    checks until a commit, instead of refusing up front."""
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
    if not wait_for_commit:
        refuse_uncommitted_installs(ctx, todo, wanted)
    started = time.monotonic()
    fast = [name for name in todo if name in CHECK_PY and name != "acceptance"]
    results = run_check_py(ctx, fast, env_for("fast"), record, ids) if fast else {}
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
    first = {
        row["name"]: row["detail"]
        for row in rows
        if row["state"] == "skipped" and row.get("detail") in (LINT_FIRST, UNIT_FIRST)
    }
    blocked = list(first)
    skipped = [name for name in skipped if name not in blocked]
    if failed:
        raise Failure(
            f"failed: {', '.join(failed)}" + (f"; {blocked[0]}: {first[blocked[0]]}" if blocked else ""),
            "read each failure's FIX line above, fix it, run "
            "python tools/retrodev check again (passing checks stay cached)",
        )
    if blocked:
        fix = (
            "python tools/check.py fix"
            if first[blocked[0]] == LINT_FIRST
            else "fix the unit failures (python tools/check.py unit)"
        )
        raise Failure(f"{blocked[0]}: {first[blocked[0]]}", f"{fix}, then python tools/retrodev check")
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
    if good:
        from . import ship  # ship imports gates, which imports this module

        step = ship.body_step(ctx, None if branch == "detached" else branch, record)
        if step:
            ctx.out.say(step)
            ctx.out.set(next=step)
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
