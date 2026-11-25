"""What a build report owes the game's test plan (``docs/game/TEST-PLAN.md``): a difficulty, a result for each open
check and, when its finishable check was played, that run's recording. Used by ``report_tools.py``."""

from __future__ import annotations

from pathlib import Path

from . import finish_run, plan_checks


def plan_problems(
    root: Path, checks: list[dict], has_difficulty: bool, run: dict | None, names_run: bool
) -> tuple[list[str], list[str]]:
    """What the report lacks by the game's test plan (problems), and what the plan itself lacks (warnings). A game
    without a test plan asks for nothing. ``run`` is the checked finishable run (None when the report names none,
    ``names_run``, or names one that is no finishable run of this build)."""
    plan = plan_checks.read_plan(root)
    if plan is None:
        return [], []
    where = plan_checks.PLAN_FILE.as_posix()
    key = plan_checks.check_key
    problems = [] if has_difficulty else [f"difficulty is required: this game has a test plan ({where})."]
    warnings = []
    if plan.unreadable:
        warnings.append(
            f"{where} has rows whose ID is no check ID, so they are not checks: {', '.join(plan.unreadable)}. An ID "
            "is 1 to 4 letters, an optional hyphen, 1 to 3 digits and an optional letter (T1, AUD2, GATE-1, T3b)."
        )
    if not plan.checks:
        warnings.append(f"{where} lists no checks (a table with an ID column, as in the game-planning template).")
    if len(plan.checks) > plan_checks.MAX_CHECKS:
        problems.append(
            f"{where} lists {len(plan.checks)} open checks; a report holds results for at most "
            f"{plan_checks.MAX_CHECKS}. Keep every approved check: propose in DECISIONS.md combining related rows "
            "into one check each (their words kept in its Then cell), and report again once the user approves."
        )
        return problems, warnings
    planned = {key(identifier) for identifier in plan.checks}
    reported = {key(check["id"]) for check in checks if check["id"]}
    missing = [identifier for identifier in plan.checks if key(identifier) not in reported]
    if missing:
        problems.append(
            f"checks has no result for {', '.join(missing)}: give every open check in {where} its result on this "
            "build ('not run' when you did not play it on this ROM)."
        )
    unknown = [check["id"] for check in checks if check["id"] and key(check["id"]) not in planned]
    if unknown:
        problems.append(f"checks names {', '.join(unknown)}, which {where} does not list as an open check.")
    finish = plan_checks.FINISH_CHECK
    result = next((check["result"] for check in checks if check["id"] and key(check["id"]) == key(finish)), None)
    if result in ("passed", "failed") and not names_run:
        problems.append(
            f"checks gives {finish} a result but finishRun names no recording of that run: {finish_run.NEW_RUN} and "
            f"give its recordingPath as finishRun, or report {finish} as not run."
        )
    elif result == "passed" and run is not None and run["status"] != "stopped":
        problems.append(
            f"checks gives {finish} passed but its recording ended {run['status']}: {finish_run.NEW_RUN} and name "
            f"that recording, or report {finish} as failed."
        )
    elif not names_run:
        warnings.append("finishRun names no recording: this report shows no recorded run from power-on of this ROM.")
    return problems, warnings
