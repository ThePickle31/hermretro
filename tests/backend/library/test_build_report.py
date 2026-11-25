"""chromatic_build_report: the Build page's build card, checked all-or-nothing and handed back."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import contracts  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import workflow  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.assets import versions as host_assets  # noqa: E402 - the repository root goes on sys.path first
from backend.library import hooks as library_hooks  # noqa: E402 - the repository root goes on sys.path first
from backend.library import report_tools  # noqa: E402 - the repository root goes on sys.path first
from backend.library import games, plan_checks, tool_args  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home  # noqa: E402 - the repository root goes on sys.path first

GOOD = {
    "title": "  Robin in the sky ",
    "summary": "The robin now flies.\n  Press A to flap.",
    "changes": [
        {"kind": "added", "text": "Flying robin sprite", "asset": "assets/sprites/robin.png"},
        {"kind": "changed", "text": "Gravity is lower"},
    ],
    "tested": ["Flapping with A"],
    "untested": ["Sound", "Real Chromatic"],
    "notes": ["The robin can leave the top of the screen."],
    "suggestions": ["Make it fly faster"],
}


class BuildReport(unittest.TestCase):
    def setUp(self):
        isolated_home(self)  # it calls a real emitter, which reaches every feature's listeners.py
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "robin"
        (self.root / "assets" / "sprites").mkdir(parents=True)
        (self.root / "assets" / "sprites" / "robin.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (self.base / "elsewhere.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        self.patches = [
            mock.patch.object(hermes_host, "_chat_project", lambda *_ids: str(self.root)),
            mock.patch.object(host_assets, "_keep_paths"),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        self.tmp.cleanup()

    def report(self, args, **kwargs):
        return json.loads(report_tools.build_report_handler(args, **{"session_id": "s1", **kwargs}))

    def test_a_good_report_is_trimmed_and_its_assets_resolved(self):
        answer = self.report(dict(GOOD))
        self.assertTrue(answer["ok"], answer)
        report = answer["report"]
        self.assertEqual(report["title"], "Robin in the sky")
        self.assertEqual(report["summary"], "The robin now flies. Press A to flap.")
        self.assertEqual(
            report["changes"][0],
            {
                "kind": "added",
                "text": "Flying robin sprite",
                "asset": str((self.root / "assets" / "sprites" / "robin.png").resolve()),
            },
        )
        self.assertEqual(report["changes"][1], {"kind": "changed", "text": "Gravity is lower"})
        self.assertEqual(report["untested"], ["Sound", "Real Chromatic"])
        self.assertEqual(answer["project"], str(self.root))
        self.assertIn("one or two short sentences", answer["message"])
        self.assertNotIn("warnings", answer)

    def test_the_build_event_carries_the_game_and_its_images(self):
        with mock.patch.object(report_tools, "emit") as emit:
            self.assertTrue(self.report(dict(GOOD))["ok"])
        emit.assert_called_once_with(
            "library.build_reported",
            game=games.game_id(self.root),
            assets=[str((self.root / "assets" / "sprites" / "robin.png").resolve())],
        )
        with mock.patch.object(hermes_host, "_chat_project", lambda *_ids: None):
            with mock.patch.object(report_tools, "emit") as emit:
                self.assertTrue(self.report({"title": "t", "summary": "s"})["ok"])
        emit.assert_called_once_with("library.build_reported", game=None, assets=[])

    def test_the_assets_listener_still_keeps_the_reported_images(self):
        def capture_time():
            host_assets._keep_paths.assert_called_once_with(
                [str((self.root / "assets" / "sprites" / "robin.png").resolve())]
            )
            return 1_000_500_000

        with mock.patch.object(report_tools.time, "time_ns", side_effect=capture_time):
            answer = self.report(dict(GOOD))  # the real emit reaches backend/assets/listeners.py
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(answer["reportedAt"], 1000.5)

    def test_the_shared_tool_helpers_answer_the_codes_the_tools_use(self):
        answer = json.loads(tool_args.tool_error("no", "X"))
        self.assertEqual((answer["ok"], answer["error"], answer["code"]), (False, "no", "X"))
        self.assertTrue(answer["nextStep"])
        self.assertEqual(tool_args.tool_project("t", {}, {}), (str(self.root), None))
        self.assertEqual(tool_args.tool_project("t", {"project": str(self.base)}, {}), (str(self.base), None))
        for bad, code in (("relative", "PROJECT_NOT_FOUND"), ("  ", "INVALID_ARGUMENTS"), (3, "INVALID_ARGUMENTS")):
            root, error = tool_args.tool_project("t", {"project": bad}, {})
            self.assertIsNone(root)
            self.assertEqual(json.loads(error)["code"], code)
        with mock.patch.object(hermes_host, "_chat_project", lambda *_ids: None):
            root, error = tool_args.tool_project("chromatic_x", {}, {})
        self.assertIsNone(root)
        self.assertEqual(json.loads(error)["code"], "NO_PROJECT")
        self.assertIn("chromatic_x", json.loads(error)["error"])

    def test_only_title_and_summary_are_required(self):
        answer = self.report({"title": "Chubbier robin", "summary": "The robin is rounder."})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(
            {key: answer["report"][key] for key in ("changes", "tested", "untested", "checks", "notes", "suggestions")},
            {"changes": [], "tested": [], "untested": [], "checks": [], "notes": [], "suggestions": []},
        )
        self.assertIsNone(answer["report"]["difficulty"])

    def plan(self, rows):
        path = plan_checks.plan_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("| ID | Then | Status |\n|---|---|---|\n" + "".join(f"| {row} |\n" for row in rows))

    def test_a_game_with_a_test_plan_reports_every_open_check_and_its_difficulty(self):
        self.plan(
            ["T1 | the title shows | passed", "T2 | the gate opens | superseded (by D2)", "T3 | it ends | not run"]
        )
        refused = self.report(dict(GOOD))
        self.assertEqual(refused["code"], "INVALID_REPORT")
        self.assertIn("difficulty is required", refused["error"])
        self.assertIn("checks has no result for T1, T3", refused["error"])
        checks = [
            {"id": "T1", "text": "Title shows", "result": "passed"},
            {"id": "t3", "text": "One run to the ending", "result": "not run"},
        ]
        difficulty = "Finished in one run from power-on in 6 minutes; the last room took 3 tries."
        answer = self.report({**GOOD, "checks": checks, "difficulty": difficulty})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(
            answer["report"]["checks"][1], {"id": "t3", "text": "One run to the ending", "result": "not run"}
        )
        self.assertEqual(answer["report"]["difficulty"], difficulty)
        for wrong, problem in (
            ([*checks, {"id": "T2", "text": "Gate", "result": "passed"}], "checks names T2, which"),
            ([*checks, {"id": "T1", "text": "Again", "result": "passed"}], "T1 is reported twice"),
            ([checks[0], {**checks[1], "result": "ok"}], "result must be one of"),
            ([checks[0], {**checks[1], "proof": "x"}], "unknown field 'proof'"),
            ([checks[0], {"id": "T3", "result": "failed"}], "checks[2].text"),
            (checks[:1] * 101, "at most 100"),
            ("T1 passed", "checks must be a list"),
        ):
            answer = self.report({**GOOD, "checks": wrong, "difficulty": difficulty})
            self.assertEqual(answer["code"], "INVALID_REPORT", wrong)
            self.assertIn(problem, answer["error"])

    def test_a_test_plan_without_checks_asks_only_for_the_difficulty(self):
        path = plan_checks.plan_path(self.root)
        path.parent.mkdir(parents=True)
        path.write_text("# Test plan\nEvery check is observable.\n")
        self.assertIn("difficulty is required", self.report(dict(GOOD))["error"])
        answer = self.report({**GOOD, "difficulty": "Easy: one screen, no way to lose."})
        self.assertTrue(answer["ok"], answer)
        self.assertIn("lists no checks", answer["warnings"][0])

    def test_checks_written_as_lines_are_held_to_like_table_rows(self):
        path = plan_checks.plan_path(self.root)
        path.parent.mkdir(parents=True)
        path.write_text(
            "# Test plan · revision 1\nT1: Given a fresh boot, then a frog appears.\n"
            "T2: Given a resting frog, when directions are held, then it hops.\n"
            "T3: Given a resting frog, when A is pressed, a croak plays.\n## Results · 2026-11-22\nT1 passed.\n"
        )
        difficulty = "No ending: a meadow to hop around in; nothing to fail."
        refused = self.report({**GOOD, "difficulty": difficulty})
        self.assertIn("checks has no result for T1, T2, T3", refused["error"])
        checks = [
            {"id": "T1", "text": "Frog in the meadow", "result": "passed"},
            {"id": "T2", "text": "Hop and rest", "result": "passed"},
            {"id": "T3", "text": "Croak", "result": "needs review"},
        ]
        answer = self.report({**GOOD, "checks": checks, "difficulty": difficulty})
        self.assertTrue(answer["ok"], answer)
        self.assertNotIn("warnings", answer)

    def test_every_open_check_fits_a_report_and_a_plan_with_too_many_says_how_to_go_on(self):
        difficulty = "Finished in one run."
        rows = [f"T{index} | step {index} | not run" for index in range(1, 32)]
        self.plan([*rows, "GATE_1 | the gate | not run", "`T40` | the end | passed"])
        checks = [{"id": f"T{index}", "text": f"Step {index}", "result": "not run"} for index in range(1, 32)]
        answer = self.report({**GOOD, "checks": checks, "difficulty": difficulty})
        self.assertIn("checks has no result for T40", answer["error"])
        checks.append({"id": "t40", "text": "The end", "result": "passed"})
        answer = self.report({**GOOD, "checks": checks, "difficulty": difficulty})
        self.assertTrue(answer["ok"], answer)
        self.assertIn("no check ID, so they are not checks: GATE_1", answer["warnings"][0])
        self.plan([f"T{index} | step {index} | not run" for index in range(1, 102)])
        answer = self.report({**GOOD, "checks": checks[:31], "difficulty": difficulty})
        self.assertEqual(answer["code"], "INVALID_REPORT")
        self.assertIn("lists 101 open checks; a report holds results for at most 100", answer["error"])
        self.assertIn("Keep every approved check", answer["error"])
        self.assertNotIn("checks has no result", answer["error"])

    def test_without_a_test_plan_checks_and_difficulty_are_optional(self):
        checks = [{"id": "X1", "text": "Robin flaps", "result": "passed"}]
        answer = self.report({**GOOD, "checks": checks, "difficulty": "x" * 201})
        self.assertIn("difficulty is 201 characters", answer["error"])
        answer = self.report({**GOOD, "checks": checks})
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(answer["report"]["checks"], checks)

    def test_any_problem_refuses_the_whole_report(self):
        cases = [
            {"summary": "x"},
            {**GOOD, "title": "   "},
            {**GOOD, "title": "t" * 49},
            {**GOOD, "summary": "s" * 281},
            {**GOOD, "changes": [{"kind": "moved", "text": "x"}]},
            {**GOOD, "changes": [{"kind": "added", "text": "x", "colour": "red"}]},
            {**GOOD, "changes": [{"kind": "added"}]},
            {**GOOD, "changes": [{"kind": "added", "text": "x"}] * 9},
            {**GOOD, "tested": ["ok"] * 7},
            {**GOOD, "notes": ["n" * 161]},
            {**GOOD, "suggestions": ["Make it fly faster and also much higher"] * 2 + ["s" * 41]},
            {**GOOD, "suggestions": "Make it fly"},
            {**GOOD, "untested": [3]},
            {**GOOD, "mood": "happy"},
            {**GOOD, "project": "relative/folder"},
        ]
        for args in cases:
            answer = self.report(args)
            self.assertFalse(answer["ok"], args)
            self.assertEqual(answer["code"], "INVALID_REPORT")
            self.assertTrue(answer["problems"], args)

    def test_an_asset_outside_the_project_or_missing_is_left_out_with_a_warning(self):
        answer = self.report(
            {
                **GOOD,
                "changes": [
                    {"kind": "added", "text": "a", "asset": str(self.base / "elsewhere.png")},
                    {"kind": "added", "text": "b", "asset": "../elsewhere.png"},
                    {"kind": "added", "text": "c", "asset": "assets/sprites/gone.png"},
                    {
                        "kind": "added",
                        "text": "d",
                        "asset": "file://" + str(self.root / "assets" / "sprites" / "robin.png"),
                    },
                ],
            }
        )
        self.assertTrue(answer["ok"], answer)
        self.assertEqual(["asset" in change for change in answer["report"]["changes"]], [False, False, False, True])
        self.assertEqual(len(answer["warnings"]), 3)

    def test_without_a_project_no_asset_is_kept(self):
        with mock.patch.object(hermes_host, "_chat_project", lambda *_ids: None):
            answer = self.report(
                {
                    **GOOD,
                    "changes": [
                        {"kind": "added", "text": "a", "asset": str(self.base / "elsewhere.png")},
                        {"kind": "added", "text": "b", "asset": "assets/robin.png"},
                    ],
                }
            )
        self.assertTrue(answer["ok"], answer)
        self.assertIsNone(answer["project"])
        # Without the chat's game there is no folder to check an image against: it could be another game's.
        self.assertNotIn("asset", answer["report"]["changes"][0])
        self.assertNotIn("asset", answer["report"]["changes"][1])
        self.assertEqual(len(answer["warnings"]), 2)

    def test_an_explicit_project_wins(self):
        other = self.base / "other"
        other.mkdir()
        answer = self.report({**GOOD, "project": str(other)})
        self.assertEqual(answer["project"], str(other))
        self.assertNotIn("asset", answer["report"]["changes"][0])

    def test_a_subagent_cannot_report(self):
        hermes_host.on_subagent_start(child_session_id="child-1")
        try:
            answer = self.report(dict(GOOD), session_id="child-1")
        finally:
            hermes_host.on_subagent_stop(child_session_id="child-1")
        self.assertEqual(answer["code"], "PARENT_ONLY")

    def test_the_handler_never_raises(self):
        with mock.patch.object(report_tools, "_report_text", side_effect=RuntimeError("bad")):
            self.assertEqual(self.report(dict(GOOD))["code"], "ADAPTER_ERROR")
        self.assertEqual(self.report(None)["code"], "INVALID_REPORT")

    def test_schema_is_plugin_owned_and_strict(self):
        schema = report_tools.BUILD_REPORT_TOOL
        self.assertEqual(schema["name"], "chromatic_build_report")
        self.assertNotIn("chromatic_build_report", {s["name"] for s in contracts.hermes_schemas()})
        parameters = schema["parameters"]
        self.assertFalse(parameters["additionalProperties"])
        self.assertEqual(parameters["required"], ["title", "summary"])
        self.assertEqual(
            set(parameters["properties"]),
            {
                "title",
                "summary",
                "changes",
                "tested",
                "untested",
                "checks",
                "difficulty",
                "notes",
                "suggestions",
                "project",
            },
        )
        self.assertFalse(parameters["properties"]["changes"]["items"]["additionalProperties"])
        for needed in (
            "once at the end of every turn",
            "chromatic_rom_build",
            "chromatic_present_game",
            "subagent",
            "one or two short sentences",
        ):
            self.assertIn(needed, schema["description"])

    def test_agent_guidance_names_the_report(self):
        self.assertIn("chromatic_build_report", workflow.SYSTEM_PROMPT_SECTION)
        self.assertLessEqual(len(workflow.SYSTEM_PROMPT_SECTION), 2000)
        section = workflow.SYSTEM_PROMPT_SECTION
        self.assertLess(section.index("chromatic_present_game"), section.index("chromatic_build_report"))
        registry = mock.Mock()
        registry.binding_for.return_value = ("game", {"title": "Robin", "projectRoot": str(self.root)})
        with (
            mock.patch.object(hermes_host, "_registry", return_value=registry),
            mock.patch.object(hermes_host, "_profile_identity", return_value="p"),
        ):
            self.assertIn("chromatic_build_report", library_hooks.build_context(session_id="s")["context"])
            registry.binding_for.return_value = ("pending", {"name": "Robin"})
            self.assertIn(
                "chromatic_build_report", library_hooks.build_context(session_id="s", is_first_turn=True)["context"]
            )


if __name__ == "__main__":
    unittest.main()
