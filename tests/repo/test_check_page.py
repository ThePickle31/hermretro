"""tools/check.py's page summary counts checks, not files, and its lint stops the run at once when its tools are
missing (before the slow checks start).

Run alone: python -m unittest tests.repo.test_check_page
"""

import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import check  # noqa: E402 - tools/check.py is imported from its own folder

# What `node --test` prints over two scenario files on tests/page/harness.mjs and one node:test file of 3 tests.
NODE_OUTPUT = """\
page-a.test.mjs: 60 passed, 0 failed
✔ tests/page/page-a.test.mjs (3261ms)
page-b.test.mjs: 34 passed, 0 failed
✔ tests/page/page-b.test.mjs (5652ms)
✔ one (1ms)
✔ two (1ms)
✔ three (1ms)
ℹ tests 5
ℹ pass 5
ℹ fail 0
"""


class PageSummary(unittest.TestCase):
    def test_the_summary_adds_up_each_scenario_files_checks_and_each_node_test(self):
        done = subprocess.CompletedProcess([], 0, NODE_OUTPUT, "")
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("page-a.test.mjs", "page-b.test.mjs", "sub/c.test.mjs", "harness.mjs"):
                (Path(tmp) / "tests/page" / name).parent.mkdir(parents=True, exist_ok=True)
                (Path(tmp) / "tests/page" / name).write_text("")
            with (
                mock.patch.object(check, "run", lambda *_a, **_k: done),
                mock.patch.object(check, "need", lambda tool: tool),
                mock.patch.object(check, "ROOT", Path(tmp)),
            ):
                said = check.check_page(mock.Mock(strict=False))
        self.assertEqual(said, "3 files, 97 checks passed, 0 failed")

    def test_a_failed_scenario_counts_its_passed_checks_and_one_failure(self):
        failed = NODE_OUTPUT.replace("34 passed, 0 failed", "12 passed, 1 failed").replace(
            "ℹ pass 5\nℹ fail 0", "ℹ pass 4\nℹ fail 1"
        )
        self.assertEqual(check.page_summary.summary(failed, 3), "3 files, 75 checks passed, 1 failed")

    def test_the_page_tests_glob_finds_the_files_node_runs(self):
        found = sorted(path.name for path in ROOT.glob(check.PAGE_TESTS))
        self.assertIn("registry.test.mjs", found)
        self.assertIn("page-games.test.mjs", found)
        self.assertNotIn("harness.mjs", found)


class LintToolsFirst(unittest.TestCase):
    def test_missing_lint_tools_fail_before_any_other_check_runs(self):
        started = []
        out = io.StringIO()
        with (
            mock.patch.object(check, "lint_tools_missing", lambda: ["ruff is not installed in .dev/py"]),
            mock.patch.dict(check.CHECKS, {name: lambda _a, n=name: started.append(n) or "ok" for name in check.ALL}),
            mock.patch.object(check.step_summary, "write", lambda rows: None),
            redirect_stdout(out),
        ):
            code = check.main([])
        self.assertEqual(code, 1)
        self.assertEqual(started, [], "no check may start while lint's tools are missing")
        self.assertIn("ruff is not installed in .dev/py", out.getvalue())
        self.assertIn("FIX: python tools/py/setup.py && npm ci --prefix tools/npm --ignore-scripts", out.getvalue())

    def test_checks_without_lint_do_not_need_its_tools(self):
        started = []
        with (
            mock.patch.object(check, "lint_tools_missing", lambda: ["ruff is not installed in .dev/py"]),
            mock.patch.dict(check.CHECKS, {"unit": lambda _a: started.append("unit") or "ok"}),
            mock.patch.object(check.step_summary, "write", lambda rows: None),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(check.main(["unit"]), 0)
        self.assertEqual(started, ["unit"])


class PageTestHeaders(unittest.TestCase):
    def test_every_page_test_names_the_command_that_runs_it_alone(self):
        # node runs each file as it stands; a scenario on harness.mjs also takes a node_modules folder (made absolute).
        wrong = []
        for path in sorted(ROOT.glob(check.PAGE_TESTS)):
            name = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            wanted = f"// Run alone: node {name}" + (
                " [path to a node_modules folder]" if "runScenario(" in text else ""
            )
            if not any(line.startswith(wanted) for line in text.splitlines()[:12]):
                wrong.append(f"{name}: wants a header line starting {wanted!r}")
        self.assertEqual(wrong, [], "FIX: write that line in the file's opening comment")


if __name__ == "__main__":
    unittest.main()
