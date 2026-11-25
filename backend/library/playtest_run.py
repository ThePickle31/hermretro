"""Replaying a game's bound checks (``playtest.py``) on its ROM as it is now, for ``chromatic_playtest``.

Each check is one ``emulator_replay`` that also judges what the replay ended in (its ``expect``) and, for the
finishable check, records the replay and stops that recording with the verdict as its outcome: the engine does all
of it in one queued operation, so no other emulator call comes between. The run is kept only when the engine
replayed every check on the ROM it started with and that ROM is still the game's; a call the broker refused keeps
nothing. Standard library only: the engine is reached through the ``call`` the tool hands in."""

from __future__ import annotations

import re
import shutil
import time
from collections.abc import Callable
from pathlib import Path

from . import finish_run, plan_checks, playtest
from .playtest import RESULTS, engine_answer

# Where the finishable check's replays are recorded. Its own folder: the engine bounds the recordings one folder holds
# (MAX_SIBLING_RECORDINGS, MAX_SIBLING_RESERVED_BYTES in its emulator worker), and those in artifacts/playtests/ are
# the agent's.
RUNS = Path("artifacts", "playtest-runs")
RUN_NAME = re.compile(r"^[a-z0-9-]{1,16}-\d{8}-\d{6}-\d{6}$")  # the folders this module names there
KEEP_RUNS = 4  # the recorded replays kept there, with the one about to be made
MAX_RESERVED = 1024 * 1024 * 1024  # the engine's bound on the bytes one folder's recordings reserve
MiB = 1024 * 1024
# A recorded replay reserves twice what its source used, so it fits however the new build draws, within these.
MIN_RUN_BYTES, MAX_RUN_BYTES = 16 * MiB, 512 * MiB

# call(engine tool, arguments) -> the broker's response; save(engine result) -> the saved image paths, in order.
Call = Callable[[str, dict], dict]
Save = Callable[[dict], list[str]]


class Refused(Exception):
    """The broker refused an engine call before anything ran: the run stops and keeps nothing."""


