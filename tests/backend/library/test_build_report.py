"""chromatic_build_report: the Build page's build card, checked all-or-nothing and handed back."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import contracts  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.assets import versions as host_assets  # noqa: E402 - the repository root goes on sys.path first
from backend.library import tools as host_tools  # noqa: E402 - the repository root goes on sys.path first
from backend.library import hooks as library_hooks  # noqa: E402 - the repository root goes on sys.path first
from backend.library import tools as library_tools  # noqa: E402 - the repository root goes on sys.path first
from backend.library import games, tool_args  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, registered_hook  # noqa: E402 - the repository root goes on sys.path first

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
        return json.loads(library_tools.build_report_handler(args, **{"session_id": "s1", **kwargs}))

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
        with mock.patch.object(library_tools, "emit") as emit:
            self.assertTrue(self.report(dict(GOOD))["ok"])
        emit.assert_called_once_with(
            "library.build_reported",
            game=games.game_id(self.root),
            assets=[str((self.root / "assets" / "sprites" / "robin.png").resolve())],
        )
        with mock.patch.object(hermes_host, "_chat_project", lambda *_ids: None):
            with mock.patch.object(library_tools, "emit") as emit:
                self.assertTrue(self.report({"title": "t", "summary": "s"})["ok"])
        emit.assert_called_once_with("library.build_reported", game=None, assets=[])

    def test_the_assets_listener_still_keeps_the_reported_images(self):
        self.assertTrue(self.report(dict(GOOD))["ok"])  # the real emit reaches backend/assets/listeners.py
        host_assets._keep_paths.assert_called_once_with(
            [str((self.root / "assets" / "sprites" / "robin.png").resolve())]
        )

    def test_the_shared_tool_helpers_live_in_tool_args(self):
        self.assertIs(library_tools._tool_project, tool_args.tool_project)
        self.assertIs(library_tools._present_error, tool_args.tool_error)
        self.assertEqual(json.loads(tool_args.tool_error("no", "X")), {"ok": False, "error": "no", "code": "X"})
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
            {key: answer["report"][key] for key in ("changes", "tested", "untested", "notes", "suggestions")},
            {"changes": [], "tested": [], "untested": [], "notes": [], "suggestions": []},
        )

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

    def test_without_a_project_only_absolute_assets_are_kept(self):
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
        self.assertEqual(answer["report"]["changes"][0]["asset"], str(self.base / "elsewhere.png"))
        self.assertNotIn("asset", answer["report"]["changes"][1])

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
        with mock.patch.object(host_tools, "_report_text", side_effect=RuntimeError("bad")):
            self.assertEqual(self.report(dict(GOOD))["code"], "ADAPTER_ERROR")
        self.assertEqual(self.report(None)["code"], "INVALID_REPORT")

    def test_schema_is_plugin_owned_and_strict(self):
        schema = library_tools.BUILD_REPORT_TOOL
        self.assertEqual(schema["name"], "chromatic_build_report")
        self.assertNotIn("chromatic_build_report", {s["name"] for s in contracts.hermes_schemas()})
        parameters = schema["parameters"]
        self.assertFalse(parameters["additionalProperties"])
        self.assertEqual(parameters["required"], ["title", "summary"])
        self.assertEqual(
            set(parameters["properties"]),
            {"title", "summary", "changes", "tested", "untested", "notes", "suggestions", "project"},
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

    def test_the_approval_hook_lets_the_report_through(self):
        ctx = mock.Mock()
        ctx.get_config.return_value = True
        self.assertIsNone(registered_hook("pre_tool_call", ctx)(tool_name="chromatic_build_report", args=GOOD))

    def test_agent_guidance_names_the_report(self):
        self.assertIn("chromatic_build_report", hermes_host.SYSTEM_PROMPT_SECTION)
        self.assertLessEqual(len(hermes_host.SYSTEM_PROMPT_SECTION), 2000)
        section = hermes_host.SYSTEM_PROMPT_SECTION
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
