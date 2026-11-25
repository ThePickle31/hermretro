"""A game's executable test plan: checks of ``docs/game/TEST-PLAN.md`` bound to recorded attempts, which
``chromatic_playtest`` (``playtest_tools.py``) replays on the game's ROM as it is now (``playtest_run.py``).

A binding names a recording in the project (``finish_run.find_recording``) by its folder and session id, its branch,
the last action to replay and what the replay must end in (``expect``): every compared frame as the recording showed
it, or the current scene and variable values. It holds the digest of the check's words when it was bound and a
revision of its own fields. Each check's last result holds the ROM it ran on and that binding revision and check
digest, so it stands only while all three still are (``current``): binding again, unbinding, editing the check's
words or reusing a retired ID leaves it out. Both are the game's ``.hermretro/playtest.json``, read once per call
(``read``) and changed under the game folder's lock. Standard library only."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path

from . import finish_run, game_card, layout, plan_checks

STATE_FILE = "playtest.json"  # in the game's .hermretro/ (layout.state)
FRAMES = ("match", "ignore")
MAX_VARIABLES = 8
MAX_NAME = 256
# A check's result on a ROM: passed; sampled (its frames matched, but the recording kept only some of them to compare);
# failed (the game showed something else); error (it could not be judged: the replay was refused or the state unread).
RESULTS = ("passed", "sampled", "failed", "error")
# What a binding's revision covers: everything that decides what its replay plays and judges.
REVISED = ("id", "check", "recording", "sessionId", "branchId", "toActionIndex", "expect", "boundAt")


def engine_answer(response: dict) -> tuple[dict | None, dict, str | None]:
    """An engine call's ``(result, structuredContent, error)``: the error when the engine refused or did not answer."""
    if not response.get("ok"):
        denied = response.get("denied") or {}
        return None, {}, denied.get("message") or response.get("error") or "the engine did not answer"
    result = response.get("result") or {}
    structured = result.get("structuredContent")
    structured = structured if isinstance(structured, dict) else {}
    if result.get("isError"):
        text = next((block.get("text") for block in result.get("content") or [] if block.get("type") == "text"), None)
        return result, structured, structured.get("error") or text or "the engine reported an error"
    return result, structured, None


def read(root: Path) -> dict:
    """The game's playtest state as one snapshot: ``{"bindings": {key: binding}, "results": {key: result}}``, by
    check key (``plan_checks.check_key``)."""
    state = layout.state(root, STATE_FILE)
    return {
        name: {key: value for key, value in (state.get(name) or {}).items() if isinstance(value, dict)}
        if isinstance(state.get(name), dict)
        else {}
        for name in ("bindings", "results")
    }


@game_card.locked
def _change(root: Path, change: Callable[[dict], object]) -> object:
    """Read the game's playtest state, ``change`` it and write it back, holding the game folder's lock: what
    ``change`` answers."""
    state = read(root)
    answer = change(state)
    layout.write_state(root, STATE_FILE, {"version": 1, **state})
    return answer


def definition(plan: plan_checks.Plan, key: str) -> str | None:
    """The digest of what the open check ``key`` says, None when it is not open."""
    words = plan.definitions.get(key)
    return None if words is None else hashlib.sha256(words.encode()).hexdigest()[:16]


def revision(binding: dict) -> str:
    return hashlib.sha256(json.dumps([binding.get(name) for name in REVISED], sort_keys=True).encode()).hexdigest()[:16]


def coverage(plan: plan_checks.Plan, state: dict) -> dict:
    """The open checks that are bound, bound before their words changed (``stale``: bind them again) and unbound,
    and the bindings of checks no longer open (``retired``)."""
    bindings = state["bindings"]
    bound, stale, unbound = [], [], []
    for identifier in plan.checks:
        key = plan_checks.check_key(identifier)
        binding = bindings.get(key)
        if binding is None:
            unbound.append(identifier)
        else:
            (bound if binding.get("check") == definition(plan, key) else stale).append(identifier)
    keys = {plan_checks.check_key(identifier) for identifier in plan.checks}
    retired = [value.get("id") or key for key, value in bindings.items() if key not in keys]
    return {"bound": bound, "stale": stale, "unbound": unbound, "retired": retired}


