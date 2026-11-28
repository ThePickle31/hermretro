"""tools/engine/bump.py: a branch's first change to the engine raises the version above the base's and starts the
changelog's list with it, a later one adds its line under the same heading, and package.json keeps its formatting."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "engine"))

import bump  # noqa: E402 - tools/engine/ goes on sys.path first

CHANGES = "# Changes\n\nWhat this is.\n\n## 2.0.2\n\n- `a.js`: one.\n\n## 2.0.1\n\n- `b.js`: two.\n"


class Version(unittest.TestCase):
    def test_the_first_change_on_a_branch_raises_the_patch_above_the_base(self):
        self.assertEqual(bump.next_version((2, 0, 2), (2, 0, 2)), (2, 0, 3))

    def test_a_branch_that_already_raised_it_keeps_its_version(self):
        self.assertEqual(bump.next_version((2, 0, 3), (2, 0, 2)), (2, 0, 3))
        self.assertEqual(bump.next_version((2, 1, 0), (2, 0, 9)), (2, 1, 0))

    def test_a_base_without_an_engine_has_no_version_to_raise(self):
        self.assertEqual(bump.next_version((2, 0, 0), None), (2, 0, 0))

    def test_package_json_keeps_its_formatting(self):
        package = '{\n  "name": "e",\n  "version": "2.0.2",\n  "deps": {"x": {"version": "1.0.0"}}\n}\n'
        self.assertEqual(bump.with_version(package, "2.0.3"), package.replace('"2.0.2"', '"2.0.3"'))

    def test_a_package_without_a_top_level_version_is_refused(self):
        with self.assertRaisesRegex(bump.Refused, "FIX: "):
            bump.with_version('{"deps": {"x": {"version": "1.0.0"}}}', "2.0.3")


class Changelog(unittest.TestCase):
    def test_a_new_version_starts_the_list(self):
        written = bump.with_line(CHANGES, "2.0.3", "`c.js`: three.")
        self.assertEqual(written, CHANGES.replace("## 2.0.2", "## 2.0.3\n\n- `c.js`: three.\n\n## 2.0.2"))

    def test_a_later_change_goes_last_under_the_same_heading(self):
        written = bump.with_line(CHANGES, "2.0.2", "`c.js`: three.")
        self.assertEqual(written, CHANGES.replace("- `a.js`: one.\n", "- `a.js`: one.\n- `c.js`: three.\n"))

    def test_the_only_version_gets_its_line_at_the_end(self):
        only = "# Changes\n\n## 2.0.0\n\n- the start\n"
        self.assertEqual(bump.with_line(only, "2.0.0", "more"), only + "- more\n")

    def test_a_long_line_wraps_at_the_changelogs_width_under_its_bullet(self):
        line = " ".join(["`engine/src/some-module.js`"] + ["word"] * 60)
        entry = bump.with_line(CHANGES, "2.0.3", line).split("## 2.0.3\n\n")[1].split("\n\n")[0].splitlines()
        self.assertTrue(entry[0].startswith("- `engine/src/some-module.js` word"))
        self.assertTrue(all(row.startswith("  ") for row in entry[1:]))
        self.assertTrue(all(len(row) <= bump.WIDTH for row in entry))
        self.assertEqual(" ".join(row.strip() for row in entry), "- " + line)

    def test_a_changelog_without_a_version_heading_is_refused(self):
        with self.assertRaisesRegex(bump.Refused, "FIX: "):
            bump.with_line("# Changes\n", "2.0.3", "x")


if __name__ == "__main__":
    unittest.main()
