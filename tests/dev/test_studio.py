"""tools/dev/studio.py: a sandbox process counts as the one it started only while its pid, start time (allowing the
second ps's clock arithmetic can drift) and command line still match."""

import importlib.util
import json
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

STARTED = studio.epoch("Sat Nov 21 20:59:43 2026")


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

    def running(self, started, command="node tools/dev/studio_browser.mjs /x"):
        return mock.patch.object(studio, "process", return_value=(started, command))

    def test_a_start_time_read_a_second_apart_is_the_same_process(self):
        self.record(STARTED)
        with self.running(STARTED + 1):
            self.assertTrue(studio.alive("browser"))
        with self.running(STARTED - 1):
            self.assertTrue(studio.alive("browser"))

    def test_another_process_with_the_pid_is_not_ours(self):
        self.record(STARTED)
        with self.running(STARTED + 60):
            self.assertFalse(studio.alive("browser"))
        with self.running(STARTED, "vim notes.txt"):
            self.assertFalse(studio.alive("browser"))
        with self.running(None, ""):
            self.assertFalse(studio.alive("browser"))

    def test_a_start_time_recorded_as_ps_printed_it_still_counts(self):
        self.record("Sat Nov 21 20:59:43 2026")
        with self.running(STARTED):
            self.assertTrue(studio.alive("browser"))

    def test_lstart_parses_in_the_c_locale_and_rejects_anything_else(self):
        self.assertEqual(studio.epoch("Sat Nov 21  9:05:00 2026"), studio.epoch("Sat Nov 21 09:05:00 2026"))
        self.assertIsNone(studio.epoch(""))


if __name__ == "__main__":
    unittest.main()
