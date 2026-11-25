"""Where a game stands in the studio's pipeline, and the gate ``chromatic_present_game`` and ``chromatic_build_report``
hold it to: the game's ROM is the last build of its sources as they stand, and its test plan's bound checks and F1
pass on that ROM (the results ``chromatic_playtest`` keeps, ``playtest.current``). Nothing is kept of its own: it reads
the library's record of the last build (``lastBuild``, whose ``sources`` is ``freshness.source_digest`` when the build
finished) and the game's playtest state. ``after_build`` names the checks a build left to replay, for
``chromatic_rom_build``'s result. Standard library only."""

from __future__ import annotations

from pathlib import Path

from . import finish_run, freshness, plan_checks, playtest
from .project import timestamp

# The override's argument on both tools: the user's request to see (or have reported) the game as it is.
OVERRIDE = "unfinished"
MAX_OVERRIDE = 160
FINISH_KEY = plan_checks.check_key(plan_checks.FINISH_CHECK)
OVERRIDE_STEP = (
    f"Only when the user asked for the game as it is now, before it passes, call again with {OVERRIDE}: their "
    "request in a few words."
)
REBUILD = "Run chromatic_rom_build for this project, then chromatic_playtest {} on the new ROM."
RUN = "Run chromatic_playtest {}: it replays every bound check on this ROM."
FIX = (
    "For each failed check, look at its evidence images in chromatic_playtest's answer, fix the game, rebuild and run "
    "chromatic_playtest {} again; for a change made on purpose, play the check again with recording:{} and bind the "
    "new recording."
)
JUDGE = (
    "Fix what chromatic_playtest said about each check it could not judge and run it again; a check no replay can "
    'judge is unbound (chromatic_playtest {"action":"unbind"}) and verified by hand, its recording given as its '
    "evidence in chromatic_build_report."
)
BIND_FINISH = (
    f"Play {plan_checks.FINISH_CHECK} from a fresh boot (chromatic_emulator_run restart:true, recording:{{}}) to the "
    'ending, stop it with chromatic_emulator_recording {"action":"stop","outcome":"passed"}, bind it with '
    f'chromatic_playtest {{"action":"bind","check":"{plan_checks.FINISH_CHECK}","recording":<its recordingPath>}} '
    "and run chromatic_playtest {}."
)


def rom_state(root: Path, last_build: dict | None) -> dict:
    """The game's ROM as ``{path, sha256, problem}``: ``problem`` says why it is not the last build of the sources as
    they stand (None when it is). The library's record of the last build decides: a failed one, another ROM than it
    made, or sources whose digest changed since. A build recorded without its sources' digest (before the library
    kept one, or a project with no ``.gbsproj``) is compared by file times."""
    root = Path(root)
    rom, sha256, why = finish_run.current_rom(root)
    if why or rom is None:
        return {"path": None, "sha256": None, "problem": "This game has no readable ROM in build/ yet."}
    last = last_build if isinstance(last_build, dict) else None
    problem = None
    if last and last.get("ok") is False:
        problem = "The last chromatic_rom_build of this game failed, so its ROM is an older build."
    elif last and isinstance(last.get("sha256"), str) and last["sha256"] != sha256:
        problem = "The ROM in build/ is not the one the last chromatic_rom_build made."
    elif _sources_changed(root, last, rom):
        problem = "Game files changed after the last build, so the ROM is not the game as its sources stand."
    return {"path": str(rom), "sha256": sha256, "problem": problem}


def _sources_changed(root: Path, last: dict | None, rom: Path) -> bool:
    recorded = (last or {}).get("sources")
    now = freshness.source_digest(root) if isinstance(recorded, str) else None
    if now is not None:
        return now != recorded
    moment = timestamp((last or {}).get("t"))
    try:
        moment = moment or rom.stat().st_mtime
    except OSError:
        return True
    return freshness.sources_newer_than(root, moment)


def checks_state(root: Path, rom_sha256: str | None, shown=()) -> dict | None:
    """The test plan's bound checks by their result on the ROM ``rom_sha256`` (``passed``, ``sampled``, ``failed``,
    ``error``, ``notRun``: no result that stands on it, ``verified``: one of ``shown``, the check IDs a build report
    shows passed on this ROM with its own evidence, that had no result or an ``error``), the open checks with no
    binding (``unbound``) or one made before their words changed (``stale``), ``finish`` (F1 when the plan lists it
    open, else None) and ``finishUnbound`` (F1 waits for a binding). None for a game without a test plan."""
    plan = plan_checks.read_plan(Path(root))
    if plan is None:
        return None
    state = playtest.read(Path(root))
    cover = playtest.coverage(plan, state)
    results = playtest.current(plan, state, rom_sha256)
    shown = {plan_checks.check_key(identifier) for identifier in shown}
    checks: dict = {name: [] for name in ("passed", "sampled", "verified", "failed", "error", "notRun")}
    for identifier in cover["bound"]:
        key = plan_checks.check_key(identifier)
        result = (results.get(key) or {}).get("result") or "notRun"
        checks["verified" if result in ("error", "notRun") and key in shown else result].append(identifier)
    finish = next((check for check in plan.checks if plan_checks.check_key(check) == FINISH_KEY), None)
    waiting = finish in cover["unbound"] + cover["stale"]
    if waiting and FINISH_KEY in shown:
        checks["verified"].append(finish)
    checks.update(
        unbound=cover["unbound"], stale=cover["stale"], finish=finish, finishUnbound=waiting and FINISH_KEY not in shown
    )
    return checks


