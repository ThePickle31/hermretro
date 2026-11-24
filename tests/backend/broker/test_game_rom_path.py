"""A project build writes the game's one ROM: the broker sets ``chromatic_rom_build``'s ``outputPath`` and refuses
any other, and the agent's tool description says so.

Run alone: python -m unittest tests.backend.broker.test_game_rom_path
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker.broker import game_rom_arguments  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.lane import Denied  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import contracts  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home, make_project  # noqa: E402 - the repository root goes on sys.path first


class GameRomPath(unittest.TestCase):
    def setUp(self):
        self.root = make_project(isolated_home(self).base, "Path Game")

    def test_a_build_without_a_path_writes_the_games_rom(self):
        self.assertEqual(
            game_rom_arguments(str(self.root), {"captureDebugArtifacts": True}),
            {"captureDebugArtifacts": True, "outputPath": "build/game.gbc"},
        )

    def test_the_games_own_path_is_accepted_relative_or_absolute(self):
        for asked in ("build/game.gbc", str(self.root / "build" / "game.gbc"), "build/../build/game.gbc"):
            with self.subTest(asked=asked):
                self.assertEqual(
                    game_rom_arguments(str(self.root), {"outputPath": asked})["outputPath"], "build/game.gbc"
                )

    def test_any_other_path_is_refused(self):
        (self.root / "project" / "settings.gbsres").write_text(json.dumps({"colorMode": "mono"}))
        for asked in ("build/game.gbc", "build/playtest-after.gbc", "build/my-game.gb", 7):
            with self.subTest(asked=asked), self.assertRaises(Denied) as refused:
                game_rom_arguments(str(self.root), {"outputPath": asked})
            self.assertEqual(refused.exception.code, "ROM_PATH")
            self.assertIn("build/game.gb", str(refused.exception))

    def test_the_tool_description_tells_the_agent(self):
        [schema] = [tool for tool in contracts.hermes_schemas() if tool["name"] == "chromatic_rom_build"]
        self.assertIn("build/game.gbc", schema["parameters"]["properties"]["outputPath"]["description"])


if __name__ == "__main__":
    unittest.main()
