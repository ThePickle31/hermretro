"""The trial rounds' regressions for this area (RoundNineNew, RoundTwelveNew, RoundTwenty), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_scaffold_new
"""

import re
from pathlib import Path
from tests.retrodev.fixture import git, parallel, retrodev_docs, write
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase
import io
from retrodev import config, output, scaffold_checks
import shlex
import shutil
from retrodev import scaffold_preview

load_tests = parallel

FORMAT_CHECK = """import sys
from pathlib import Path
gone = Path(".no-ruff").exists()
if sys.argv[1] == "lint-files":
    if gone:
        print("ruff is missing (ruff is not installed in .dev/py), so new's 2 Python files were not linted: setup")
        sys.exit(1)
    bad = [f for f in sys.argv[2:] if f.endswith(".py") and any(m in Path(f).read_text() for m in ("  =  ", "rdprobe_bad"))]
    print("\\n".join(bad) or "new's own files pass lint alone")
    sys.exit(1 if bad else 0)
code = 0
for name in sys.argv[1:]:
    bad = sorted(str(p) for p in Path(".").rglob("*.py") if p.parts[0] != "tools" and "  =  " in p.read_text())
    if name == "lint" and gone:
        print(f" FAILED  lint         0.2 s  ruff is not installed in .dev/py")
        print("         page/pages/build/index.js:1:1  x is not defined [no-undef]")
        code = 1
    elif name == "lint" and bad:
        print(f" FAILED  lint         0.2 s  {len(bad)} Python files are not in ruff's format:")
        for path in bad:
            print("         " + path)
        print("         FIX: python tools/check.py fix")
        code = 1
    else:
        print(f"{'ok':>7}  {name:<10} {0.1:5.1f} s  fine")
sys.exit(code)
"""

NEW_COMMAND = re.compile(r"(?:python tools/retrodev |(?<=\| ))new [a-z]+")


class DryRunAnywhere(ScaffoldCase):
    def test_a_dry_run_on_dev_lists_the_files_and_writes_nothing(self):
        git(self.tree, "switch", "-q", "-c", "master")  # a protected branch, holding the real files new reads
        state = Path(git(self.main, "rev-parse", "--git-common-dir").strip())
        state = (state if state.is_absolute() else self.main / state) / "retrodev"
        before = sorted((p.relative_to(state), p.read_bytes()) for p in state.rglob("*") if p.is_file())
        self.assertTrue(before, f"the branch record is in {state}")
        status = git(self.tree, "status", "--porcelain")
        done, out = self.run_cli("new", "feature", "rdprobe", "--dry-run", cwd=self.tree, as_json=True)
        self.assertEqual(done, 0, out)
        self.assertIn("backend/rdprobe/__init__.py", out["created"])
        self.assertEqual(git(self.tree, "status", "--porcelain"), status)
        after = sorted((p.relative_to(state), p.read_bytes()) for p in state.rglob("*") if p.is_file())
        self.assertEqual(after, before, "the state is untouched too")
        done, out = self.run_cli("new", "feature", "rdprobe", cwd=self.tree)
        self.assertEqual(done, 1, out)
        self.assertIn("only on a work branch", out)


