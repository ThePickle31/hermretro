"""A project build writes the game's one ROM: the broker sets ``chromatic_rom_build``'s ``outputPath`` and refuses
any other, and the agent's tool description says so.

Run alone: python -m unittest tests.backend.broker.test_game_rom_path
"""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker.broker import Lane, game_rom_arguments  # noqa: E402 - the repository root goes on sys.path first
from backend.broker.lane import Denied  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import contracts  # noqa: E402 - the repository root goes on sys.path first
from backend.library import games  # noqa: E402 - the repository root goes on sys.path first
from tests.backend.broker.bare import EngineStub, bare_broker  # noqa: E402 - the repository root goes on sys.path first
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

    def test_only_the_games_own_project_file_is_built(self):
        own = self.root / "path-game.gbsproj"
        for asked in ("path-game.gbsproj", str(own)):
            with self.subTest(asked=asked):
                self.assertEqual(game_rom_arguments(str(self.root), {"projectPath": asked})["projectPath"], asked)
        (self.root / "zz-other.gbsproj").write_text("{}")
        with self.assertRaises(Denied) as refused:
            game_rom_arguments(str(self.root), {"projectPath": "zz-other.gbsproj"})
        self.assertIn("without projectPath", str(refused.exception))

    def test_a_path_that_cannot_be_resolved_is_refused_not_retried(self):
        with self.assertRaises(Denied) as refused:
            game_rom_arguments(str(self.root), {"outputPath": "build/game\x00.gbc"})
        self.assertEqual(refused.exception.code, "ROM_PATH")

    def test_letter_case_counts_only_where_volumes_keep_it(self):
        with mock.patch.object(sys, "platform", "darwin"):
            self.assertEqual(
                game_rom_arguments(str(self.root), {"outputPath": "BUILD/Game.GBC"})["outputPath"], "build/game.gbc"
            )
        with mock.patch.object(sys, "platform", "linux"), self.assertRaises(Denied):
            game_rom_arguments(str(self.root), {"outputPath": "BUILD/Game.GBC"})

    def test_a_standalone_c_build_may_write_any_rom_but_the_games(self):
        for asked in ({"sourcePath": "probe.c"}, {"sourcePath": "game.c", "outputPath": "build/probe.gb"}):
            with self.subTest(asked=asked):
                self.assertEqual(game_rom_arguments(str(self.root), asked), asked)
        for asked in (
            {"sourcePath": "game.c"},
            {"sourcePath": "src/game.c", "colorMode": "gbc"},
            {"sourcePath": "probe.c", "outputPath": "build/game.gbc"},
        ):
            with self.subTest(asked=asked), self.assertRaises(Denied) as refused:
                game_rom_arguments(str(self.root), asked)
            self.assertIn("another outputPath", str(refused.exception))

    def call(self, broker, arguments):
        return broker.call({"tool": "rom_build", "arguments": arguments})

    def test_the_broker_sends_every_project_build_to_the_games_rom(self):
        registry = games.Registry(self.root.parent / "lib")
        engine = EngineStub(self.root)
        engine.pid = 0
        lane = Lane(("/profiles/studio", "chat"))
        lane.selected_root, lane.engine = str(self.root), engine
        broker = bare_broker(games=registry, tools={"rom_build"}, read_only=frozenset(), hardware_lock=None)
        broker.lanes[lane.owner] = lane
        broker.owner_of = lambda _request: lane.owner
        broker.ensure_engine = lambda _lane: engine
        broker.select_bound_game = lambda _lane, _engine: None
        broker.acquire_writer = lambda _lane: None
        self.call(broker, {})
        (self.root / "project" / "settings.gbsres").write_text(json.dumps({"colorMode": "mono"}))
        self.call(broker, {"captureDebugArtifacts": True})
        self.assertEqual(
            engine.calls,
            [
                ("rom_build", {"outputPath": "build/game.gbc"}),
                ("rom_build", {"captureDebugArtifacts": True, "outputPath": "build/game.gb"}),
            ],
        )
        with self.assertRaises(Denied):
            self.call(broker, {"outputPath": "build/other.gb"})
        self.assertEqual(len(engine.calls), 2, "a refused build never reaches the engine")

    def test_the_tool_description_tells_the_agent(self):
        [schema] = [tool for tool in contracts.hermes_schemas() if tool["name"] == "chromatic_rom_build"]
        self.assertIn("build/game.gbc", schema["parameters"]["properties"]["outputPath"]["description"])


if __name__ == "__main__":
    unittest.main()
