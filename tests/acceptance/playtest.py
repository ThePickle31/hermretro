"""The test plan run as chromatic_playtest runs it (backend/library/playtest_run.py), on B's worker: checks bound to one
recorded route, replayed on their own ROM and on a rebuild that moves the player's start."""

import base64
import hashlib
import shutil
from pathlib import Path

from backend.library import finish_run, playtest, playtest_run, report_plan
from tests.acceptance.fixture import OWNER_B, structured

PLAN = """# Test plan

| ID | Given | When | Then | Status |
|---|---|---|---|---|
| T1 | power-on | the text box is closed | the start scene shows as recorded | not run |
| T2 | power-on | the text box is closed | the start scene is current with Oil unchanged | not run |
| F1 | power-on | the route is played | it ends | not run |
"""
ROUTE = [{"buttons": [], "frames": 30}, {"buttons": ["a"], "frames": 2}, {"buttons": [], "frames": 40}]
RECORDING = {"maxBytes": 4 * 1024 * 1024}


def check_playtest(suite, client_b):
    root = suite.project_b
    (root / "docs" / "game").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "game" / "TEST-PLAN.md").write_text(PLAN)
    saved = suite.work / "playtest-images"
    saved.mkdir(exist_ok=True)
    called = []

    def call(tool, arguments):
        called.append(tool)
        return client_b.call(OWNER_B, tool, arguments)

    def save(result):
        paths = []
        for block in result.get("content") or []:
            if block.get("type") == "image":
                data = base64.b64decode(block["data"])
                path = saved / f"{hashlib.sha256(data).hexdigest()}.png"
                path.write_bytes(data)
                paths.append(str(path))
        return paths

    route = root / "artifacts" / "plan-routes" / "route"
    bound = record_and_bind(client_b, root, call, route)
    # An attempt still being recorded when the run starts: the run ends it and says so.
    live = root / "artifacts" / "plan-routes" / "live"
    rom = str(finish_run.current_rom(root)[0])
    client_b.call(
        OWNER_B, "emulator_run", {"romPath": rom, "restart": True, "recording": {**RECORDING, "outputPath": str(live)}}
    )
    called.clear()
    same, why = playtest_run.run(root, call, save)
    same = same or {"error": why}
    results = {entry["id"]: entry for entry in same.get("checks", [])}
    run, refused = finish_run.read_run(root, same.get("finishRun") or "")
    reserved = (finish_run.read_manifest(Path(run["recordingPath"])) or {}) if run else {}
    reported = [{"id": key, "text": key, "result": "passed"} for key in ("T1", "T2", "F1")]
    problems, _warnings = report_plan.playtest_problems(root, reported)
    ended = (same.get("endedSession") or {}).get("recording") or {}
    unfinished, why_not = playtest.bind(root, call, "F1", str(live))
    suite.check(
        "X1",
        "The test plan's checks, bound to one recorded route (frames to an action while it was still recording, a "
        "scene and variable at its end, the whole route), all pass when replayed on their own ROM with one engine call "
        "each; the run names the live attempt it ended; F1's recorded replay, finished in its replay's call and "
        "reserving 16 MiB, is a finishable run of that ROM; F1 binds no run that was not stopped passed; the build "
        "report takes the results",
        all(binding is not None for binding in bound.values())
        and same.get("counts") == {"passed": 3, "sampled": 0, "failed": 0, "error": 0, "stale": 0, "unbound": 0}
        and called == ["emulator_replay"] * 3
        and results["T1"]["replay"]["replayedActions"] == bound["T1"]["toActionIndex"]
        and results["T2"]["observed"] == {k: v for k, v in bound["T2"]["expect"].items() if k != "frames"}
        and ended.get("recordingPath") == str(live)
        and ended.get("status") == "recording"
        and (finish_run.read_manifest(live) or {}).get("status") != "recording"
        and run is not None
        and run.get("outcome") == "passed"
        and (reserved.get("limits") or {}).get("maxBytes") == playtest_run.MIN_RUN_BYTES
        and unfinished is None
        and "ended with outcome none" in " ".join(why_not)
        and problems == []
        and all(check.get("playtest", {}).get("result") == "passed" for check in reported),
        bound=bound,
        run=same,
        finish_run=run or refused,
        reserved=reserved.get("limits"),
        f1_on_unfinished=why_not,
        report_problems=problems,
    )

    # Move the player's start and rebuild: the recorded frames change, the scene and variable do not.
    start = structured(client_b.call(OWNER_B, "project_inspect"))["settings"].get("startX", 0)
    client_b.call(OWNER_B, "settings_update", {"settings": {"startX": start + 1 if start < 10 else start - 1}})
    rebuilt = structured(client_b.call(OWNER_B, "rom_build", {}))
    moved, why = playtest_run.run(root, call, save)
    moved = moved or {"error": why}
    results = {entry["id"]: entry for entry in moved.get("checks", [])}
    t1 = results.get("T1", {})
    failed_run, _refused = finish_run.read_run(root, moved.get("finishRun") or "")
    t1_passed = [{"id": "T1", "text": "T1", "result": "passed"}]
    problems, _warnings = report_plan.playtest_problems(root, t1_passed)

    # The route's attempt is deleted and another recorded in its folder: no check replays the other attempt.
    shutil.rmtree(route)
    client_b.call(
        OWNER_B,
        "emulator_run",
        {"romPath": rebuilt.get("outputPath"), "restart": True, "recording": {**RECORDING, "outputPath": str(route)}},
    )
    client_b.call(OWNER_B, "emulator_step", {"inputs": ROUTE[:1]})
    client_b.call(OWNER_B, "emulator_recording", {"action": "stop", "outcome": "passed"})
    reused, why = playtest_run.run(root, call, save)
    reused = reused or {"error": why}
    unjudged, _warnings = report_plan.playtest_problems(root, [dict(check) for check in t1_passed])
    verified = [{**t1_passed[0], "evidence": str(route)}]
    by_hand, _warnings = report_plan.playtest_problems(root, verified)
    runs = [entry for entry in (root / playtest_run.RUNS).iterdir() if finish_run.read_manifest(entry)]
    suite.check(
        "X2",
        "On a rebuild that moves the player, the frame-bound checks fail at the first differing frame with the "
        "replayed image (and the recorded one when kept), the scene-and-variable check still passes, F1's failed "
        "replay is the failed finishRun, and a report giving the failed check passed is refused; once the route's "
        "folder holds another attempt every check is an error that a report verifies only with evidence of this ROM; "
        "the recorded replays reserve 16 MiB each and stay within the kept number",
        rebuilt.get("success") is not False
        and moved.get("rom", {}).get("sha256") != same.get("rom", {}).get("sha256")
        and moved.get("counts") == {"passed": 1, "sampled": 0, "failed": 2, "error": 0, "stale": 0, "unbound": 0}
        and t1.get("result") == "failed"
        and isinstance((t1.get("divergence") or {}).get("frame"), int)
        and all(saved_path.startswith(str(saved)) for saved_path in t1.get("evidence", {}).values())
        and "actual" in t1.get("evidence", {})
        and results.get("T2", {}).get("result") == "passed"
        and results.get("F1", {}).get("result") == "failed"
        and failed_run is not None
        and failed_run.get("outcome") == "failed"
        and len(problems) == 1
        and reused.get("counts", {}).get("error") == 3
        and all("holds the attempt" in " ".join(entry["problems"]) for entry in reused.get("checks", []))
        and reused.get("finishRun") is None
        and len(unjudged) == 1
        and by_hand == []
        and verified[0].get("playtest", {}).get("verifiedBy") == str(route)
        and 2 <= len(runs) <= playtest_run.KEEP_RUNS
        and all(finish_run.read_manifest(entry)["limits"]["maxBytes"] == playtest_run.MIN_RUN_BYTES for entry in runs),
        run=moved,
        failed_run=failed_run,
        report_problems=problems,
        reused=reused,
        unjudged=unjudged,
        by_hand=by_hand,
        runs=[entry.name for entry in runs],
    )


