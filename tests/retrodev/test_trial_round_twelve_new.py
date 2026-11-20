"""Friction the twelfth round of fresh-agent trials found in `new`: listener's --dry-run diff showed the text before
ruff formatted it; its next steps asked to isolate tests that already were; new's checks blamed new for a file it
never wrote; the listener docstring copied a long EVENTS description onto one line, and its test passed strings for
every key whatever the type; nothing said every place an event's payload is spelled out. Each test failed before its
fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_twelve_new
"""

import io
import re

from retrodev import config, output, scaffold_checks

from tests.retrodev.fixture import git, parallel, retrodev_docs, write
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase

load_tests = parallel
LINE_LENGTH = 120  # tools/py/ruff.toml

# A library front door with an event whose keys hint their types, and one whose keys make a long signature.
DOOR = '''"""The games library (a probe of its front door's shape)."""

__all__ = []

EVENTS = {
    "library.rdprobe_typed": (
        "a probe happened, described at length so that the copied description runs well past one line of the "
        "listener's docstring; count=<how many, int>, title=<the game's title, str>, root=<the project folder, "
        "pathlib.Path>, fresh=<whether it is new, bool>, other=<id>"
    ),
    "library.rdprobe_wide": (
        "a wide one; the_first_rather_long_key_name=<a, str>, the_second_rather_long_key_name=<b, str>, "
        "the_third_rather_long_key_name=<c, str>"
    ),
}
'''
EMITTING = '''"""Tests that emit library.rdprobe_typed (a probe)."""

import unittest

from backend.system import events
from tests.support import isolated_home


class Isolated(unittest.TestCase):
    def setUp(self):
        isolated_home(self)

    def test_emits(self):
        events.emit("library.rdprobe_typed", count=1)


class InheritsIsolation(Isolated):
    def test_emits_too(self):
        events.emit("library.rdprobe_typed", count=2)


class Bare(unittest.TestCase):
    def test_emits(self):
        events.emit("library.rdprobe_typed", count=3)


class Unrelated(unittest.TestCase):
    def test_other(self):
        self.assertTrue(True)
'''
LISTENERS = "backend/history/listeners.py"


def joined(out) -> str:
    return " ".join(out["next"])


class Listener(ScaffoldCase):
    def setUp(self):
        super().setUp()
        write(self.tree, "backend/library/__init__.py", DOOR)
        write(self.tree, "tests/backend/library/test_rdprobe_emits.py", EMITTING)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Probe events")

    def with_ruff(self) -> None:
        ruff = ROOT / ".dev" / "py"
        if not (ruff / "bin" / "ruff").is_file():
            self.skipTest("the pinned ruff is not set up here (python tools/py/setup.py)")
        (self.tree / ".dev").mkdir(exist_ok=True)
        (self.tree / ".dev" / "py").symlink_to(ruff)
        write(self.tree, "tools/py/ruff.toml", (ROOT / "tools/py/ruff.toml").read_text())

    def test_the_dry_run_diff_is_the_ruff_formatted_text_the_write_produces(self):
        self.with_ruff()
        diff = self.new("listener", "history", "library.rdprobe_wide", "--dry-run")["diff"]
        part = diff[diff.index(f"+++ b/{LISTENERS}") :].split("\n--- ", 1)[0]
        shown = "".join(line[1:] + "\n" for line in part.splitlines()[2:] if line.startswith("+"))
        self.new("listener", "history", "library.rdprobe_wide")
        written = self.read(LISTENERS)
        self.assertIn("def on_library_rdprobe_wide(\n", written, "ruff wrapped the long signature")
        self.assertEqual(shown, written)

    def test_the_next_steps_say_which_emitting_tests_are_already_isolated(self):
        steps = joined(self.new("listener", "history", "library.rdprobe_typed"))
        test = "tests/backend/library/test_rdprobe_emits.py"
        self.assertIn(
            f"give each isolated_home(self) (tests/support.py) in setUp, so it never touches the real home: "
            f"{test}::Bare; already isolated: {test}::Isolated, {test}::InheritsIsolation",
            steps,
        )
        self.assertNotIn("Unrelated", steps)

    def test_the_docstring_wraps_within_120_characters_and_keeps_the_placeholder_whole(self):
        self.new("listener", "history", "library.rdprobe_typed")
        text = self.read(LISTENERS)
        long = [line for line in text.splitlines() if len(line) > LINE_LENGTH]
        self.assertEqual(long, [])
        self.assertIn("say what this listener does", text)
        self.assertIn("pathlib.Path>, fresh=<whether it is new, bool>", " ".join(text.split()))

    def test_the_test_s_sample_values_follow_the_type_hints(self):
        self.new("listener", "history", "library.rdprobe_typed")
        test = self.read("tests/backend/history/test_listener_on_library_rdprobe_typed.py")
        self.assertIn(
            'on_library_rdprobe_typed(count=1, title="probe", root=Path("/games/probe"), fresh=True, '
            'other="sample other")',
            test,
        )
        self.assertIn("from pathlib import Path", test)

    def test_the_next_steps_point_to_changing_an_event_s_payload(self):
        steps = joined(self.new("listener", "history", "library.rdprobe_typed"))
        self.assertIn(
            "when library.rdprobe_typed's payload changes: tools/retrodev/REFERENCE.md \"Changing an event's "
            'payload" lists every place, this listener among them',
            steps,
        )
        event = joined(self.new("event", "history", "rdprobe_moved", "--payload", "game=<id, str>"))
        self.assertIn("tools/retrodev/REFERENCE.md \"Changing an event's payload\" lists every place", event)
        self.assertIn("grep -rln 'history.rdprobe_moved' tests/backend/history", event)
        reference = retrodev_docs("REFERENCE.md")
        for place in (
            "its function in `backend/<feature>/emits.py`",
            "every caller of that function, which passes the keys (`grep -rn '<name>(' backend/<feature>`)",
            "its `EVENTS` entry in `backend/<feature>/__init__.py`",
            "its row in `docs/dev/CONTRACT.md`",
            "`tests/backend/<feature>/test_event_<name>.py`",
            "the emitter's own tests that assert the payload (`grep -rln '<feature>.<name>' tests/backend/<feature>`)",
        ):
            self.assertIn(place, reference)


