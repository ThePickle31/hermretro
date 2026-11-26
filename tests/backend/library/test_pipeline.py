"""The pipeline gate (backend/library/pipeline.py): chromatic_present_game and chromatic_build_report wait until the
game's ROM is the last build of its sources and its bound test-plan checks and F1 passed on it, unless the call says
why the game goes out unfinished; chromatic_rom_build's result names the checks a build left to replay."""

import json
import os
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
    playtest,
    playtest_run,
    playtest_tools,
    report_tools,
)
from backend.library import games as library  # noqa: E402 - the repository root goes on sys.path first
from backend.library import tools as library_tools  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.library.playtest_fakes import (  # noqa: E402 - the repository root goes on sys.path first
    ROM,
    ROM_SHA,
    FakeEngine,
    PlaytestCase,
    finished,
    replayed,
    write_recording,
)
from tests.support import isolated_home, make_library_game, record_build  # noqa: E402 - the repository root goes on sys.path first

UNFINISHED = "The user asked to see it as it is."


def built(root: Path, **fields) -> dict:
    """The library's record of a successful build of ``root`` as it stands, as the broker writes it."""
    sha = finish_run.current_rom(root)[1]
    return {"t": time.time(), "ok": True, "sha256": sha, "sources": freshness.source_digest(root), **fields}


