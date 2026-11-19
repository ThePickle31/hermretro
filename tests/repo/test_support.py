"""tests/support.py's isolated_home gives each test a runtime folder of its own, whatever the temp base or the
developer's shell says.

Run alone: python -m unittest tests.repo.test_support
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.system import paths  # noqa: E402 - the repository root goes on the path first
from tests.support import isolated_home  # noqa: E402 - the repository root goes on the path first

SHARED = Path("/tmp") / f"hermretro-{os.getuid()}"


class IsolatedRuntime(unittest.TestCase):
    def assert_own_runtime(self, avoid: Path | None = None) -> Path:
        runtime = paths.default_runtime_dir()
        self.assertNotEqual(runtime, SHARED)
        if avoid is not None:
            self.assertNotEqual(runtime, avoid)
        self.assertLessEqual(len(os.fsencode(runtime / "broker.sock")), paths.SOCKET_PATH_LIMIT)
        self.assertEqual(os.environ.get("HERMRETRO_RUNTIME_DIR"), str(runtime))
        return runtime

    def run_inner(self, body) -> None:
        """Run ``body`` inside a throwaway TestCase's isolated_home, then its cleanups."""

        class Inner(unittest.TestCase):
            def runTest(self):
                pass

        inner = Inner()
        try:
            isolated_home(inner)
            body()
        finally:
            inner.doCleanups()

    def test_a_deep_temp_base_still_gets_its_own_short_runtime_folder(self):
        with tempfile.TemporaryDirectory() as outer:
            deep = Path(outer) / ("d" * 60) / ("e" * 60)
            deep.mkdir(parents=True)
            with mock.patch.object(tempfile, "tempdir", str(deep)):
                seen = []
                self.run_inner(lambda: seen.append(self.assert_own_runtime()))
            self.assertFalse(seen[0].exists(), "the runtime folder is removed by the test's cleanups")

    def test_an_inherited_runtime_override_is_replaced(self):
        inherited = Path("/tmp") / "someone-elses-runtime"
        with mock.patch.dict(os.environ, {"HERMRETRO_RUNTIME_DIR": str(inherited)}):
            self.run_inner(lambda: self.assert_own_runtime(avoid=inherited))
            self.assertEqual(os.environ["HERMRETRO_RUNTIME_DIR"], str(inherited))


if __name__ == "__main__":
    unittest.main()