class PreExisting(ScaffoldCase):
    def standin(self, path: str = "", text: str = "x  =  1\n", check: str = FORMAT_CHECK) -> None:
        write(self.tree, "tools/check.py", check)
        if path:
            write(self.tree, path, text)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "A stand-in check.py and an unrelated failure")

    def test_a_failure_in_a_file_new_did_not_write_is_reported_as_pre_existing_and_new_keeps_its_scaffold(self):
        self.standin("backend/history/untidy.py")
        code, out = self.run_cli("new", "rpc", "history", "rdprobe_pre", cwd=self.tree)
        self.assertEqual(code, 0, out)
        self.assertIn("new's own files pass lint alone", out)
        self.assertIn("pre-existing on this tree (not from new): the lint failure above", out)
        self.assertIn("the scaffold stays", out)
        self.assertIn("next: ", out)
        self.assertTrue((self.tree / "tests/backend/history/test_rpc_rdprobe_pre.py").is_file())
        self.assertTrue(re.search(r"pre-existing on this tree", retrodev_docs("REFERENCE.md")))

    def test_a_failure_in_the_root_init_is_pre_existing_too(self):  # review 2, 1
        self.standin("__init__.py")
        code, out = self.run_cli("new", "rpc", "history", "rdprobe_root", cwd=self.tree)
        self.assertEqual(code, 0, out)
        self.assertIn("pre-existing on this tree (not from new)", out)
        self.assertIn("next: ", out)

    def test_a_missing_ruff_beside_an_unrelated_page_error_keeps_new_failing(self):  # review 2, 0
        self.standin(".no-ruff", "")
        write(self.tree, "page/pages/build/index.js", "x\n" + (self.tree / "page/pages/build/index.js").read_text())
        code, out = self.run_cli("new", "rpc", "history", "rdprobe_noruff", cwd=self.tree)
        self.assertEqual(code, 1, out)
        self.assertIn("new's own lint: ruff is missing", out)
        self.assertNotIn("pre-existing on this tree", out)
        self.assertNotIn("the scaffold stays", out)

    def test_new_s_own_file_failing_lint_keeps_new_failing_beside_an_unrelated_one(self):
        self.standin("backend/history/untidy.py")
        code, out = self.run_cli("new", "rpc", "history", "rdprobe_bad", cwd=self.tree)
        self.assertEqual(code, 1, out)
        self.assertIn("new's own lint: backend/history/", out)
        self.assertNotIn("pre-existing on this tree", out)

    def test_a_unit_failure_beside_an_unrelated_lint_failure_is_new_s(self):
        unit_fails = FORMAT_CHECK.replace(
            "    else:\n",
            "    elif name == 'unit':\n"
            "        print(' FAILED  unit         0.1 s  FAILED (failures=1)')\n"
            "        code = 1\n"
            "    else:\n",
        )
        self.standin("backend/history/untidy.py", check=unit_fails)
        code, out = self.run_cli("new", "rpc", "history", "rdprobe_unit", cwd=self.tree)
        self.assertEqual(code, 1, out)
        self.assertNotIn("new's own files pass lint alone", out, "only a lint-only failure is linted again")
        self.assertNotIn("pre-existing on this tree", out)

    def test_a_check_skipped_beside_a_pre_existing_lint_failure_keeps_new_failing(self):  # review 1, 0
        # No Node: bundle and page print skipped rows, as check.py does without its tool; lint fails only on a file
        # new did not write. Neither page check proved anything, so new's run is no pass.
        no_node = FORMAT_CHECK.replace(
            "    else:\n",
            "    elif name in ('bundle', 'page'):\n"
            "        print(f\"{'skipped':>7}  {name:<10} {0.0:5.1f} s  node is not installed\")\n"
            "    else:\n",
        )
        self.standin("backend/history/untidy.py", check=no_node)
        code, out = self.run_cli("new", "page", "rdprobe", "--no-build", cwd=self.tree)
        self.assertEqual(code, 1, out)
        self.assertIn("not run, so new's files are not proven: bundle, page", out)
        self.assertNotIn("pre-existing on this tree", out)
        ctx = config.Context.make(self.tree, output.Out(stream=io.StringIO()))
        ok = [{"name": "lint", "state": "FAILED"}, {"name": "bundle", "state": "ok"}, {"name": "page", "state": "ok"}]
        self.assertEqual(scaffold_checks.unproven(ctx, ok, ["lint", "bundle", "page"]), [])
        self.assertEqual(scaffold_checks.unproven(ctx, ok[:2], ["lint", "bundle", "page"]), ["page"], "no row")


