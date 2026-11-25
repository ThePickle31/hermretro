"""The pipeline gate (backend/library/pipeline.py): chromatic_present_game and chromatic_build_report wait until the
game's ROM is the last build of its sources and its bound test-plan checks and F1 passed on it, unless the call says
why the game goes out unfinished; chromatic_rom_build's result names the checks a build left to replay."""

import json
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import results  # noqa: E402 - the repository root goes on sys.path first
from backend.library import (  # noqa: E402 - the repository root goes on sys.path first
    finish_run,
    freshness,
    pipeline,
    playtest_run,
    report_tools,
)
from backend.library import games as library  # noqa: E402 - the repository root goes on sys.path first
from backend.library import tools as library_tools  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.library.playtest_fakes import (  # noqa: E402 - the repository root goes on sys.path first
    ROM,
    FakeEngine,
    PlaytestCase,
    finished,
    replayed,
    write_recording,
)
from tests.support import isolated_home, make_library_game  # noqa: E402 - the repository root goes on sys.path first

UNFINISHED = "The user asked to see it as it is."


def built(root: Path, **fields) -> dict:
    """The library's record of a successful build of ``root`` as it stands, as the broker writes it."""
    return {"t": time.time(), "ok": True, "sha256": finish_run.current_rom(root)[1], **fields}


class RomState(PlaytestCase):
    def test_the_rom_is_current_while_its_sources_are_what_it_was_built_from(self):
        (self.root / "game.gbsproj").write_text("{}")
        (self.root / "project").mkdir()
        (self.root / "project" / "scene.gbsres").write_text("{}")
        last = built(self.root, sources=freshness.source_digest(self.root))
        self.assertIsNone(pipeline.rom_state(self.root, last)["problem"])
        (self.root / "docs" / "game" / "NOTES.md").write_text("not a source")
        self.assertIsNone(pipeline.rom_state(self.root, last)["problem"])
        (self.root / "project" / "scene.gbsres").write_text('{"changed": true}')
        self.assertIn("Game files changed after the last build", pipeline.rom_state(self.root, last)["problem"])

    def test_a_failed_build_another_rom_or_none_is_not_current(self):
        self.assertIn("failed", pipeline.rom_state(self.root, {"t": time.time(), "ok": False})["problem"])
        other = {"t": time.time(), "ok": True, "sha256": "0" * 64}
        self.assertIn("not the one the last chromatic_rom_build made", pipeline.rom_state(self.root, other)["problem"])
        (self.root / "build" / "game.gbc").unlink()
        state = pipeline.rom_state(self.root, built(self.root))
        self.assertEqual((state["sha256"], state["problem"]), (None, "This game has no readable ROM in build/ yet."))

    def test_a_build_recorded_without_its_sources_is_compared_by_file_times(self):
        self.assertIsNone(pipeline.rom_state(self.root, None)["problem"])
        self.assertIsNone(pipeline.rom_state(self.root, built(self.root))["problem"])
        earlier = built(self.root, t=time.time() - 60)
        (self.root / "main.c").write_text("int main;")
        self.assertIn("Game files changed", pipeline.rom_state(self.root, earlier)["problem"])