def _reservation(manifest: dict | None) -> int:
    used = (manifest or {}).get("bytesUsed")
    used = used if type(used) is int and used > 0 else 0
    return min(MAX_RUN_BYTES, max(MIN_RUN_BYTES, -(-(2 * used) // MiB) * MiB))


def _reserved(manifest: dict) -> int:
    limit = (manifest.get("limits") or {}).get("maxBytes")
    return limit if type(limit) is int and limit > 0 else MAX_RUN_BYTES


def _make_room(root: Path, reserve: int, protected: set[Path]) -> None:
    """Remove the oldest recorded replays this module made in ``RUNS`` until one more reserving ``reserve`` bytes
    fits beside the rest by count and by bytes. Only finished ones, and none a binding or a kept result names."""
    folder = Path(root).resolve() / RUNS
    try:
        entries = [entry for entry in folder.iterdir() if entry.is_dir() and not entry.is_symlink()]
    except OSError:
        return
    recordings = [(entry, manifest) for entry in entries if (manifest := finish_run.read_manifest(entry)) is not None]
    count, reserved = len(recordings), sum(_reserved(manifest) for _entry, manifest in recordings)
    owned = sorted(
        (
            (str(manifest.get("createdAt") or ""), entry, manifest)
            for entry, manifest in recordings
            if RUN_NAME.match(entry.name) and manifest.get("status") != "recording" and entry not in protected
        ),
        key=lambda item: item[:2],
    )
    for _created, entry, manifest in owned:
        if count < KEEP_RUNS and reserved + reserve <= MAX_RESERVED:
            return
        shutil.rmtree(entry, ignore_errors=True)
        count, reserved = count - 1, reserved - _reserved(manifest)


def _protected(root: Path, state: dict) -> set[Path]:
    """The recording folders a binding or a kept result names."""
    paths = [binding.get("recording") for binding in state["bindings"].values()]
    paths += [result.get("recordingPath") for result in state["results"].values()]
    return {(Path(root).resolve() / path).resolve() for path in paths if isinstance(path, str) and path}


def _outcome(verdict: dict, expect: dict, coverage) -> str:
    """A check's result from the engine's verdict."""
    outcome = verdict.get("outcome")
    if outcome == "passed":
        return "sampled" if expect["frames"] == "match" and coverage != "every-frame" else "passed"
    return "failed" if outcome == "failed" else "error"


def _finished(root: Path, entry: dict, structured: dict) -> None:
    """Hold the finishable check's recorded replay to what a build report's finishRun needs: finished in the same
    call with the verdict as its outcome, of this ROM, from power-on, the whole route when it passed. When it is
    not, the check is an error; when it is, the recording is its evidence, passed or failed."""
    recording = structured.get("recording") or {}
    path = recording.get("recordingPath")
    wanted = {"passed": "passed", "sampled": "passed", "failed": "failed"}.get(entry["result"], "needs-review")
    run, why = (None, None) if not path or recording.get("finishError") else finish_run.read_run(Path(root), path)
    replay = entry["replay"] or {}
    if not path:
        why = "the replay made no recording"
    elif recording.get("finishError"):
        why = f"its recording could not be stopped: {recording['finishError']}"
    elif run is not None and run.get("outcome") != wanted:
        why = f"its recording ended with outcome {run.get('outcome') or 'none'}, not {wanted}"
    elif run is not None and wanted == "passed" and replay.get("replayedActions") != replay.get("actionCount"):
        why = f"the replay played {replay.get('replayedActions')} of the run's {replay.get('actionCount')} actions"
    if why:
        entry["problems"].append(f"Its recorded replay is no finished run of this ROM ({why}).")
        entry["result"] = "error"
    elif run is not None:
        entry["evidence"]["recordingPath"] = run["recordingPath"]


def _run_one(root: Path, call: Call, save: Save, rom: Path, binding: dict, record: bool, state: dict):
    """Replay one bound check on ``rom``: ``(its entry, the engine's account: the ROM it replayed on and the session
    the replay ended)``. Raises Refused when the broker refused the call."""
    expect = binding["expect"]
    semantic = "scene" in expect or "variables" in expect
    source = Path(root).resolve() / binding["recording"]
    entry = {
        "id": binding["id"],
        "result": "error",
        "recordingPath": str(source),
        "sessionId": binding["sessionId"],
        "branchId": binding["branchId"],
        "toActionIndex": binding["toActionIndex"],
        "expect": expect,
        "revision": binding["revision"],
        "replay": None,
        "divergence": None,
        "observed": None,
        "problems": [],
        "notes": [],
        "evidence": {},
    }
    arguments = {
        "romPath": str(rom),
        "recordingPath": str(source),
        "sessionId": binding["sessionId"],
        "branchId": binding["branchId"],
        "onDivergence": "continue" if semantic else "stop",
        "expect": expect,
        "recording": False,
    }
    if binding["toActionIndex"] is not None:
        arguments["toActionIndex"] = binding["toActionIndex"]
    if record:
        reserve = _reservation(finish_run.read_manifest(source))
        _make_room(root, reserve, _protected(root, state))
        name = f"{binding['id'].lower()}-{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 1_000_000:06d}"
        arguments["recording"] = {"outputPath": str(Path(root).resolve() / RUNS / name), "maxBytes": reserve}
        arguments["finishRecording"] = True
    response = call("emulator_replay", arguments)
    if response.get("denied") or not (response.get("ok") or response.get("dispatched")):
        raise Refused(engine_answer(response)[2])
    result, structured, error = engine_answer(response)
    if error:
        entry["problems"].append(f"emulator_replay: {error}")
        return entry, {}
    replay = structured.get("replay") or {}
    account = {"romSha256": structured.get("romSha256"), "endedSession": replay.get("endedSession")}
    entry["replay"] = {
        "status": replay.get("status"),
        "replayedActions": replay.get("replayedActions"),
        "toActionIndex": replay.get("toActionIndex"),
        "actionCount": (replay.get("source") or {}).get("actionCount"),
        "comparedFrames": replay.get("comparedFrames"),
        "coverage": replay.get("coverage"),
        "deterministic": replay.get("deterministic"),
        "frame": structured.get("frame"),
    }
    divergence = replay.get("divergence")
    if isinstance(divergence, dict):
        kept = ("frame", "actionIndex", "lastMatchedFrame", "differingFrames")
        entry["divergence"] = {key: divergence[key] for key in kept if key in divergence}
    roles = [image.get("role") for image in structured.get("images") or [] if isinstance(image, dict)]
    try:
        entry["evidence"] = dict(zip(roles, save(result or {}), strict=False))  # an image not delivered is left out
    except OSError as problem:
        entry["notes"].append(f"The replay's images could not be saved ({problem}).")
    if replay.get("coverage") not in (None, "every-frame"):
        entry["notes"].append(f"Coverage {replay['coverage']}: only the frames the recording kept were compared.")
    if replay.get("deterministic") is False:
        entry["notes"].append("The cartridge has a real-time clock, so the replay is best effort.")
    verdict = structured.get("verdict") if isinstance(structured.get("verdict"), dict) else {}
    entry["observed"] = verdict.get("observed")
    entry["problems"] = [*verdict.get("problems", []), *([verdict["unreadable"]] if verdict.get("unreadable") else [])]
    entry["result"] = _outcome(verdict, expect, replay.get("coverage"))
    if not verdict:
        entry["problems"].append("The engine gave no verdict on this replay.")
    if (replay.get("source") or {}).get("sessionId") != binding["sessionId"]:
        entry["problems"].append("The engine replayed another attempt than the one bound.")
        entry["result"] = "error"
    if record:
        _finished(root, entry, structured)
    return entry, account


def run(root: Path, call: Call, save: Save, only: list[str] | None = None) -> tuple[dict | None, str | None]:
    """Replay every bound open check (or the ``only`` ones) on the game's ROM as it is now and keep the results:
    ``(the answer, None)``, or ``(None, why nothing was kept)``."""
    root = Path(root)
    plan = plan_checks.read_plan(root)
    if plan is None:
        return None, f"This game has no test plan ({plan_checks.PLAN_FILE.as_posix()})."
    rom, sha256, why = finish_run.current_rom(root, "chromatic_playtest")
    if why:
        return None, why
    state = playtest.read(root)
    cover = playtest.coverage(plan, state)
    keys = [plan_checks.check_key(identifier) for identifier in cover["bound"]]
    if only is not None:
        wanted = {plan_checks.check_key(identifier) for identifier in only}
        stale = [identifier for identifier in cover["stale"] if plan_checks.check_key(identifier) in wanted]
        if stale:
            return None, (
                f"{', '.join(stale)} changed in {plan_checks.PLAN_FILE.as_posix()} since it was bound: play it again "
                'and bind the new recording with chromatic_playtest {"action":"bind"}.'
            )
        missing = sorted(wanted - set(keys))
        if missing:
            return None, f"checks names {', '.join(missing)}, which no open check's binding has: bind them first."
        keys = [key for key in keys if key in wanted]
    finish = plan_checks.check_key(plan_checks.FINISH_CHECK)
    keys.sort(key=lambda key: key == finish)  # its replay is recorded once the others ran
    ran = []
    try:
        for key in keys:
            ran.append(_run_one(root, call, save, rom, state["bindings"][key], key == finish, state))
    except Refused as refusal:
        return None, f"The engine call was refused, so nothing was kept: {refusal}"
    _rom, now, _why = finish_run.current_rom(root)
    if now != sha256 or any(account and account["romSha256"] != sha256 for _entry, account in ran):
        return None, (
            "The game's ROM changed while its checks were replayed (a build finished during the run), so nothing was "
            "kept: run chromatic_playtest again."
        )
    entries = [entry for entry, _account in ran]
    ran_at = int(time.time() * 1000)
    bindings = state["bindings"]
    dropped = playtest.keep(
        root, {plan_checks.check_key(entry["id"]): _kept(entry, bindings, sha256, ran_at) for entry in entries}
    )
    for entry in entries:
        if entry["id"] in dropped:
            entry["notes"].append("Not kept: the check was bound again or unbound while it ran.")
    finished = next((entry for entry in entries if plan_checks.check_key(entry["id"]) == finish), {})
    ended = next((account["endedSession"] for _entry, account in ran[:1] if account.get("endedSession")), None)
    answer = {
        "ok": True,
        "project": str(root),
        "rom": {"path": str(rom), "sha256": sha256},
        "ranAt": ran_at,
        "counts": {
            **{result: sum(entry["result"] == result for entry in entries) for result in RESULTS},
            "stale": len(cover["stale"]),
            "unbound": len(cover["unbound"]),
        },
        "checks": entries,
        "stale": cover["stale"],
        "unbound": cover["unbound"],
        "retired": cover["retired"],
        "finishRun": (finished.get("evidence") or {}).get("recordingPath"),
        **({"endedSession": ended} if ended else {}),
    }
    answer["nextStep"] = next_step(answer)
    return answer, None


def _kept(entry: dict, bindings: dict, rom_sha256: str, ran_at: int) -> dict:
    """A check's result as the game's state keeps it (``playtest.keep``)."""
    binding = bindings[plan_checks.check_key(entry["id"])]
    kept = {
        "id": entry["id"],
        "result": entry["result"],
        "ranAt": ran_at,
        "romSha256": rom_sha256,
        "revision": binding["revision"],
        "check": binding["check"],
        "problems": [problem[:300] for problem in entry["problems"][:4]],
        "notes": [note[:300] for note in entry["notes"][:4]],
    }
    if (entry["replay"] or {}).get("coverage"):
        kept["coverage"] = entry["replay"]["coverage"]
    if entry["evidence"].get("recordingPath"):
        kept["recordingPath"] = entry["evidence"]["recordingPath"]
    return kept


def next_step(answer: dict) -> str:
    """What the agent does with a run's answer."""
    steps = []
    ended = (answer.get("endedSession") or {}).get("recording") or {}
    if ended.get("status") == "recording":
        steps.append(
            f"The run ended the attempt {ended.get('recordingPath')} that was still recording (it is kept, stopped): "
            "boot again with recording:{} to go on playing."
        )
    if answer["counts"]["failed"]:
        steps.append(
            "For each failed check, look at its evidence images and fix the game, then rebuild and run "
            "chromatic_playtest again; for a change you made on purpose, play the check again with recording:{} and "
            "bind the new recording."
        )
    if answer["counts"]["error"]:
        steps.append(
            "A check with an error could not be judged: its problems say why. Fix that and run again, or verify it "
            "yourself on this ROM and give the recording that shows it as that check's evidence in "
            "chromatic_build_report."
        )
    waiting = answer["stale"] + answer["unbound"]
    if waiting:
        steps.append(
            f"Not bound: {', '.join(waiting)}. Play each from a fresh boot with recording:{{}} and bind it with "
            'chromatic_playtest {"action":"bind"} once it passes.'
        )
    if not answer["checks"]:
        return " ".join(steps)
    report = "Give these results in chromatic_build_report's checks (a bound check's result there must agree with them)"
    if answer.get("finishRun"):
        report += f", and {answer['finishRun']} as finishRun"
    steps.append(report + ".")
    return " ".join(steps)
