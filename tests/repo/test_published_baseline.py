"""Exercise the manual Nightly baseline command with real release history and paginated metadata."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "ci" / "published_baseline.py"


def release(tag: str, *, draft: bool = False, prerelease: bool = False) -> dict:
    return {"tag_name": tag, "draft": draft, "prerelease": prerelease, "published_at": None if draft else "then"}


class PublishedBaseline(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git("init", "-q", "-b", "dev")
        self.earlier = self.tag_commit("v0.0.8")
        self.tag_commit("v0.0.9")
        self.tag_commit("v0.0.10")
        self.tag_commit("v0.0.11-rc.1")
        self.candidate = self.tag_commit("v0.0.11")
        self.git("tag", "v0.0.11-alias")
        self.tag_commit("v0.0.12")
        self.git("switch", "--detach", self.candidate)

    def git(self, *args: str) -> str:
        cmd = [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            *args,
        ]
        return subprocess.run(cmd, cwd=self.root, check=True, capture_output=True, text=True).stdout.strip()

    def tag_commit(self, tag: str) -> str:
        self.git("commit", "--quiet", "--allow-empty", "-m", tag)
        self.git("tag", "-a", tag, "-m", tag)
        return self.git("rev-parse", "HEAD")

    def select(self, data: object):
        return subprocess.run(
            [sys.executable, "-I", str(SCRIPT)], input=json.dumps(data), cwd=self.root, capture_output=True, text=True
        )

    def test_skips_the_candidate_newer_draft_prerelease_and_nonancestor(self):
        result = self.select(
            [
                [release("v0.0.12"), release("v0.0.11"), release("v0.0.11-rc.1", prerelease=True)],
                [release("v0.0.10", draft=True), release("v0.0.9", prerelease=True), release("v0.0.8")],
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), self.earlier)

    def test_without_a_valid_predecessor_it_prints_no_baseline_and_fails(self):
        result = self.select([[release("v0.0.12"), release("v0.0.11"), release("v0.0.10", draft=True)]])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("no earlier published stable release", result.stderr)

    def test_malformed_github_response_is_not_an_empty_release_list(self):
        result = self.select({"message": "Service unavailable"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("expected a paginated GitHub releases response", result.stderr)
