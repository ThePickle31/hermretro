"""chromatic_playtest's bindings (backend/library/playtest.py): test-plan checks bound to recorded attempts, and the
results that stand only while the check's binding and words are the ones they ran for."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import layout, plan_checks, playtest, playtest_run  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.library.playtest_fakes import (  # noqa: E402 - the repository root goes on sys.path first
    OTHER,
    SESSION,
    FakeEngine,
    PlaytestCase,
    answer,
    replayed,
)


class Binding(PlaytestCase):
    def test_a_check_binds_to_a_recording_in_the_project(self):
        folder = self.recording()
        binding, problems = self.bind("t1", SESSION, to_action_index=6)
        self.assertEqual(problems, [])
        self.assertEqual(binding["id"], "T1")
        self.assertEqual(binding["recording"], "artifacts/playtests/session-1")
        self.assertEqual((binding["sessionId"], binding["branchId"]), (SESSION, "branch-0001"))
        self.assertEqual(binding["expect"], {"frames": "match"})
        self.assertEqual(binding["revision"], playtest.revision(binding))
        self.assertEqual(playtest.public(self.root, binding)["recording"], str(folder))
        plan = plan_checks.read_plan(self.root)
        self.assertEqual(
            playtest.coverage(plan, playtest.read(self.root)),
            {"bound": ["T1"], "stale": [], "unbound": ["T2", "F1"], "retired": []},
        )
        stored = layout.state(self.root, playtest.STATE_FILE)
        self.assertEqual(stored["version"], 1)
        self.assertEqual(stored["bindings"]["T1"], binding)
        self.assertTrue(playtest.unbind(self.root, "T1"))
        self.assertFalse(playtest.unbind(self.root, "T1"))
        self.assertEqual(playtest.read(self.root)["bindings"], {})

    def test_a_binding_must_name_an_open_check_and_a_recording(self):
        self.recording()
        self.recording("live", status="recording")
        for check, recording, options, problem in (
            ("T9", "artifacts/playtests/session-1", {}, "check must be an open check"),
            ("T1", "artifacts/playtests/missing", {}, "recording: artifacts/playtests/missing is no recording"),
            ("T1", "artifacts/playtests/session-1", {"branch_id": "branch-0002"}, "branchId must be one of"),
            ("T1", "artifacts/playtests/session-1", {"to_action_index": -1}, "toActionIndex must be"),
            ("T1", "artifacts/playtests/live", {}, "still being made"),
            ("T1", "artifacts/playtests/session-1", {"expect": {"frames": "ignore"}}, "expect checks nothing"),
            ("T1", "artifacts/playtests/session-1", {"expect": {"scene": ""}}, "expect.scene must be"),
            ("T1", "artifacts/playtests/session-1", {"expect": {"variables": {"Oil": 1.5}}}, "expect.variables"),
            ("T1", "artifacts/playtests/session-1", {"expect": {"hp": 3}}, "unknown field 'hp'"),
        ):
            binding, problems = self.bind(check, recording, **options)
            self.assertIsNone(binding, problem)
            self.assertIn(problem, " ".join(problems))
        self.assertEqual(playtest.read(self.root)["bindings"], {})
        (self.root / plan_checks.PLAN_FILE).unlink()
        self.assertIn("no test plan", self.bind()[1][0])

    def test_a_recording_still_being_made_binds_as_the_engine_sees_it(self):
        # Its recording.json lists the branches it started with; a checkpoint restored since added branch-0002.
        self.recording("live", status="recording")
        live = {"sessionId": SESSION, "status": "recording", "branchId": "branch-0002"}
        live["branches"] = [{"branchId": "branch-0001"}, {"branchId": "branch-0002", "checkpointId": "c"}]
        engine = FakeEngine(emulator_recording=[answer(live)])
        binding, problems = self.bind("T1", "artifacts/playtests/live", engine, to_action_index=4)
        self.assertEqual(problems, [])
        self.assertEqual(binding["branchId"], "branch-0002")
        self.assertEqual(
            engine.calls,
            [
                (
                    "emulator_recording",
                    {"action": "status", "recordingPath": str(self.root / "artifacts/playtests/live")},
                )
            ],
        )
        for response, problem in (
            (answer({**live, "sessionId": OTHER}), "now holds another attempt"),
            ({"ok": False, "denied": {"code": "LEASE_REQUIRED", "message": "not here"}}, "not here"),
        ):
            engine = FakeEngine(emulator_recording=[response])
            binding, problems = self.bind("T2", "artifacts/playtests/live", engine, to_action_index=4)
            self.assertIsNone(binding)
            self.assertIn(problem, " ".join(problems))
        self.assertEqual(list(playtest.read(self.root)["bindings"]), ["T1"])

    def test_the_finishable_check_binds_only_a_whole_run_that_passed(self):
        self.recording("passed", outcome="passed")
        self.recording("failed", status="failed", outcome="failed")
        self.recording("stopped")
        self.recording("live", status="recording")
        restored = [{"branchId": "branch-0001"}, {"branchId": "branch-0002", "checkpointId": "c"}]
        self.recording("restored", outcome="passed", branchId="branch-0002", branches=restored)
        for name, options, problem in (
            ("failed", {}, "ended with outcome failed"),
            ("stopped", {}, "ended with outcome none"),
            ("live", {}, "is still recording"),
            ("restored", {}, "restored a checkpoint"),
            ("passed", {"to_action_index": 3}, "F1 replays the whole run"),
        ):
            binding, problems = self.bind("F1", f"artifacts/playtests/{name}", **options)
            self.assertIsNone(binding, name)
            self.assertIn(problem, " ".join(problems), name)
        binding, problems = self.bind("F1", "artifacts/playtests/passed")
        self.assertEqual((problems, binding["toActionIndex"]), ([], None))

    def test_a_scene_or_variables_decide_instead_of_the_frames(self):
        self.recording()
        binding, _ = self.bind(expect={"scene": "Cellar", "variables": {"Oil": 1}})
        self.assertEqual(binding["expect"], {"scene": "Cellar", "variables": {"Oil": 1}, "frames": "ignore"})
        binding, _ = self.bind(expect={"scene": "Cellar", "frames": "match"})
        self.assertEqual(binding["expect"]["frames"], "match")


class Results(PlaytestCase):
    def run_t1(self):
        self.play(FakeEngine(emulator_replay=[replayed()]), only=["T1"])

    def test_a_result_stands_on_its_rom_for_the_binding_it_ran_for(self):
        self.recording()
        self.bind()
        self.run_t1()
        self.assertEqual(self.kept(), {"T1": "passed"})
        self.assertEqual(self.kept("0" * 64), {})
        self.bind(to_action_index=3)  # bound again: the result was for the binding before
        self.assertEqual(self.kept(), {})
        self.run_t1()
        self.assertTrue(playtest.unbind(self.root, "T1"))
        self.assertEqual(self.kept(), {})
        self.assertNotIn("T1", playtest.read(self.root)["results"])

    def test_editing_a_checks_words_makes_its_binding_stale(self):
        self.recording()
        self.bind()
        self.run_t1()
        # Its status changes nothing; its words do.
        self.plan("T1 | the gate stays shut | passed", "T2 | the lamp lights | not run", "F1 | the ending | not run")
        self.assertEqual(self.kept(), {"T1": "passed"})
        self.plan("T1 | the gate opens | not run", "T2 | the lamp lights | not run", "F1 | the ending | not run")
        plan = plan_checks.read_plan(self.root)
        self.assertEqual(playtest.coverage(plan, playtest.read(self.root))["stale"], ["T1"])
        self.assertEqual(self.kept(), {})
        engine = FakeEngine()
        result = self.play(engine)
        self.assertEqual((engine.calls, result["stale"], result["counts"]["stale"]), ([], ["T1"], 1))
        _result, why = playtest_run.run(self.root, FakeEngine(), self.save, ["T1"])
        self.assertIn("T1 changed in docs/game/TEST-PLAN.md since it was bound", why)

    def test_a_retired_id_used_again_is_another_check(self):
        self.recording()
        self.bind()
        self.run_t1()
        self.plan("T2 | the lamp lights | not run", "F1 | the ending | not run")
        plan = plan_checks.read_plan(self.root)
        self.assertEqual(playtest.coverage(plan, playtest.read(self.root))["retired"], ["T1"])
        self.plan("T1 | the bridge holds | not run", "T2 | the lamp lights | not run", "F1 | the ending | not run")
        self.assertEqual(self.kept(), {})
        plan = plan_checks.read_plan(self.root)
        self.assertEqual(playtest.coverage(plan, playtest.read(self.root))["stale"], ["T1"])

    def test_a_result_for_a_binding_replaced_during_its_run_is_not_kept(self):
        self.recording()
        self.bind()
        self.bind("T2")

        def rebind_meanwhile(_arguments):
            self.bind("T2", to_action_index=2)
            return replayed()

        result = self.play(FakeEngine(emulator_replay=[replayed(), rebind_meanwhile]))
        self.assertEqual(self.kept(), {"T1": "passed"})
        self.assertIn("bound again or unbound while it ran", result["checks"][1]["notes"][-1])

    def test_the_state_is_read_once_as_a_snapshot(self):
        self.recording()
        self.bind()
        state = playtest.read(self.root)
        self.assertEqual(set(state), {"bindings", "results"})
        layout.write_state(self.root, playtest.STATE_FILE, {"bindings": [], "results": {"T1": "x"}})
        self.assertEqual(playtest.read(self.root), {"bindings": {}, "results": {}})


if __name__ == "__main__":
    unittest.main()
