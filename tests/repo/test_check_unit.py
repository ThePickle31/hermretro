"""tools/check.py's unit run neither reads nor writes Python bytecode.

Proving a regression test means running it against the old code and the new: a `git stash` and an edit of the
same size within the same second leave the .pyc's recorded size and time unchanged, so a run that reads
__pycache__ tests the code that was there before. The unit check passes -B and PYTHONDONTWRITEBYTECODE=1.
"""

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import check  # noqa: E402  (tools/check.py, imported from its folder)


class UnitCheckBytecodeTests(unittest.TestCase):
    def test_the_unit_run_skips_bytecode(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return subprocess.CompletedProcess(cmd, 0, "", "Ran 1 test in 0.001s\n\nOK\n")

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


if __name__ == "__main__":
    unittest.main()
