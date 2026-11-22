"""tools/release.py's version rules: which version comes next, which tag a candidate gets, and that the version pull
request changes only plugin.yaml's version line. (The steps that push and publish run only when the owner asks.)"""

import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("release", ROOT / "tools" / "release.py")
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)


class Versions(unittest.TestCase):
    def test_the_last_stable_release_ignores_candidates_and_other_tags(self):
        tags = ["v1.2.3", "v1.2.10", "v1.2.11-rc.1", "v1.3", "nightly", "v1.2.9"]
        self.assertEqual(release.last_stable(tags), "1.2.10", "compared as numbers, not text")
        self.assertIsNone(release.last_stable(["v1.2.11-rc.1"]))

    def test_the_next_version_is_a_patch(self):
        self.assertEqual(release.next_patch("1.2.9"), "1.2.10")
        with self.assertRaises(release.Stop):
            release.next_patch("1.2")

    def test_a_candidate_takes_the_next_number_for_its_version(self):
        tags = ["v1.2.4-rc.1", "v1.2.4-rc.2", "v1.2.5-rc.7", "v1.2.3"]
        self.assertEqual(release.next_rc(tags, "1.2.4"), "v1.2.4-rc.3")
        self.assertEqual(release.next_rc(tags, "1.2.6"), "v1.2.6-rc.1")
        self.assertEqual(release.last_rc(tags, "1.2.4"), "v1.2.4-rc.2")
        self.assertIsNone(release.last_rc(tags, "1.2.6"))

    def test_the_version_change_touches_only_the_version_line(self):
        manifest = "name: hermretro\nversion: 1.2.3  # the one version\ndescription: version: not this one\n"
        self.assertEqual(release.manifest_version(manifest), "1.2.3")
        changed = release.with_version(manifest, "1.2.4")
        self.assertEqual(changed, manifest.replace("1.2.3", "1.2.4"))
        self.assertRegex(release.manifest_version((ROOT / "plugin.yaml").read_text()), r"^\d+\.\d+\.\d+$")


class Resume(unittest.TestCase):
    """Running again after a step failed finishes the same release: the state comes from the remote and GitHub."""

    def run_release(self, *, tags, made, versions, rc=False, dev="d" * 40, main="m" * 40):
        commands = []

        def fake_run(*command, env=None):
            commands.append(command)
            if command[:2] == ("git", "rev-parse"):
                return dev if command[2].endswith("/dev") else main
            if command[:2] == ("git", "show"):
                return f"name: hermretro\nversion: {versions[command[2].split(':')[0]]}\n"
            if command[:2] == ("git", "merge-base"):
                return command[2]
            return "https://example.invalid/release" if command[:3] == ("gh", "release", "create") else ""

        with (
            mock.patch.object(release, "run", fake_run),
            mock.patch.object(release, "remote_tags", return_value=tags),
            mock.patch.object(release, "github_releases", return_value=made),
            mock.patch.object(release, "ci_state", return_value="success"),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(release.release(rc), 0)
        return commands

    def pushes(self, commands):
        return [command[-1] for command in commands if command[:2] == ("git", "push")]

    def test_a_pushed_tag_without_its_draft_gets_the_draft_and_nothing_else(self):
        commands = self.run_release(
            tags={"v1.2.3": "a" * 40, "v1.2.4": "m" * 40}, made={"v1.2.3": True}, versions={"d" * 40: "1.2.4"}
        )
        self.assertEqual(self.pushes(commands), [], "neither main nor the tag again")
        created = [command for command in commands if command[:3] == ("gh", "release", "create")]
        self.assertEqual(created[0][3], "v1.2.4")
        self.assertIn("v1.2.3", created[0], "notes from the last published release")

    def test_a_main_already_moved_is_the_release_commit_not_dev_s_newer_head(self):
        commands = self.run_release(
            tags={"v1.2.3": "a" * 40},
            made={"v1.2.3": True},
            versions={"d" * 40: "1.2.4", "m" * 40: "1.2.4"},
        )
        self.assertEqual(self.pushes(commands), ["refs/tags/v1.2.4"], "main stays; the tag goes on main's commit")
        self.assertIn(("git", "tag", "-f", "v1.2.4", "m" * 40), commands)

    def test_an_unpublished_candidate_is_finished_not_renumbered(self):
        commands = self.run_release(
            tags={"v1.2.3": "a" * 40, "v1.2.4-rc.1": "d" * 40},
            made={"v1.2.3": True},
            versions={"d" * 40: "1.2.4", "m" * 40: "1.2.3"},
            rc=True,
        )
        created = [command for command in commands if command[:3] == ("gh", "release", "create")]
        self.assertEqual(created[0][3], "v1.2.4-rc.1")
        self.assertIn("--prerelease", created[0])
        commands = self.run_release(
            tags={"v1.2.3": "a" * 40, "v1.2.4-rc.1": "d" * 40},
            made={"v1.2.3": True, "v1.2.4-rc.1": True},
            versions={"d" * 40: "1.2.4", "m" * 40: "1.2.3"},
            rc=True,
        )
        self.assertEqual(self.pushes(commands), ["refs/tags/v1.2.4-rc.2"], "a published candidate: the next number")


if __name__ == "__main__":
    unittest.main()
