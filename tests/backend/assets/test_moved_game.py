"""An installed game's edited copy keeps its images' kept versions when it moves to a folder of its own
(backend/assets/moved.py, the ``library.game_moved`` listener).

Run alone: python -m unittest tests.backend.assets.test_moved_game
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.assets import listeners, versions  # noqa: E402 - the repository root goes on sys.path first
from backend.hermes import host  # noqa: E402
from tests.support import isolated_home  # noqa: E402


class MovedGame(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)
        self.base = host._data_dir() / "asset-versions"

    def folder(self, root, image):
        root, image = os.path.realpath(root), os.path.realpath(image)
        return self.base / versions._digest(f"{root}\0{image}")

    def test_the_versions_follow_the_remix_and_the_old_place_starts_clean(self):
        old_root, new_root = self.home.base / "Space Game", self.home.base / "Space Game (edited)"
        (new_root / "assets" / "sprites").mkdir(parents=True)
        (old_root / "assets" / "sprites").mkdir(parents=True)  # the update now in the old place
        image = new_root / "assets" / "sprites" / "hero.png"
        image.write_bytes(b"png")
        (old_root / "assets" / "sprites" / "hero.png").write_bytes(b"theirs")
        kept = self.folder(old_root, old_root / "assets" / "sprites" / "hero.png")
        kept.mkdir(parents=True)
        (kept / "1.png").write_bytes(b"v1")
        listeners.follow_moved_game(old="a" * 12, new="b" * 12, old_root=str(old_root), new_root=str(new_root))
        self.assertTrue((self.folder(new_root, image) / "1.png").is_file())
        self.assertFalse(kept.exists())

    def test_an_image_with_versions_of_its_own_keeps_them(self):
        old_root, new_root = self.home.base / "a", self.home.base / "b"
        (new_root).mkdir()
        image = new_root / "x.png"
        image.write_bytes(b"png")
        for folder in (self.folder(old_root, old_root / "x.png"), self.folder(new_root, image)):
            folder.mkdir(parents=True)
        listeners.follow_moved_game(old_root=str(old_root), new_root=str(new_root))
        self.assertTrue(self.folder(old_root, old_root / "x.png").is_dir())


if __name__ == "__main__":
    unittest.main()
