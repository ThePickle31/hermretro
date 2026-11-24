"""The game's one ROM: every build of a project writes ``build/game.gbc`` (``build/game.gb`` for a monochrome
project), and the library reads that file as the game, never another ROM left in ``build/``.

Run alone: python -m unittest tests.backend.library.test_game_rom
"""

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.library import games, project  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, make_project  # noqa: E402 - the repository root goes on sys.path first


class GameRom(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        self.root = make_project(self.home.base, "Rom Game")

    def color_mode(self, mode):
        (self.root / "project" / "settings.gbsres").write_text(json.dumps({"colorMode": mode}))

    def test_the_rom_is_named_by_the_projects_colour_mode(self):
        self.assertEqual(project.canonical_rom(self.root), "build/game.gbc")
        for mode, rom in (("mono", "build/game.gb"), ("mixed", "build/game.gbc"), ("color", "build/game.gbc")):
            with self.subTest(mode=mode):
                self.color_mode(mode)
                self.assertEqual(project.canonical_rom(self.root), rom)

    def test_an_older_single_file_project_names_its_rom_from_its_own_settings(self):
        descriptor = self.root / "rom-game.gbsproj"
        descriptor.write_text(json.dumps({"name": "Rom Game", "settings": {"colorMode": "mono"}}))
        self.assertEqual(project.canonical_rom(self.root), "build/game.gb")

    def test_a_newer_rom_left_in_build_is_not_the_game(self):
        stray = self.root / "build" / "playtest.gbc"
        stray.write_bytes(b"\4" * 1024)
        later = (self.root / "build" / "game.gbc").stat().st_mtime + 60
        os.utime(stray, (later, later))
        artifacts, _built = project.build_artifacts(self.root, {})
        self.assertEqual(artifacts["rom"]["path"], str(self.root / "build" / "game.gbc"))

    def test_a_game_built_before_the_one_rom_keeps_its_recorded_build(self):
        (self.root / "build" / "game.gbc").unlink()
        older = self.root / "build" / "project.gb"
        older.write_bytes(b"\5" * 512)
        artifacts, _built = project.build_artifacts(self.root, {"ok": True, "rom": str(older)})
        self.assertEqual(artifacts["rom"]["path"], str(older))

    def test_the_registry_records_the_rom_the_build_wrote(self):
        registry = games.Registry(self.home.base / "library")
        rom = self.root / "build" / "game.gbc"
        registry.observe(
            "rom_build",
            {},
            {"success": True, "outputPath": str(rom)},
            False,
            lane_root=str(self.root),
            conversation_id="c",
        )
        self.assertEqual(registry.get(games.game_id(self.root))["lastBuild"]["rom"], str(rom))


if __name__ == "__main__":
    unittest.main()
