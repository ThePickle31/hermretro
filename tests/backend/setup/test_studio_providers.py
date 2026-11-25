"""After setup: which profiles the background sync runs between, and the studio's own Claude sign-in."""

import json
import sys
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.setup import claude_login, studio_profile as sp, studio_providers  # noqa: E402 - repository root first
from tests.support import isolated_home  # noqa: E402 - the repository root goes on sys.path first


def read_config(home):
    try:
        return json.loads((home / "config.yaml").read_text())
    except FileNotFoundError:
        return {}


class StudioProviders(unittest.TestCase):
    def setUp(self):
        base = isolated_home(self).base
        self.source, self.studio = base / "profiles" / "work", base / "profiles" / sp.STUDIO_PROFILE
        self.source.mkdir(parents=True)
        (self.studio / "plugins" / "hermretro").mkdir(parents=True)
        (self.studio / "plugins" / "hermretro" / "plugin.yaml").write_text("name: hermretro\n")
        (self.studio / sp.MARKER).parent.mkdir(parents=True)
        (self.studio / sp.MARKER).write_text(json.dumps({"from_profile": "work"}))
        for target, name, effect in (
            (sp, "studio_dir", lambda: self.studio),
            (sp.hermes_api, "profile_dir", lambda name: self.source.parent / name),
        ):
            patch = unittest.mock.patch.object(target, name, side_effect=effect)
            patch.start()
            self.addCleanup(patch.stop)

    def test_either_profile_finds_the_pair_once_the_studio_is_finished(self):
        self.assertEqual(studio_providers.sync_pair(self.source), (self.source, self.studio))
        self.assertEqual(studio_providers.sync_pair(self.studio), (self.source, self.studio))
        (self.studio / sp.MARKER).unlink()
        self.assertIsNone(studio_providers.sync_pair(self.source))
        self.assertIsNone(studio_providers.sync_pair(self.studio))

    def test_another_profile_the_plugin_is_in_or_a_deleted_studio_is_never_synced(self):
        other = self.source.parent / "other"
        other.mkdir()
        self.assertIsNone(studio_providers.sync_pair(other))  # the studio was made from "work"
        with unittest.mock.patch.object(sp.hermes_api, "profile_is_deleted", return_value=True):
            self.assertIsNone(studio_providers.sync_pair(self.source))

    def test_a_provider_turned_on_after_setup_is_linked_and_on_before_its_route_is_copied(self):
        provider = self.source / "plugins" / "new-provider"
        provider.mkdir(parents=True)
        (provider / "plugin.yaml").write_text("name: new-provider\nkind: model-provider\n")
        (self.source / "config.yaml").write_text(json.dumps({"plugins": {"enabled": ["new-provider"]}}))
        commands = []
        with (
            unittest.mock.patch.object(sp.hermes_api, "read_profile_config", side_effect=read_config),
            unittest.mock.patch.object(sp, "run_hermes", side_effect=lambda _home, *args: commands.append(args)),
            unittest.mock.patch.object(studio_providers.provider_sync, "sync") as sync,
        ):
            studio_providers._sync(self.source, self.studio)
        self.assertEqual((self.studio / "plugins" / "new-provider").resolve(), provider.resolve())
        self.assertEqual(commands, [("plugins", "enable", "new-provider")])
        self.assertEqual(sync.call_args.kwargs["plugins"], ["new-provider"])

    def test_a_sync_already_running_is_not_started_twice(self):
        with unittest.mock.patch.object(studio_providers.provider_sync, "sync") as sync:
            with studio_providers.provider_sync.lock:
                studio_providers._sync(self.source, self.studio)
            sync.assert_not_called()

    def test_the_sign_in_selects_the_studios_own_folder(self):
        commands = []
        with (
            unittest.mock.patch.object(claude_login, "sign_in", return_value="/studio/claude") as sign_in,
            unittest.mock.patch.object(sp, "run_hermes", side_effect=lambda *args: commands.append(args)),
            unittest.mock.patch.object(claude_login, "state", return_value={"signed_in": True}),
        ):
            answer = studio_providers.sign_in_to_claude(self.source)
        sign_in.assert_called_once_with(self.studio)
        self.assertEqual(commands, [(self.studio, "config", "set", claude_login.SETTING, "/studio/claude")])
        self.assertEqual(answer, {"ok": True, "claude_login": {"signed_in": True}})


if __name__ == "__main__":
    unittest.main()
