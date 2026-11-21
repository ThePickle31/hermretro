"""tools/check.py's unit run neither reads stale Python bytecode nor writes any.

Proving a regression test means running it against the old code and the new: a `git stash` and an edit of the
same size within the same second leave the .pyc's recorded size and time unchanged, so a run that reads
__pycache__ tests the code that was there before. -B and PYTHONDONTWRITEBYTECODE=1 only stop writes; the unit
check also gives its run a fresh, empty PYTHONPYCACHEPREFIX, so no earlier .pyc is ever read.
"""

import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import check  # noqa: E402 - tools/check.py is imported from its own folder
import importlib.util
import re

PROBE = ["-c", "import probe; print(probe.WORD)"]
OK = "Ran 1 test in 0.001s\n\nOK\n"


def seed_stale_bytecode(folder: Path) -> None:
    """probe.py says "fresh" while its __pycache__ .pyc, still matching its size and time, says "stale"."""
    source = folder / "probe.py"
    source.write_text('WORD = "stale"\n')
    stamp = source.stat()
    # Into the folder's own __pycache__ even when this run has a PYTHONPYCACHEPREFIX (the unit check gives it one).
    cached = folder / "__pycache__" / f"probe.{sys.implementation.cache_tag}.pyc"
    timestamp = py_compile.PycInvalidationMode.TIMESTAMP
    py_compile.compile(str(source), cfile=str(cached), invalidation_mode=timestamp, doraise=True)
    source.write_text('WORD = "fresh"\n')
    os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))


