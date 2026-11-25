"""The studio profile's compaction cap (backend/setup/studio_profile.py ``refresh_compaction_cap``, run when the plugin
registers in the hermretro profile): set where the profile's raw config has none or an earlier release's, never over
the user's own value or an explicit null.

Run alone: python -m unittest tests.backend.setup.test_compaction_cap
"""

import json
import unittest

from backend.setup import studio_profile as sp
from tests.support import fake_profile_config, isolated_home


class CompactionCap(unittest.TestCase):
    def setUp(self):
        self.profile = isolated_home(self).base / "profiles" / sp.STUDIO_PROFILE
        self.profile.mkdir(parents=True)
        self.written = fake_profile_config(self)

    def read(self, home):
        return json.loads((home / "config.yaml").read_text())

    def refreshed(self, config) -> bool:
        (self.profile / "config.yaml").write_text(json.dumps(config))
        return sp.refresh_compaction_cap(self.profile)

    def test_a_missing_cap_or_an_earlier_releases_gets_this_ones(self):
        for config, expected in (
            ({}, {"compression": {"threshold_tokens": 300000}}),
            ({"compression": None}, {"compression": {"threshold_tokens": 300000}}),
            (
                {"model": {"provider": "x"}, "compression": {"threshold": 0.6, "threshold_tokens": 200000}},
                {"model": {"provider": "x"}, "compression": {"threshold": 0.6, "threshold_tokens": 300000}},
            ),
        ):
            with self.subTest(config=config):
                self.assertTrue(self.refreshed(config))
                self.assertEqual(self.read(self.profile), expected)
        self.assertEqual({key for key, _value in self.written}, {"compression.threshold_tokens"}, "only the one key")

    def test_the_users_own_cap_or_an_explicit_null_is_kept(self):
        for config in (
            {"compression": {"threshold_tokens": None}},
            {"compression": {"threshold_tokens": 250000}},
            {"compression": {"threshold_tokens": 300000}},
            {"compression": "off"},
        ):
            with self.subTest(config=config):
                self.assertFalse(self.refreshed(config))
        self.assertEqual(self.written, [], "nothing of the user's is rewritten")


if __name__ == "__main__":
    unittest.main()
