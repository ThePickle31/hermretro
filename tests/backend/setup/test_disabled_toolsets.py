"""The studio profile's disabled toolsets (backend/setup/studio_profile.py ``refresh_disabled_toolsets``, run when the
plugin registers in the hermretro profile): the list the plugin gave the profile becomes this release's, once, never
the user's own. Also how the automatic config updates write (``_update_config``), and what Hermes leaves the profile.

Run alone: python -m unittest tests.backend.setup.test_disabled_toolsets
(HERMES_SOURCE=<a hermes-agent checkout> runs the Hermes toolset check too.)
"""

import importlib.util
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from backend.setup import studio_profile as sp
from tests.support import fake_profile_config, isolated_home

OLDER = ["tts", "connections", "computer_use", "cronjob"]


class DisabledToolsets(unittest.TestCase):
    def setUp(self):
        self.profile = isolated_home(self).base / "profiles" / sp.STUDIO_PROFILE
        self.profile.mkdir(parents=True)
        self.written = fake_profile_config(self)
        self.mark({"made_by": "hermretro", "from_profile": "default"})  # as a release before this one wrote it

    def mark(self, marker: dict) -> None:
        (self.profile / sp.MARKER).parent.mkdir(parents=True, exist_ok=True)
        (self.profile / sp.MARKER).write_text(json.dumps(marker))

    def marker(self) -> dict:
        return json.loads((self.profile / sp.MARKER).read_text())

    def config(self) -> dict:
        return json.loads((self.profile / "config.yaml").read_text())

    def refreshed(self, config) -> bool:
        (self.profile / "config.yaml").write_text(json.dumps(config))
        return sp.refresh_disabled_toolsets(self.profile)

    def test_an_earlier_releases_list_gets_this_ones_and_the_marker_records_it(self):
        # Hermes keeps what `config set` was given as its JSON text, or as a list.
        for older in (json.dumps(OLDER), OLDER, list(reversed(OLDER))):
            with self.subTest(older=older):
                self.mark({"made_by": "hermretro", "from_profile": "default"})
                self.assertTrue(self.refreshed({"agent": {"max_turns": 90, "disabled_toolsets": older}}))
                self.assertEqual(
                    self.config(), {"agent": {"max_turns": 90, "disabled_toolsets": list(sp.DISABLED_TOOLSETS)}}
                )
                self.assertEqual(
                    self.marker(),
                    {
                        "made_by": "hermretro",
                        "from_profile": "default",
                        "disabled_toolsets": list(sp.DISABLED_TOOLSETS),
                    },
                )
        self.assertEqual({key for key, _value in self.written}, {"agent.disabled_toolsets"}, "only the one key")
        self.assertIn("code_execution", sp.DISABLED_TOOLSETS)

    def test_it_runs_once_so_the_user_can_take_code_execution_off_again(self):
        self.assertTrue(self.refreshed({"agent": {"disabled_toolsets": OLDER}}))
        self.assertFalse(self.refreshed({"agent": {"disabled_toolsets": OLDER}}))
        self.assertEqual(self.config(), {"agent": {"disabled_toolsets": OLDER}})

    def test_a_profile_made_or_repaired_by_this_release_is_left_alone(self):
        self.mark({"made_by": "hermretro", "disabled_toolsets": list(sp.DISABLED_TOOLSETS)})
        self.assertFalse(self.refreshed({"agent": {"disabled_toolsets": OLDER}}))
        self.assertEqual(self.written, [])

    def test_the_list_the_marker_records_is_the_one_replaced(self):
        given = ["tts", "code_execution"]
        self.mark({"made_by": "hermretro", "disabled_toolsets": given})
        self.assertFalse(self.refreshed({"agent": {"disabled_toolsets": OLDER}}), "not what this profile was given")
        self.assertTrue(self.refreshed({"agent": {"disabled_toolsets": given}}))
        self.assertEqual(self.config(), {"agent": {"disabled_toolsets": list(sp.DISABLED_TOOLSETS)}})

    def test_a_profile_the_plugin_never_finished_is_left_alone(self):
        (self.profile / sp.MARKER).unlink()
        self.assertFalse(self.refreshed({"agent": {"disabled_toolsets": OLDER}}))
        self.assertEqual(self.written, [])

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
        self.assertNotIn("disabled_toolsets", self.marker())


