"""player.capture_root: the one answer to where a game's captures live, shared by the RPCs, tools and the server."""

import unittest
import unittest.mock
from pathlib import Path

from backend import player
from backend.system import paths
from tests.support import isolated_home


class CaptureRootTest(unittest.TestCase):
    def setUp(self):
        isolated_home(self)

    def test_the_demo_cartridge_uses_the_library_folder(self):
        resolve = unittest.mock.Mock()
        self.assertEqual(player.capture_root(player.DEMO_ID, resolve), paths.library_dir())
        resolve.assert_not_called()

    def test_a_library_game_uses_its_project_folder(self):
        root = Path("/projects/comet")
        self.assertEqual(player.capture_root("aaa111aaa111", {"aaa111aaa111": root}.get), root)
        self.assertIsNone(player.capture_root("bbb222bbb222", {}.get), "an unknown game has none")

    def test_an_invalid_id_never_reaches_the_resolver(self):
        resolve = unittest.mock.Mock()
        self.assertIsNone(player.capture_root("../etc", resolve))
        resolve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
