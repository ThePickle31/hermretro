"""The game folder's layout (backend/library/layout.py): what ensure fills in and keeps, what check reports, what a
publish would hold, and the publish record.

Run alone: python -m unittest tests.backend.library.test_layout
"""

import json
import os
import shutil
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.library import freshness, game_card, games, hooks, layout, release  # noqa: E402 - the repository root goes first
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
        self.assertIn("- ROM: [build/game.gbc](build/game.gbc)", readme)
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
        self.assertNotIn("notes.txt", release.files(self.root, source=True))

    def test_a_missing_project_or_unreadable_card_is_a_problem(self):
        (self.root / "game.json").write_text("{")
        shutil.rmtree(self.root / "project")
        codes = [item["code"] for item in layout.check(self.root)["problems"]]
        self.assertEqual(codes, ["NO_SOURCE", "CARD_UNREADABLE"])

    def test_a_remix_is_a_game_of_its_own(self):
        layout.ensure(self.root)
        original = self.card()["id"]
        release.prepare_release(self.root, "0.2.0", "First levels.")
        release.record_publish(
            self.root, repo="https://example.invalid/game", commit="c" * 40, version="0.2.0", source=True
        )
        release.record_install(self.root, repo="https://example.invalid/game", commit="c" * 40, source=True)
        identifier = layout.new_identity(self.root)
        self.assertNotEqual(identifier, original)
        card = self.card()
        self.assertEqual((card["id"], card["gameVersion"]), (identifier, "0.1.0"))
        self.assertEqual(card["remixOf"], {"id": original, "version": "0.2.0"})
        self.assertEqual((self.root / "CHANGELOG.md").read_text(), "# Changelog\n")
        self.assertIsNone(release.published(self.root))
        self.assertIsNone(release.installed(self.root))

    def test_the_agents_plans_and_an_older_single_file_project_fit_the_layout(self):
        self.assertEqual(layout.kind_of(self.root, "docs"), "local")
        shutil.rmtree(self.root / "project")
        (self.root / "layout-game.gbsproj").write_text(json.dumps({"name": "Layout Game", "scenes": []}))
        layout.ensure(self.root)
        self.assertEqual(layout.check(self.root)["problems"], [])

    def test_a_game_installed_without_its_source(self):
        layout.ensure(self.root)
        identifier, rom = self.card()["id"], self.root / "build" / "game.gbc"
        for name in ("layout-game.gbsproj", ".hermretro"):
            path = self.root / name
            shutil.rmtree(path) if path.is_dir() else path.unlink()
        shutil.rmtree(self.root / "project")
        (self.root / "build" / "web").rename(self.home.base / "web-elsewhere")
        game_card.set_fields(self.root, {"rom": "build/game.gb"})
        rom.rename(self.root / "build" / "game.gb")
        self.assertEqual(layout.game_rom(self.root), "build/game.gb")
        self.assertEqual(layout.ensure(self.root), [".hermretro/identity.json"], "only the author's id is kept")
        self.assertEqual(layout.game_identity(self.root), identifier)
        self.assertTrue(layout.check(self.root)["ok"])
        (self.root / "build" / "game.gb").unlink()
        self.assertEqual([item["code"] for item in layout.check(self.root)["problems"]], ["NO_ROM"])

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

    def test_a_game_made_before_the_layout_gets_it_on_the_shelf(self):
        root = make_project(self.home.base, "Older Game", card=False)
        (root / "README.md").write_text(
            (paths.ENGINE_ROOT / "examples" / "starter" / "README.md").read_text(encoding="utf-8"), encoding="utf-8"
        )
        registry = games.Registry(self.home.base / "shelf")
        registry.upsert(str(root))
        (root / "notes.txt").write_text("ideas")
        [game] = [item for item in registry.library() if item["projectRoot"] == os.path.realpath(root)]
        card = game_card.load(root)
        self.assertEqual((card["title"], card["rom"], card["gameVersion"]), ("Older Game", "build/game.gbc", "0.1.0"))
        self.assertIn("# Older Game", (root / "README.md").read_text())
        self.assertEqual(game["layout"]["problems"], [])
        self.assertEqual([item["path"] for item in game["layout"]["warnings"]], ["notes.txt"])

    def test_a_local_file_is_never_a_change_to_the_game(self):
        layout.ensure(self.root)
        moment = (self.root / "build" / "game.gbc").stat().st_mtime
        for name in ("notes.txt", "docs/BRIEF.md", "art/draw.py"):
            path = self.root / name
            path.parent.mkdir(exist_ok=True)
            path.write_text("later")
            os.utime(path, (moment + 60, moment + 60))
        self.assertFalse(freshness.sources_newer_than(self.root, moment))
        scene = self.root / "project" / "scene.gbsres"
        os.utime(scene, (moment + 60, moment + 60))
        self.assertTrue(freshness.sources_newer_than(self.root, moment))

    def test_only_its_own_marker_line_makes_a_file_replaceable(self):
        layout.ensure(self.root)
        mine = f"# Notes: {layout.GENERATED} is what hermretro puts in its files\n"
        (self.root / "README.md").write_text(mine)
        layout.ensure(self.root)
        self.assertEqual((self.root / "README.md").read_text(), mine)

    def test_two_processes_laying_out_one_game_agree_on_its_id(self):
        root = make_project(self.home.base, "Raced Game", card=False)
        results = []
        threads = [threading.Thread(target=lambda: results.append(layout.ensure(root))) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(game_card.load(root)["id"], layout.game_identity(root))
        self.assertEqual(sum(".hermretro/identity.json" in written for written in results), 1)

    def test_the_hook_reads_where_a_tool_writes_not_what_it_writes(self):
        record = self.root / ".hermretro"
        record.mkdir(exist_ok=True)
        alias = self.home.base / "alias"
        alias.symlink_to(record)

        def blocked(tool, args):
            return (hooks.guard_game_record(tool_name=tool, args=args) or {}).get("action") == "block"

        notes = (
            "*** Begin Patch\n*** Update File: docs/notes.md\n@@\n+ids live in .hermretro/identity.json\n*** End Patch"
        )
        self.assertFalse(blocked("patch", {"mode": "patch", "patch": notes}))
        self.assertTrue(blocked("write_file", {"path": str(alias / "identity.json")}))
        self.assertTrue(blocked("write_file", {"path": str(self.root / ".HermRetro" / "identity.json")}))


class PresentLayout(unittest.TestCase):
    def setUp(self):
        home = isolated_home(self)
        patch = mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None))
        patch.start()
        self.addCleanup(patch.stop)
        _id, self.root = make_library_game(home)

    def present(self):
        return json.loads(
            library_tools.present_game_handler({"project": str(self.root)}, conversation_id="", session_id="")
        )

    def test_an_edited_id_is_put_back_before_the_game_is_shown(self):
        layout.ensure(self.root)
        identifier = game_card.load(self.root)["id"]
        game_card.set_fields(self.root, {"id": "f" * 32})
        self.assertTrue(self.present()["ok"])
        self.assertEqual(game_card.load(self.root)["id"], identifier)

    def test_an_unreadable_card_is_a_layout_problem_not_missing_fields(self):
        (self.root / "game.json").write_text("{")
        answer = self.present()
        self.assertEqual(answer["code"], "LAYOUT")
        self.assertIn("game.json cannot be read", answer["error"])


if __name__ == "__main__":
    unittest.main()
