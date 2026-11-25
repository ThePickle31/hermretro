"""chromatic_playtest's runs (backend/library/playtest_run.py) with a fake engine: one replay per check judged by the
engine, kept only when every check ran on the game's ROM as it still is; the build report held to those results
(report_plan.py); and the tool (playtest_tools.py)."""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.library import (  # noqa: E402 - the repository root goes on sys.path first
    playtest,
    playtest_run,
    playtest_tools,
    report_tools,
)
from tests.backend.library.playtest_fakes import (  # noqa: E402 - the repository root goes on sys.path first
    MiB,
    ROM,
    ROM_SHA,
    SESSION,
    FakeEngine,
    PlaytestCase,
    answer,
    finished,
    replayed,
    write_recording,
)

DENIED = {"ok": False, "dispatched": False, "denied": {"code": "LEASE_REQUIRED", "message": "Not from a subagent."}}


class Runs(PlaytestCase):
    def test_every_bound_check_replays_on_the_games_rom(self):
        source = self.recording()
        self.bind("T1", to_action_index=6)
        self.bind("T2")
        diverged = replayed("failed", status="diverged", problems=["Frame 140 (action 2) differs."])
        engine = FakeEngine(emulator_replay=[replayed(), diverged])
        result = self.play(engine)
        first, second = engine.calls[0][1], engine.calls[1][1]
        self.assertEqual(
            first,
            {
                "romPath": str(self.root / "build" / "game.gbc"),
                "recordingPath": str(source),
                "sessionId": SESSION,
                "branchId": "branch-0001",
                "onDivergence": "stop",
                "expect": {"frames": "match"},
                "recording": False,
                "toActionIndex": 6,
            },
        )
        self.assertNotIn("toActionIndex", second)
        counts = {"passed": 1, "sampled": 0, "failed": 1, "error": 0, "stale": 0, "unbound": 1}
        self.assertEqual(result["counts"], counts)
        self.assertEqual((result["unbound"], result["rom"]["sha256"]), (["F1"], ROM_SHA))
        passed, failed = result["checks"]
        self.assertEqual((passed["id"], passed["result"], passed["problems"]), ("T1", "passed", []))
        self.assertEqual(passed["evidence"], {"end": self.saved[0]})
        self.assertEqual((failed["result"], failed["problems"]), ("failed", ["Frame 140 (action 2) differs."]))
        self.assertEqual(failed["divergence"], {"frame": 140, "actionIndex": 2, "lastMatchedFrame": 139})
        self.assertEqual(failed["evidence"], {"expected": self.saved[1], "actual": self.saved[2]})
        self.assertIsNone(result["finishRun"])
        self.assertEqual(self.kept(), {"T1": "passed", "T2": "failed"})
        stored = playtest.read(self.root)["results"]["T2"]
        self.assertEqual((stored["romSha256"], stored["problems"]), (ROM_SHA, ["Frame 140 (action 2) differs."]))

    def test_a_scene_and_variables_are_judged_where_the_replay_ended(self):
        self.recording()
        self.bind(expect={"scene": "Cellar", "variables": {"Oil": 2}})
        observed = {"scene": "Cellar", "variables": {"Oil": 3}}
        engine = FakeEngine(emulator_replay=[replayed("failed", problems=["Oil is 3, not 2."], observed=observed)])
        entry = self.play(engine)["checks"][0]
        arguments = engine.calls[0][1]
        self.assertEqual(arguments["onDivergence"], "continue")
        self.assertEqual(arguments["expect"], {"scene": "Cellar", "variables": {"Oil": 2}, "frames": "ignore"})
        self.assertEqual((entry["result"], entry["observed"]), ("failed", observed))
        unread = replayed("needs-review", unreadable="Rebuild it in this session.", mode="rom")
        entry = self.play(FakeEngine(emulator_replay=[unread]))["checks"][0]
        self.assertEqual((entry["result"], entry["problems"]), ("error", ["Rebuild it in this session."]))

    def test_frames_matched_only_where_the_recording_kept_them_are_sampled(self):
        self.recording()
        self.bind()
        entry = self.play(FakeEngine(emulator_replay=[replayed(coverage="retained-frames")]))["checks"][0]
        self.assertEqual(entry["result"], "sampled")
        stored = playtest.read(self.root)["results"]["T1"]
        self.assertEqual(stored["coverage"], "retained-frames")
        self.assertIn("only the frames the recording kept", stored["notes"][0])

    def test_a_replay_the_engine_refused_is_an_error_kept_as_evidence(self):
        self.recording()
        self.bind()
        refused = answer({"error": "recordingPath holds the attempt x, not y"}, error=True)
        unknown = {"ok": False, "dispatched": True, "error": "worker gone"}
        for response, problem in (
            (refused, "emulator_replay: recordingPath holds the attempt x, not y"),
            (unknown, "emulator_replay: worker gone"),
        ):
            entry = self.play(FakeEngine(emulator_replay=[response]))["checks"][0]
            self.assertEqual((entry["result"], entry["problems"]), ("error", [problem]))
            self.assertEqual(playtest.read(self.root)["results"]["T1"]["problems"], [problem])
        entry = self.play(FakeEngine(emulator_replay=[replayed(session="f" * 32)]))["checks"][0]
        self.assertEqual(entry["result"], "error")

    def test_a_call_the_broker_refused_keeps_nothing(self):
        self.recording()
        self.bind()
        self.bind("T2")
        self.play(FakeEngine(emulator_replay=[replayed(), replayed()]))
        before = playtest.read(self.root)
        for response in (DENIED, {"ok": False, "dispatched": False, "error": "no broker"}):
            result, why = playtest_run.run(self.root, FakeEngine(emulator_replay=[replayed(), response]), self.save)
            self.assertIsNone(result)
            self.assertIn("refused, so nothing was kept", why)
        self.assertEqual(playtest.read(self.root), before)

    def test_a_run_across_a_rebuild_keeps_nothing(self):
        self.recording()
        self.bind()
        self.bind("T2")

        def rebuilt(_arguments):
            (self.root / "build" / "game.gbc").write_bytes(ROM + b"rebuilt")
            return replayed()

        for responses in ([replayed(), replayed(rom="0" * 64)], [replayed(), rebuilt]):
            result, why = playtest_run.run(self.root, FakeEngine(emulator_replay=responses), self.save)
            self.assertIsNone(result)
            self.assertIn("ROM changed while its checks were replayed", why)
            self.assertEqual(playtest.read(self.root)["results"], {})

    def test_the_session_a_run_ended_is_named(self):
        self.recording()
        self.bind()
        live = {"romSha256": ROM_SHA, "frame": 90, "recording": {"recordingPath": "/live", "status": "recording"}}
        result = self.play(FakeEngine(emulator_replay=[replayed(ended=live)]))
        self.assertEqual(result["endedSession"], live)
        self.assertIn("ended the attempt /live that was still recording", result["nextStep"])

    def test_a_run_of_some_checks_keeps_the_others_results(self):
        self.recording()
        self.bind("T1")
        self.bind("T2")
        self.play(FakeEngine(emulator_replay=[replayed(), replayed()]))
        self.play(FakeEngine(emulator_replay=[replayed("failed")]), only=["t2"])
        self.assertEqual(self.kept(), {"T1": "passed", "T2": "failed"})
        self.assertIn("which no open check's binding has", playtest_run.run(self.root, None, self.save, ["F1"])[1])
        (self.root / "build" / "game.gbc").unlink()
        self.assertIn("has no ROM in build/", playtest_run.run(self.root, FakeEngine(), self.save)[1])


