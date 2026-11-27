"""The engine's version: one home (engine/package.json), a heading for it in engine/CHANGES.md, and CI's job
`engine-version` (tools/engine/version.py), which fails a change to the engine that does not raise it. The script runs
against a throwaway repository, as the workflow runs it (the script and its two revisions)."""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first

SCRIPT = ROOT / "tools" / "engine" / "version.py"
# A throwaway repository: no identity, signing or hooks of whoever runs the tests.
ISOLATED = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]


def package(version: str) -> str:
    return json.dumps({"name": "hermretro-engine", "version": version}) + "\n"


START = {
    "engine/package.json": package("2.0.0"),
    "engine/src/entry.js": "export const A = 1;\n",
    "engine/CHANGES.md": "# Changes\n\n## 2.0.0\n\n- the start\n",
    "engine/contract/tools.json": "{}\n",
    "backend/core.py": "VALUE = 1\n",
}


class Headings(unittest.TestCase):
    def test_the_newest_heading_in_the_changelog_is_the_engine_version(self):
        text = (paths.ENGINE_ROOT / "CHANGES.md").read_text(encoding="utf-8")
        headings = re.findall(r"(?m)^## (.+)$", text)
        self.assertTrue(headings, "engine/CHANGES.md has no version heading")
        self.assertEqual(headings[0], paths.ENGINE_VERSION, "FIX: start engine/CHANGES.md's list with the version")
        for heading in headings:
            self.assertRegex(heading, r"^[0-9]+\.[0-9]+\.[0-9]+$", "a heading in engine/CHANGES.md is a version")
        versions = [tuple(map(int, heading.split("."))) for heading in headings]
        self.assertEqual(versions, sorted(set(versions), reverse=True), "each version once, newest first")

    def test_the_backend_reads_the_engine_package(self):
        self.assertEqual(paths.ENGINE_VERSION, json.loads((paths.ENGINE_ROOT / "package.json").read_text())["version"])
        with tempfile.TemporaryDirectory() as folder:
            unreadable = Path(folder) / "package.json"
            self.assertIsNone(paths._engine_version(unreadable))
            for text in ("{", '{"version": "2.0"}', '{"version": 2}', "[]"):
                unreadable.write_text(text)
                self.assertIsNone(paths._engine_version(unreadable), text)


class Bump(unittest.TestCase):
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

    def commit(self, files: dict, moves: dict | None = None) -> None:
        for old, new in (moves or {}).items():
            (self.repo / new).parent.mkdir(parents=True, exist_ok=True)
            self.git("mv", old, new)
        for name, text in files.items():
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text(text)
        self.git("add", "-A")
        self.git("commit", "--quiet", "--allow-empty", "-m", "change")

    def check(self, files: dict, moves: dict | None = None) -> subprocess.CompletedProcess:
        self.commit(files, moves)
        return subprocess.run(
            [sys.executable, "-I", str(SCRIPT), self.base, "HEAD"], cwd=self.repo, capture_output=True, text=True
        )

    def assert_passes(self, files: dict, moves: dict | None = None) -> None:
        done = self.check(files, moves)
        self.assertEqual(done.returncode, 0, done.stderr)

    def assert_fails(self, files: dict, moves: dict | None = None) -> str:
        done = self.check(files, moves)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertRegex(done.stderr.splitlines()[-1], r"^FIX: ")
        return done.stderr

    def test_a_change_to_the_engine_without_a_new_version_fails(self):
        cases = {
            "a module": ({"engine/src/entry.js": "export const A = 2;\n"}, None),
            "a new file": ({"engine/docs/guide.md": "# Guide\n"}, None),
            "a move": ({}, {"engine/src/entry.js": "engine/src/main.js"}),
            "only its changelog line with it": (
                {
                    "engine/src/entry.js": "export const A = 2;\n",
                    "engine/CHANGES.md": START["engine/CHANGES.md"] + "- x\n",
                },
                None,
            ),
        }
        for name, (files, moves) in cases.items():
            with self.subTest(name):
                self.setUp()
                said = self.assert_fails(files, moves)
                self.assertIn("is still 2.0.0", said)
                self.assertIn('"version" in engine/package.json to 2.0.1', said)

    def test_a_lower_version_fails(self):
        said = self.assert_fails({"engine/package.json": package("1.9.9")})
        self.assertIn("went down from 2.0.0 to 1.9.9", said)

    def test_a_missing_or_unreadable_package_fails(self):
        cases = {
            "deleted": ({}, None, "is gone"),
            "moved": ({}, {"engine/package.json": "engine/scripts/package.json"}, "is gone"),
            "not JSON": ({"engine/package.json": "{"}, None, "holds no x.y.z version"),
            "an array": ({"engine/package.json": "[]\n"}, None, "holds no x.y.z version"),
            "two numbers": ({"engine/package.json": package("2.1")}, None, "holds no x.y.z version"),
        }
        for name, (files, moves, said) in cases.items():
            with self.subTest(name):
                self.setUp()
                if name == "deleted":
                    self.git("rm", "--quiet", "engine/package.json")
                self.assertIn(said, self.assert_fails(files, moves))

    def test_a_change_with_a_new_version_passes(self):
        for version in ("2.0.1", "2.1.0", "3.0.0"):
            with self.subTest(version):
                self.setUp()
                self.assert_passes(
                    {"engine/package.json": package(version), "engine/src/entry.js": "export const A = 2;\n"}
                )

    def test_the_engine_record_and_other_files_need_no_new_version(self):
        cases = {
            "the changelog": {"engine/CHANGES.md": START["engine/CHANGES.md"] + "- a note\n"},
            "the contract": {"engine/contract/tools.json": '{"tools": []}\n'},
            "the backend": {"backend/core.py": "VALUE = 2\n"},
            "nothing": {},
        }
        for name, files in cases.items():
            with self.subTest(name):
                self.setUp()
                self.assert_passes(files)

    def test_a_record_name_deeper_in_the_engine_is_part_of_the_engine(self):
        self.assert_fails({"engine/docs/CHANGES.md": "# Docs\n", "engine/src/contract/x.js": "export {};\n"})

    def test_a_base_without_the_engine_needs_nothing(self):
        self.git("rm", "--quiet", "-r", "engine")
        self.git("commit", "--quiet", "-m", "no engine")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.assert_passes(START)


if __name__ == "__main__":
    unittest.main()
