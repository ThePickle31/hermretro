"""tools/release.py's version rules: which version comes next, which tag a candidate gets, and that the version pull
request changes only plugin.yaml's version line. (The steps that push and publish run only when the owner asks.)"""

import importlib.util
import unittest
from pathlib import Path

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

    def test_the_version_change_touches_only_the_version_line(self):
        manifest = "name: hermretro\nversion: 1.2.3  # the one version\ndescription: version: not this one\n"
        self.assertEqual(release.manifest_version(manifest), "1.2.3")
        changed = release.with_version(manifest, "1.2.4")
        self.assertEqual(changed, manifest.replace("1.2.3", "1.2.4"))
        self.assertRegex(release.manifest_version((ROOT / "plugin.yaml").read_text()), r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
