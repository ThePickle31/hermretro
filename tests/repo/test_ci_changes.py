"""CI's job `changes` (tools/ci/changes.py): which changes need the integration tier (the real-engine run), the
nested scaffold run and the update from dev. A change of only plugin.yaml's `version:` line needs no engine run on a
pull request or a single-commit push; anything more does as before. Run against a throwaway repository, as the
workflow runs it (the script and its two revisions).
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "ci" / "changes.py"
sys.path.insert(0, str(SCRIPT.parent))

import changes  # noqa: E402 - tools/ci goes on sys.path first

# A throwaway repository: no identity, signing or hooks of whoever runs the tests.
ISOLATED = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
START = {
    "plugin.yaml": "name: hermretro\nversion: 0.0.1\nrequires_hermes: 0.23.1\n",
    "docs/guide.md": "# Guide\n",
    "page/pages/games/view.js": "export const A = 1\n",
    "tools/retrodev/notes.txt": "kept\n",
}


class Changes(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        self.git("init", "--quiet")
        self.commit(START)
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args: str) -> str:
        done = subprocess.run(["git", *ISOLATED, *args], cwd=self.repo, capture_output=True, text=True)
        if done.returncode:
            raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
        return done.stdout

    def commit(self, files: dict) -> None:
        for name, text in files.items():
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text(text)
        self.git("add", "-A")
        self.git("commit", "--quiet", "-m", "change")

    def decide(self, files: dict, *flags: str, moves: dict | None = None) -> dict:
        for old, new in (moves or {}).items():
            (self.repo / new).parent.mkdir(parents=True, exist_ok=True)
            self.git("mv", old, new)
        self.commit(files)
        command = [sys.executable, "-I", str(SCRIPT), *flags, self.base, "HEAD"]
        done = subprocess.run(command, cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.splitlines()
        self.assertEqual([line.split("=")[0] for line in lines], ["engine", "scaffold", "upgrade"], done.stdout)
        return {key: value for key, value in (line.split("=", 1) for line in lines)}

    def engine(self, files: dict, *flags: str) -> str:
        return "engine=" + self.decide(files, *flags)["engine"]

    def bumped(self, text: str = "") -> dict:
        return {"plugin.yaml": START["plugin.yaml"].replace("0.0.1", "0.0.2") + text}

    def test_the_version_line_alone_skips_the_engine_run_on_a_pull_request_and_a_push(self):
        for flags in ((), ("--push",)):
            with self.subTest(flags=flags):
                self.setUp()
                self.assertEqual(self.engine(self.bumped(), *flags), "engine=false")

    def test_the_version_line_and_anything_more_needs_it(self):
        cases = {
            "another plugin.yaml line": self.bumped("license: MIT\n"),
            "another file": {**self.bumped(), "docs/guide.md": "# Guide, longer\n"},
            "plugin.yaml without the version": {"plugin.yaml": START["plugin.yaml"] + "license: MIT\n"},
            "the backend": {"backend/library/core.py": "VALUE = 2\n"},
        }
        for name, files in cases.items():
            for flags in ((), ("--push",)):
                with self.subTest(name, flags=flags):
                    self.setUp()
                    self.assertEqual(self.engine(files, *flags), "engine=true")

    def test_paths_outside_the_engine_s_reach_skip_it_on_a_pull_request_but_never_on_a_push(self):
        self.assertEqual(self.engine({"docs/guide.md": "# Guide, longer\n"}), "engine=false")
        self.setUp()
        self.assertEqual(self.engine({"docs/guide.md": "# Guide, longer\n"}, "--push"), "engine=true")

    def test_only_one_version_line_out_and_one_in_counts(self):
        bump = "--- a/plugin.yaml\n+++ b/plugin.yaml\n@@ -2 +2 @@\n-version: 0.0.1\n+version: 0.0.2\n"
        self.assertTrue(changes.only_version_line(bump))
        self.assertFalse(changes.only_version_line(bump + "@@ -5,0 +6 @@\n+license: MIT\n"))
        self.assertFalse(changes.only_version_line(bump.replace("+version: 0.0.2", "+license: MIT")))
        self.assertFalse(changes.only_version_line(""))

    def test_an_ordinary_change_gets_the_scaffold_smoke_and_no_update_from_dev(self):
        for files in (
            {"docs/guide.md": "# Guide, longer\n"},
            {"page/pages/games/view.js": "export const A = 2\n", "desktop/plugin.js": "export const A = 2\n"},
            {"tests/backend/library/test_core.py": "X = 1\n"},
        ):
            with self.subTest(files=list(files)):
                self.setUp()
                said = self.decide(files)
                self.assertEqual((said["scaffold"], said["upgrade"]), ("false", "false"), said)

    def test_scaffold_code_its_inputs_its_judges_and_the_grown_copy_s_tests_get_the_nested_run(self):
        for name in (
            "tools/retrodev/scaffold_page.py",
            "tools/retrodev/templates/rpc.py.tmpl",
            "tools/check.py",
            "tools/bundle/bundle.mjs",
            "tools/layout.toml",
            "tests/retrodev/test_scaffold_tree.py",
            "tests/repo/test_docs.py",
            "tests/support.py",
            "tests/page/harness.mjs",
            "backend/features.py",
            "page/pages/index.js",
            "page/pages/build/transcript/step-words.js",
            "docs/dev/CONTRACT.md",
            "tools/npm/package-lock.json",
            "tools/ci/changes.py",
            ".github/workflows/ci.yml",
        ):
            with self.subTest(name):
                self.setUp()
                self.assertEqual(self.decide({name: "changed\n"})["scaffold"], "true")

    def test_what_only_the_nested_steps_on_the_real_tree_read_gets_the_nested_run(self):  # review 1, 0 (#112)
        """The nested guard's steps on REAL pages and features (tests/retrodev/scaffold_steps.py) read and edit these
        (a page or tab descriptor's tabs, slots and contributes; the registry test's pins; a front door's EVENTS; the
        grown features' listeners and RPCs): a change there can break only the nested run."""
        for name in (
            "page/pages/games/index.js",
            "page/pages/setup/index.js",
            "page/pages/build/attract/index.js",
            "page/pages/games/README.md",
            "tests/page/registry.test.mjs",
            "tests/page/slots.test.mjs",
            "tests/page/page-games.test.mjs",
            "tests/page/page-setup.test.mjs",
            "backend/history/__init__.py",
            "backend/assets/listeners.py",
            "backend/library/rpcs.py",
            "backend/history/README.md",
        ):
            with self.subTest(name):
                self.assertTrue((ROOT / name).is_file(), f"{name}: name a real file the nested steps read")
                self.setUp()
                self.assertEqual(self.decide({name: "changed\n"})["scaffold"], "true")

    def test_wrapping_the_real_games_contribution_gets_the_nested_run(self):  # review 1, 0 (#112)
        """The review's case, as the real diff: Games' one-line contribution to emulator.barActions wrapped onto
        several lines (the nested step adding a second contribution to that slot reads the one-line form), and the
        registry test it is pinned by, each starting from the checkout's own file."""
        door = "page/pages/games/index.js"
        text = (ROOT / door).read_text()
        one_line = "    'emulator.barActions': [InstallButton]\n"
        self.assertIn(one_line, text, "the real contribution this case wraps")
        wrapped = text.replace(one_line, "    'emulator.barActions': [\n      InstallButton\n    ]\n")
        registry = "tests/page/registry.test.mjs"
        for name, before, after in ((door, text, wrapped), (registry, (ROOT / registry).read_text(), None)):
            with self.subTest(name):
                self.setUp()
                self.commit({name: before})
                self.base = self.git("rev-parse", "HEAD").strip()
                said = self.decide({name: after if after is not None else before + "// one more pin\n"})
                self.assertEqual(said["scaffold"], "true", said)

    def test_a_page_s_view_and_the_tests_new_never_reads_keep_the_smoke(self):
        for name in (
            "page/pages/games/view.js",
            "page/pages/games/game-card.js",
            "page/pages/build/attract/world.js",
            "tests/page/format.test.mjs",
            "tests/page/games-fixture.mjs",
            "backend/library/games.py",
        ):
            with self.subTest(name):
                self.setUp()
                self.assertEqual(self.decide({name: "changed\n"})["scaffold"], "false")

    def test_every_push_gets_the_nested_scaffold_run(self):
        for files in ({"docs/guide.md": "# Guide, longer\n"}, self.bumped()):
            with self.subTest(files=list(files)):
                self.setUp()
                self.assertEqual(self.decide(files, "--push")["scaffold"], "true")

    def test_what_an_install_runs_or_a_deletion_gets_the_update_from_dev(self):
        for name in (
            "__init__.py",
            "backend/broker/server.py",
            "page/app/update/flow.js",
            "profile/SOUL.md",
            "skills/game/SKILL.md",
            "tools/layout.toml",
            "tools/ci/update_check.py",
            "plugin.yaml",
        ):
            with self.subTest(name):
                self.setUp()
                self.assertEqual(self.decide({name: "changed\n"})["upgrade"], "true")
        self.setUp()
        self.git("rm", "--quiet", "docs/guide.md")
        self.assertEqual(self.decide({})["upgrade"], "true", "a deletion anywhere")
        self.setUp()
        self.assertEqual(self.decide({}, moves={"docs/guide.md": "docs/moved/guide.md"})["upgrade"], "true")

    def test_an_ignore_only_change_gets_the_update_from_dev(self):  # review 1, 1 (#112)
        """The update check judges each ignored leftover file by the ignore rules: a pull request that changes only
        them (the root's or a folder's) still updates from dev."""
        for name in (".gitignore", "player/.gitignore"):
            with self.subTest(name):
                self.setUp()
                said = self.decide({name: "deps/\n"})
                self.assertEqual(said["upgrade"], "true", said)

    def test_a_move_counts_its_old_path_too(self):
        said = self.decide({}, moves={"tools/retrodev/notes.txt": "docs/notes.txt"})
        self.assertEqual(said["scaffold"], "true", "moved out of tools/retrodev/: rename detection would hide it")

    def test_the_version_line_alone_needs_neither_the_nested_run_nor_the_update_from_dev(self):
        said = self.decide(self.bumped())
        self.assertEqual(said, {"engine": "false", "scaffold": "false", "upgrade": "false"})

    def test_a_missing_revision_fails_instead_of_deciding(self):
        command = [sys.executable, "-I", str(SCRIPT), self.base, "0" * 40]
        done = subprocess.run(command, cwd=self.repo, capture_output=True, text=True)
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "", "nothing for $GITHUB_OUTPUT")
        self.assertIn("FIX:", done.stderr)


class GuardRoundFive(unittest.TestCase):
    def test_ci_runs_the_scaffold_check_nested_when_job_changes_says_so_else_the_smoke(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        step = workflow[workflow.index("- name: python tools/check.py bundle lint page scaffold") :].split("\n\n")[0]
        self.assertIn("SCAFFOLD: ${{ needs.changes.outputs.scaffold }}", step)
        self.assertIn("true) export RD_SCAFFOLD_FULL=nested ;;", step)
        self.assertIn("false) export RD_SCAFFOLD_FULL=smoke ;;", step)
        self.assertIn("*) echo", step)  # no decision: the step fails
        self.assertIn("python tools/check.py bundle lint page scaffold --strict", step)


if __name__ == "__main__":
    unittest.main()
