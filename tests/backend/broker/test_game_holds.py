"""Holding a game while an installed game's files are replaced (backend/broker/holds.py).

Run alone: python -m unittest tests.backend.broker.test_game_holds
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.broker.broker import Denied, Lane  # noqa: E402 - the repository root goes on sys.path first
from backend.broker import holds  # noqa: E402
from tests.backend.broker.bare import bare_broker  # noqa: E402
from tests.support import isolated_home  # noqa: E402

PROFILE = "/profiles/studio"


class Engine:
    def __init__(self, alive=True):
        self.living = alive

    def alive(self):
        return self.living


class Holds(unittest.TestCase):
    def setUp(self):
        self.base = isolated_home(self).base
        self.root = os.path.realpath(self.base / "Space Game")
        os.makedirs(self.root)
        self.closed = []
        self.broker = bare_broker()
        self.broker.close_lane_engine = lambda lane, reason: self.closed.append((lane.owner, reason))

    def lane(self, name, *, selected=True, engine=None, inflight=0):
        lane = Lane((PROFILE, name))
        lane.selected_root = self.root if selected else None
        lane.engine, lane.inflight = engine, inflight
        self.broker.lanes[lane.owner] = lane
        if selected:
            self.broker.writer_leases[self.root] = lane.owner
        return lane

    def op(self, op):
        return self.broker.control({"op": op, "root": self.root})

    def test_a_game_open_in_a_conversation_is_not_held(self):
        for engine, inflight in ((Engine(), 0), (None, 1)):
            with self.subTest(engine=engine, inflight=inflight):
                self.broker.lanes.clear()
                self.lane("chat", engine=engine, inflight=inflight)
                with self.assertRaises(Denied) as refused:
                    self.op("hold_game")
                self.assertEqual(refused.exception.code, "GAME_BUSY")

    def test_a_hold_forgets_a_gone_workers_selection_and_refuses_calls_until_released(self):
        gone = self.lane("gone", engine=Engine(alive=False))
        self.assertEqual(self.op("hold_game"), {"ok": True})
        self.assertIsNone(gone.selected_root)
        self.assertNotIn(self.root, self.broker.writer_leases)
        other = self.lane("other")
        with self.assertRaises(Denied) as refused:
            self.broker.refuse_held(other, None)
        self.assertEqual(refused.exception.code, "GAME_BUSY")
        with self.assertRaises(Denied):
            self.broker.refuse_held(self.lane("opener", selected=False), self.root)
        self.op("release_game")
        self.broker.refuse_held(self.lane("later", selected=False), self.root)
        self.assertIsNone(other.selected_root)  # it opened the game meanwhile: its worker has the old files
        self.assertIn(other.owner, [owner for owner, _ in self.closed])

    def test_a_hold_ends_on_its_own(self):
        self.op("hold_game")
        with mock.patch.object(holds.time, "monotonic", return_value=holds.time.monotonic() + holds.HOLD_SECONDS + 1):
            self.broker.refuse_held(self.lane("later", selected=False), self.root)

    def test_a_relative_root_is_refused(self):
        with self.assertRaises(Denied) as refused:
            self.broker.control({"op": "hold_game", "root": "games/x"})
        self.assertEqual(refused.exception.code, "INVALID_ARGUMENTS")


if __name__ == "__main__":
    unittest.main()
