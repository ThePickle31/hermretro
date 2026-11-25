"""The studio profile's disabled toolsets (backend/setup/studio_profile.py ``refresh_disabled_toolsets``, run when the
plugin registers in the hermretro profile): an earlier release's list becomes this one's, never the user's own.

Run alone: python -m unittest tests.backend.setup.test_disabled_toolsets
"""

import json
import unittest
from unittest import mock

from backend.setup import studio_profile as sp
from tests.support import isolated_home

OLDER = ["tts", "connections", "computer_use", "cronjob"]


class DisabledToolsets(unittest.TestCase):
    def setUp(self):
        self.profile = isolated_home(self).base / "profiles" / sp.STUDIO_PROFILE
        self.profile.mkdir(parents=True)
        self.written = []
        for name, effect in (("read_profile_config", self.read), ("write_profile_config", self.write)):
            patch = mock.patch.object(sp.hermes_api, name, side_effect=effect)
            patch.start()
            self.addCleanup(patch.stop)

    @staticmethod
    def read(home):
        """The tests' profiles write config.yaml as JSON (YAML reads it the same)."""
        return json.loads((home / "config.yaml").read_text())

    def write(self, home, config):
        self.written.append(config)
        (home / "config.yaml").write_text(json.dumps(config))

    def refreshed(self, config) -> bool:
        (self.profile / "config.yaml").write_text(json.dumps(config))
        return sp.refresh_disabled_toolsets(self.profile)

    def test_an_earlier_releases_list_gets_this_ones(self):
        # Hermes keeps what `config set` was given as its JSON text, or as a list.
        for older in (json.dumps(OLDER), OLDER, list(reversed(OLDER))):
            with self.subTest(older=older):
                self.assertTrue(self.refreshed({"agent": {"max_turns": 90, "disabled_toolsets": older}}))
                self.assertEqual(
                    self.read(self.profile),
                    {"agent": {"max_turns": 90, "disabled_toolsets": list(sp.DISABLED_TOOLSETS)}},
                )
        self.assertIn("code_execution", sp.DISABLED_TOOLSETS)

    def test_the_users_own_list_or_none_is_kept(self):
        for config in (
            {},
            {"agent": None},
            {"agent": {"max_turns": 90}},
            {"agent": {"disabled_toolsets": []}},
            {"agent": {"disabled_toolsets": [*OLDER, "browser"]}},
            {"agent": {"disabled_toolsets": OLDER[:3]}},
            {"agent": {"disabled_toolsets": list(sp.DISABLED_TOOLSETS)}},
            {"agent": {"disabled_toolsets": "tts"}},
        ):
            with self.subTest(config=config):
                self.assertFalse(self.refreshed(config))
        self.assertEqual(self.written, [], "nothing of the user's is rewritten")


if __name__ == "__main__":
    unittest.main()