class Previews(ScaffoldCase):
    def test_a_text_dry_run_shows_the_next_steps_as_a_preview_and_writes_nothing(self):
        text = self.new("feature", "rdprobe_tw", "--dry-run", as_json=False)
        lines = text.splitlines()
        self.assertIn(scaffold_preview.HEAD, lines)
        self.assertIn(
            "would next: python tools/retrodev new rpc rdprobe_tw <name> --dry-run | new tool rdprobe_tw <name> "
            "--dry-run | new event rdprobe_tw <name> --dry-run",
            lines,
        )
        self.assertFalse([line for line in lines if line.startswith(("next: ", "then: "))], text)  # nothing to run
        self.assertEqual(lines[-1], "dry run: nothing was written")
        self.assertEqual(git(self.tree, "status", "--porcelain"), "")
        data = self.new("feature", "rdprobe_tw", "--dry-run")  # JSON: the same previewed steps
        self.assertEqual(
            ["would next: " + step for step in data["next"]], [x for x in lines if x.startswith("would next: ")]
        )
        real = self.new("feature", "rdprobe_tw")  # the real run's steps run as printed
        self.assertNotIn("--dry-run", " ".join(real["next"]))
        self.assertIn("python tools/retrodev new rpc rdprobe_tw <name> | new tool", " ".join(real["next"]))
        headers = [line for line in data["diff"].splitlines() if line.startswith(("--- ", "+++ "))]
        empty = [rel for rel in data["created"] if (self.tree / rel).stat().st_size == 0]  # no hunk to show
        planned = sorted(set(data["created"] + data["changed"]) - set(empty))
        self.assertEqual(len(headers), 2 * len(planned), "every edited file has its diff, changed files too")
        targets = sorted(header.removeprefix("+++ b/") for header in headers[1::2])
        self.assertEqual(targets, planned)
        for old, new in zip(headers[::2], headers[1::2], strict=True):
            rel = new.removeprefix("+++ b/")
            self.assertEqual(old, "--- /dev/null" if rel in data["created"] else f"--- a/{rel}", rel)
        self.assertTrue(all(line in lines for line in data["diff"].splitlines()), "the text run shows the same diff")
        edits = [
            line
            for line in data["diff"].splitlines()
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---")) and line[1:].strip()
        ]
        self.assertTrue(edits, "the diff shows the edits, not just the file names")

    def test_every_new_command_a_preview_prints_keeps_dry_run(self):
        shutil.copyfile(ROOT / "backend/library/__init__.py", self.tree / "backend/library/__init__.py")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "Library front door")
        runs = (
            ["feature", "rdprobe_tw"],
            ["page", "rdprobe-tw"],
            ["event", "history", "rdprobe_moved"],
            ["tab", "build", "rdprobe-extra"],  # build has no tabs: the --from-page step
        )
        said = []
        for argv in runs:
            steps = self.new(*argv, "--dry-run")["next"]
            for step in steps:
                for match in NEW_COMMAND.finditer(step):
                    rest = re.split(r"[|;()`]", step[match.end() :], maxsplit=1)[0]
                    self.assertTrue(rest.rstrip().endswith("--dry-run"), (argv, step))
            said.append(" ".join(steps))
        self.assertIn("`python tools/retrodev new listener <feature> history.rdprobe_moved --dry-run` writes", said[2])
        self.assertIn("`python tools/retrodev new tab build main --from-page --dry-run` makes its current", said[3])
        self.assertIn("python tools/retrodev new tab rdprobe-tw <tab> --dry-run | new slot", said[1])
        self.assertEqual(git(self.tree, "status", "--porcelain"), "")

    def test_previewed_leaves_prose_and_an_existing_dry_run_alone(self):
        step = "python tools/retrodev new tab x <tab> --dry-run | new slot x <name>"
        self.assertEqual(scaffold_preview.previewed(step), step + " --dry-run")
        self.assertEqual(scaffold_preview.previewed("new put it after the others"), "new put it after the others")

    def test_a_page_id_cannot_replace_the_dry_run_flag_in_the_first_tab_command(self):
        page = "probe--dry-run"
        self.new("page", page)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "A tabless probe page")
        output = self.new("tab", page, "extra", "--dry-run")
        assert isinstance(output, dict)
        argv = shlex.split(output["next"][0].split("`")[1])
        self.assertEqual(argv, ["python", "tools/retrodev", "new", "tab", page, "main", "--from-page", "--dry-run"])
        text = self.new(*argv[3:], as_json=False)
        self.assertIn("dry run: nothing was written", text)
        self.assertEqual(git(self.tree, "status", "--porcelain"), "")
