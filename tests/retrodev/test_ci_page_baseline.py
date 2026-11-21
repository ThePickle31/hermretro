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
import types
from retrodev import checks, config, output, repo, state
from tests.retrodev.fixture import GOOD_BODY, write

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


ACT = (
    "An update to BuildNewGame inside a test was not wrapped in act(...).\n\nWhen testing, code that causes React state "
    "updates should be wrapped into act(...):\n\nact(() => {\n  /* fire events that update state */\n});\n"
    "/* assert on the output */\n\nThis ensures that you're testing the behavior the user would see in the browser.\n"
)

SPEC = (
    "page-build-shelf.test.mjs: 7 passed, 0 failed\n✔ tests/page/page-build-shelf.test.mjs (1319.8ms)\n"
    + ACT
    + "check failed: an approval seen both as an event and by the poll is one card\n"
    "AssertionError [ERR_ASSERTION]: Expected values to be strictly equal:\n\n0 !== 1\n\n"
    "    at file:///x/tests/page/page-build.test.mjs:193:12\n"
    + ACT
    + "page-build.test.mjs: 13 passed, 1 failed\n✖ tests/page/page-build.test.mjs (2105.5ms)\n"
    "✔ clock() is minutes:seconds (0.7ms)\n✖ waits (201.2ms)\n  'test timed out after 200ms'\n"
    "ℹ tests 4\nℹ pass 2\nℹ fail 1\nℹ cancelled 1\n\n✖ failing tests:\n\n"
    "test at tests/page/page-build.test.mjs:1:1\n✖ tests/page/page-build.test.mjs (2105.5ms)\n  'test failed'\n\n"
    "test at tests/page/slow.test.mjs:1:31\n✖ waits (201.2ms)\n  'test timed out after 200ms'\n"
)


class FlowFixes(RepoCase):
    def passed(self, tree, name):
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        record = state.load_branch(self.main, name)
        record.update(passed_tree=repo.tree_digest(tree), passed_checks=sorted(checks.required(ctx)))
        state.save_branch(self.main, record)

    def ready(self, name="docs/tidy"):
        tree = self.worktree(name)
        self.commit(tree, "docs/guide.md", "# Guide, better\n", "Improve the guide")
        self.passed(tree, name)
        return tree, str(write(self.base, "body.md", GOOD_BODY))

    def test_the_lint_summary_names_each_page_warning(self):
        spec = importlib.util.spec_from_file_location("check_py_copy", ROOT / "tools" / "check.py")
        module = importlib.util.module_from_spec(spec)  # a private copy: rebinding its names touches no other test
        spec.loader.exec_module(module)
        lint = "warning: page/a.js:208:9  'x' is unused. [no-unused-vars]\n    why: ...\n3 files: 0 errors, 1 warnings"

        class Done:
            def __init__(self, text):
                self.text, self.returncode = text, 0

            def communicate(self):
                return self.text, None

        module.shutil = types.SimpleNamespace(which=lambda name: "/usr/bin/" + name)
        module.ruff_missing = lambda: None
        module.start = lambda command: Done(lint if "lint-page.mjs" in " ".join(command) else "")
        summary = module.check_lint(types.SimpleNamespace(strict=False))
        self.assertIn("page: 3 files: 0 errors, 1 warnings (warnings: page/a.js:208)", summary)


class WholeScaffoldCheckFirst(unittest.TestCase):
    def check_py(self):
        spec = importlib.util.spec_from_file_location("check_py_probe_nine_first", ROOT / "tools/check.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not (ROOT / "tools/npm/node_modules").is_dir():
            self.skipTest("the npm tools are not set up here")
        return module

    def scaffold(self, module, args, page=None):
        ran = []

        def run(command, **kwargs):
            ran.append(kwargs.get("env", {}))
            return subprocess.CompletedProcess(command, 0, "", "Ran 12 tests\n\nOK\n")

        with (
            mock.patch.object(module, "run", run),
            mock.patch.object(module, "ruff_missing", lambda: None),
            mock.patch.object(module, "need", lambda tool: tool),
            mock.patch.dict(module.CHECKS, {"page": page or (lambda _args: "fine")}),
        ):
            try:
                return module.check_scaffold(args), ran
            except module.Skip as skip:
                return str(skip), ran

    def invocation(self, page_state: str):
        done = threading.Event()
        done.set()
        return argparse.Namespace(strict=False, finished={"page": done}, states={"page": page_state})

    @staticmethod
    def fail(_args):
        raise AssertionError("page ran a second time")

    def test_a_page_row_of_the_same_run_that_failed_skips_the_whole_check(self):
        module = self.check_py()
        said, ran = self.scaffold(module, self.invocation("FAILED"), page=self.fail)
        self.assertEqual(said.splitlines()[0], "skipped: the tree fails page (fix page first)")
        self.assertIn("FIX: python tools/check.py page", said)
        self.assertEqual(ran, [], "the scaffold module does not run at all")

    def test_a_page_row_of_the_same_run_that_passed_is_reused(self):
        module = self.check_py()
        said, ran = self.scaffold(module, self.invocation("ok"), page=self.fail)  # page itself would fail: unused
        self.assertEqual(said, "retrodev new of every kind passes the real checks")
        self.assertEqual([env.get("RD_SCAFFOLD_BASE") for env in ran], ["page"])

    def test_without_a_page_row_check_py_runs_page_once_itself(self):
        module = self.check_py()
        calls = []

        def page(_args):
            calls.append(1)
            raise AssertionError("not ok 1 - rdprobe")

        said, ran = self.scaffold(module, argparse.Namespace(strict=False), page=page)
        first, shown = said.splitlines()[:2]
        self.assertEqual((first, calls, ran), ("skipped: the tree fails page (fix page first)", [1], []))
        self.assertEqual(shown, "not ok 1 - rdprobe", "the failure shows, not only that there was one")


class PageFailure(RepoCase):
    def test_a_failing_page_file_shows_its_own_assertion_not_only_test_failed(self):
        said = check_py().page_failure(SPEC)
        self.assertIn("tests/page/page-build.test.mjs failed:", said)
        self.assertIn("check failed: an approval seen both as an event and by the poll is one card", said)
        self.assertIn("0 !== 1", said)
        self.assertIn("page-build.test.mjs: 13 passed, 1 failed", said)
        self.assertNotIn("not wrapped in act", said, "React's act() warnings are noise here")
        self.assertNotIn("page-build-shelf", said, "only the failing file's own output")
        fix = said.splitlines()[-1]
        self.assertTrue(fix.startswith("FIX: waits timed out (stopped for taking too long, not an assertion)"), fix)
        self.assertIn("node tests/page/page-build.test.mjs; node tests/page/slow.test.mjs", fix)

    def test_without_a_timeout_the_fix_says_nothing_of_one(self):
        spec = SPEC.replace("'test timed out after 200ms'", "'boom'")
        fix = check_py().page_failure(spec).splitlines()[-1]
        self.assertNotIn("timed out", fix)
        self.assertTrue(fix.startswith("FIX: run it alone: node tests/page/page-build.test.mjs"), fix)

    def test_the_scaffold_check_keeps_the_page_file_s_output_above_its_last_lines(self):
        module = check_py()
        block = module.page_failure(SPEC).replace("\n", "\n         ")
        stderr = "new tab rdtabs first:\n FAILED  page            3.8 s  " + block + "\n" + "more\n" * 60
        said = module.scaffold_said(stderr)
        self.assertIn("check failed: an approval seen both as an event and by the poll is one card", said)
        self.assertTrue(said.endswith("more"), "and the last lines still follow")


if __name__ == "__main__":
    unittest.main()
