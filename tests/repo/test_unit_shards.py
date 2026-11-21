"""tools/py/unit_shards.py: check.py unit runs the suite as several processes at once. Every test module runs in
exactly one of them, the dev CLI suite keeps its own (its package puts its modules on one thread pool), and
modules are dealt by recorded time so no process is left with most of the work.
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "py"))

import unit_home  # noqa: E402 - tools/py/ goes on sys.path first
import unit_shards  # noqa: E402 - tools/py/ goes on sys.path first

DEV_CLI = ["discover", "-s", "tests/retrodev", "-t", "."]


class Groups(unittest.TestCase):
    def setUp(self):
        self.modules = unit_home.test_modules(ROOT)
        self.product = [name for name in self.modules if not name.startswith("tests.retrodev.")]

    def test_every_product_module_runs_in_exactly_one_process_and_the_dev_cli_in_its_own(self):
        for cpus in (1, 3, 4, 20):
            with self.subTest(cpus=cpus):
                found = unit_shards.groups(ROOT, self.modules, product_only=False, times={}, cpus=cpus)
                self.assertEqual(found[-1], DEV_CLI)
                dealt = [name for group in found[:-1] for name in group]
                self.assertCountEqual(dealt, self.product, "each product module once, none of the dev CLI's")
                self.assertLessEqual(len(found) - 1, unit_shards.MAX_PRODUCT_SHARDS)

    def test_a_product_only_run_has_no_dev_cli_process(self):
        found = unit_shards.groups(ROOT, self.modules, product_only=True, times={}, cpus=4)
        self.assertNotIn(DEV_CLI, found)
        self.assertCountEqual([name for group in found for name in group], self.product)

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


if __name__ == "__main__":
    unittest.main()
