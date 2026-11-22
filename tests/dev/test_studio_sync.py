"""tools/dev/studio_sync.py: the sandbox's checkout follows origin/dev by fast-forward only, never over local work,
and a feature branch is only told how far behind it is."""

import contextlib
import importlib.util
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOP = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("studio_sync", TOP / "tools" / "dev" / "studio_sync.py")
studio_sync = importlib.util.module_from_spec(_spec)
sys.modules["studio_sync"] = studio_sync
_spec.loader.exec_module(studio_sync)


def git(cwd: Path, *args: str) -> str:
    env = {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
    }
    identity = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "init.defaultBranch=dev"]
    return subprocess.run(
        ["git", *identity, *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
    ).stdout


class SyncCheckoutTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        self.origin, self.clone, self.writer = (self.folder / name for name in ("origin.git", "clone", "writer"))
        git(self.folder, "init", "--bare", str(self.origin))
        git(self.folder, "clone", str(self.origin), str(self.writer))
        self.commit("first")
        git(self.folder, "clone", str(self.origin), str(self.clone))
        self.commit("second")  # origin/dev is now one ahead of the clone

    def commit(self, name: str):
        (self.writer / name).write_text(name)
        git(self.writer, "add", name)
        git(self.writer, "commit", "-m", name)
        git(self.writer, "push", "-q", "origin", "HEAD:dev")

    def sync(self) -> tuple[bool, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            moved = studio_sync.sync_checkout(self.clone)
        return moved, out.getvalue()

    def test_a_clean_dev_checkout_is_fast_forwarded(self):
        moved, said = self.sync()
        self.assertTrue(moved)
        self.assertIn("now at origin/dev", said)
        self.assertTrue((self.clone / "second").is_file())
        self.assertEqual(self.sync()[0], False)  # already current

    def test_local_changes_on_dev_are_never_touched(self):
        (self.clone / "first").write_text("mine")
        moved, said = self.sync()
        self.assertFalse(moved)
        self.assertIn("local changes", said)
        self.assertEqual((self.clone / "first").read_text(), "mine")
        self.assertFalse((self.clone / "second").exists())

    def test_a_feature_branch_is_told_how_far_behind_it_is(self):
        git(self.clone, "checkout", "-q", "-b", "feat/x")
        moved, said = self.sync()
        self.assertFalse(moved)
        self.assertIn("feat/x is 1 commits behind dev", said)
        self.assertIn("FIX: git rebase origin/dev", said)
        self.assertFalse((self.clone / "second").exists())


if __name__ == "__main__":
    unittest.main()