def current(plan: plan_checks.Plan, state: dict, rom_sha256: str | None) -> dict[str, dict]:
    """The results that still stand on the ROM ``rom_sha256``, by check key: run on that ROM, for the check's binding
    as it is now and the check's words as they are now."""
    results = {}
    for key, result in state["results"].items():
        binding = state["bindings"].get(key)
        if (
            rom_sha256
            and binding is not None
            and result.get("romSha256") == rom_sha256
            and result.get("revision") == binding.get("revision")
            and result.get("check") == binding.get("check") == definition(plan, key)
            and result.get("result") in RESULTS
        ):
            results[key] = result
    return results


# -- binding a check ------------------------------------------------------------------------


def _expectation(expect, problems: list[str]) -> dict:
    """``expect`` checked, with ``frames`` filled in: ``match`` unless a scene or variables decide instead."""
    if expect is None:
        expect = {}
    if not isinstance(expect, dict):
        problems.append("expect must be an object with frames, scene or variables.")
        return {}
    problems += [f"expect has unknown field {key!r}." for key in sorted(set(expect) - {"frames", "scene", "variables"})]
    result: dict = {}
    scene = expect.get("scene")
    if scene is not None:
        if isinstance(scene, str) and 0 < len(scene.strip()) <= MAX_NAME:
            result["scene"] = scene.strip()
        else:
            problems.append(f"expect.scene must be the scene's name (1 to {MAX_NAME} characters).")
    variables = expect.get("variables")
    if variables is not None:
        if (
            isinstance(variables, dict)
            and 0 < len(variables) <= MAX_VARIABLES
            and all(isinstance(name, str) and 0 < len(name.strip()) <= MAX_NAME for name in variables)
            and all(type(value) is int and -32768 <= value <= 65535 for value in variables.values())
        ):
            result["variables"] = {name.strip(): value for name, value in variables.items()}
        else:
            problems.append(
                f"expect.variables must map 1 to {MAX_VARIABLES} variable names to whole numbers (-32768 to 65535)."
            )
    frames = expect.get("frames", "ignore" if scene is not None or variables is not None else "match")
    if frames not in FRAMES:
        problems.append(f"expect.frames must be one of {', '.join(FRAMES)}.")
    elif frames == "ignore" and scene is None and variables is None:
        problems.append("expect checks nothing: give a scene or variables, or leave frames as match.")
    result["frames"] = frames
    return result


def _live(call: Callable[[str, dict], dict], folder: Path, problems: list[str]) -> dict | None:
    """The engine's own account of a recording still being made (its branches, current branch and session), since
    its recording.json lists only the branches it started with."""
    _result, status, error = engine_answer(
        call("emulator_recording", {"action": "status", "recordingPath": str(folder)})
    )
    if error:
        problems.append(f"The recording is still being made and the engine could not say where it stands: {error}")
        return None
    return status


def _finish_problems(manifest: dict, value: str, to_action_index) -> list[str]:
    """What keeps the attempt ``manifest`` from showing the finishable check: it must be one ended run from power-on,
    stopped with outcome passed, replayed whole."""
    finish = plan_checks.FINISH_CHECK
    problems = []
    why = finish_run.unfinished(manifest, value, "recording")
    if why:
        problems.append(why)
    elif manifest.get("outcome") != "passed":
        problems.append(
            f"{finish} binds a run that reached the ending: {value} ended with outcome "
            f"{manifest.get('outcome') or 'none'}. Stop the run with chromatic_emulator_recording "
            '{"action":"stop","outcome":"passed"} once the ending shows, and bind that recording.'
        )
    if to_action_index is not None:
        problems.append(f"{finish} replays the whole run: leave toActionIndex out.")
    return problems


