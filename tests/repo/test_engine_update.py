"""tools/engine/update.py and report.py, on a small git repository standing in for hermretro."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "engine"))


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"engine_{name}", ROOT / "tools" / "engine" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


update, report = load("update"), load("report")
ENGINE = "engine/modretro-chromatic"
ARCHIVE = "third-party/chromatic-cli/notices.br"
IDENTITY = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}
SERVER = (
    "// dist/a.js\nvar one = 1;\nvar two = 2;\nvar three = 3;\nvar four = 4;\nvar five = 5;\n// dist/b.js\nvar b = 1;\n"
)


def files(folder: Path, contents: dict[str, str]) -> Path:
    for rel, text in contents.items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_text(text)
    return folder


class EngineUpdateTests(unittest.TestCase):
    def setUp(self):
        identity = mock.patch.dict(os.environ, IDENTITY)
        identity.start()
        self.addCleanup(identity.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "dev")
        # The first release, tagged the way update.py tags every later one (that one has a parent).
        first = self.release("1.0.0", {"dist/server.js": SERVER})
        index = {"GIT_INDEX_FILE": str(self.base / "index")}
        stage = self.base / "stage"
        shutil.copytree(first, stage / ENGINE, dirs_exist_ok=True)
        self.git(f"--work-tree={stage}", "add", "-A", env=index)
        commit = self.git("commit-tree", self.git("write-tree", env=index).strip(), stdin="1.0.0").strip()
        self.git("tag", "engine-upstream-1.0.0", commit)
        shutil.copytree(first, self.repo / ENGINE)
        files(
            self.repo,
            {
                "backend/system/paths.py": 'ENGINE_VERSION = "1.0.0"\n',
                "skills/setup/SKILL.md": "---\nname: setup\nversion: 1.0.0\n---\n",
                "THIRD_PARTY_NOTICES.md": "engine/pins/1.0.0/ and ModRetro's 1.0.0; CLI 11.0.0\n",
                "engine/pins/1.0.0/tools.json": "{}",
            },
        )
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "start")

    def git(self, *args, stdin=None, env=None) -> str:
        done = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            input=stdin,
            capture_output=True,
            text=True,
            env={**os.environ, **(env or {})},
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def release(self, version: str, contents: dict[str, str]) -> Path:
        folder = self.base / f"release-{version}"
        package = json.dumps({"name": "modretro-chromatic", "version": version})
        return files(folder, {"package.json": package, **contents})

    def ours(self, server: str) -> None:
        (self.repo / ENGINE / "dist/server.js").write_text(server)
        self.git("commit", "-q", "-am", "our change")

    def run_update(self, server: str) -> list[str]:
        release = self.release("1.1.0", {"dist/server.js": server, ARCHIVE: "packed again"})
        update.check_start(self.repo, "1.0.0", "1.1.0")
        tag = update.tag_release(self.repo, release, "1.0.0", "1.1.0")
        return update.merge(self.repo, "engine-upstream-1.0.0", tag)

    def test_the_release_is_tagged_without_left_out_files_on_the_old_release(self):
        self.run_update(SERVER)
        listed = self.git("ls-tree", "-r", "--name-only", "engine-upstream-1.1.0").split()
        self.assertEqual(listed, [f"{ENGINE}/dist/server.js", f"{ENGINE}/package.json"])
        parent = self.git("rev-parse", "engine-upstream-1.1.0^{commit}^").strip()
        self.assertEqual(parent, self.git("rev-parse", "engine-upstream-1.0.0^{commit}").strip())

    def test_our_change_and_theirs_both_land_when_they_do_not_overlap(self):
        self.ours(SERVER.replace("var one = 1;", "var one = 10;"))
        conflicts = self.run_update(SERVER.replace("var five = 5;", "var five = 50;"))
        self.assertEqual(conflicts, [])
        merged = (self.repo / ENGINE / "dist/server.js").read_text()
        self.assertIn("var one = 10;", merged)
        self.assertIn("var five = 50;", merged)
        self.assertIn('"1.1.0"', (self.repo / ENGINE / "package.json").read_text())

    def test_both_sides_changing_one_line_leaves_conflict_markers(self):
        self.ours(SERVER.replace("var three = 3;", "var three = 30;"))
        conflicts = self.run_update(SERVER.replace("var three = 3;", "var three = 300;"))
        self.assertEqual(conflicts, ["dist/server.js"])
        self.assertIn("<<<<<<<", (self.repo / ENGINE / "dist/server.js").read_text())

    def test_it_refuses_uncommitted_engine_changes_and_a_known_version(self):
        with self.assertRaisesRegex(update.UpdateError, "already 1.0.0"):
            update.check_start(self.repo, "1.0.0", "1.0.0")
        (self.repo / ENGINE / "dist/server.js").write_text("edited")
        with self.assertRaisesRegex(update.UpdateError, "uncommitted"):
            update.check_start(self.repo, "1.0.0", "1.1.0")

    def test_the_version_moves_everywhere_and_the_pins_move(self):
        release = self.release("1.1.0", {"dist/server.js": SERVER, ARCHIVE: "packed again"})
        folder = update.move_pins(self.repo, release, "1.0.0", "1.1.0")
        update.bump(self.repo, "1.0.0", "1.1.0")
        self.assertFalse((self.repo / "engine/pins/1.0.0").exists())
        entries = {e["path"] for e in json.loads((folder / "manifest.json").read_text())["entries"]}
        self.assertIn(ARCHIVE, entries)  # recorded from the release although the repository leaves it out
        self.assertIn('"1.1.0"', (self.repo / "backend/system/paths.py").read_text())
        self.assertIn("version: 1.1.0", (self.repo / "skills/setup/SKILL.md").read_text())
        notices = (self.repo / "THIRD_PARTY_NOTICES.md").read_text()
        self.assertEqual(notices, "engine/pins/1.1.0/ and ModRetro's 1.1.0; CLI 11.0.0\n")

    def test_the_report_names_changed_modules_and_our_overlap(self):
        self.ours(SERVER.replace("var one = 1;", "var one = 10;"))
        start = self.git("rev-parse", "HEAD").strip()
        conflicts = self.run_update(SERVER.replace("var b = 1;", "var b = 2;"))
        written = report.write(
            self.repo, self.base / "notes", "engine-upstream-1.0.0", "engine-upstream-1.1.0", start, conflicts, None
        )
        text = written.read_text()
        self.assertIn("**changed**: `dist/b.js`", text)
        self.assertIn("ModRetro also changed: dist/server.js", text)
        self.assertTrue((self.base / "notes/modules/dist_b.js.diff").is_file())


class BundleModuleTests(unittest.TestCase):
    def test_renumbered_names_alone_are_a_rename(self):
        old = "// dist/a.js\nvar process2 = 1;\n// node_modules/zod/index.js\nvar z = 1;\n"
        new = "// dist/a.js\nvar process3 = 1;\n// node_modules/zod/index.js\nvar z = 2;\n"
        self.assertEqual(
            report.compare_modules(old, new),
            {"added": [], "removed": [], "changed": ["node_modules/zod/index.js"], "renamed": ["dist/a.js"]},
        )

    def test_a_module_written_twice_keeps_both_parts(self):
        found = report.modules("head\n// dist/a.js\nx\n// dist/b.js\ny\n// dist/a.js\nz\n")
        self.assertEqual(found["dist/a.js"], "// dist/a.js\nx\n// dist/a.js\nz\n")
        self.assertEqual(found["(bundle header)"], "head\n")


if __name__ == "__main__":
    unittest.main()
