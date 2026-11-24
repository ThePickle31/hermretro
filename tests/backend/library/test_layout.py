"""The game folder's layout (backend/library/layout.py): what ensure fills in and keeps, what check reports, what a
publish would hold, and the publish record.

Run alone: python -m unittest tests.backend.library.test_layout
"""

import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.library import freshness, game_card, games, hooks, layout  # noqa: E402 - the repository root goes first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from backend.library import tools as library_tools  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, make_library_game, make_project  # noqa: E402 - the repository root goes first


class Layout(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        self.root = make_project(self.home.base, "Layout Game")

    def card(self):
        return game_card.load(self.root)

    def test_ensure_gives_a_game_its_layout_once(self):
        written = layout.ensure(self.root)
        self.assertEqual(
            sorted(written), [".gitignore", ".hermretro/identity.json", "CHANGELOG.md", "README.md", "game.json"]
        )
        card = self.card()
        self.assertRegex(card["id"], r"^[0-9a-f]{32}$")
        self.assertEqual(card["id"], layout.game_identity(self.root))
        self.assertEqual((card["gameVersion"], card["rom"]), ("0.1.0", "build/game.gbc"))
        self.assertEqual(card["version"], game_card.VERSION, "the card's own schema version is untouched")
        readme = (self.root / "README.md").read_text()
        self.assertIn("# Space Game", readme)
        self.assertIn("![Space Game](cover.png)", readme)
        self.assertIn("- ROM: `build/game.gbc`", readme)
        self.assertEqual((self.root / "CHANGELOG.md").read_text(), "# Changelog\n")
        ignored = (self.root / ".gitignore").read_text().splitlines()
        self.assertIn("/build/*", ignored)
        self.assertIn("!/build/game.gbc", ignored)
        self.assertIn("/.hermretro/", ignored)
        self.assertEqual(layout.ensure(self.root), [], "a second pass changes nothing")
        self.assertEqual(layout.check(self.root), {"ok": True, "problems": [], "warnings": []})

    def test_the_id_survives_a_hand_edit_of_the_card(self):
        layout.ensure(self.root)
        identifier = self.card()["id"]
        game_card.set_fields(self.root, {"id": "f" * 32})
        self.assertFalse(layout.check(self.root)["ok"])
        layout.ensure(self.root)
        self.assertEqual(self.card()["id"], identifier)

    def test_a_game_brought_in_with_an_id_keeps_it(self):
        game_card.set_fields(self.root, {"id": "a" * 32})
        layout.ensure(self.root)
        self.assertEqual(layout.game_identity(self.root), "a" * 32)

    def test_the_readme_follows_the_card_but_a_hand_written_one_is_kept(self):
        layout.ensure(self.root)
        game_card.set_fields(self.root, {"tagline": "Now with comets."})
        layout.ensure(self.root)
        self.assertIn("*Now with comets.*", (self.root / "README.md").read_text())
        (self.root / "README.md").write_text("# My own words\n")
        layout.ensure(self.root)
        self.assertEqual((self.root / "README.md").read_text(), "# My own words\n")
        self.assertEqual([item["code"] for item in layout.check(self.root)["warnings"]], ["OWN_README"])

    def test_the_starter_projects_readme_is_replaced(self):
        starter = paths.ENGINE_ROOT / "examples" / "starter" / "README.md"
        shutil.copyfile(starter, self.root / "README.md")
        layout.ensure(self.root)
        self.assertIn("# Space Game", (self.root / "README.md").read_text())

    def test_a_monochrome_game_names_its_gb_rom(self):
        (self.root / "project" / "settings.gbsres").write_text(json.dumps({"colorMode": "mono"}))
        layout.ensure(self.root)
        self.assertEqual(self.card()["rom"], "build/game.gb")
        self.assertIn("!/build/game.gb", (self.root / ".gitignore").read_text().splitlines())

    def test_unknown_entries_stay_local_with_a_warning(self):
        layout.ensure(self.root)
        (self.root / "notes.txt").write_text("ideas")
        (self.root / "captures").mkdir()
        report = layout.check(self.root)
        self.assertTrue(report["ok"])
        self.assertEqual(
            [(item["code"], item["path"]) for item in report["warnings"]], [("UNKNOWN_ENTRY", "notes.txt")]
        )
        self.assertEqual(layout.kind_of(self.root, "notes.txt"), "local")
        self.assertNotIn("notes.txt", layout.files(self.root, source=True))

    def test_a_missing_project_or_unreadable_card_is_a_problem(self):
        (self.root / "game.json").write_text("{")
        shutil.rmtree(self.root / "project")
        codes = [item["code"] for item in layout.check(self.root)["problems"]]
        self.assertEqual(codes, ["NO_SOURCE", "CARD_UNREADABLE"])

    def test_files_lists_the_game_alone_or_with_its_source(self):
        layout.ensure(self.root)
        (self.root / "assets" / "sprites").mkdir(parents=True)
        (self.root / "assets" / "sprites" / "hero.png").write_bytes(b"png")
        (self.root / "assets" / ".DS_Store").write_bytes(b"")
        (self.root / "assets" / "link.png").symlink_to(self.root / "assets" / "sprites" / "hero.png")
        (self.root / "docs" / "game").mkdir(parents=True)
        (self.root / "docs" / "game" / "GAME-BRIEF.md").write_text("brief")
        (self.root / "captures").mkdir()
        (self.root / "captures" / "shot.png").write_bytes(b"png")
        game = ["CHANGELOG.md", "README.md", "build/game.gbc", "cover.png", "game.json"]
        self.assertEqual(layout.files(self.root, source=False), sorted(game + [".gitignore"]))
        self.assertEqual(
            layout.files(self.root, source=True),
            sorted(
                game
                + [".gitignore", "layout-game.gbsproj", "project/scene.gbsres"]
                + ["assets/sprites/hero.png", "docs/game/GAME-BRIEF.md"]
            ),
        )

    def test_a_remix_is_a_game_of_its_own(self):
        layout.ensure(self.root)
        original = self.card()["id"]
        layout.record_publish(self.root, repo="https://example.invalid/game", commit="c" * 40, version="0.2.0")
        identifier = layout.new_identity(self.root)
        self.assertNotEqual(identifier, original)
        self.assertEqual((self.card()["id"], self.card()["gameVersion"]), (identifier, "0.1.0"))
        self.assertIsNone(layout.published(self.root))

    def test_a_publish_is_recorded_and_later_changes_are_seen(self):
        layout.ensure(self.root)
        self.assertIsNone(layout.unpublished_changes(self.root))
        record = layout.record_publish(
            self.root, repo="https://example.invalid/game", commit="c" * 40, version="0.2.0", notes="First levels."
        )
        self.assertEqual(layout.published(self.root), record)
        self.assertEqual(self.card()["gameVersion"], "0.2.0")
        changelog = (self.root / "CHANGELOG.md").read_text()
        self.assertRegex(changelog, r"^# Changelog\n\n## 0\.2\.0 \(\d{4}-\d{2}-\d{2}\)\n\nFirst levels\.\n")
        self.assertIn("- Version: 0.2.0", (self.root / "README.md").read_text())
        self.assertFalse(layout.unpublished_changes(self.root))
        (self.root / "project" / "scene.gbsres").write_text('{"changed": true}')
        self.assertTrue(layout.unpublished_changes(self.root))
        with self.assertRaises(ValueError):
            layout.record_publish(self.root, repo="r", commit="c", version="1.0")

    def test_next_version(self):
        self.assertEqual(
            [layout.next_version("1.2.3", part) for part in ("patch", "minor", "major")], ["1.2.4", "1.3.0", "2.0.0"]
        )
        self.assertEqual(layout.next_version("nonsense"), "0.1.1")

    def test_what_ensure_writes_is_not_a_change_to_the_game(self):
        moment = (self.root / "build" / "game.gbc").stat().st_mtime
        layout.ensure(self.root)
        self.assertFalse(freshness.sources_newer_than(self.root, moment))

    def test_a_new_game_gets_its_layout_when_it_is_made(self):
        root = make_project(self.home.base, "Brand New", card=False)
        registry = games.Registry(self.home.base / "library")
        registry.observe(
            "project_create", {}, {"projectRoot": str(root)}, False, lane_root=str(root), conversation_id="c"
        )
        self.assertTrue(layout.game_identity(root))
        self.assertEqual(game_card.load(root)["rom"], "build/game.gbc")
        self.assertTrue((root / "README.md").is_file())

    def test_the_agents_file_tools_cannot_write_the_games_record(self):
        record = str(self.root / ".hermretro" / "identity.json")
        blocked = hooks.guard_game_record(tool_name="write_file", args={"path": record, "content": "{}"})
        self.assertEqual(blocked["action"], "block")
        patch = f"*** Begin Patch\n*** Update File: {record}\n@@\n-a\n+b\n*** End Patch"
        self.assertEqual(
            hooks.guard_game_record(tool_name="patch", args={"mode": "patch", "patch": patch})["action"], "block"
        )
        for tool, args in (
            ("write_file", {"path": str(self.root / "game.json")}),
            ("write_file", {"path": str(self.root / "notes.hermretro")}),
            ("read_file", {"path": record}),
        ):
            with self.subTest(tool=tool, args=args):
                self.assertIsNone(hooks.guard_game_record(tool_name=tool, args=args))


class PresentLayout(unittest.TestCase):
    def test_a_game_out_of_its_layout_is_not_presented(self):
        home = isolated_home(self)
        patch = mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None))
        patch.start()
        self.addCleanup(patch.stop)
        _id, root = make_library_game(home)
        layout.ensure(root)
        game_card.set_fields(root, {"id": "f" * 32})
        answer = json.loads(
            library_tools.present_game_handler({"project": str(root)}, conversation_id="", session_id="")
        )
        self.assertEqual(answer["code"], "LAYOUT")
        self.assertIn("game.json's id is not this game's id", answer["error"])
        layout.ensure(root)
        answer = library_tools.present_game_handler({"project": str(root)}, conversation_id="", session_id="")
        self.assertTrue(json.loads(answer)["ok"])


if __name__ == "__main__":
    unittest.main()
