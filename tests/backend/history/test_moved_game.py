"""History follows an installed game's edited copy to its own folder (backend/history/listeners.py), and a restore
waits for the game folder's lock (the one an installed game's update holds).

Run alone: python -m unittest tests.backend.history.test_moved_game
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from unittest import mock  # noqa: E402

from backend.history import listeners, rpcs  # noqa: E402 - the repository root goes on sys.path first
from backend.history.rpcs import _snapshots_dir  # noqa: E402
from backend.library import game_card  # noqa: E402
from tests.support import isolated_home, make_library_game  # noqa: E402


class MovedGame(unittest.TestCase):
    def setUp(self):
        self.home = isolated_home(self)

    def test_the_snapshots_move_with_the_game(self):
        old = _snapshots_dir() / "aaaaaaaaaaaa"
        (old / "1").mkdir(parents=True)
        (old / "1" / "snapshot.json").write_text("{}")
        listeners.follow_moved_game(old="aaaaaaaaaaaa", new="bbbbbbbbbbbb")
        self.assertTrue((_snapshots_dir() / "bbbbbbbbbbbb" / "1" / "snapshot.json").is_file())
        self.assertFalse(old.exists())

    def test_a_game_that_has_history_already_keeps_it(self):
        for name in ("aaaaaaaaaaaa", "bbbbbbbbbbbb"):
            (_snapshots_dir() / name).mkdir(parents=True)
        listeners.follow_moved_game(old="aaaaaaaaaaaa", new="bbbbbbbbbbbb")
        self.assertTrue((_snapshots_dir() / "aaaaaaaaaaaa").is_dir())
        listeners.follow_moved_game(old=None, new="x")  # nothing to do

    def test_a_restore_holds_the_game_folders_lock(self):
        game, root = make_library_game(self.home)
        held = []

        def restore(*_args, **_kwargs):
            held.append(bool(getattr(game_card._held, "locks", None)))
            return {"restored": []}

        with mock.patch.object(rpcs.snapshots, "restore", side_effect=restore):
            rpcs.rpc_build_restore(None)({"game": game, "id": "1000"})
        self.assertEqual(held, [True])


if __name__ == "__main__":
    unittest.main()
