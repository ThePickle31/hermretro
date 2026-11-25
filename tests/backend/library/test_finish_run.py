"""chromatic_build_report's finishRun: the recording of the one run from power-on to the ending, checked against the
game's ROM (backend/library/finish_run.py) and required when the test plan's F1 was played."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.assets import versions as host_assets  # noqa: E402 - the repository root goes on sys.path first
from backend.library import plan_checks, report_plan, report_tools  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home  # noqa: E402 - the repository root goes on sys.path first

REPORT = {"title": "Burrow Run", "summary": "Three mazes to the den."}
SESSION = "0123456789abcdef0123456789abcdef"
ROM = b"\x00" * 0x150 + b"burrow"
UNFINISHED = "F1 still fails at the den; no fix found this turn."


class FinishRun(unittest.TestCase):
    def setUp(self):
        isolated_home(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "burrow"
        (self.root / "build").mkdir(parents=True)
        (self.root / "build" / "game.gbc").write_bytes(ROM)
        for patch in (
            mock.patch.object(hermes_host, "_chat_project", lambda *_ids: str(self.root)),
            mock.patch.object(host_assets, "_keep_paths"),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def recording(self, name="session-1", *, rom=ROM, status="stopped", branches=None, journal=True, **extra):
        """A recording folder as the engine's emulator worker leaves it (only what the report reads): its manifest
        and, with ``journal``, an ``events.jsonl`` that agrees with it (a list of rows to write instead)."""
        folder = self.root / "artifacts" / "playtests" / name
        folder.mkdir(parents=True)
        manifest = {
            "schemaVersion": 1,
            "kind": "gb-studio-playtest",
            "sessionId": SESSION,
            "rom": {"sha256": hashlib.sha256(rom).hexdigest(), "cgb": True},
            "status": status,
            "totalFrames": 5504,
            "branches": branches or [{"branchId": "branch-0001", "frame": 5504}],
            **extra,
        }
        (folder / "recording.json").write_text(json.dumps(manifest))
        if journal is True:
            journal = [{"sequence": 1, "kind": "header", "sessionId": SESSION, "rom": manifest["rom"]}]
            journal.append({"sequence": 2, "kind": "action", "frameHashes": "0" * 16 * 3600})
            if status != "recording":
                finish = {"status": status, **({"outcome": extra["outcome"]} if "outcome" in extra else {})}
                journal.append({"sequence": 3, "kind": "finish", "totalFrames": 5504, **finish})
        if journal:
            (folder / "events.jsonl").write_text("".join(json.dumps(row) + "\n" for row in journal))
        return folder

    def plan(self, *rows):
        path = plan_checks.plan_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("| ID | Then | Status |\n|---|---|---|\n" + "".join(f"| {row} |\n" for row in rows))

    def report(self, **args):
        return json.loads(report_tools.build_report_handler({**REPORT, **args}, session_id="s1"))

    def planned(self, result, **args):
        """A report for a game whose plan has T1 and the finishable check F1, with F1 at ``result``."""
        self.plan("T1 | the title shows | passed", "F1 | the ending shows | not run")
        checks = [
            {"id": "T1", "text": "Title shows", "result": "passed"},
            {"id": "F1", "text": "One run to the den", "result": result},
        ]
        return self.report(checks=checks, difficulty="Finished in one run in 9 minutes.", **args)

    def test_a_recorded_run_of_this_rom_is_kept_in_the_report(self):
        folder = self.recording(outcome="passed")
        for named in (str(folder), "artifacts/playtests/session-1", str(folder / "recording.json"), SESSION):
            answer = self.planned("passed", finishRun=named)
            self.assertTrue(answer["ok"], answer)
            self.assertEqual(
                answer["report"]["finishRun"],
                {
                    "recordingPath": str(folder.resolve()),
                    "sessionId": SESSION,
                    "status": "stopped",
                    "frames": 5504,
                    "outcome": "passed",
                },
            )
            self.assertNotIn("warnings", answer)

    def test_a_played_finish_check_needs_its_recording(self):
        for result in ("passed", "failed"):
            answer = self.planned(result)
            self.assertEqual(answer["code"], "INVALID_REPORT")
            self.assertIn("checks gives F1 a result but finishRun names no recording", answer["error"])
            self.assertIn("restart:true and recording:{}", answer["error"])
        # F1 not played on this ROM holds the report (pipeline.gate) until the turn says why it ends unfinished.
        self.assertEqual(self.planned("not run")["code"], "PLAYTEST_FIRST")
        answer = self.planned("not run", unfinished=UNFINISHED)
        self.assertTrue(answer["ok"], answer)
        self.assertIsNone(answer["report"]["finishRun"])
        self.assertIn("finishRun names no recording", answer["warnings"][0])

    def test_a_passed_run_needs_a_recording_stopped_as_passed(self):
        self.recording(status="failed", outcome="failed")
        answer = self.planned("passed", finishRun=SESSION)
        self.assertIn("checks gives F1 passed but its recording ended failed with outcome failed", answer["error"])
        answer = self.planned("failed", finishRun=SESSION, unfinished=UNFINISHED)
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(answer["report"]["finishRun"]["outcome"], "failed")
        # Closing the emulator, or stopping without a pass, ends a recording "stopped" too.
        for name, extra, ended in (
            ("closed", {}, "stopped with no outcome"),
            ("review", {"outcome": "needs-review"}, "stopped with outcome needs-review"),
        ):
            folder = self.recording(name, **extra)
            answer = self.planned("passed", finishRun=str(folder))
            self.assertEqual(answer["code"], "INVALID_REPORT", name)
            self.assertIn(f"checks gives F1 passed but its recording ended {ended}", answer["error"])
            self.assertIn('"outcome":"passed"', answer["error"])
            self.assertTrue(self.planned("failed", finishRun=str(folder), unfinished=UNFINISHED)["ok"], name)

    def test_the_journal_must_be_there_and_tell_the_same_run(self):
        header = {"sequence": 1, "kind": "header", "sessionId": SESSION}
        rom = {"sha256": hashlib.sha256(ROM).hexdigest(), "cgb": True}
        finish = {"sequence": 2, "kind": "finish", "status": "stopped", "outcome": "passed"}
        for name, journal in (
            ("no-journal", False),
            ("empty", []),
            ("other-rom", [{**header, "rom": {**rom, "sha256": "0" * 64}}, finish]),
            ("other-session", [{**header, "sessionId": "f" * 32, "rom": rom}, finish]),
            ("no-header", [finish]),
            ("unfinished", [{**header, "rom": rom}]),
            ("other-status", [{**header, "rom": rom}, {**finish, "status": "failed"}]),
            ("other-outcome", [{**header, "rom": rom}, {**finish, "outcome": "needs-review"}]),
        ):
            folder = self.recording(name, journal=journal, outcome="passed")
            answer = self.planned("passed", finishRun=str(folder))
            self.assertEqual(answer["code"], "INVALID_REPORT", name)
            self.assertIn("has no events.jsonl, or one that does not match its recording.json", answer["error"])
        # An attempt still recording has no finish row yet, and its last row may be half written.
        folder = self.recording("active", status="recording", journal=[{**header, "rom": rom}])
        with (folder / "events.jsonl").open("a") as journal:
            journal.write('{"sequence": 2, "kind": "act')
        self.assertIn("is still recording", self.report(finishRun=str(folder))["error"])

    def test_a_recording_that_is_no_finishable_run_of_this_build_is_refused(self):
        self.recording("other-rom", rom=b"an earlier build")
        self.recording(
            "restored",
            branches=[
                {"branchId": "branch-0001"},
                {"branchId": "branch-0002", "checkpointId": "checkpoint-" + "a" * 32},
            ],
        )
        self.recording("active", status="recording")
        (self.root / "artifacts" / "playtests" / "empty").mkdir()
        outside = self.base / "outside"
        outside.mkdir()
        for named, problem in (
            ("artifacts/playtests/other-rom", "played another ROM"),
            ("artifacts/playtests/restored", "restored a checkpoint"),
            ("artifacts/playtests/active", "is still recording"),
            ("artifacts/playtests/empty", "is no recording"),
            ("artifacts/playtests/gone", "is no recording"),
            (str(outside), "outside the project"),
            ("../outside", "outside the project"),
            ("f" * 32, "no recording in artifacts/playtests/ has the session id"),
            ("~no-such-user-hermretro/run", "is not a usable path"),
        ):
            answer = self.report(finishRun=named)
            self.assertEqual(answer["code"], "INVALID_REPORT", named)
            self.assertIn(problem, answer["error"])
        for wrong in ("  ", 3, None):
            self.assertIn("finishRun must be a recording's path", self.report(finishRun=wrong)["error"])

    def test_the_run_is_checked_against_the_games_rom_as_it_is_now(self):
        folder = self.recording()
        (self.root / "build" / "game.gbc").write_bytes(ROM + b"rebuilt")
        self.assertIn("played another ROM", self.report(finishRun=str(folder))["error"])
        (self.root / "build" / "game.gbc").unlink()
        self.assertIn("has no ROM in build/", self.report(finishRun=str(folder))["error"])

    def test_a_recording_the_lookup_cannot_find_is_named_by_its_path(self):
        archive = self.root / "artifacts" / "recording-archives" / "c0ffee" / "recording"
        archive.parent.mkdir(parents=True)
        self.recording(outcome="passed").rename(archive)
        # Archiving leaves only a pointer at the original path.
        original = self.root / "artifacts" / "playtests" / "session-1"
        original.mkdir()
        (original / ".recording-archive.json").write_text("{}")
        for named in (SESSION, str(original)):
            error = self.planned("passed", finishRun=named)["error"]
            self.assertIn("give the recordingPath chromatic_emulator_run returned", error)
            self.assertIn("the archivePath chromatic_emulator_recording retrieve returned", error)
        self.assertTrue(self.planned("passed", finishRun=str(archive))["ok"])

    def test_without_a_plan_the_run_is_optional_but_still_checked(self):
        answer = self.report()
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(answer["warnings"], [report_plan.NO_RUN])
        self.assertIsNone(answer["report"]["finishRun"])
        answer = self.report(finishRun=str(self.recording()))
        self.assertTrue(answer["ok"], answer)
        self.assertNotIn("warnings", answer)
        self.assertIn("has no events.jsonl", self.report(finishRun=str(self.recording("bare", journal=False)))["error"])
        with mock.patch.object(hermes_host, "_chat_project", lambda *_ids: None):
            answer = self.report(finishRun=SESSION)
        self.assertIn("this chat has no game project", answer["error"])


if __name__ == "__main__":
    unittest.main()
