"""Feature flags: on from HERMRETRO_FLAGS, or from a flag's switch in the plugin settings."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.system import flags  # noqa: E402 - the repository root goes on sys.path first

MANIFEST = """name: hermretro
config_schema:
  hardware_enabled:
    type: bool
    default: false

# a comment between settings
  flag_level_editor:  # a note
    type: bool
    default: false
    label: Level editor
  # another
  flag_tabs:
    type: bool
provides_hooks:
  - flag_not_a_setting:
"""


def settings(**on):
    return lambda key, default=None: on.get(key, default)


class Flags(unittest.TestCase):
    def environment(self, value):
        clean = {key: item for key, item in os.environ.items() if key != flags.ENV}
        self.enterContext(
            mock.patch.dict(os.environ, {**clean, flags.ENV: value} if value is not None else clean, clear=True)
        )

    def test_the_environment_names_flags_separated_by_commas(self):
        for value, expected in ((None, set()), ("", set()), ("one", {"one"}), (" one , two,,", {"one", "two"})):
            with self.subTest(value=value):
                self.environment(value)
                self.assertEqual(flags.from_environment(), expected)

    def test_only_config_schema_keys_named_flag_are_switches(self):
        self.assertEqual(flags.switches(MANIFEST), {"level_editor", "tabs"})
        self.assertEqual(flags.switches("name: hermretro\n"), frozenset())

    def test_a_key_in_another_form_is_refused_not_skipped(self):
        for key in ('"flag_quoted":', "flag-dashed:", "'flag_single':"):
            with self.subTest(key=key), self.assertRaises(ValueError) as caught:
                flags.switches(f"config_schema:\n  {key}\n    type: bool\n")
            self.assertIn(key, str(caught.exception))

    def test_a_flag_is_on_from_the_environment_or_its_switch(self):
        self.environment("from_env")
        self.enterContext(mock.patch.object(flags, "SWITCHES", frozenset({"switched", "left_off"})))
        self.assertEqual(flags.enabled(settings(flag_switched=True)), ["from_env", "switched"])
        self.assertEqual(flags.enabled(settings()), ["from_env"])

    def test_the_shipped_manifest_reads(self):
        self.assertIsInstance(flags.SWITCHES, frozenset)


if __name__ == "__main__":
    unittest.main()