class UnitCheckBytecodeTests(unittest.TestCase):
    def test_the_unit_run_writes_no_bytecode(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return subprocess.CompletedProcess(cmd, 0, "", OK)

        with mock.patch.object(check, "run", fake_run):
            check.check_unit(None)
        (cmd, kwargs), *_ = calls
        self.assertEqual(
            cmd[1:4],
            ["-B", "-m", "unittest"],
            "tools/check.py's unit run must pass -B\nFIX: run [sys.executable, '-B', '-m', 'unittest', ...]",
        )
        self.assertEqual(
            kwargs["env"].get("PYTHONDONTWRITEBYTECODE"),
            "1",
            "tools/check.py's unit run must set PYTHONDONTWRITEBYTECODE=1 for its subprocess\n"
            "FIX: add it to the env check_unit passes",
        )

    def test_the_unit_run_runs_an_edit_that_kept_the_size_and_time_of_its_cached_bytecode(self):
        folder = Path(tempfile.mkdtemp(prefix="hermretro-pyc-test-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        seed_stale_bytecode(folder)
        plain = {key: value for key, value in os.environ.items() if not key.startswith("PYTHON")}
        control = subprocess.run([sys.executable, *PROBE], cwd=folder, env=plain, text=True, capture_output=True)
        self.assertEqual(control.stdout.strip(), "stale", f"the probe must reuse its seeded .pyc\n{control.stderr}")
        seen = []

        def fake_run(cmd, **kwargs):  # the probe under exactly the interpreter flags and env the unit run gets
            probe = [cmd[0], *cmd[1 : cmd.index("-m")], *PROBE]
            seen.append(subprocess.run(probe, cwd=folder, env=kwargs["env"], text=True, capture_output=True))
            return subprocess.CompletedProcess(cmd, 0, "", OK)

        with mock.patch.object(check, "run", fake_run):
            check.check_unit(None)
        self.assertEqual(
            seen[0].stdout.strip(),
            "fresh",
            "tools/check.py's unit run read a stale .pyc (-B and PYTHONDONTWRITEBYTECODE only stop writes)\n"
            f"{seen[0].stderr}\nFIX: give the run a fresh, empty PYTHONPYCACHEPREFIX in check_unit",
        )


class UnitCheckDiscovery(unittest.TestCase):
    def test_product_discovery_omits_only_dev_cli_ids(self):
        probe = """\
import json
import unittest

def ids(suite):
    for item in suite:
        if isinstance(item, unittest.BaseTestSuite):
            yield from ids(item)
        else:
            yield item.id()

loader = unittest.TestLoader()
suite = loader.discover('tests', top_level_dir='.')
assert not loader.errors, loader.errors
print(json.dumps(list(ids(suite))))
"""
        env = dict(os.environ)
        env.pop("HERMRETRO_UNIT_PRODUCT_ONLY", None)
        scopes = []
        for flags in (env, {**env, "HERMRETRO_UNIT_PRODUCT_ONLY": "1"}):
            result = subprocess.run(
                [sys.executable, "-B", "-c", probe], cwd=ROOT, env=flags, capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            scopes.append(json.loads(result.stdout))
        full, product = scopes
        wanted = [name for name in full if not name.startswith("tests.retrodev.")]
        self.assertTrue(wanted, "full discovery must contain product tests")
        self.assertLess(len(wanted), len(full), "full discovery must also contain dev CLI tests")
        self.assertCountEqual(product, wanted)

    def test_only_an_explicit_product_run_omits_the_dev_cli(self):
        runs = []

        def fake_run(cmd, **kwargs):
            runs[-1].append((kwargs["env"].get("HERMRETRO_UNIT_PRODUCT_ONLY"), "tests/retrodev" in cmd))
            return subprocess.CompletedProcess(cmd, 0, "", OK)

        with mock.patch.object(check, "run", fake_run), mock.patch.dict(os.environ, HERMRETRO_UNIT_PRODUCT_ONLY="1"):
            for args in (None, Namespace(unit_product_only=True)):
                runs.append([])
                check.check_unit(args)
        full, product = runs
        self.assertEqual({flag for flag, _ in full}, {None}, "the shell's variable alone never narrows the run")
        self.assertTrue(any(dev_cli for _, dev_cli in full), "a full run also runs the dev CLI suite")
        self.assertEqual(set(product), {("1", False)}, "--unit-product-only runs no dev CLI process")


class UnitCheckHomeTests(unittest.TestCase):
    def test_product_leak_diagnosis_reruns_only_in_scope_modules(self):
        product = "tests.backend.library.test_build_report"
        dev_cli = "tests.retrodev.test_check_ship"
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            (Path(kwargs["env"]["HOME"]) / "leak").touch()
            return subprocess.CompletedProcess(cmd, 0, "", OK)

        with (
            mock.patch.object(check, "run", fake_run),
            mock.patch.object(check.unit_shards.unit_home, "test_modules", return_value=[product, dev_cli]),
            self.assertRaises(AssertionError) as caught,
        ):
            check.check_unit(Namespace(unit_product_only=True))
        self.assertEqual([cmd for cmd in calls if dev_cli in cmd or "tests/retrodev" in cmd], [])
        self.assertIn([sys.executable, "-B", "-m", "unittest", product], calls, "the in-scope module is rerun alone")
        self.assertIn(f"written by: {product}", str(caught.exception))

    def test_a_write_to_hermes_plugin_data_folder_fails_the_run(self):
        def fake_run(cmd, **kwargs):  # what Hermes's plugin_data_dir would do, from the env the run gets
            data = Path(kwargs["env"]["HERMES_HOME"]) / "plugin-data" / "hermretro" / "snapshots"
            data.mkdir(parents=True)
            return subprocess.CompletedProcess(cmd, 0, "", OK)

        with mock.patch.object(check, "run", fake_run), self.assertRaises(AssertionError) as caught:
            check.check_unit(None)
        self.assertIn(
            "plugin-data",
            str(caught.exception),
            "a write to Hermes's plugin data folder must fail the unit run\n"
            "FIX: point HERMES_HOME inside the empty HOME that check_unit watches",
        )

    def test_a_leak_names_the_test_module_that_wrote_there(self):
        calls = []

        def fake_run(cmd, **kwargs):  # the whole suite leaks; rerun alone, only one module does
            calls.append(cmd)
            if "tests.backend.library.test_build_report" in cmd:  # its process, then the module rerun alone
                (Path(kwargs["env"]["HOME"]) / ".hermes" / "hermretro").mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(cmd, 0, "", OK)

        with mock.patch.object(check, "run", fake_run), self.assertRaises(AssertionError) as caught:
            check.check_unit(None)
        message = str(caught.exception)
        self.assertIn("written by: tests.backend.library.test_build_report (.hermes", message)
        self.assertNotIn("test_check_unit", message, "only the module that wrote there is named")
        self.assertIn("calls a real emitter", message)
        self.assertGreater(len(calls), 2, "each module was rerun on its own")

    def test_the_row_names_the_files_behind_layout_warnings(self):
        warned = (
            "layout warning: tests/page/big.test.mjs has 437 lines (warning above 400, failure above 600)\n"
            "layout warning: allowance backend/x.py:3 front-door: a reason\n" + OK
        )

        def fake_run(cmd, **kwargs):  # only the process that runs tests.repo.test_layout prints its warnings
            return subprocess.CompletedProcess(cmd, 0, "", warned if "tests.repo.test_layout" in cmd else OK)

        with mock.patch.object(check, "run", fake_run):
            row = check.check_unit(None)
        self.assertIn("2 layout warnings; over the size warning: tests/page/big.test.mjs (all: python -m unittest", row)

    def test_a_temp_folder_left_behind_fails_the_run_and_names_its_module(self):
        def fake_run(cmd, **kwargs):  # a tempfile.mkdtemp() without a cleanup, in the TMPDIR the run gets
            if "tests.backend.setup.test_onboarding" in cmd:  # its process, then the module rerun alone
                tempfile.mkdtemp(prefix="leaked-", dir=kwargs["env"]["TMPDIR"])
            return subprocess.CompletedProcess(cmd, 0, "", OK)

        with mock.patch.object(check, "run", fake_run), self.assertRaises(AssertionError) as caught:
            check.check_unit(None)
        message = str(caught.exception)
        self.assertRegex(message, r"left files in the temp folder: \S*hermretro-tmp-\w+/leaked-", "names the path")
        self.assertIn("left by: tests.backend.setup.test_onboarding (leaked-", message)
        self.assertIn("FIX: clean up with addCleanup / TemporaryDirectory", message)


class LayoutSummary(unittest.TestCase):
    def test_the_branch_s_own_big_files_are_named_first(self):
        spec = importlib.util.spec_from_file_location("unit_home_round_eighteen", ROOT / "tools/py/unit_home.py")
        unit_home = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(unit_home)
        lines = [f"layout warning: backend/f{n}.py has 450 lines (over 400)" for n in range(9)]
        note = unit_home.layout_note(lines, ["backend/f8.py", "docs/x.md"])
        self.assertTrue(re.search(r"over the size warning: backend/f8\.py, backend/f0\.py", note), note)
        self.assertIn("and 3 more", note)


if __name__ == "__main__":
    unittest.main()