class RomState(PlaytestCase):
    def test_the_rom_is_current_while_its_sources_are_what_it_was_built_from(self):
        (self.root / "game.gbsproj").write_text("{}")
        (self.root / "project").mkdir()
        (self.root / "project" / "scene.gbsres").write_text("{}")
        last = built(self.root)
        self.assertIsNone(pipeline.rom_state(self.root, last)["problem"])
        (self.root / "docs" / "game" / "NOTES.md").write_text("not a source")
        (self.root / "assets").mkdir()
        (self.root / "assets" / ".DS_Store").write_text("a file browser's")
        self.assertIsNone(pipeline.rom_state(self.root, last)["problem"])
        (self.root / "project" / "scene.gbsres").write_text('{"changed": true}')
        self.assertEqual(pipeline.rom_state(self.root, last)["problem"], pipeline.CHANGED)

    def test_a_failed_build_another_rom_or_none_is_not_current(self):
        self.assertIn("failed", pipeline.rom_state(self.root, {"t": time.time(), "ok": False})["problem"])
        other = built(self.root, sha256="0" * 64)
        self.assertIn("not the one the last chromatic_rom_build made", pipeline.rom_state(self.root, other)["problem"])
        (self.root / "build" / "game.gbc").unlink()
        state = pipeline.rom_state(self.root, built(self.root))
        self.assertEqual((state["sha256"], state["problem"]), (None, "This game has no readable ROM in build/ yet."))

    def test_only_a_recorded_digest_passes_never_file_times(self):
        self.assertEqual(pipeline.rom_state(self.root, None)["problem"], pipeline.NO_RECORD)
        later = time.time() + 600  # the ROM looks newer than every source
        os.utime(self.root / "build" / "game.gbc", (later, later))
        for last in (built(self.root, sources=None), built(self.root, sha256=None), {"t": later, "ok": True}):
            self.assertEqual(pipeline.rom_state(self.root, last)["problem"], pipeline.UNKNOWN_SOURCES, last)

    def test_removing_the_gbsproj_is_a_change(self):
        (self.root / "game.gbsproj").write_text("{}")
        last = built(self.root)
        (self.root / "game.gbsproj").unlink()
        self.assertEqual(pipeline.rom_state(self.root, last)["problem"], pipeline.CHANGED)

    def test_a_c_games_sources_leave_out_its_notes_and_scratch_in_any_spelling(self):
        (self.root / "main.c").write_text("int main;")
        last = built(self.root)
        (self.root / "NOTES.md").write_text("what I tried")
        (self.root / "game.json").write_text("{}")
        (self.root / "Scratch").mkdir()
        (self.root / "Scratch" / "helper.py").write_text("print(1)")
        with mock.patch.object(freshness, "ignores_case", return_value=True):
            self.assertIsNone(pipeline.rom_state(self.root, last)["problem"])
        with mock.patch.object(freshness, "ignores_case", return_value=False):
            self.assertEqual(pipeline.rom_state(self.root, last)["problem"], pipeline.CHANGED, "another folder there")
        (self.root / "Scratch" / "helper.py").unlink()
        (self.root / "Scratch").rmdir()
        stamp = (self.root / "main.c").stat().st_mtime
        (self.root / "main.c").write_text("int main();")
        os.utime(self.root / "main.c", (stamp, stamp))  # an edit within the same second still counts
        self.assertEqual(pipeline.rom_state(self.root, last)["problem"], pipeline.CHANGED)

    def test_the_source_list_stops_at_its_bound_while_listing(self):
        for index in range(5):
            (self.root / f"part{index}.c").write_text("")
        with mock.patch.object(freshness, "MAX_SOURCE_FILES", 3):
            self.assertIsNone(freshness.source_files(self.root))
            self.assertIsNone(freshness.source_digest(self.root))
        self.assertEqual(len(freshness.source_files(self.root)), 5)


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
        self.assertIn("call chromatic_present_game again", held["nextStep"])
        self.assertNotIn("chromatic_playtest", held["nextStep"], "no test plan to replay")
        self.plan("T1 | the gate stays shut | not run")
        self.assertIn("chromatic_playtest {} on the new ROM", pipeline.gate("x", self.root, None)["nextStep"])

    def test_bound_checks_and_f1_wait_for_a_passing_run_on_this_rom(self):
        held = self.gate()
        self.assertEqual(held["code"], "PLAYTEST_FIRST")
        self.assertIn(f"{pipeline.FINISH_WORDS} is bound to none.", held["error"])
        self.assertIn(f"{pipeline.FINISH_WORDS} is bound to none.", held["reasons"])
        self.assertIn('"check":"F1"', held["nextStep"])
        self.assertIn("as the test plan says", held["nextStep"], "F1 is not always a run to an ending")
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
        self.assertIn(pipeline.EVIDENCE_COUNTS, held["nextStep"])
        self.assertIsNone(self.gate(shown=["t1"]))

    def test_evidence_a_build_report_kept_counts_on_its_rom_while_the_checks_words_stand(self):
        self.recording()
        self.bind("T1")
        self.play(FakeEngine(emulator_replay=[replayed()]))
        plan = playtest.plan_checks.read_plan(self.root)
        playtest.verify(self.root, plan, ROM_SHA, {"F1": "artifacts/playtests/session-1"})
        self.assertIsNone(self.gate())
        self.plan("T1 | the gate stays shut | not run", "F1 | the ending, in other words | not run")
        self.assertIn("is bound to none", self.gate()["error"])  # F1's words changed after it was shown
        self.plan("T1 | the gate stays shut | not run", "F1 | the ending | not run")
        (self.root / "build" / "game.gbc").write_bytes(ROM + b"rebuilt")
        self.assertIn("is bound to none", pipeline.gate("x", self.root, built(self.root))["error"])  # another ROM

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
    def after(self, arguments=None, sha=ROM_SHA):
        return pipeline.after_build(self.root, arguments or {}, sha)

    def test_a_build_names_the_bound_checks_whose_results_it_left_on_an_earlier_rom(self):
        self.assertIsNone(self.after())  # nothing bound
        self.recording()
        self.bind("T1")
        self.bind("T2")
        self.assertEqual(self.after()["notRun"], ["T1", "T2"])
        self.play(FakeEngine(emulator_replay=[replayed(), replayed()]), only=["T1"])
        self.assertEqual(self.after()["notRun"], ["T2"])
        self.play(FakeEngine(emulator_replay=[replayed(), replayed()]))
        self.assertIsNone(self.after())  # a rebuild to the same bytes leaves every result
        (self.root / "build" / "game.gbc").write_bytes(ROM + b"rebuilt")
        left = self.after(sha=finish_run.current_rom(self.root)[1])
        self.assertEqual((left["staleResults"], left["notRun"]), (["T1", "T2"], []))
        self.assertIn("chromatic_playtest {}", left["nextStep"])

    def test_only_a_build_that_made_the_games_rom_says_so(self):
        self.recording()
        self.bind("T1")
        self.assertIsNone(self.after(sha="0" * 64), "it wrote another ROM than the game's")
        self.assertIsNone(self.after(sha=None))
        (self.root / "game.gbsproj").write_text("{}")
        self.assertIsNone(self.after({"sourcePath": "scratch/test.c"}), "a C experiment inside a GB Studio game")
        self.assertEqual(self.after()["notRun"], ["T1"])

    def test_the_build_result_carries_it_as_test_plan(self):
        self.recording()
        self.bind("T1")
        content = {"success": True, "projectRoot": str(self.root), "rom": {"sha256": ROM_SHA}}
        build = {"ok": True, "result": {"structuredContent": content}}
        extra = hermes_host._build_extra(build, {}, "c1", "s1")
        self.assertEqual(extra["testPlan"]["notRun"], ["T1"])
        payload = json.loads(results.encode(build, "chromatic_rom_build", None, False, None, extra))
        self.assertEqual(list(payload)[:2], ["buildRef", "testPlan"])
        (self.root / "game.gbsproj").write_text("{}")
        self.assertIsNone(hermes_host._build_extra(build, {"sourcePath": "scratch/t.c"}, "c1", "s1"))
        failed = {"ok": True, "result": {"structuredContent": {**content, "success": False}}}
        self.assertIsNone(hermes_host._build_extra(failed, {}, "c1", "s1"))
        self.assertIsNone(hermes_host._build_extra({"ok": False, "error": "gone"}, {}, "c1", "s1"))


