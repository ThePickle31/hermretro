"""CI's job `changes` (tools/ci/changes.py): which changes need the integration tier (the real-engine run) and
the update from dev. A change of only plugin.yaml's `version:` line needs no engine run on a
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
        self.assertEqual([line.split("=")[0] for line in lines], ["engine", "upgrade"], done.stdout)
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

    def test_the_version_line_alone_needs_neither_the_engine_run_nor_the_update_from_dev(self):
        said = self.decide(self.bumped())
        self.assertEqual(said, {"engine": "false", "upgrade": "false"})

    def test_a_missing_revision_fails_instead_of_deciding(self):
        command = [sys.executable, "-I", str(SCRIPT), self.base, "0" * 40]
        done = subprocess.run(command, cwd=self.repo, capture_output=True, text=True)
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "", "nothing for $GITHUB_OUTPUT")
        self.assertIn("FIX:", done.stderr)


if __name__ == "__main__":
    unittest.main()
