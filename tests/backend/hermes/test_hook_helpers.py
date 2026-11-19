"""host.tool_result_payload and host.library_game_for: how a post_tool_call hook reads an engine tool's result and
finds the library game it touched (backend/history/hooks.py uses both).

Run alone: python -m unittest tests.backend.hermes.test_hook_helpers
"""

import json
import os
import unittest
from pathlib import Path

from backend.hermes import host
from backend.library import games
from tests.backend.library.test_games import make_project
from tests.support import isolated_home


class ToolResultPayload(unittest.TestCase):
    def test_json_text_a_dict_and_the_multimodal_summary_read_the_same(self):
        payload = {"structuredContent": {"success": True}}
        self.assertEqual(host.tool_result_payload(json.dumps(payload)), payload)
        self.assertEqual(host.tool_result_payload(payload), payload)
        envelope = {"_multimodal": True, "text_summary": json.dumps(payload), "content": []}
        self.assertEqual(host.tool_result_payload(envelope), payload)

    def test_anything_else_is_none(self):
        for result in (None, "not json", "[1, 2]", 3, {"_multimodal": True, "text_summary": None}):
            self.assertIsNone(host.tool_result_payload(result), result)


class LibraryGameFor(unittest.TestCase):
    def setUp(self):
        home = isolated_home(self)
        self.root = make_project(home.base / "games")
        games.Registry(host.paths.library_dir()).upsert(str(self.root))
        self.game = games.game_id(self.root)

    def test_the_project_or_a_path_inside_it_finds_the_game(self):
        real = Path(os.path.realpath(self.root))
        self.assertEqual(host.library_game_for([str(self.root)]), (self.game, real))
        inside = str(self.root / "build" / "web" / "rom.gb")
        self.assertEqual(host.library_game_for([None, 7, "", inside]), (self.game, real))

    def test_a_path_outside_every_game_finds_nothing(self):
        self.assertIsNone(host.library_game_for([str(self.root.parent), "/nowhere", None]))


if __name__ == "__main__":
    unittest.main()