class Tools(unittest.TestCase):
    """The two tools the gate holds, on a library game ready to present but for its test plan."""

    def setUp(self):
        self.home = isolated_home(self)
        self.game, self.root = make_library_game(self.home, "Lantern", chat="c1")
        self.sha = finish_run.current_rom(self.root)[1]
        self.plan("| T1 | the lamp lights | not run |\n")
        write_recording(self.root / "artifacts" / "playtests" / "t1")
        for patch in (
            mock.patch.object(hermes_host, "_chat_project", lambda *_ids: str(self.root)),
            mock.patch.object(
                library_tools.player_server, "get_server", **{"return_value.play_url.return_value": "http://x/"}
            ),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        playtest.bind(self.root, FakeEngine(), "T1", "artifacts/playtests/t1")

    def plan(self, rows: str):
        path = self.root / "docs" / "game" / "TEST-PLAN.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("| ID | Then | Status |\n|---|---|---|\n" + rows)

    def present(self, **args):
        return json.loads(library_tools.present_game_handler(args, conversation_id="c1", session_id="s1"))

    def report(self, checks=None, **args):
        card = {"title": "Lantern", "summary": "A lamp in the dark.", "difficulty": "Easy."}
        card["checks"] = checks or [{"id": "T1", "text": "The lamp lights", "result": "passed"}]
        return json.loads(report_tools.build_report_handler({**card, **args}, conversation_id="c1", session_id="s1"))

    def passed(self):
        engine = FakeEngine(emulator_replay=[replayed(rom=self.sha)])
        self.assertIsNone(playtest_run.run(self.root, engine, lambda result: [])[1])

    def presented(self):
        return (hermes_host._registry().get(self.game) or {}).get("presented")

    def test_present_waits_for_the_checks_unless_the_user_asked_for_it_unfinished(self):
        held = self.present()
        self.assertEqual(held["code"], "PLAYTEST_FIRST")
        self.assertIn("T1 has no result on this ROM.", held["error"])
        self.assertIsNone(self.presented())
        shown = self.present(unfinished=UNFINISHED)
        self.assertTrue(shown["ok"], shown)
        self.assertEqual(shown["unfinished"], {"request": UNFINISHED, "notVerified": ["T1 has no result on this ROM."]})
        self.assertIn("marked unfinished", shown["message"])
        self.assertEqual(self.presented()["unfinished"], shown["unfinished"], "the library keeps it with the game")
        listed = hermes_host._registry().presentations()
        self.assertEqual(listed[-1]["unfinished"]["request"], UNFINISHED)
        self.assertEqual(self.present(unfinished="")["code"], "INVALID_ARGUMENTS")
        self.passed()
        shown = self.present()
        self.assertTrue(shown["ok"], shown)
        self.assertNotIn("unfinished", shown)
        self.assertNotIn("unfinished", self.presented())

    def test_asked_for_as_it_is_the_last_intact_copy_is_shown_as_not_current(self):
        self.passed()
        scene = self.root / "project" / "scene.gbsres"
        scene.write_text('{"broken": true}')  # an edit after the build, not built yet
        held = self.present()
        self.assertEqual(held["code"], "BUILD_FIRST")
        shown = self.present(unfinished=UNFINISHED)
        self.assertTrue(shown["ok"], shown)
        self.assertIn("changed after the playable copy", shown["unfinished"]["notCurrent"])
        self.assertEqual(shown["unfinished"]["notVerified"], [pipeline.CHANGED])
        (self.root / "build" / "web" / "index.html").write_text("<html>edited</html>")  # no intact copy
        self.assertEqual(self.present(unfinished=UNFINISHED)["code"], "BUILD_FIRST")

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
        self.assertEqual(taken["report"]["notVerified"], ["T1 has no result on this ROM."], "the card shows it")
        self.assertIn(f"Reported unfinished ({UNFINISHED})", taken["warnings"][-1])
        self.passed()
        taken = self.report()
        self.assertTrue(taken["ok"], taken)
        self.assertNotIn("unfinished", taken["report"])
        self.assertNotIn("notVerified", taken["report"])

    def test_a_library_game_with_no_rom_is_reported_only_as_unfinished(self):
        (self.root / "build" / "game.gbc").unlink()
        held = self.report(checks=[{"id": "T1", "text": "The lamp lights", "result": "not run"}])
        self.assertEqual(
            (held["code"], held["reasons"]), ("BUILD_FIRST", ["This game has no readable ROM in build/ yet."])
        )
        taken = self.report(
            checks=[{"id": "T1", "text": "The lamp lights", "result": "not run"}], unfinished="Planned it only."
        )
        self.assertTrue(taken["ok"], taken)
        self.assertEqual(taken["report"]["notVerified"], ["This game has no readable ROM in build/ yet."])

    def test_f1_a_replay_cannot_judge_is_shown_by_the_report_and_then_presented(self):
        self.plan("| T1 | the lamp lights | not run |\n| F1 | one run through every room | not run |\n")
        self.passed()
        self.assertIn(pipeline.EVIDENCE_COUNTS, self.present()["nextStep"])
        rom = (self.root / "build" / "game.gbc").read_bytes()
        run = write_recording(self.root / "artifacts" / "playtests" / "f1", outcome="passed", rom=rom)
        checks = [
            {"id": "T1", "text": "The lamp lights", "result": "passed"},
            {"id": "F1", "text": "One run through every room", "result": "passed"},
        ]
        taken = self.report(checks=checks, finishRun=str(run))
        self.assertTrue(taken["ok"], taken)
        self.assertEqual(playtest.read(self.root)["verified"]["F1"]["evidence"], str(run.resolve()))
        shown = self.present()
        self.assertTrue(shown["ok"], shown)
        self.assertNotIn("unfinished", shown)

    def test_a_change_to_the_sources_after_the_build_holds_both(self):
        self.passed()
        self.assertTrue(self.report()["ok"])
        (self.root / "project" / "scenes" / "extra.gbsres").parent.mkdir(parents=True, exist_ok=True)
        (self.root / "project" / "scenes" / "extra.gbsres").write_text("{}")
        self.assertEqual(self.report()["code"], "BUILD_FIRST")

    def test_an_unbind_that_takes_away_a_failure_says_so(self):
        engine = FakeEngine(emulator_replay=[replayed("failed", status="diverged", rom=self.sha)])
        playtest_run.run(self.root, engine, lambda result: [])
        answer = json.loads(
            playtest_tools.playtest_handler({"action": "unbind", "check": "T1"}, conversation_id="c1", session_id="s1")
        )
        self.assertEqual(answer["cleared"], {"check": "T1", "result": "failed"})
        self.assertIn("report its true result", answer["nextStep"])
        playtest.bind(self.root, FakeEngine(), "T1", "artifacts/playtests/t1")
        answer = json.loads(
            playtest_tools.playtest_handler({"action": "unbind", "check": "T1"}, conversation_id="c1", session_id="s1")
        )
        self.assertNotIn("cleared", answer, "it had no result to lose")


class LastBuild(unittest.TestCase):
    def setUp(self):
        home = isolated_home(self)
        _game, self.root = make_library_game(home, "Burrow")
        self.registry = library.Registry(hermes_host.paths.library_dir())

    def observe(self, failed=False, **options):
        rom = self.root / "build" / "game.gbc"
        structured = {"outputPath": str(rom), "rom": {"sha256": library.file_sha256(rom)}}
        return self.registry.observe(
            "rom_build", {}, structured, failed, lane_root=str(self.root), conversation_id=None, **options
        )["lastBuild"]

    def test_the_library_records_the_built_roms_hash_and_the_sources_from_before_the_build(self):
        before = freshness.source_digest(self.root)
        entry = self.observe(sources_before=before)
        self.assertEqual(entry["sources"], before)
        self.assertEqual(entry["sha256"], library.file_sha256(self.root / "build" / "game.gbc"))
        self.assertNotIn("sources", self.observe(), "no digest from before the build")
        self.assertNotIn("sources", self.observe(True, sources_before=before), "a failed build")

    def test_a_file_saved_while_the_build_ran_leaves_its_sources_unrecorded(self):
        before = freshness.source_digest(self.root)
        (self.root / "project" / "scene.gbsres").write_text('{"saved": "mid-build"}')
        entry = self.observe(sources_before=before)
        self.assertNotIn("sources", entry)
        self.assertEqual(pipeline.rom_state(self.root, entry)["problem"], pipeline.UNKNOWN_SOURCES)

    def test_a_recorded_build_of_the_fixture_is_current(self):
        record_build(self.root)
        entry = self.registry.get(library.game_id(self.root))
        self.assertIsNone(pipeline.rom_state(self.root, entry["lastBuild"])["problem"])


if __name__ == "__main__":
    unittest.main()