class Gate(PlaytestCase):
    def gate(self, shown=()):
        return pipeline.gate("chromatic_present_game", self.root, built(self.root), shown)

    def bind_all(self):
        self.recording()
        write_recording(self.root / "artifacts" / "playtests" / "run", outcome="passed")
        self.bind("T1")
        self.bind("F1", "artifacts/playtests/run")

    def test_a_game_without_a_test_plan_needs_only_a_current_rom(self):
        (self.root / "docs" / "game" / "TEST-PLAN.md").unlink()
        self.assertIsNone(self.gate())
        held = pipeline.gate("chromatic_present_game", self.root, {"t": time.time(), "ok": False})
        self.assertEqual(held["code"], "BUILD_FIRST")
        self.assertIn("chromatic_rom_build", held["nextStep"])

    def test_bound_checks_and_f1_wait_for_a_passing_run_on_this_rom(self):
        held = self.gate()
        self.assertEqual(held["code"], "PLAYTEST_FIRST")
        self.assertIn("F1, the run from power-on to the ending, is bound to none.", held["error"])
        self.assertIn('"check":"F1"', held["nextStep"])
        self.assertTrue(held["nextStep"].endswith(pipeline.OVERRIDE_STEP))
        self.bind_all()
        held = self.gate()
        self.assertIn("T1, F1 have no result on this ROM.", held["error"])
        self.assertIn("chromatic_playtest {}", held["nextStep"])
        self.assertEqual(
            held["pipeline"]["checks"]["unbound"], ["T2"]
        )  # an unbound check other than F1 waits for no one
        self.play(FakeEngine(emulator_replay=[replayed("failed", status="diverged"), finished("failed")]))
        self.assertIn("T1, F1 failed on this ROM.", self.gate()["error"])
        self.play(FakeEngine(emulator_replay=[replayed(coverage="retained-frames"), finished()]))
        self.assertIsNone(self.gate())  # sampled counts, as the build report takes it
        (self.root / "build" / "game.gbc").write_bytes(ROM + b"rebuilt")
        self.assertIn("T1, F1 have no result on this ROM.", self.gate()["error"])

    def test_a_check_no_replay_could_judge_holds_until_shown_otherwise(self):
        self.bind_all()
        self.play(FakeEngine(emulator_replay=[replayed("needs-review"), finished()]))
        held = self.gate()
        self.assertIn("chromatic_playtest could not judge T1 on this ROM.", held["error"])
        self.assertIn('"action":"unbind"', held["nextStep"])
        self.assertIsNone(self.gate(shown=["t1"]))

    def test_f1_shown_by_the_reports_own_run_counts_for_an_unbound_f1(self):
        self.recording()
        self.bind("T1")
        self.play(FakeEngine(emulator_replay=[replayed()]))
        self.assertEqual(self.gate()["code"], "PLAYTEST_FIRST")
        self.assertIsNone(self.gate(shown=["F1"]))
        self.plan("T1 | the gate stays shut | not run", "F1 | the ending, in other words | not run")
        self.assertIn("is bound to none", self.gate()["error"])  # T1's words are the same; F1 had no binding

    def test_the_override_is_the_users_request_in_a_few_words(self):
        self.assertEqual(pipeline.override(None), (None, None))
        self.assertEqual(pipeline.override("  show   me now "), ("show me now", None))
        for value in ("", "   ", "x" * (pipeline.MAX_OVERRIDE + 1), 3):
            self.assertIsNotNone(pipeline.override(value)[1], value)


class AfterBuild(PlaytestCase):
    def test_a_build_names_the_bound_checks_whose_results_it_left_on_an_earlier_rom(self):
        self.assertIsNone(pipeline.after_build(self.root))  # nothing bound
        self.recording()
        self.bind("T1")
        self.bind("T2")
        self.assertEqual(pipeline.after_build(self.root)["notRun"], ["T1", "T2"])
        self.play(FakeEngine(emulator_replay=[replayed(), replayed()]), only=["T1"])
        self.assertEqual(pipeline.after_build(self.root)["notRun"], ["T2"])
        self.play(FakeEngine(emulator_replay=[replayed(), replayed()]))
        self.assertIsNone(pipeline.after_build(self.root))  # a rebuild to the same bytes leaves every result
        (self.root / "build" / "game.gbc").write_bytes(ROM + b"rebuilt")
        left = pipeline.after_build(self.root)
        self.assertEqual((left["staleResults"], left["notRun"]), (["T1", "T2"], []))
        self.assertIn("chromatic_playtest {}", left["nextStep"])

    def test_the_build_result_carries_it_as_test_plan(self):
        self.recording()
        self.bind("T1")
        build = {"ok": True, "result": {"structuredContent": {"success": True, "projectRoot": str(self.root)}}}
        extra = hermes_host._build_extra(build, "c1", "s1")
        self.assertEqual(extra["testPlan"]["notRun"], ["T1"])
        payload = json.loads(results.encode(build, "chromatic_rom_build", None, False, None, extra))
        self.assertEqual(list(payload)[:2], ["buildRef", "testPlan"])
        failed = {"ok": True, "result": {"structuredContent": {"success": False, "projectRoot": str(self.root)}}}
        self.assertIsNone(hermes_host._build_extra(failed, "c1", "s1"))
        self.assertIsNone(hermes_host._build_extra({"ok": False, "error": "gone"}, "c1", "s1"))