class FinishRun(PlaytestCase):
    def setUp(self):
        super().setUp()
        self.recording(outcome="passed", bytesUsed=3 * MiB)
        self.bind("F1")
        self.runs = self.root / playtest_run.RUNS

    def test_the_finishable_checks_replay_is_recorded_and_finished_in_the_same_call(self):
        self.bind("T1")
        engine = FakeEngine(emulator_replay=[replayed(), finished()])
        result = self.play(engine)
        self.assertEqual([call[1]["recording"] is False for call in engine.calls], [True, False])  # F1 last
        arguments = engine.calls[1][1]
        output = Path(arguments["recording"]["outputPath"])
        self.assertEqual((output.parent, arguments["recording"]["maxBytes"]), (self.runs, 16 * MiB))
        self.assertTrue(arguments["finishRecording"])
        self.assertEqual(result["finishRun"], str(output))
        self.assertEqual(result["checks"][1]["evidence"]["recordingPath"], str(output))
        self.assertEqual(playtest.read(self.root)["results"]["F1"]["recordingPath"], str(output))
        self.assertIn(f"{output} as finishRun", result["nextStep"])

    def test_a_failed_run_is_evidence_and_a_bad_recording_is_an_error(self):
        result = self.play(FakeEngine(emulator_replay=[finished("failed", status="diverged")]))
        self.assertEqual(result["checks"][0]["result"], "failed")
        self.assertTrue(result["finishRun"])
        for response, problem in (
            (finished(written="needs-review"), "ended with outcome needs-review, not passed"),
            (finished(replayed_actions=5), "played 5 of the run's 6 actions"),
            (replayed(recording={"recordingPath": "x", "finishError": "disk full"}), "could not be stopped: disk full"),
            (replayed(), "the replay made no recording"),
        ):
            result = self.play(FakeEngine(emulator_replay=[response]))
            entry = result["checks"][0]
            self.assertEqual(entry["result"], "error", problem)
            self.assertIn(problem, entry["problems"][-1])
            self.assertIsNone(result["finishRun"])

    def test_room_is_made_by_count_and_bytes_and_never_from_what_is_named(self):
        old = "2026-01-01T00:00:00+00:00"
        for index in range(2):  # two big replays made before: 1 GiB reserved between them
            write_recording(self.runs / f"f1-2026010{index}-000000-000000", limits={"maxBytes": 512 * MiB})
        bound = write_recording(self.runs / "f1-20250101-000000-000000", outcome="passed", createdAt=old)
        write_recording(self.runs / "mine", createdAt=old)  # not one this module named
        write_recording(self.runs / "f1-20250102-000000-000000", status="recording", createdAt=old)
        self.bind("T1", str(bound))
        self.play(FakeEngine(emulator_replay=[replayed(), finished()]))
        left = sorted(entry.name for entry in self.runs.iterdir())
        self.assertNotIn("f1-20260100-000000-000000", left)
        self.assertNotIn("f1-20260101-000000-000000", left)
        for kept in ("f1-20250101-000000-000000", "f1-20250102-000000-000000", "mine"):
            self.assertIn(kept, left)


