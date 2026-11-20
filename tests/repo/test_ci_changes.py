"""CI's job `changes` (tools/ci/changes.py): which changes need the integration tier (the real-engine run). A change
of only plugin.yaml's `version:` line does not, on a pull request or a single-commit push; anything more does as
before. Run against a throwaway repository, as the workflow runs it (the script and its two revisions).
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
START = {"plugin.yaml": "name: hermretro\nversion: 0.0.1\nrequires_hermes: 0.23.1\n", "docs/guide.md": "# Guide\n"}


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

    def engine(self, files: dict, *flags: str) -> str:
        self.commit(files)
        command = [sys.executable, "-I", str(SCRIPT), *flags, self.base, "HEAD"]
        done = subprocess.run(command, cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.strip()

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


if __name__ == "__main__":
    unittest.main()
