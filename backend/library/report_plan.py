"""What a build report owes the game's test plan (``docs/game/TEST-PLAN.md``): a difficulty, a result for each open
check that agrees with ``chromatic_playtest``'s last run on this ROM and, when its finishable check was played, that
run's recording. Used by ``report_tools.py``."""

from __future__ import annotations

from pathlib import Path

from . import finish_run, plan_checks, playtest

NO_RUN = "finishRun names no recording: this report shows no recorded run from power-on of this ROM."


def plan_problems(
    root: Path, checks: list[dict], has_difficulty: bool, run: dict | None, names_run: bool
) -> tuple[list[str], list[str]]:
    """What the report lacks by the game's test plan (problems), and what the plan or the report leaves unshown
    (warnings). A game without a test plan asks for nothing, but is still told when no recorded run is named.
    ``run`` is the checked finishable run (None when the report names none, ``names_run``, or names one that is no
    finishable run of this build)."""
    plan = plan_checks.read_plan(root)
    if plan is None:
        return [], [] if names_run else [NO_RUN]
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
    elif result == "passed" and run is not None and run.get("outcome") != "passed":
        ended = run["status"] + (f" with outcome {run['outcome']}" if run.get("outcome") else " with no outcome")
        problems.append(
            f"checks gives {finish} passed but its recording ended {ended}: {finish_run.NEW_RUN}, stop it with "
            f'chromatic_emulator_recording {{"action":"stop","outcome":"passed"}} once the ending shows, and name '
            f"that recording, or report {finish} as failed or needs review."
        )
    elif not names_run:
        warnings.append(NO_RUN)
    return problems, warnings


def _verified(root: Path, check: dict, sha256: str | None) -> str | None:
    """Why ``check``'s evidence is no recording of this ROM in the project, None when it is one."""
    value = check.get("evidence")
    if not value:
        return "give the recording that shows it as its evidence"
    _folder, manifest, why = finish_run.find_recording(Path(root), value, f"checks {check['id']} evidence")
    if why:
        return why
    if finish_run.played_rom(manifest or {}) != sha256:
        return f"its evidence {value} played another ROM: give a recording of this ROM"
    return None


def playtest_problems(root: Path, checks: list[dict]) -> tuple[list[str], list[str]]:
    """Hold a build report's ``checks`` to the results ``chromatic_playtest`` keeps for this ROM, the check's binding
    and its words as they are now (``playtest.current``): a check that failed cannot be reported passed, nor one it
    judged reported not run; one it could not judge (error) is reported passed only with ``evidence``, a recording
    of this ROM that shows it. Each check it ran gets ``playtest`` (its result, when it ran and, for an error
    reported passed, the evidence). A bound check reported passed with no result on this ROM, or one that matched
    only on sampled frames, adds a warning. Returns (problems, warnings)."""
    plan = plan_checks.read_plan(root)
    if plan is None:
        return [], []
    _rom, sha256, _why = finish_run.current_rom(Path(root))
    state = playtest.read(root)
    results = playtest.current(plan, state, sha256)
    bound = {plan_checks.check_key(identifier) for identifier in playtest.coverage(plan, state)["bound"]}
    problems, warnings, unplayed, sampled = [], [], [], []
    for check in checks:
        key = plan_checks.check_key(check.get("id") or "")
        ran = results.get(key)
        reported = check.get("result")
        if ran is None:
            if key in bound and reported == "passed":
                unplayed.append(check["id"])
            continue
        check["playtest"] = {"result": ran["result"], "ranAt": ran.get("ranAt")}
        if reported == "passed" and ran["result"] == "failed":
            problems.append(
                f"checks gives {check['id']} passed, but chromatic_playtest replayed it on this ROM and it failed: "
                "report it failed, or fix the game, rebuild and run chromatic_playtest again (for a change made on "
                "purpose, bind a new recording of the check)."
            )
        elif reported == "passed" and ran["result"] == "error":
            why = _verified(root, check, sha256)
            if why:
                problems.append(
                    f"checks gives {check['id']} passed, but chromatic_playtest could not judge it on this ROM "
                    f"({'; '.join(ran.get('problems') or []) or 'error'}): {why}, or fix what it said and run it again."
                )
            else:
                check["playtest"]["verifiedBy"] = check["evidence"]
        elif reported == "not run" and ran["result"] in ("passed", "sampled", "failed"):
            problems.append(
                f"checks gives {check['id']} not run, but chromatic_playtest replayed it on this ROM and it "
                f"{'passed' if ran['result'] == 'sampled' else ran['result']}: report that result."
            )
        elif reported == "passed" and ran["result"] == "sampled":
            sampled.append(check["id"])
    if unplayed:
        warnings.append(
            f"{', '.join(unplayed)} {'is' if len(unplayed) == 1 else 'are'} bound to a recording, but "
            "chromatic_playtest has not replayed them on this ROM: run it after every rebuild."
        )
    if sampled:
        warnings.append(
            f"{', '.join(sampled)} matched only on the frames {'its' if len(sampled) == 1 else 'their'} recording "
            "kept: record the check again from a fresh boot and bind it, so every frame is compared."
        )
    return problems, warnings