class Report(PlaytestCase):
    def report(self, **results):
        """A report with these check results. F1 is never played here, so the report says why the turn ends with the
        game unfinished: the pipeline gate (test_pipeline.py) would hold it otherwise."""
        checks = [{"id": key, "text": f"Check {key}", "result": value} for key, value in results.items()]
        for check in checks:
            if isinstance(check["result"], tuple):
                check["result"], check["evidence"] = check["result"]
        args = {"title": "Lantern", "summary": "A lamp in the dark.", "checks": checks, "difficulty": "Easy."}
        args["unfinished"] = "F1 is not played yet."
        return json.loads(report_tools.build_report_handler(args, session_id="s1"))

    def test_a_build_report_is_held_to_the_results_on_this_rom(self):
        self.recording()
        self.bind("T1")
        self.bind("T2")
        warned = self.report(T1="passed", T2="not run", F1="not run")
        self.assertTrue(warned["ok"], warned)
        self.assertIn(
            "T1 is bound to a recording, but chromatic_playtest has not replayed", " ".join(warned["warnings"])
        )
        self.play(FakeEngine(emulator_replay=[replayed(), replayed("failed")]))
        refused = self.report(T1="not run", T2="passed", F1="not run")
        self.assertEqual(refused["code"], "INVALID_REPORT")
        self.assertIn("T1 not run, but chromatic_playtest replayed it on this ROM and it passed", refused["error"])
        self.assertIn("T2 passed, but chromatic_playtest replayed it on this ROM and it failed", refused["error"])
        accepted = self.report(T1="passed", T2="failed", F1="not run")
        self.assertTrue(accepted["ok"], accepted)
        checks = {check["id"]: check for check in accepted["report"]["checks"]}
        self.assertEqual((checks["T1"]["playtest"]["result"], checks["T2"]["playtest"]["result"]), ("passed", "failed"))
        self.assertNotIn("playtest", checks["F1"])
        self.bind("T2", to_action_index=2)  # bound again, on purpose: the failure was for the binding before
        self.assertTrue(self.report(T1="passed", T2="passed", F1="not run")["ok"])

    def test_a_check_the_run_could_not_judge_is_verified_with_evidence(self):
        self.recording()
        self.bind()
        self.play(FakeEngine(emulator_replay=[answer({"error": "source debug missing"}, error=True)]), only=["T1"])
        refused = self.report(T1="passed", T2="not run", F1="not run")
        self.assertIn("could not judge it on this ROM (emulator_replay: source debug missing)", refused["error"])
        self.recording("by-hand")
        accepted = self.report(T1=("passed", "artifacts/playtests/by-hand"), T2="not run", F1="not run")
        self.assertTrue(accepted["ok"], accepted)
        verified = accepted["report"]["checks"][0]["playtest"]
        self.assertEqual(
            verified, {"result": "error", "ranAt": verified["ranAt"], "verifiedBy": "artifacts/playtests/by-hand"}
        )
        self.recording("older", rom=b"older rom")
        refused = self.report(T1=("passed", "artifacts/playtests/older"), T2="not run", F1="not run")
        self.assertIn("played another ROM", refused["error"])

    def test_a_check_matched_on_sampled_frames_passes_with_a_warning(self):
        self.recording()
        self.bind()
        self.play(FakeEngine(emulator_replay=[replayed(coverage="retained-frames")]))
        accepted = self.report(T1="passed", T2="not run", F1="not run")
        self.assertTrue(accepted["ok"], accepted)
        self.assertIn("T1 matched only on the frames its recording kept", " ".join(accepted["warnings"]))


