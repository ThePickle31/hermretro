"""The seventh round's event tests that reach the real dispatcher (moved from test_trial_round_seven_new.py): a
real emit loads every feature's listeners, so each test calls isolated_home, which moves process-wide state (the
environment, the host's data folder) and registers listeners in the dispatcher's own table. Two of them overlapping
on the shared pool's threads could undo each other's isolation, so this module runs alone: after the pool, never
during it (review 3, 2).

Run alone: python -m unittest tests.retrodev.test_trial_round_seven_alone
"""

import unittest

from backend.system import events

from tests.retrodev.fixture import alone, git, write
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase
from tests.retrodev.test_trial_round_seven_new import DISPATCHER
from tests.support import isolated_home

load_tests = alone


class Event(ScaffoldCase):
    def test_the_generated_emitter_reaches_a_listener_through_the_real_dispatcher(self):  # review 2, 1
        write(self.tree, DISPATCHER, (ROOT / DISPATCHER).read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "The real dispatcher")
        self.new("event", "history", "rdprobe_renamed", "--payload", "game=<id>, title=<new title>, old=<old title>")
        emits = self.read("backend/history/emits.py")
        isolated_home(self)  # a real emit loads every feature's listeners
        scope = {}
        exec(compile(emits.replace("from ..system.events import emit", ""), "emits.py", "exec"), scope)
        scope["emit"] = events.emit  # the real dispatcher, not a stand-in
        heard = []
        listener = events.on("history.rdprobe_renamed")(lambda **payload: heard.append(payload))
        self.addCleanup(events._listeners["history.rdprobe_renamed"].remove, listener)
        scope["rdprobe_renamed"](game="g", title="New", old="Old")
        self.assertEqual(heard, [{"game": "g", "title": "New", "old": "Old"}])

    def test_a_python_keyword_key_keeps_payload_and_still_reaches_the_dispatcher(self):  # review 2, 1
        self.new("event", "history", "rdprobe_sorted", "--payload", "class=<kind>, for=<whom>")
        emits = self.read("backend/history/emits.py")
        self.assertIn("def rdprobe_sorted(**payload) -> None:", emits)
        isolated_home(self)
        scope = {}
        exec(compile(emits.replace("from ..system.events import emit", ""), "emits.py", "exec"), scope)
        scope["emit"] = events.emit
        heard = []
        listener = events.on("history.rdprobe_sorted")(lambda **payload: heard.append(payload))
        self.addCleanup(events._listeners["history.rdprobe_sorted"].remove, listener)
        scope["rdprobe_sorted"](**{"class": "a", "for": "b"})
        self.assertEqual(heard, [{"class": "a", "for": "b"}])


if __name__ == "__main__":
    unittest.main()
