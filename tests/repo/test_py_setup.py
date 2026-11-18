"""tools/py/setup.py names the real reason when it cannot create the venv.

A full disk or a folder this user cannot write is not a missing venv module, so each gets its own FIX; only a
missing ensurepip/venv gets the python3-venv advice. Venv creation is mocked; nothing is installed.

Run alone: python -m unittest tests.repo.test_py_setup
"""

import errno
import importlib.util
import io
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


def load_setup() -> Any:
    spec = importlib.util.spec_from_file_location("hermretro_py_setup", ROOT / "tools" / "py" / "setup.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VenvFailure(unittest.TestCase):
    def setUp(self):
        self.setup = load_setup()
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp, True)
        # Point every path at a temp checkout, so the real .dev/py is never removed.
        self.setup.ROOT, self.setup.VENV = temp, temp / ".dev" / "py"
        self.setup.STAMP, self.setup.RUFF = self.setup.VENV / "stamp", self.setup.VENV / "bin" / "ruff"

    def fail_with(self, error: BaseException) -> str:
        out = io.StringIO()
        with (
            mock.patch.object(self.setup.venv.EnvBuilder, "create", side_effect=error),
            mock.patch.object(self.setup, "ready", return_value=False),
            redirect_stdout(out),
        ):
            self.assertEqual(self.setup.main([]), 1)
        text = out.getvalue()
        self.assertIn("could not create the venv", text)
        return text.split("FIX:", 1)[1]

    def test_a_full_disk_says_free_space(self):
        fix = self.fail_with(OSError(errno.ENOSPC, "No space left on device", "/x/.dev/py/lib"))
        self.assertIn("free space on that filesystem", fix)
        self.assertNotIn("python3-venv", fix)

    def test_no_permission_says_check_the_path(self):
        fix = self.fail_with(PermissionError(errno.EACCES, "Permission denied", "/x/.dev"))
        self.assertIn("check the permissions on that path", fix)
        self.assertIn("/x/.dev", fix)
        self.assertNotIn("python3-venv", fix)

    def test_a_missing_ensurepip_says_install_venv(self):
        fix = self.fail_with(subprocess.CalledProcessError(1, ["python", "-m", "ensurepip"]))
        self.assertIn("python3-venv", fix)

    def test_another_error_does_not_blame_the_venv_module(self):
        fix = self.fail_with(OSError(errno.EIO, "Input/output error", "/x/.dev/py"))
        self.assertNotIn("python3-venv", fix)
        self.assertIn("read the error above", fix)


if __name__ == "__main__":
    unittest.main()
