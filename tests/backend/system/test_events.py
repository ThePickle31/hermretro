"""backend/system/events.py: owners emit, other features listen; a failing listener never breaks the emitter."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.system import events  # noqa: E402


class Events(unittest.TestCase):
    def test_listeners_run_in_order_and_a_failure_is_logged_not_raised(self):
        heard = []
        with mock.patch.dict(events._listeners, {}, clear=True), mock.patch.object(events, "_loaded", True):
            events.on("test.happened")(lambda **payload: heard.append(("one", payload)))
            events.on("test.happened")(lambda **_payload: 1 / 0)
            events.on("test.happened")(lambda **payload: heard.append(("three", payload)))
            with self.assertLogs(events.logger, "ERROR"):
                events.emit("test.happened", game="g")
        self.assertEqual(heard, [("one", {"game": "g"}), ("three", {"game": "g"})])

    def test_the_first_emit_loads_every_features_listeners(self):
        events.emit("test.nobody_listens")
        self.assertIn("library.build_reported", events._listeners)   # backend/assets/listeners.py


if __name__ == "__main__":
    unittest.main()
