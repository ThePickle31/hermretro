"""plugin.yaml's `version:` line alone, as release run, the release guard and land's release-approval gate read a
diff (version_diff); anything more in plugin.yaml does not count.

Run alone: python -m unittest tests.retrodev.test_version_diff
"""

import unittest

from retrodev import version_diff


class Diff(unittest.TestCase):
    def test_only_one_version_line_out_and_one_in_counts(self):
        bump = "--- a/plugin.yaml\n+++ b/plugin.yaml\n@@ -1 +1 @@\n-version: 0.0.1\n+version: 0.0.2\n"
        self.assertTrue(version_diff.only_version_line(bump))
        self.assertTrue(version_diff.only_version_line(bump.replace("+version: 0.0.2", '+version: "0.0.2" # x')))
        for diff in (
            bump + "@@ -5,0 +6 @@\n+name: other\n",  # one line more
            bump.replace("+version: 0.0.2", "+name: 0.0.2"),  # the version line replaced by another
            "--- a/plugin.yaml\n+++ b/plugin.yaml\n@@ -1,0 +2 @@\n+version: 0.0.2\n",  # a second version line
            "",  # no change at all (a mode change, say)
        ):
            self.assertFalse(version_diff.only_version_line(diff), diff)
