"""The history.build_kept event of backend/history. Run alone: python -m unittest tests.backend.history.test_event_build_kept"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import backend.history as feature  # noqa: E402 - the repository root goes on sys.path first
from backend.history import emits  # noqa: E402 - the repository root goes on sys.path first
from backend.system import events  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home  # noqa: E402 - the repository root goes on sys.path first


class EventBuildKept(unittest.TestCase):
    def setUp(self):
        # The real emitter reaches every feature's listeners (rule 7 in AGENTS.md): they write only here.
        isolated_home(self)

    def test_it_is_declared_and_reaches_a_listener(self):
        self.assertIn("history.build_kept", feature.EVENTS)
        heard = []
        listener = events.on("history.build_kept")(lambda **payload: heard.append(payload))
        self.addCleanup(events._listeners["history.build_kept"].remove, listener)
        emits.build_kept(game="abc123abc123", root=Path("/games/probe"))
        self.assertEqual(heard, [{"game": "abc123abc123", "root": Path("/games/probe")}])


if __name__ == "__main__":
    unittest.main()
