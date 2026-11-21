"""Step 4's checks, only what changed: tools/check.py runs them; retrodev decides which and remembers results.

    check                    the fast checks (unit, bundle, lint, page, scan) whose inputs changed since their
                             last pass on this branch: what a draft push needs
    check unit lint          just these (also the slow ones: scaffold, acceptance, clean_install, update)
    check --again            ignore earlier passes
    check --full             the fast checks, scaffold, acceptance and the clean install
    check --watch            run again on every file change or commit (Ctrl+C stops; watch.py)

Each check's inputs (policy.toml [checks.inputs]) are digested; a pass is kept per branch against that digest
and prints "ok (cached)" while nothing it reads changed. When every fast check has passed on the current tree,
that tree's digest is recorded with their names: ship pushes only a tree that passed them. The slow checks never
run on their own: CI runs them on the pull request's exact head, and land merges only on that green run. One asked
for here that fails or is skipped is said so, and never stands for a pass. Times are printed against the budgets
in policy.toml (measured cold runs); a check over its budget twice in a row on the branch (each passing run's time
is recorded: a failure stops early or late, so its time says nothing of speed) gets a warning that it is slower
than usual, never a failure: one slow run is load or a cold cache, not news.
"""

from __future__ import annotations

import os
import time

from . import repo, state
from .checks_run import (  # noqa: F401 - the other modules and the tests use them from here
    CHECK_PY,
    LINT_FIRST,
    PAGE_FIRST,
    UNIT_FIRST,
    ROW,
    SCRIPTS,
    _row_text,
    _stream,
    env_for,
    fails,
    inputs_digest,
    run_check_py,
    run_script,
    short_tmp,
)
from .output import Failure

SLOW = {"scaffold": "--full", "acceptance": "--full", "clean_install": "--full"}  # what --full adds


def known(ctx) -> list[str]:
    return list(ctx.policy["checks"]["inputs"])


def required(ctx) -> dict[str, str]:
    """What must pass on a tree before it may be shipped: the fast checks (CI runs the slow ones on the exact head)."""
    return {name: "fast" for name in ctx.policy["checks"]["fast"]}


def select(ctx, names: list[str], full: bool) -> dict[str, str]:
    """{check: why} for this run: the named checks, else the fast ones (with --full, the slow ones too)."""
    if names:
        unknown = [name for name in names if name not in known(ctx)]
        if unknown:
            raise Failure(f"unknown check: {', '.join(unknown)}", "use one of: " + ", ".join(known(ctx)))
        return {name: "asked" for name in names}
    return required(ctx) | (SLOW if full else {})


def nested(env: dict | None = None) -> bool:
    """The scaffold check runs nested (RD_SCAFFOLD_FULL=nested, as CI's page job runs it): asked for by the
    caller's environment or ``env``, never chosen by retrodev."""
    return {**os.environ, **(env or {})}.get("RD_SCAFFOLD_FULL") == "nested"


def budget(ctx, name: str) -> float:
    budgets = ctx.policy["checks"]["budgets"]
    return float(budgets.get(name, budgets["default"]))


NESTED_KEY = "scaffold_nested"  # the nested scaffold run's budget, duration and cache key (a mode-1 pass is not it)


def budget_key(name: str, deep: bool) -> str:
    """The name a check's budget and recorded time go under: scaffold run nested has its own."""
    return NESTED_KEY if name == "scaffold" and deep else name


def input_digest(ctx, ids: dict, name: str, deep: bool = False) -> str:
    """The digest a check's pass is kept against: its inputs, and for scaffold run nested the mode too, so a pass
    in the fast mode never stands for the nested one."""
    found = inputs_digest(ctx, ids, name)
    return found + "+nested" if budget_key(name, deep) == NESTED_KEY else found


def refuse_uncommitted_installs(ctx, todo: list[str], wanted: dict[str, str], retry: str) -> None:
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
            f"'<what changed>'), then {retry}",
        )


