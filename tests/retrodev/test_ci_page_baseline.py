"""CI's page job (run 44709440973 of #64): `RD_SCAFFOLD_FULL=nested check.py bundle lint page scaffold` skipped
scaffold as "the tree fails unit" after 420 s, with "FIX: install what is missing" and no failing test named. The
base unit run inherited RD_SCAFFOLD_FULL=nested, so the unit suite ran the whole slow scaffold module (nested)
inside itself, and check.py scaffold's own tests turned to that mode and failed. Now the unit suite never sees
RD_SCAFFOLD_*, a baseline skip shows that run's last lines and names `check.py unit` as its next step, and the page
job leaves unit to CI's unit job. And macOS (run 44705952356): a RepoCase's cleanup `rm -rf` failed with "Directory
not empty" because git commit's detached `git maintenance run --auto` still wrote in .git; the test repositories
now run with automatic maintenance off, and the cleanup retries. Each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_ci_page_baseline
"""

from __future__ import annotations

import argparse
import io
import importlib.util
import os
import subprocess
import tempfile
import threading
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest import mock

from tests.retrodev.fixture import RepoCase, git, parallel, remove_tree
from tests.retrodev.tree_copy import NO_MAINTENANCE

load_tests = parallel

ROOT = Path(__file__).resolve().parents[2]


def check_py():
    spec = importlib.util.spec_from_file_location("check_py_probe_page_baseline", ROOT / "tools/check.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TheUnitSuiteNeverSeesTheScaffoldModes(unittest.TestCase):
    def test_rd_scaffold_variables_stay_out_of_the_unit_run(self):
        unit_home = check_py().unit_home  # tools/py/unit_home.py, as check.py imports it
        source = {"PATH": "/bin", "RD_SCAFFOLD_FULL": "nested", "RD_SCAFFOLD_BASE": "page", "RD_SCAFFOLD_KEEP": "1"}
        env = unit_home.unit_env("/h", "/b", "/t", source=source)
        self.assertEqual([key for key in env if key.startswith("RD_SCAFFOLD_")], [])
        self.assertEqual(env["PATH"], "/bin")


class TheBaseline(unittest.TestCase):
    def invocation(self, **rows):
        done = threading.Event()
        done.set()
        return argparse.Namespace(
            strict=True,
            finished={name: done for name in rows},
            states={name: state for name, (state, _) in rows.items()},
            details={name: detail for name, (_, detail) in rows.items()},
        )

    def test_the_page_job_leaves_unit_to_the_unit_job(self):
        module, ci = check_py(), {"GITHUB_ACTIONS": "true"}
        self.assertEqual(module.scaffold_baseline(argparse.Namespace(), "nested", ci), (["page"], ["unit"]))
        with_unit = self.invocation(unit=("ok", ""))  # this invocation runs unit too: its row is reused
        self.assertEqual(module.scaffold_baseline(with_unit, "nested", ci), (["unit", "page"], []))
        self.assertEqual(module.scaffold_baseline(argparse.Namespace(), "nested", {}), (["unit", "page"], []))
        self.assertEqual(module.scaffold_baseline(argparse.Namespace(), "1", ci), (["page"], []))

    def test_a_tree_failing_unit_shows_the_failing_tests_and_the_command_to_see_them(self):
        module = check_py()
        if not (ROOT / "tools/npm/node_modules").is_dir():
            self.skipTest("the npm tools are not set up here")
        failure = "FAIL: test_probe (tests.backend.x.test_y.Case.test_probe)\nRan 9 tests\nFIX: read the failures above"
        args = self.invocation(unit=("FAILED", failure), page=("ok", ""))
        with (
            mock.patch.object(module, "ruff_missing", lambda: None),
            mock.patch.object(module, "need", lambda tool: tool),
            mock.patch.object(module, "scaffold_mode", lambda: "nested"),
            mock.patch.object(module, "run", lambda *a, **k: self.fail("the scaffold module ran")),
        ):
            with self.assertRaises(module.Skip) as said:
                module.check_scaffold(args)
        text = str(said.exception)
        self.assertTrue(text.startswith(module.UNIT_FIRST), text)
        self.assertIn("FAIL: test_probe (tests.backend.x.test_y.Case.test_probe)", text)
        self.assertIn("FIX: python tools/check.py unit", text)
        self.assertNotIn("read the failures above", text, "the inner FIX line is left out")
        self.assertNotIn("install what is missing", text)


class StrictSkipsKeepTheirOwnNextStep(unittest.TestCase):
    def test_a_skip_naming_its_fix_is_not_told_to_install_anything(self):
        module = check_py()

        def skipping(_args):
            raise module.Skip("skipped: the tree fails unit (fix unit first)\nFAIL: x\nFIX: python tools/check.py unit")

        out = io.StringIO()
        with (
            mock.patch.dict(module.CHECKS, {"scan": skipping}),
            mock.patch.object(module, "step_summary", SimpleNamespace(write=lambda rows: None)),
            mock.patch.object(module, "print", lambda *a, **k: out.write(" ".join(map(str, a)) + "\n"), create=True),
        ):
            code = module.main(["scan", "--strict"])
        said = out.getvalue()
        self.assertEqual(code, 1, said)
        self.assertIn("FAIL: x", said)
        self.assertIn("FIX: python tools/check.py unit", said)
        self.assertNotIn("install what is missing", said)


class TestRepositoriesStartNoDetachedMaintenance(RepoCase):
    def test_a_commit_in_a_test_repository_starts_no_maintenance(self):
        traced = subprocess.run(
            ["git", "commit", "-q", "--allow-empty", "-m", "probe"],
            cwd=self.main,
            env={**os.environ, "GIT_TRACE": "1"},
            capture_output=True,
            text=True,
        )
        self.assertEqual(traced.returncode, 0, traced.stderr)
        self.assertNotIn("maintenance", traced.stderr)
        self.assertEqual(git(self.main, "config", "maintenance.auto").strip(), "false")

    def test_a_scaffold_copy_commit_starts_no_maintenance(self):
        with tempfile.TemporaryDirectory(prefix="rd-maint-") as temp:
            env = {**os.environ, **NO_MAINTENANCE, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TRACE": "1"}
            for command in (["init", "-q", "-b", "w"], ["commit", "-q", "--allow-empty", "-m", "x"]):
                done = subprocess.run(["git", *command], cwd=temp, env=env, capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stderr)
            self.assertNotIn("maintenance run", done.stderr)

    def test_remove_tree_removes_read_only_git_objects_and_a_missing_folder_is_fine(self):
        folder = self.base / "gone"
        (folder / "objects").mkdir(parents=True)
        (folder / "objects" / "pack").write_text("x")
        os.chmod(folder / "objects" / "pack", 0o444)
        remove_tree(folder)
        self.assertFalse(folder.exists())
        remove_tree(folder)


if __name__ == "__main__":
    unittest.main()