class AutomaticUpdates(unittest.TestCase):
    """Both automatic updates (the compaction cap and the toolsets) write one key, never through a link and never
    over a change made while they decided."""

    REFRESHES = (
        (sp.refresh_compaction_cap, {"compression": {"threshold_tokens": 200000}}),
        (sp.refresh_disabled_toolsets, {"agent": {"disabled_toolsets": OLDER}}),
    )

    def setUp(self):
        self.base = isolated_home(self).base
        self.profile = self.base / "profiles" / sp.STUDIO_PROFILE
        (self.profile / sp.MARKER).parent.mkdir(parents=True)
        (self.profile / sp.MARKER).write_text(json.dumps({"made_by": "hermretro"}))
        self.written = fake_profile_config(self)

    def test_a_linked_config_is_never_written(self):
        # Hermes writes through a link: here it would change another profile's config.
        other = self.base / "profiles" / "work" / "config.yaml"
        other.parent.mkdir(parents=True)
        (self.profile / "config.yaml").symlink_to(other)
        for refresh, config in self.REFRESHES:
            with self.subTest(refresh=refresh.__name__):
                other.write_text(json.dumps(config))
                self.assertFalse(refresh(self.profile))
                self.assertEqual(json.loads(other.read_text()), config)
        self.assertEqual(self.written, [])

    def test_a_change_made_meanwhile_is_kept_and_left_for_the_next_time(self):
        config_file = self.profile / "config.yaml"
        for refresh, config in self.REFRESHES:
            with self.subTest(refresh=refresh.__name__):
                config_file.write_text(json.dumps(config))
                read = sp.hermes_api.read_profile_config

                def read_then_the_user_changes_it(home, read=read):
                    seen = read(home)
                    config_file.write_text(json.dumps({**seen, "model": {"default": "theirs"}}))
                    return seen

                with mock.patch.object(sp.hermes_api, "read_profile_config", side_effect=read_then_the_user_changes_it):
                    self.assertFalse(refresh(self.profile))
                self.assertEqual(json.loads(config_file.read_text()), {**config, "model": {"default": "theirs"}})
                self.assertTrue(refresh(self.profile), "the next registration writes it")


def hermes_toolsets():
    """Hermes's own toolsets.py (it imports nothing of Hermes) from HERMES_SOURCE, or None."""
    source = Path(os.environ.get("HERMES_SOURCE") or "/nonexistent") / "toolsets.py"
    if not source.is_file():
        return None
    spec = importlib.util.spec_from_file_location("hermes_toolsets", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(hermes_toolsets(), "HERMES_SOURCE names no hermes-agent checkout")
class WhatHermesLeaves(unittest.TestCase):
    """The tools Hermes selects for the studio profile's settings (model_tools._select_tool_names: every toolset but
    the session-platform ones, then each disabled toolset's tools subtracted)."""

    def test_only_execute_code_goes_and_the_terminal_stays(self):
        toolsets = hermes_toolsets()

        def tools(names) -> set[str]:
            return set().union(*(toolsets.resolve_toolset(name, include_registry=False) for name in names))

        everything = tools(
            name for name in toolsets.get_toolset_names() if name not in toolsets.TOOLSET_SESSION_PLATFORMS
        )
        for name in sp.DISABLED_TOOLSETS:
            self.assertTrue(toolsets.validate_toolset(name), f"Hermes has no toolset {name}")
            # A bundle or posture is subtracted only in part; these are plain toolsets, subtracted whole.
            self.assertFalse(name.startswith("hermes-") or toolsets.get_toolset(name).get("posture"), name)
        before = everything - tools(OLDER)
        after = everything - tools(sp.DISABLED_TOOLSETS)
        self.assertEqual(before - after, {"execute_code"})
        self.assertLessEqual({"terminal", "process_manage"}, after)


if __name__ == "__main__":
    unittest.main()