def run(ctx, names: list[str], again: bool = False, full: bool = False, wait_for_commit: bool = False, env=None) -> int:
    """``wait_for_commit`` (check --watch): run the other checks on uncommitted changes and skip the install
    checks until a commit, instead of refusing up front. ``env``: variables added to the checks' processes only."""
    branch = repo.branch(ctx.top) or "detached"
    record = state.load_branch(ctx.top, branch) if branch != "detached" else {"branch": branch, "checks": {}}
    record.setdefault("checks", {})
    ids = repo.file_ids(ctx.top)
    tree = repo.digest(ids)
    need = required(ctx)
    wanted = select(ctx, names, full)
    deep = nested(env)
    retry = "python tools/retrodev check"
    if names:
        retry += " " + " ".join(names)
    elif full:
        retry += " --full"
    if deep and "scaffold" in wanted:
        retry = "RD_SCAFFOLD_FULL=nested " + retry
    digests = {name: input_digest(ctx, ids, name, deep) for name in wanted}
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
        refuse_uncommitted_installs(ctx, todo, wanted, retry)
    started = time.monotonic()
    fast = [name for name in todo if name in CHECK_PY and name != "acceptance"]
    fast_env = env_for("fast", env)
    if "scaffold" in fast:
        # CI's smoke is not the full fast scaffold check and cannot grant its cache credit.
        fast_env["RD_SCAFFOLD_FULL"] = "nested" if deep else "1"
    results = run_check_py(ctx, fast, fast_env, record, ids) if fast else {}
    wall = time.monotonic() - started
    if "acceptance" in todo:
        results |= run_check_py(ctx, ["acceptance"], env_for("acceptance", env))
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
            results[name] = run_script(ctx, name, env_for(name, env))
            digests[name] = inputs_digest(ctx, committed, name)
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
                "budget": budget_key(name, deep),
            }
        )
    passing = all(results[name]["state"] == "ok" for name in fast)  # the wall of a run with a failure is no measure
    whole_fast = set(fast) >= set(ctx.policy["checks"]["fast"]) and passing
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
    unpassed = [  # fast checks without a pass on these very inputs: skipped or failed is no pass
        name
        for name in need
        if (last := record["checks"].get(name, {})).get("digest") != input_digest(ctx, ids, name)
        or last.get("state") != "ok"
    ]
    good = not unpassed
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
        unpassed=unpassed,
        fast_wall=round(wall, 1) if fast else None,
    )
    failed = [row["name"] for row in rows if row["state"] == "FAILED"]
    skipped = [
        row["name"]
        for row in rows
        if row["state"] == "skipped" and row["name"] not in may_skip and row["name"] not in uncommitted
    ]
    first = {row["name"]: row["detail"] for row in rows if row["state"] == "skipped" and row.get("detail") in FIRST_FIX}
    blocked = list(first)
    skipped = [name for name in skipped if name not in blocked]
    shippable = (
        "; the fast checks passed on this tree, so it may ship as a draft (CI runs the slow checks on its exact head)"
        if good
        else ""
    )
    if failed:
        raise Failure(
            f"failed: {', '.join(failed)}" + (f"; {blocked[0]}: {first[blocked[0]]}" if blocked else "") + shippable,
            f"read each failure's FIX line above, fix it, then run {retry} (passing checks stay cached)",
        )
    if blocked:
        fix = FIRST_FIX[first[blocked[0]]]
        raise Failure(f"{blocked[0]}: {first[blocked[0]]}" + shippable, f"{fix}, then {retry}")
    if uncommitted:
        raise Failure(
            f"not run on uncommitted changes: {', '.join(uncommitted)} (an install gets only what is committed)"
            + shippable,
            f"commit first, then {retry}",
        )
    if skipped:
        raise Failure(
            f"skipped (a tool is missing): {', '.join(skipped)}; a skipped check proves nothing" + shippable,
            f"install what each skip names (python tools/retrodev doctor lists it), then {retry}",
        )
    let_skip = [row["name"] for row in rows if row["state"] == "skipped"]  # only may_skip ones get this far
    ran = sum(not row["cached"] and row["state"] == "ok" for row in rows)
    ctx.out.say(
        (f"{len(rows) - len(let_skip)} of {len(rows)} passed" if let_skip else f"all {len(rows)} passed")
        + f" ({ran} ran, {sum(row['cached'] for row in rows)} cached)"
        + (f", fast checks {wall:.1f} s wall" if fast else "")
        + (f"; skipped, so not proven here: {', '.join(let_skip)} (CI runs it on the exact head)" if let_skip else "")
        + ("; this tree may ship" if good else f"; not passed on this tree yet: {', '.join(unpassed)}")
    )
    if good:
        from . import body_names, ship  # ship imports gates, which imports this module

        step = ship.body_step(ctx, None if branch == "detached" else branch, record)
        if step:
            ctx.out.say(step)
            ctx.out.set(next=step)
        body_names.say(
            ctx, None if step else body_names.body_warning(ctx, None if branch == "detached" else branch, record)
        )
    return 0


FAST_TOTAL = "fast_total"
# A check skipped because the tree already fails another (scaffold copies the tree): what to fix first.
FIRST_FIX = {
    LINT_FIRST: "python tools/check.py fix",
    UNIT_FIRST: "fix the unit failures (python tools/check.py unit)",
    PAGE_FIRST: "fix the page failures (python tools/check.py page)",
}


def over(ctx, name: str, seconds: float) -> bool:
    limit = float(ctx.policy["checks"]["budgets"][name]) if name == FAST_TOTAL else budget(ctx, name)
    return seconds > limit


def durations(rows: list[dict], wall: float | None, before: dict) -> dict:
    """{check: seconds} of each check's latest passing run on the branch (fast_total: the fast checks together, when
    all of them ran and passed). A cached, failed or skipped row keeps its last passing run's time."""
    found = dict(before)
    for row in rows:
        if not row["cached"] and row["state"] == "ok":  # only a passing run measures the check
            found[row.get("budget", row["name"])] = round(float(row["seconds"]), 1)
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
        name = row.get("budget", row["name"])  # scaffold run nested: its own budget and last time
        limit = budget(ctx, name)
        if (
            not row["cached"]
            and row["state"] == "ok"
            and over(ctx, name, row["seconds"])
            and over(ctx, name, before.get(name, 0.0))
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
