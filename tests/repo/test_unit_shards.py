"""tools/py/unit_shards.py: check.py unit runs the suite as several processes at once. Every test module runs in
exactly one of them, the dev CLI suite keeps its own (its package puts its modules on one thread pool), and
modules are dealt by recorded time so no process is left with most of the work.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "py"))

import unit_home  # noqa: E402 - tools/py/ goes on sys.path first
import unit_shards  # noqa: E402 - tools/py/ goes on sys.path first


class Groups(unittest.TestCase):
    def test_every_module_runs_in_exactly_one_process(self):
        modules = unit_home.test_modules(ROOT)
        for cpus in (1, 3, 4, 20):
            with self.subTest(cpus=cpus):
                found = unit_shards.groups(ROOT, modules, times={}, cpus=cpus)
                self.assertCountEqual([name for group in found for name in group], modules)
                self.assertLessEqual(len(found), unit_shards.MAX_SHARDS)

    def test_recorded_times_spread_the_work(self):
        weights = {"a": 10.0, "b": 6.0, "c": 5.0, "d": 1.0}
        self.assertEqual(unit_shards.deal(weights, 2), [["a", "d"], ["b", "c"]])
        self.assertEqual(unit_shards.deal({"a": 1.0}, 3), [["a"]], "no empty process")


class Times(unittest.TestCase):
    STDERR = (
        "Slowest test durations\n"
        "1.500s     test_one (tests.repo.test_x.Case.test_one)\n"
        "0.500s     test_two (tests.repo.test_x.Case.test_two)\n"
        "0.250s     test_three (tests.backend.a.test_y.Other.test_three)\n"
    )

    def test_durations_are_summed_per_module_and_the_slowest_named(self):
        self.assertEqual(
            unit_shards.module_times(self.STDERR), {"tests.repo.test_x": 2.0, "tests.backend.a.test_y": 0.25}
        )
        self.assertEqual(unit_shards.slowest(self.STDERR, 2), [(1.5, "test_one"), (0.5, "test_two")])

    def test_times_are_kept_for_the_next_run_and_an_empty_run_keeps_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".dev" / "unit-times.json"
            unit_shards.save(path, {})
            self.assertFalse(path.exists(), "a run without durations (a fake, Python 3.11) writes nothing")
            unit_shards.save(path, {"tests.repo.test_x": 2.0})
            self.assertEqual(unit_shards.load(path), {"tests.repo.test_x": 2.0})
            path.write_text("not json")
            self.assertEqual(unit_shards.load(path), {})


def passed(cmd, **_kwargs):
    return subprocess.CompletedProcess(cmd, 0, "", "Ran 1 test in 0.001s\n\nOK\n")


class Discovery(unittest.TestCase):
    def test_the_processes_run_every_module_unittest_discovery_finds(self):
        # A module discovery finds but no process names (testcoverage.py: test*.py, not test_*.py) would never run.
        probe = (
            "import json, unittest\n"
            "def ids(suite):\n"
            "    for item in suite:\n"
            "        yield from ids(item) if isinstance(item, unittest.BaseTestSuite) else [item.id()]\n"
            "loader = unittest.TestLoader()\n"
            "suite = loader.discover('tests', top_level_dir='.')\n"
            "assert not loader.errors, loader.errors\n"
            "print(json.dumps(sorted({i.rsplit('.', 2)[0] for i in ids(suite)})))\n"
        )
        found = subprocess.run([sys.executable, "-B", "-c", probe], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(found.returncode, 0, found.stderr)
        discovered = {name for name in json.loads(found.stdout) if name.startswith("tests.")}
        groups = unit_shards.groups(ROOT, unit_home.test_modules(ROOT), times={}, cpus=4)
        self.assertEqual(discovered - {name for group in groups for name in group}, set())

    def test_the_module_list_follows_discovery_s_rules(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in (
                "tests/__init__.py",
                "tests/a/__init__.py",
                "tests/a/testcoverage.py",
                "tests/a/test_x.py",
                "tests/a/test-bad.py",
                "tests/loose/test_y.py",
                "tests/a/helper.py",
            ):
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text("")
            self.assertEqual(unit_home.test_modules(root), ["tests.a.test_x", "tests.a.testcoverage"])


class Reports(unittest.TestCase):
    def test_a_failure_keeps_its_traceback_above_the_timing_rows(self):
        rows = "".join(f"0.{i:03d}s     test_{i} (tests.repo.test_x.Case.test_{i})\n" for i in range(60))
        stderr = (
            "FAIL: test_one (tests.repo.test_x.Case.test_one)\nTraceback (most recent call last):\n"
            "AssertionError: the reason it failed\n\nSlowest test durations\n"
            + "-" * 70
            + "\n"
            + rows
            + "\n(durations < 0.001s were hidden; use -v to show these durations)\nRan 60 tests in 1s\n\n"
            "FAILED (failures=1)\n"
        )
        failing = lambda cmd, **_kwargs: subprocess.CompletedProcess(cmd, 1, "", stderr)  # noqa: E731 - one-line fake
        row, failure = unit_shards.run_suite(ROOT, failing, tempfile.gettempdir())
        self.assertEqual(row, "")
        self.assertIn("AssertionError: the reason it failed", failure)
        self.assertNotIn("test_59 (", failure)

    def test_a_failure_keeps_what_a_server_printed_far_above_its_tail(self):
        # A request the server dropped: its handler's traceback is printed long before the test's own failure.
        dropped = (
            "-" * 40 + "\nException occurred during processing of request from ('127.0.0.1', 5000)\n"
            "Traceback (most recent call last):\n  File \"server.py\", line 9, in do_GET\n"
            "OSError: the reason the server gave no answer\n" + "-" * 40 + "\n"
        )
        stderr = dropped + "ok\n" * 80 + "ERROR: test_fetch (tests.repo.test_x.Case.test_fetch)\nRemoteDisconnected\n"
        failing = lambda cmd, **_kwargs: subprocess.CompletedProcess(cmd, 1, "", stderr)  # noqa: E731 - one-line fake
        _row, failure = unit_shards.run_suite(ROOT, failing, tempfile.gettempdir())
        self.assertIn("printed by a server or thread during the run:", failure)
        self.assertIn("OSError: the reason the server gave no answer", failure)
        self.assertIn("RemoteDisconnected", failure)

    def test_only_the_last_background_tracebacks_are_kept_each_ending_at_its_exception(self):
        died = "Exception in thread worker:\nTraceback (most recent call last):\n  File \"x.py\", line 1\nValueError: {}\nafter\n"
        blocks = unit_shards.background_errors("".join(died.format(n) for n in range(5)))
        self.assertEqual(
            [block.splitlines()[-1] for block in blocks], ["ValueError: 2", "ValueError: 3", "ValueError: 4"]
        )

    def test_each_leaking_process_names_its_own_leftovers_and_modules(self):
        home_writer, tmp_writer = "tests.repo.test_layout", "tests.repo.test_docs"

        def fake_run(cmd, **kwargs):
            env = kwargs["env"]
            if home_writer in cmd:
                (Path(env["HOME"]) / "from-home-writer").touch()
            if tmp_writer in cmd:
                (Path(env["TMPDIR"]) / "from-tmp-writer").touch()
            return passed(cmd)

        with (
            mock.patch.object(unit_home, "test_modules", return_value=[home_writer, tmp_writer]),
            mock.patch.object(unit_shards.os, "cpu_count", return_value=4),
        ):
            row, failure = unit_shards.run_suite(ROOT, fake_run, tempfile.gettempdir())
        self.assertEqual(row, "")
        self.assertIn(f"from-home-writer\nwritten by: {home_writer} (from-home-writer)", failure)
        self.assertIn(f"left by: {tmp_writer} (from-tmp-writer)", failure)
        self.assertNotIn(f"written by: {home_writer} (from-home-writer); ", failure)


if __name__ == "__main__":
    unittest.main()
