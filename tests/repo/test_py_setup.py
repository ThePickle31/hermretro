"""tools/py/setup.py names the real reason when it cannot create the venv.

A full disk or a folder this user cannot write is not a missing venv module, so each gets its own FIX, whether it
arrives as an OSError or in a failed ensurepip's output (which is shown); only that output naming a missing
ensurepip/venv gets the python3-venv advice. Venv creation is mocked; nothing is installed.

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

    def fail_with(self, error: BaseException, shown: str = "") -> str:
        out = io.StringIO()
        with (
            mock.patch.object(self.setup.venv.EnvBuilder, "create", side_effect=error),
            mock.patch.object(self.setup, "ready", return_value=False),
            redirect_stdout(out),
        ):
            self.assertEqual(self.setup.main([]), 1)
        text = out.getvalue()
        self.assertIn("could not create the venv", text)
        self.assertIn(shown, text.split("FIX:", 1)[0])
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
        for said in ("No module named ensurepip", "ensurepip is not available", "No module named venv"):
            error = subprocess.CalledProcessError(1, ["python", "-m", "ensurepip"], output=f"error: {said}\n")
            fix = self.fail_with(error, said)
            self.assertIn("python3-venv", fix, said)

    def ensurepip_failed(self, said: str, as_bytes: bool = False) -> str:
        text = f"Traceback (most recent call last):\n  ...\n{said}\n"
        error = subprocess.CalledProcessError(
            1, ["python", "-m", "ensurepip", "--upgrade"], stderr=text.encode() if as_bytes else text
        )
        return self.fail_with(error, said)

    def test_ensurepip_on_a_full_disk_says_free_space(self):
        fix = self.ensurepip_failed("OSError: [Errno 28] No space left on device: '/tmp/tmpab/pip.whl'")
        self.assertIn("free space on that filesystem", fix)
        self.assertNotIn("python3-venv", fix)

    def test_ensurepip_without_permission_says_check_the_permissions(self):
        fix = self.ensurepip_failed("PermissionError: [Errno 13] Permission denied: '/x/.dev/py/lib'", as_bytes=True)
        self.assertIn("check the permissions on that path", fix)
        self.assertNotIn("python3-venv", fix)

    def test_another_ensurepip_failure_says_read_the_error(self):
        fix = self.ensurepip_failed("ERROR: Could not install packages due to an unexpected error")
        self.assertIn("read the error above", fix)
        self.assertNotIn("python3-venv", fix)

    def test_another_error_does_not_blame_the_venv_module(self):
        fix = self.fail_with(OSError(errno.EIO, "Input/output error", "/x/.dev/py"))
        self.assertNotIn("python3-venv", fix)
        self.assertIn("read the error above", fix)


if __name__ == "__main__":
    unittest.main()