def state(root: Path, last_build: dict | None, shown=()) -> dict:
    """Where the game stands: ``{rom, checks, ready}`` (``checks`` None without a test plan). Ready means the ROM is
    the last build of the current sources and every bound check passed on it (sampled counts, as the build report
    takes it), F1 among them when the plan lists it; ``shown`` as ``checks_state``."""
    rom = rom_state(root, last_build)
    checks = checks_state(root, rom["sha256"], shown)
    ready = rom["problem"] is None and not (
        checks and (checks["failed"] or checks["error"] or checks["notRun"] or checks["finishUnbound"])
    )
    return {"rom": rom, "checks": checks, "ready": ready}


def gate(tool: str, root: Path, last_build: dict | None, shown=()) -> dict | None:
    """None when ``tool`` may present or report the game (``state`` is ready); else its refusal, ``{ok: false, code,
    error, nextStep, pipeline}``: ``BUILD_FIRST`` while the ROM is not the last build of the current sources (its
    results would be of another game), ``PLAYTEST_FIRST`` while a bound check or F1 has not passed on it."""
    where = state(root, last_build, shown)
    if where["ready"]:
        return None
    rom, checks = where["rom"], where["checks"]
    if rom["problem"]:
        return _refusal(tool, "BUILD_FIRST", [rom["problem"]], [REBUILD], where)
    reasons, steps = [], []
    if checks["notRun"]:
        reasons.append(f"{_names(checks['notRun'])} {_has(checks['notRun'])} no result on this ROM.")
        steps.append(RUN)
    if checks["failed"]:
        reasons.append(f"{_names(checks['failed'])} failed on this ROM.")
        steps.append(FIX)
    if checks["error"]:
        reasons.append(f"chromatic_playtest could not judge {_names(checks['error'])} on this ROM.")
        steps.append(JUDGE)
    if checks["finishUnbound"]:
        how = "only to a recording made before its words changed" if checks["finish"] in checks["stale"] else "to none"
        reasons.append(f"{checks['finish']}, the run from power-on to the ending, is bound {how}.")
        steps.append(BIND_FINISH)
    return _refusal(tool, "PLAYTEST_FIRST", reasons, steps, where)


def _refusal(tool: str, code: str, reasons: list[str], steps: list[str], where: dict) -> dict:
    return {
        "ok": False,
        "code": code,
        "error": f"{tool} waits until the game's latest build passes its checks: " + " ".join(reasons),
        "nextStep": " ".join([*steps, OVERRIDE_STEP]),
        "pipeline": where,
    }


def _names(identifiers: list[str]) -> str:
    return ", ".join(identifiers)


def _has(identifiers: list[str]) -> str:
    return "has" if len(identifiers) == 1 else "have"


def override(value) -> tuple[str | None, str | None]:
    """The override argument checked: ``(the request, None)``, ``(None, None)`` when absent, or ``(None, why not)``."""
    if value is None:
        return None, None
    if isinstance(value, str) and value.strip() and len(value.strip()) <= MAX_OVERRIDE:
        return " ".join(value.split()), None
    return None, f"{OVERRIDE} must be the user's request in 1 to {MAX_OVERRIDE} characters."


def after_build(root: Path) -> dict | None:
    """What a build of the game left for its test plan, for ``chromatic_rom_build``'s result: the bound checks whose
    last result was on an earlier ROM (``staleResults``) and those never replayed (``notRun``), with what to do. None
    for a game without a test plan, or when every bound check's result stands on the new ROM (it did not change)."""
    root = Path(root)
    _rom, sha256, why = finish_run.current_rom(root)
    plan = plan_checks.read_plan(root)
    if why or plan is None:
        return None
    saved = playtest.read(root)
    results = playtest.current(plan, saved, sha256)
    stale, never = [], []
    for identifier in playtest.coverage(plan, saved)["bound"]:
        key = plan_checks.check_key(identifier)
        if key not in results:
            (stale if key in saved["results"] else never).append(identifier)
    if not stale and not never:
        return None
    return {
        "staleResults": stale,
        "notRun": never,
        "nextStep": "Once this build holds what you meant to change, run chromatic_playtest {}: "
        "chromatic_present_game and chromatic_build_report wait until its bound checks pass on this ROM.",
    }
