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
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first

SCRIPT = ROOT / "tools" / "engine" / "version.py"
PINNED = ROOT / "engine" / "contract" / "tools.json"
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
            self.assertIsNone(paths.engine_version(unreadable))
            for text in ("{", '{"version": "2.0"}', '{"version": 2}', "[]"):
                unreadable.write_text(text)
                self.assertIsNone(paths.engine_version(unreadable), text)

    def test_an_engine_without_a_version_does_not_verify(self):
        # Even when its manifest matches: a null or two-number version is no version at all.
        for version in (None, "2.0"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as folder:
                root, manifest = Path(folder) / "engine", Path(folder) / "manifest.json"
                (root / "scripts").mkdir(parents=True)
                (root / "scripts" / "start-mcp.mjs").write_text("// the launcher\n")
                (root / "package.json").write_text(json.dumps({"name": "hermretro-engine", "version": version}))
                entries = [
                    {"path": rel, "sha256": paths._file_sha256(root / rel)}
                    for rel in ("package.json", "scripts/start-mcp.mjs")
                ]
                manifest.write_text(json.dumps({"entries": entries}))
                with (
                    mock.patch.object(paths, "ENGINE_ROOT", root),
                    mock.patch.object(paths, "ENGINE_MANIFEST", manifest),
                ):
                    paths.verify_engine.cache_clear()
                    try:
                        check = paths.verify_engine()
                    finally:
                        paths.verify_engine.cache_clear()
                self.assertEqual((check["verified"], check["version"]), (False, None))
                self.assertEqual(check["detail"], "package.json has no x.y.z version")

    def test_the_contract_check_needs_the_live_version_to_be_the_package_version(self):
        sys.path.insert(0, str(ROOT / "tools" / "engine"))
        import reconcile_schemas  # tools/engine goes on sys.path first

        pinned = {"initialize": {"serverInfo": {"name": "hermretro-engine", "title": "hermretro engine"}}, "tools": []}
        for live_version, package_version, passed in (
            ("2.0.0", "2.0.0", True),
            ("2.0.0", "2.0.1", False),
            (None, None, False),
        ):
            with self.subTest(live=live_version, package=package_version):
                server = {**pinned["initialize"]["serverInfo"], "version": live_version}
                live = {"initialize": {"serverInfo": server}, "tools": [], "pages": 1, "ready_seconds": 0.1}
                report = reconcile_schemas.compare(pinned, {**live, "package_version": package_version}, PINNED)
                self.assertEqual(report["passed"], passed)
                self.assertNotIn("version", report["live_server_info"], "a bump changes no recorded report")


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
            (self.repo / name).write_text(text, encoding="utf-8", errors="surrogateescape")  # \udcff: byte 0xff
        if files:  # only these: an entry staged in the index directly stays as it is
            self.git("add", "--", *files)
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

    def test_a_file_in_place_of_the_engine_gets_its_fix(self):
        self.git("rm", "--quiet", "-r", "engine")
        self.assertIn("is gone", self.assert_fails({"engine": "not a folder\n"}))

    def test_a_file_name_that_is_not_utf8_gets_its_fix(self):
        # Staged in git's index directly: macOS's file system refuses such a name for a file.
        git = ["git", *ISOLATED]
        written = subprocess.run(
            [*git, "hash-object", "-w", "--stdin"], cwd=self.repo, input=b"export {};\n", capture_output=True
        )
        self.assertEqual(written.returncode, 0, written.stderr)
        entry = f"100644,{written.stdout.decode().strip()},".encode() + b"engine/src/\xff.js"
        staged = subprocess.run(
            [*git, "update-index", "--add", "--cacheinfo", entry], cwd=self.repo, capture_output=True
        )
        self.assertEqual(staged.returncode, 0, staged.stderr)
        self.assertIn("is still 2.0.0", self.assert_fails({}))

    def test_a_lower_version_fails(self):
        said = self.assert_fails({"engine/package.json": package("1.9.9")})
        self.assertIn("went down from 2.0.0 to 1.9.9", said)

    def test_a_missing_or_unreadable_package_fails(self):
        cases = {
            "deleted": ({}, None, "is gone"),
            "moved": ({}, {"engine/package.json": "engine/scripts/package.json"}, "is gone"),
            "not JSON": ({"engine/package.json": "{"}, None, "holds no x.y.z version"),
            "an array": ({"engine/package.json": "[]\n"}, None, "holds no x.y.z version"),
            "UTF-16": (
                {"engine/package.json": "\udcff\udcfe" + package("2.0.1").encode("utf-16-le").decode("latin-1")},
                None,
                "holds no x.y.z version",
            ),
            "not UTF-8": (
                {"engine/package.json": '{"version": "2.0.1", "x": "\udcff"}'},
                None,
                "holds no x.y.z version",
            ),
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
