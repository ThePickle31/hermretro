"""tools/check.py's unit run neither reads stale Python bytecode nor writes any.

Proving a regression test means running it against the old code and the new: a `git stash` and an edit of the
same size within the same second leave the .pyc's recorded size and time unchanged, so a run that reads
__pycache__ tests the code that was there before. -B and PYTHONDONTWRITEBYTECODE=1 only stop writes; the unit
check also gives its run a fresh, empty PYTHONPYCACHEPREFIX, so no earlier .pyc is ever read.
"""

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
    def test_only_an_explicit_product_run_omits_the_dev_cli(self):
        flags = []

        def fake_run(cmd, **kwargs):
            flags.append(kwargs["env"].get("HERMRETRO_UNIT_PRODUCT_ONLY"))
            return subprocess.CompletedProcess(cmd, 0, "", OK)

        with mock.patch.object(check, "run", fake_run), mock.patch.dict(os.environ, HERMRETRO_UNIT_PRODUCT_ONLY="1"):
            check.check_unit(None)
            check.check_unit(Namespace(unit_product_only=True))
        self.assertEqual(flags, [None, "1"])


class UnitCheckHomeTests(unittest.TestCase):
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
            if "discover" in cmd or cmd[-1] == "tests.backend.library.test_build_report":
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
        with mock.patch.object(check, "run", lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, "", warned)):
            row = check.check_unit(None)
        self.assertIn("2 layout warnings; over the size warning: tests/page/big.test.mjs (all: python -m unittest", row)

    def test_a_temp_folder_left_behind_fails_the_run_and_names_its_module(self):
        def fake_run(cmd, **kwargs):  # a tempfile.mkdtemp() without a cleanup, in the TMPDIR the run gets
            if "discover" in cmd or cmd[-1] == "tests.backend.setup.test_onboarding":
                tempfile.mkdtemp(prefix="leaked-", dir=kwargs["env"]["TMPDIR"])
            return subprocess.CompletedProcess(cmd, 0, "", OK)

        with mock.patch.object(check, "run", fake_run), self.assertRaises(AssertionError) as caught:
            check.check_unit(None)
        message = str(caught.exception)
        self.assertRegex(message, r"left files in the temp folder: \S*hermretro-tmp-\w+/leaked-", "names the path")
        self.assertIn("left by: tests.backend.setup.test_onboarding (leaked-", message)
        self.assertIn("FIX: clean up with addCleanup / TemporaryDirectory", message)


if __name__ == "__main__":
    unittest.main()
