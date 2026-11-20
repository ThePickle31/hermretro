"""check's triggers for a version-only branch: plugin.yaml's `version:` line alone calls for the clean install but
not the real-engine run (as CI's tools/ci/changes.py decides); anything more, in plugin.yaml or elsewhere, still does.

Run alone: python -m unittest tests.retrodev.test_version_triggers
"""

import io
import unittest

from retrodev import checks_triggers, config, output

from tests.retrodev.fixture import RepoCase, parallel, write

load_tests = parallel


class Triggers(RepoCase):
    def triggered(self, files: dict, commit: bool = True) -> dict:
        self.trees = getattr(self, "trees", 0) + 1
        tree = self.worktree(f"chore/bump-{self.trees}")
        for name, text in files.items():
            if commit:
                self.commit(tree, name, text)
            else:
                write(tree, name, text)
        return checks_triggers.triggered(config.Context.make(tree, output.Out(stream=io.StringIO())))

    def test_the_version_line_alone_adds_the_clean_install_but_not_acceptance(self):
        for commit in (True, False):  # committed, or still in the working tree
            with self.subTest(commit=commit):
                found = self.triggered({"plugin.yaml": "version: 0.0.2\n"}, commit)
                self.assertIn("clean_install", found)
                self.assertNotIn("acceptance", found)

    def test_the_version_line_and_anything_more_still_adds_acceptance(self):
        cases = {
            "another plugin.yaml line": {"plugin.yaml": "version: 0.0.2\nname: other\n"},
            "another file": {"plugin.yaml": "version: 0.0.2\n", "docs/extra.md": "# Extra\n"},
            "plugin.yaml without its version line": {"plugin.yaml": "name: other\n"},
        }
        for name, files in cases.items():
            with self.subTest(name):
                found = self.triggered(files)
                self.assertEqual(found.get("acceptance"), "changed plugin.yaml", found)
                self.assertIn("clean_install", found)


class Diff(unittest.TestCase):
    def test_only_one_version_line_out_and_one_in_counts(self):
        bump = "--- a/plugin.yaml\n+++ b/plugin.yaml\n@@ -1 +1 @@\n-version: 0.0.1\n+version: 0.0.2\n"
        self.assertTrue(checks_triggers.only_version_line(bump))
        self.assertTrue(checks_triggers.only_version_line(bump.replace("+version: 0.0.2", '+version: "0.0.2" # x')))
        for diff in (
            bump + "@@ -5,0 +6 @@\n+name: other\n",  # one line more
            bump.replace("+version: 0.0.2", "+name: 0.0.2"),  # the version line replaced by another
            "--- a/plugin.yaml\n+++ b/plugin.yaml\n@@ -1,0 +2 @@\n+version: 0.0.2\n",  # a second version line
            "",  # no change at all (a mode change, say)
        ):
            self.assertFalse(checks_triggers.only_version_line(diff), diff)
