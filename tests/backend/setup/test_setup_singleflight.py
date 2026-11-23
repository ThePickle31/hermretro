"""Finishing the studio profile runs once at a time, and a profile someone else owns is named before any download."""

import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from backend.setup import studio_profile as sp


class SingleFlight(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.home, self.target = root / "profiles" / "work", root / "profiles" / sp.STUDIO_PROFILE
        self.home.mkdir(parents=True)
        self.target.mkdir(parents=True)
        (self.target / "profile.yaml").write_text(f"description: '{sp.DESCRIPTION}'\n")
        config = mock.patch.object(sp.hermes_api, "profile_config", return_value={})
        config.start()
        self.addCleanup(config.stop)

    def test_a_second_finish_waits_for_the_first_and_shares_its_answer(self):
        gate, started, commands = threading.Event(), threading.Event(), []

        def run(target, *arguments):
            commands.append(arguments)
            started.set()
            gate.wait(5)

        answers = []
        first = threading.Thread(
            target=lambda: answers.append(sp.finish(self.home, target=self.target, enabled=[], run=run))
        )
        first.start()
        self.assertTrue(started.wait(5))
        second = threading.Thread(
            target=lambda: answers.append(sp.finish(self.home, target=self.target, enabled=[], run=run))
        )
        second.start()
        second.join(0.2)
        self.assertTrue(second.is_alive(), "the second call waits instead of running hermes commands alongside")
        gate.set()
        first.join(5)
        second.join(5)
        self.assertEqual(len(commands), 8, "the hermes commands ran once")
        self.assertEqual(sorted(bool(answer.get("shared")) for answer in answers), [False, True])

    def test_a_failure_is_shared_and_the_next_call_runs_again(self):
        def broken(target, *arguments):
            raise sp.StudioProfileError("HERMES_COMMAND_FAILED", "no")

        with self.assertRaises(sp.StudioProfileError):
            sp.finish(self.home, target=self.target, enabled=[], run=broken)
        self.assertTrue(sp.finish(self.home, target=self.target, enabled=[], run=lambda *_: None)["ok"])

    def test_someone_elses_profile_is_a_conflict(self):
        (self.target / "profile.yaml").write_text("description: 'my own profile'\n")
        self.assertTrue(sp.describe(self.home, self.target)["studio"]["conflict"])
        (self.target / "profile.yaml").write_text(f"description: '{sp.DESCRIPTION}'\n")
        self.assertFalse(sp.describe(self.home, self.target)["studio"]["conflict"])


if __name__ == "__main__":
    unittest.main()
