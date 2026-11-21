"""tools/check.py's page summary counts checks, not files, and its lint stops the run at once when its tools are
missing (before the slow checks start).

Run alone: python -m unittest tests.repo.test_check_page
"""

import io
import shutil
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

# Real `node --test --test-reporter=<spec|tap> tests/page/harness-text.test.mjs tests/page/page-setup.test.mjs` output
# (Node 26), only the scenario's JSON dump left out: 5 node:test tests plus one scenario file of 51 checks.
SPEC_CAPTURED = """\
✔ the closest match is the longest leading part of a string or a RegExp the page has (1.255284ms)
✔ a failure shows about 300 characters around the closest match, not the whole page (0.908616ms)
✔ a passing assertion says nothing (0.115461ms)
✔ a relative node_modules argument is made absolute (the temp folder links to it); none means look it up (0.093666ms)
✔ pageTab looks only in a page's own tab bar (.cs-tabs), by its exact label (0.136933ms)
page-setup.test.mjs: 51 passed, 0 failed
✔ tests/page/page-setup.test.mjs (1243.582308ms)
ℹ tests 6
ℹ suites 0
ℹ pass 6
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1255.293394
"""
TAP_CAPTURED = """\
TAP version 13
# Subtest: the closest match is the longest leading part of a string or a RegExp the page has
ok 1 - the closest match is the longest leading part of a string or a RegExp the page has
# Subtest: a failure shows about 300 characters around the closest match, not the whole page
ok 2 - a failure shows about 300 characters around the closest match, not the whole page
# Subtest: a passing assertion says nothing
ok 3 - a passing assertion says nothing
# Subtest: a relative node_modules argument is made absolute (the temp folder links to it); none means look it up
ok 4 - a relative node_modules argument is made absolute (the temp folder links to it); none means look it up
# Subtest: pageTab looks only in a page's own tab bar (.cs-tabs), by its exact label
ok 5 - pageTab looks only in a page's own tab bar (.cs-tabs), by its exact label
# page-setup.test.mjs: 51 passed, 0 failed
# Subtest: tests/page/page-setup.test.mjs
ok 2 - tests/page/page-setup.test.mjs
1..6
# tests 6
# suites 0
# pass 6
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 1301.693963
"""
CAPTURED_CHECKS = "2 files, 56 checks passed, 0 failed"


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

    def test_real_spec_reporter_output_is_counted(self):
        self.assertEqual(check.page_summary.summary(SPEC_CAPTURED, 2), CAPTURED_CHECKS)

    def test_real_tap_reporter_output_is_counted(self):
        # node's default reporter when its output is captured (CI) is TAP, not spec.
        self.assertEqual(check.page_summary.summary(TAP_CAPTURED, 2), CAPTURED_CHECKS)

    def test_output_it_cannot_read_never_reads_as_zero_checks_passed(self):
        said = check.page_summary.summary("some reporter nobody parses\n", 7)
        self.assertEqual(said, "7 files passed (check count unavailable)")
        self.assertNotIn("0 checks passed", said)

    def test_the_page_command_names_the_spec_reporter(self):
        seen = []
        done = subprocess.CompletedProcess([], 0, SPEC_CAPTURED, "")
        with (
            mock.patch.object(check, "run", lambda cmd, *_a, **_k: seen.append(cmd) or done),
            mock.patch.object(check, "need", lambda tool: tool),
        ):
            check.check_page(mock.Mock(strict=False))
        self.assertEqual(seen[0][:3], ["node", "--test", "--test-reporter=spec"])

    @unittest.skipUnless(shutil.which("node"), "node is missing")
    def test_a_live_run_reads_the_same_with_either_reporter(self):
        # Exercise both actual Node reporters without depending on the size of a product scenario.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenario = root / "page-probe.test.mjs"
            scenario.write_text("console.log('page-probe.test.mjs: 3 passed, 0 failed')\n")
            ordinary = root / "ordinary.test.mjs"
            ordinary.write_text("import { test } from 'node:test'\ntest('ordinary check', () => {})\n")
            for reporter in ("spec", "tap"):
                with self.subTest(reporter=reporter):
                    result = subprocess.run(
                        [shutil.which("node"), "--test", f"--test-reporter={reporter}", scenario, ordinary],
                        cwd=root,
                        text=True,
                        capture_output=True,
                        timeout=30,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-2000:])
                    said = check.page_summary.summary(result.stdout + result.stderr, 2)
                    self.assertEqual(said, "2 files, 4 checks passed, 0 failed")

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
