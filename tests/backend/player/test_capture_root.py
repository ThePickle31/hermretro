"""player.capture_root: the one answer to where a game's captures live, shared by the RPCs, tools and the server."""

import threading
import unittest
import unittest.mock
from pathlib import Path

from backend import player
from backend.library import PNG_MAGIC
from backend.system import paths
from tests.support import isolated_home


class CaptureRootTest(unittest.TestCase):
    def setUp(self):
        self.places = isolated_home(self)

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

    def test_a_capture_waits_while_they_are_paused_and_a_game_that_is_gone_gets_none(self):
        root = self.places.base / "Frog"
        root.mkdir()
        saved, refused = [], []

        def save():
            try:
                saved.append(
                    player.save_capture(root, "aaa111aaa111", "screenshot", PNG_MAGIC + b"x", "image/png", None)
                )
            except player.PlayerError as error:
                refused.append(str(error))

        with player.captures_paused():
            writer = threading.Thread(target=save)
            writer.start()
            writer.join(0.2)
            self.assertEqual(saved, [], "nothing is written while the reset holds them")
            root.rmdir()
        writer.join(2)
        self.assertEqual((saved, refused), ([], ["The game is no longer there."]))
        self.assertFalse(root.exists(), "the deleted game's folder is not made again")


if __name__ == "__main__":
    unittest.main()