class Tool(PlaytestCase):
    def tool(self, session_id="s1", **args):
        return json.loads(playtest_tools.playtest_handler(args, session_id=session_id, conversation_id="c1"))

    def engine(self, engine, context=None, notice=None):
        def engine_call(tool, arguments, kwargs):
            response = engine(tool, arguments)
            return ({**response, "notice": notice} if notice else response), context

        return mock.patch.object(hermes_host, "engine_call", engine_call)

    def test_the_tool_binds_runs_and_unbinds(self):
        self.recording()
        bound = self.tool(action="bind", check="T1", recording=SESSION)
        self.assertTrue(bound["ok"], bound)
        self.assertEqual(bound["unbound"], ["T2", "F1"])
        self.assertIn("after every rebuild", bound["nextStep"])
        refused = self.tool(action="bind", check="T7", recording=SESSION)
        self.assertEqual(refused["code"], "INVALID_BINDING")
        with self.engine(FakeEngine(emulator_replay=[replayed()]), "where the chat stands", "Engine restarted."):
            with mock.patch.object(playtest_tools, "_saved", self.save):
                ran = self.tool()
        self.assertEqual(next(iter(ran)), "hermretroContext")
        self.assertEqual((ran["checks"][0]["result"], ran["notice"]), ("passed", "Engine restarted."))
        self.assertEqual(self.tool(action="unbind", check="T1")["bound"], [])
        for args, problem in (
            ({"action": "remove"}, "action must be one of"),
            ({"action": "run", "check": "T1"}, "run takes no check"),
            ({"checks": "T1"}, "checks must be a list"),
        ):
            self.assertEqual(self.tool(**args)["code"], "INVALID_ARGUMENTS", args)
            self.assertIn(problem, self.tool(**args)["error"])
        self.assertEqual(self.tool(checks=["T1"])["code"], "NOT_RUN")

    def test_a_refused_run_keeps_the_note_and_the_notice(self):
        self.recording()
        self.tool(action="bind", check="T1", recording=SESSION)
        with self.engine(FakeEngine(emulator_replay=[DENIED]), "where the chat stands", "Engine restarted."):
            ran = self.tool()
        self.assertEqual(
            (ran["code"], ran["hermretroContext"], ran["notice"]),
            ("NOT_RUN", "where the chat stands", "Engine restarted."),
        )

    def test_a_subagent_changes_nothing(self):
        self.recording()
        self.tool(action="bind", check="T1", recording=SESSION)
        before = playtest.read(self.root)
        with mock.patch.object(hermes_host, "_is_child", lambda _session: True):
            for args in (
                {},
                {"action": "bind", "check": "T2", "recording": SESSION},
                {"action": "unbind", "check": "T1"},
            ):
                self.assertEqual(self.tool(**args)["code"], "PARENT_ONLY", args)
        self.assertEqual(playtest.read(self.root), before)

    def test_a_broker_that_cannot_start_points_at_setup(self):
        self.recording()
        self.bind()
        down = mock.Mock(side_effect=hermes_host.BrokerUnavailable("no node"))
        with mock.patch.object(hermes_host, "ensure_broker", down):
            answer = self.tool()
        self.assertEqual(answer["code"], "UNAVAILABLE")
        self.assertIn("hermretro:setup", answer["nextStep"])

    def test_a_broker_of_older_code_that_will_not_make_way_asks_to_try_again_later(self):
        self.recording()
        self.bind()
        before = playtest.read(self.root)
        old = mock.Mock(side_effect=hermes_host.BrokerRestarting("an older hermretro is still running", waits=False))
        with mock.patch.object(hermes_host, "ensure_broker", old):
            answer = self.tool()
        self.assertEqual(answer["code"], "RESTARTING")
        self.assertIn("Do not stop or restart hermretro's background processes", answer["nextStep"])
        self.assertEqual(playtest.read(self.root), before)


if __name__ == "__main__":
    unittest.main()