def bind(
    root: Path, call: Callable[[str, dict], dict], check, recording, branch_id=None, to_action_index=None, expect=None
) -> tuple[dict | None, list]:
    """Bind the open check ``check`` to the recording ``recording`` names (a path or a session id): ``(the binding,
    [])``, or ``(None, problems)``. A recording still being made needs ``to_action_index`` (where the check passed),
    since its inputs go on, and is read from the engine (``call``). The finishable check binds only a finished run
    stopped with outcome passed. Replaces the check's earlier binding and drops its result."""
    problems: list[str] = []
    plan = plan_checks.read_plan(root)
    where = plan_checks.PLAN_FILE.as_posix()
    if plan is None:
        return None, [f"This game has no test plan ({where}) to bind checks of."]
    known = {plan_checks.check_key(identifier): identifier for identifier in plan.checks}
    key = plan_checks.check_key(check.strip()) if isinstance(check, str) else None
    if key not in known:
        problems.append(f"check must be an open check of {where}: {', '.join(plan.checks) or 'it lists none'}.")
    if not isinstance(recording, str) or not recording.strip() or len(recording) > 4096:
        return None, [*problems, "recording must be a recording's path or session id."]
    folder, manifest, why = finish_run.find_recording(Path(root), recording.strip(), "recording")
    if why:
        return None, [*problems, why]
    if to_action_index is not None and (type(to_action_index) is not int or to_action_index < 0):
        problems.append("toActionIndex must be a whole number, 0 or more.")
    if key == plan_checks.check_key(plan_checks.FINISH_CHECK):
        problems += _finish_problems(manifest, recording.strip(), to_action_index)
    elif to_action_index is None and manifest.get("status") == "recording":
        problems.append(
            "The recording is still being made, so its inputs go on: give toActionIndex, the recordingSpan's "
            "toActionIndex of the step where the check passed."
        )
    expectation = _expectation(expect, problems)
    if problems:
        return None, problems
    live = _live(call, folder, problems) if manifest.get("status") == "recording" else None
    if live is not None and live.get("sessionId") != manifest.get("sessionId"):
        problems.append(f"{recording} now holds another attempt than its recording.json names: bind that attempt.")
    account = live or manifest
    branches = [b.get("branchId") for b in account.get("branches") or [] if isinstance(b, dict)]
    branch = account.get("branchId") if branch_id is None else branch_id
    if branch not in branches and not problems:
        problems.append(f"branchId must be one of the recording's branches: {', '.join(map(str, branches))}.")
    if problems:
        return None, problems
    binding = {
        "id": known[key],
        "check": definition(plan, key),
        "recording": folder.relative_to(Path(root).resolve()).as_posix(),
        "sessionId": manifest.get("sessionId"),
        "branchId": branch,
        "toActionIndex": to_action_index,
        "expect": expectation,
        "romSha256": finish_run.played_rom(manifest),
        "boundAt": int(time.time() * 1000),
    }
    binding["revision"] = revision(binding)

    def change(state: dict) -> None:
        state["bindings"][key] = binding
        state["results"].pop(key, None)

    _change(root, change)
    return binding, []


def unbind(root: Path, check) -> bool:
    """Remove ``check``'s binding and its result; False when it had none."""
    key = plan_checks.check_key(check.strip()) if isinstance(check, str) else None

    def change(state: dict) -> bool:
        state["results"].pop(key, None)
        return state["bindings"].pop(key, None) is not None

    return key is not None and key in read(root)["bindings"] and bool(_change(root, change))


def keep(root: Path, results: dict[str, dict]) -> list[str]:
    """Keep each of a run's ``results`` (by check key) whose binding is still the one replayed (the same revision),
    over that check's earlier result; answer the IDs of the others, bound again or unbound while they ran."""

    def change(state: dict) -> list[str]:
        dropped = []
        for key, result in results.items():
            if (state["bindings"].get(key) or {}).get("revision") == result["revision"]:
                state["results"][key] = result
            else:
                dropped.append(result["id"])
        return dropped

    dropped = _change(root, change)
    return dropped if isinstance(dropped, list) else []


def public(root: Path, binding: dict) -> dict:
    """A binding as the tool answers it: its recording as an absolute path."""
    return {**binding, "recording": str(Path(root).resolve() / binding["recording"])}