class Tools(unittest.TestCase):
    """The two tools the gate holds, on a library game ready to present but for its test plan."""

    def setUp(self):
        self.home = isolated_home(self)
        self.game, self.root = make_library_game(self.home, "Lantern", chat="c1")
        self.sha = finish_run.current_rom(self.root)[1]
        self.rom_time = (self.root / "build" / "game.gbc").stat().st_mtime  # the web copy was made with it
        hermes_host._registry().upsert(str(self.root), build=built(self.root, t=self.rom_time))
        plan = self.root / "docs" / "game" / "TEST-PLAN.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("| ID | Then | Status |\n|---|---|---|\n| T1 | the lamp lights | not run |\n")
        write_recording(self.root / "artifacts" / "playtests" / "t1")
        for patch in (
            mock.patch.object(hermes_host, "_chat_project", lambda *_ids: str(self.root)),
            mock.patch.object(
                library_tools.player_server, "get_server", **{"return_value.url.return_value": "http://x/"}
            ),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        from backend.library import playtest

        playtest.bind(self.root, FakeEngine(), "T1", "artifacts/playtests/t1")

    def present(self, **args):
        return json.loads(library_tools.present_game_handler(args, conversation_id="c1", session_id="s1"))

    def report(self, **args):
        card = {"title": "Lantern", "summary": "A lamp in the dark.", "difficulty": "Easy."}
        card["checks"] = [{"id": "T1", "text": "The lamp lights", "result": "passed"}]
        return json.loads(report_tools.build_report_handler({**card, **args}, conversation_id="c1", session_id="s1"))

    def passed(self):
        engine = FakeEngine(emulator_replay=[replayed(rom=self.sha)])
        self.assertIsNone(playtest_run.run(self.root, engine, lambda result: [])[1])

    def test_present_waits_for_the_checks_unless_the_user_asked_for_it_unfinished(self):
        held = self.present()
        self.assertEqual(held["code"], "PLAYTEST_FIRST")
        self.assertIn("T1 has no result on this ROM.", held["error"])
        self.assertIsNone((hermes_host._registry().get(self.game) or {}).get("presented"))
        shown = self.present(unfinished=UNFINISHED)
        self.assertTrue(shown["ok"], shown)
        self.assertEqual(shown["unfinished"]["request"], UNFINISHED)
        self.assertIn("T1 has no result on this ROM.", shown["unfinished"]["notVerified"])
        self.assertEqual(self.present(unfinished="")["code"], "INVALID_ARGUMENTS")
        self.passed()
        shown = self.present()
        self.assertTrue(shown["ok"], shown)
        self.assertNotIn("unfinished", shown)

    def test_a_report_waits_for_the_checks_and_names_its_other_problems_with_them(self):
        held = self.report()
        self.assertEqual(held["code"], "PLAYTEST_FIRST")
        self.assertIn("chromatic_build_report waits", held["error"])
        both = self.report(suggestions=["x" * 41])
        self.assertEqual(both["code"], "INVALID_REPORT")
        self.assertIn("T1 has no result on this ROM.", " ".join(both["problems"]))
        taken = self.report(unfinished=UNFINISHED)
        self.assertTrue(taken["ok"], taken)
        self.assertEqual(taken["report"]["unfinished"], UNFINISHED)
        self.assertIn(f"Reported unfinished ({UNFINISHED})", taken["warnings"][-1])
        self.passed()
        taken = self.report()
        self.assertTrue(taken["ok"], taken)
        self.assertNotIn("unfinished", taken["report"])

    def test_a_change_to_the_sources_after_the_build_holds_both(self):
        self.passed()
        sources = freshness.source_digest(self.root)
        hermes_host._registry().upsert(str(self.root), build=built(self.root, t=self.rom_time, sources=sources))
        self.assertTrue(self.report()["ok"])
        (self.root / "project" / "scenes" / "extra.gbsres").parent.mkdir(parents=True, exist_ok=True)
        (self.root / "project" / "scenes" / "extra.gbsres").write_text("{}")
        self.assertEqual(self.report()["code"], "BUILD_FIRST")


class LastBuild(unittest.TestCase):
    def test_the_library_records_the_built_roms_hash_and_its_sources(self):
        home = isolated_home(self)
        _game, root = make_library_game(home, "Burrow")
        structured = {"outputPath": str(root / "build" / "game.gbc"), "rom": {"sha256": "a" * 64}}
        entry = library.Registry(hermes_host.paths.library_dir()).observe(
            "rom_build", {}, structured, False, lane_root=str(root), conversation_id=None
        )
        self.assertEqual(entry["lastBuild"]["sha256"], "a" * 64)
        self.assertEqual(entry["lastBuild"]["sources"], freshness.source_digest(root))
        entry = library.Registry(hermes_host.paths.library_dir()).observe(
            "rom_build", {}, {"error": "no"}, True, lane_root=str(root), conversation_id=None
        )
        self.assertNotIn("sources", entry["lastBuild"])


if __name__ == "__main__":
    unittest.main()