# A stand-in check.py whose lint, like ruff's, names each Python file not in its format (here: holding '  =  ').
FORMAT_CHECK = '''import sys
from pathlib import Path
code = 0
for name in sys.argv[1:]:
    bad = sorted(str(p) for p in Path("backend").rglob("*.py") if "  =  " in p.read_text())
    if name == "lint" and bad:
        print(f" FAILED  lint         0.2 s  {len(bad)} Python files are not in ruff's format:")
        for path in bad:
            print("         " + path)
        print("         FIX: python tools/check.py fix")
        code = 1
    else:
        print(f"{'ok':>7}  {name:<10} {0.1:5.1f} s  fine")
sys.exit(code)
'''


class PreExisting(ScaffoldCase):
    def test_a_failure_in_a_file_new_did_not_write_is_reported_as_pre_existing_and_new_keeps_its_scaffold(self):
        write(self.tree, "tools/check.py", FORMAT_CHECK)
        write(self.tree, "backend/history/untidy.py", "x  =  1\n")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "An unformatted file")
        code, out = self.run_cli("new", "rpc", "history", "rdprobe_pre", cwd=self.tree)
        self.assertEqual(code, 0, out)
        self.assertIn("pre-existing on this tree (not from new): backend/history/untidy.py", out)
        self.assertIn("new's own files pass; the scaffold stays", out)
        self.assertTrue((self.tree / "tests/backend/history/test_rpc_rdprobe_pre.py").is_file())

    def test_a_failure_naming_a_file_new_wrote_is_still_new_s(self):
        ctx = config.Context.make(self.tree, output.Out(stream=io.StringIO()))
        write(self.tree, "backend/history/untidy.py", "x  =  1\n")
        rows = [
            {"name": "lint", "state": "FAILED", "detail": "2 files", "more": ["backend/history/rpcs.py"]},
            {"name": "unit", "state": "FAILED", "detail": "FAILED (failures=1)", "more": []},
            {"name": "page", "state": "ok", "detail": "fine", "more": []},
        ]
        self.assertEqual(scaffold_checks.blame(ctx, rows, {"backend/history/rpcs.py"}), (["lint", "unit"], []))
        page = {"name": "page", "state": "FAILED", "detail": "1 failed", "more": ["tests/page/registry.test.mjs"]}
        write(self.tree, "tests/page/registry.test.mjs", "// a test new's code may break\n")
        self.assertEqual(scaffold_checks.blame(ctx, [page], set()), (["page"], []), "a test failure is new's")
        rows[0]["more"] = ["backend/history/untidy.py", "FIX: python tools/check.py fix"]
        self.assertEqual(
            scaffold_checks.blame(ctx, rows[:1], {"backend/history/rpcs.py"}), ([], ["backend/history/untidy.py"])
        )
        self.assertTrue(re.search(r"pre-existing on this tree", retrodev_docs("REFERENCE.md")))

    def test_a_check_skipped_beside_a_pre_existing_lint_failure_keeps_new_failing(self):  # review 1, 0
        # No Node: bundle and page print skipped rows, as check.py does without its tool; lint fails only on a file
        # new did not write. Neither page check proved anything, so new's run is no pass.
        no_node = FORMAT_CHECK.replace(
            "    else:\n",
            "    elif name in ('bundle', 'page'):\n"
            "        print(f\"{'skipped':>7}  {name:<10} {0.0:5.1f} s  node is not installed\")\n"
            "    else:\n",
        )
        write(self.tree, "tools/check.py", no_node)
        write(self.tree, "backend/history/untidy.py", "x  =  1\n")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "An unformatted file")
        code, out = self.run_cli("new", "page", "rdprobe", "--no-build", cwd=self.tree)
        self.assertEqual(code, 1, out)
        self.assertIn("pre-existing on this tree (not from new): backend/history/untidy.py", out)
        self.assertIn("not run, so new's files are not proven: bundle, page", out)
        self.assertNotIn("new's own files pass", out)
        ctx = config.Context.make(self.tree, output.Out(stream=io.StringIO()))
        ok = [{"name": "lint", "state": "FAILED"}, {"name": "bundle", "state": "ok"}, {"name": "page", "state": "ok"}]
        self.assertEqual(scaffold_checks.unproven(ctx, ok, ["lint", "bundle", "page"]), [])
        self.assertEqual(scaffold_checks.unproven(ctx, ok[:2], ["lint", "bundle", "page"]), ["page"], "no row")
