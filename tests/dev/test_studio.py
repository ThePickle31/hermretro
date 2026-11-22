"""tools/dev/studio.py: a sandbox process counts as the one it started only while its exact start mark and its
command line still match, and records from before the marks were exact are still recognised."""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOP / "tools" / "dev"))
_spec = importlib.util.spec_from_file_location("studio", TOP / "tools" / "dev" / "studio.py")
studio = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(studio)

BROWSER = "node tools/dev/studio_browser.mjs /x"


class AliveTest(unittest.TestCase):
    def setUp(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self.processes = folder / "processes.json"
        patcher = mock.patch.object(studio, "PROCESSES", self.processes)
        patcher.start()
        self.addCleanup(patcher.stop)

    def record(self, started):
        self.processes.write_text(json.dumps({"browser": {"pid": 4242, "started": started}}))

    def running(self, started, command=BROWSER):
        return mock.patch.object(studio, "process", return_value=(started, command))

    def test_the_same_start_mark_and_command_is_ours(self):
        self.record("tick:1000")
        with self.running("tick:1000"):
            self.assertTrue(studio.alive("browser"))

    def test_another_process_with_the_pid_is_not_ours(self):
        self.record("tick:1000")
        with self.running("tick:1001"):  # a pid reused a moment later, with the same command
            self.assertFalse(studio.alive("browser"))
        with self.running("tick:1000", "vim notes.txt"):
            self.assertFalse(studio.alive("browser"))
        with self.running(None, ""):
            self.assertFalse(studio.alive("browser"))

    def test_a_record_from_before_exact_marks_is_compared_the_way_it_was_made(self):
        self.record("Sat Nov 21 20:59:43 2026")
        with (
            self.running("tick:1000"),
            mock.patch.object(studio, "legacy_started", return_value="Sat Nov 21 20:59:43 2026"),
        ):
            self.assertTrue(studio.alive("browser"))
        with (
            self.running("tick:1000"),
            mock.patch.object(studio, "legacy_started", return_value="Sat Nov 21 21:30:00 2026"),
        ):
            self.assertFalse(studio.alive("browser"))

    def test_this_process_has_a_mark_and_a_gone_one_has_none(self):
        started, command = studio.process(os.getpid())
        self.assertTrue(started.startswith(("tick:", "lstart:")))
        self.assertIn("python", command.lower())
        self.assertEqual(studio.process(2**22 + 12345), (None, ""))


if __name__ == "__main__":
    unittest.main()