def record_and_bind(client_b, root, call, output):
    """Play ROUTE from a fresh recorded boot of a new build and bind T1, while it is still recording, to the frames up
    to its first two actions, then T2 to the scene and Oil at its end and F1 to the whole route stopped passed."""
    built = structured(client_b.call(OWNER_B, "rom_build", {}))
    client_b.call(
        OWNER_B,
        "emulator_run",
        {
            "romPath": built.get("outputPath"),
            "restart": True,
            "initialFrames": 120,
            "recording": {**RECORDING, "outputPath": str(output)},
        },
    )
    first = structured(client_b.call(OWNER_B, "emulator_step", {"inputs": ROUTE[:2]}))
    span = first.get("recordingSpan") or {}
    t1 = playtest.bind(root, call, "T1", str(output), None, span.get("toActionIndex"))[0]
    client_b.call(OWNER_B, "emulator_step", {"inputs": ROUTE[2:]})
    end = structured(
        client_b.call(OWNER_B, "emulator_debug", {"includeScene": True, "variableNames": ["Oil"], "referenceLimit": 0})
    )
    client_b.call(OWNER_B, "emulator_recording", {"action": "stop", "outcome": "passed"})
    scene = (end.get("scene") or {}).get("name")
    oil = next((variable.get("value") for variable in end.get("variables") or []), None)
    return {
        "T1": t1,
        "T2": playtest.bind(root, call, "T2", str(output), None, None, {"scene": scene, "variables": {"Oil": oil}})[0],
        "F1": playtest.bind(root, call, "F1", str(output))[0],
    }
