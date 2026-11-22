"""chromatic_present_game shows only the engine's own playable copy of the current game: a copy made or edited by
hand, one older than the last build, or one older than a source edit is refused, each with its own next step.

Run alone: python -m unittest tests.backend.library.test_present_freshness
"""

import json
import os
import shutil
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.hermes import host as hermes_host  # noqa: E402 - the repository root goes on sys.path first
from backend.library import games  # noqa: E402 - the repository root goes on sys.path first
from backend.library import tools as library_tools  # noqa: E402 - the repository root goes on sys.path first
from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, make_library_game  # noqa: E402 - the repository root goes on sys.path first


class PresentFreshness(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        patch = mock.patch.object(hermes_host, "try_connect", lambda _dir: (None, None))
        patch.start()
        self.addCleanup(patch.stop)
        _id, self.root = make_library_game(self.home)
        self.web = self.root / "build" / "web"

    def present(self):
        answer = library_tools.present_game_handler({"project": str(self.root)}, conversation_id="", session_id="")
        return json.loads(answer)

    def freshness(self):
        entry = games.Registry(paths.library_dir()).get(games.game_id(self.root)) or {}
        return games.export_freshness(self.root, entry.get("lastBuild"), entry.get("lastWebExport"))

    def test_the_engines_own_copy_of_the_current_game_is_shown(self):
        self.assertEqual(self.freshness(), (True, None, None))
        self.assertTrue(self.present()["ok"])

    def test_a_copy_without_the_engines_record_is_refused(self):
        (self.web / games.WEB_MANIFEST).unlink()  # assembled by hand, e.g. from the GB Studio command line
        refused = self.present()
        self.assertEqual(refused["code"], "BUILD_FIRST")
        self.assertIn("not made by hermretro", refused["error"])
        self.assertIn("Never make, copy or edit files in build/", refused["nextStep"])

    def test_a_copy_whose_rom_was_swapped_is_refused(self):
        rom = self.web / "rom" / "game.gbc"
        stamp = rom.stat().st_mtime
        rom.write_bytes(b"\2" * 512)
        os.utime(rom, (stamp, stamp))
        self.assertFalse(games.engine_made_export(self.root))
        self.assertEqual(self.present()["code"], "BUILD_FIRST")

    def test_a_copy_moved_in_from_elsewhere_keeps_its_record_but_must_match_it(self):
        other = self.root.parent / "elsewhere"
        shutil.copytree(self.web, other)
        (other / "index.html").write_text("<html>another game</html>")
        shutil.rmtree(self.web)
        shutil.copytree(other, self.web)
        self.assertFalse(games.engine_made_export(self.root))

    def test_a_source_edit_after_the_copy_asks_for_a_build(self):
        scene = self.root / "project" / "scene.gbsres"
        scene.write_text('{"edited": true}')
        fresh, why, next_step = self.freshness()
        self.assertFalse(fresh)
        self.assertIn("changed after the playable copy", why)
        self.assertIn("chromatic_rom_build", next_step)

    def test_the_card_and_the_plans_are_not_game_sources(self):
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / "docs" / "PLAN.md").write_text("later notes")
        (self.root / "game.json").write_text((self.root / "game.json").read_text())
        self.assertTrue(self.freshness()[0])

    def test_a_recorded_build_newer_than_its_copy_asks_for_the_copy_not_another_build(self):
        build = {"t": time.time(), "ok": True, "rom": None, "sha256": None, "error": None}
        hermes_host._registry().upsert(str(self.root), build=build)
        fresh, why, next_step = self.freshness()
        self.assertFalse(fresh)
        self.assertIn("older than the last ROM build", why)
        self.assertIn("chromatic_web_preview", next_step)
        self.assertNotIn("Run chromatic_rom_build", next_step)

    def test_a_newer_rom_nobody_recorded_asks_for_a_real_build(self):
        rom = self.root / "build" / "project.gb"
        later = time.time()
        os.utime(rom, (later, later))
        self.assertIn("Run chromatic_rom_build", self.freshness()[2])

    def test_a_failed_build_says_to_fix_it_first(self):
        build = {"t": time.time(), "ok": False, "rom": None, "sha256": None, "error": "x"}
        hermes_host._registry().upsert(str(self.root), build=build)
        self.assertIn("Fix what the build reported first", self.freshness()[2])


if __name__ == "__main__":
    unittest.main()
