"""tests/support.py's make_library_game: a ready game by default, and the not-ready ones its make_project switches give,
always registered with an id.

Run alone: python -m unittest tests.backend.library.test_library_fixture
"""

import unittest
from pathlib import Path

from backend.hermes import host
from backend.library import game_card, games
from tests.support import make_library_game, isolated_home


class LibraryGameFixture(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)

    def state(self, *args, **switches):
        game, root = make_library_game(self.home, *args, **switches)
        self.assertTrue(games.valid_id(game), game)
        self.assertEqual(Path(host._game_root(game)), root)
        fresh, _why = games.export_freshness(root)
        return root, fresh, game_card.status(root, strict=True)["complete"]

    def test_by_default_the_game_is_ready_to_present(self):
        root, fresh, complete = self.state("Ready Game")  # the name stays the second positional argument
        self.assertEqual(root.name, "ready-game")
        self.assertEqual((fresh, complete), (True, True))
        self.assertTrue((root / "build" / "project.gb").is_file())

    def test_the_switches_make_a_not_ready_game(self):
        self.assertEqual(self.state("No Copy", web=False)[1:], (False, True))
        self.assertEqual(self.state("No Card", card=False)[1:], (True, False))
        root, _fresh, _complete = self.state("No Rom", built=False)
        self.assertFalse((root / "build" / "project.gb").exists())
        self.assertTrue((root / "build" / "web" / "index.html").is_file())


if __name__ == "__main__":
    unittest.main()
