"""The dedicated hermretro profile: what the page is told, and what finishing it does."""
import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.system import paths  # noqa: E402
from backend.setup import studio_profile as sp  # noqa: E402


class StudioProfile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / "profiles" / "work"            # where the user installed the plugin
        self.target = root / "profiles" / sp.STUDIO_PROFILE
        (self.home / "plugins" / "my-provider").mkdir(parents=True)
        (self.home / "plugins" / "my-provider" / "plugin.yaml").write_text("name: my-provider\nkind: model-provider\n")
        (self.home / "plugins" / "other").mkdir()
        (self.home / "plugins" / "other" / "plugin.yaml").write_text("name: other\nkind: tool\n")
        self.commands = []

    def tearDown(self):
        self.tmp.cleanup()

    def created(self, description=sp.DESCRIPTION):
        """What Hermes's profiles.create leaves behind."""
        self.target.mkdir(parents=True)
        (self.target / "profile.yaml").write_text(f"description: '{description}'\n")
        (self.target / "SOUL.md").write_text("default soul")

    def finish(self):
        return sp.finish(self.home, target=self.target, enabled=["my-provider", "other", "gone"],
                         run=lambda target, *args: self.commands.append((target, args)))

    def test_the_page_is_told_which_profile_answers_and_how_to_create_the_studio_one(self):
        told = sp.describe(self.home, self.target)
        self.assertEqual((told["name"], told["is_studio"]), ("work", False))
        self.assertEqual(told["studio"], {"name": "hermretro", "exists": False, "installed": False, "ours": False})
        self.assertEqual(told["create"], {"name": "hermretro", "description": sp.DESCRIPTION,
                                          "no_skills": True, "share_auth": True, "no_alias": True})
        self.assertTrue(sp.describe(self.target)["is_studio"])
        self.assertEqual(sp.profile_name(Path(self.tmp.name)), "default")

    def test_finishing_needs_the_profile_to_exist(self):
        with self.assertRaises(sp.StudioProfileError) as raised:
            self.finish()
        self.assertEqual(raised.exception.code, "NOT_CREATED")

    def test_a_profile_of_that_name_made_by_someone_else_is_left_alone(self):
        self.created(description="my own profile")
        with self.assertRaises(sp.StudioProfileError) as raised:
            self.finish()
        self.assertEqual(raised.exception.code, "NAME_TAKEN")
        self.assertFalse((self.target / "plugins").exists())
        self.assertEqual(self.commands, [])

    def test_finishing_links_the_plugin_carries_model_providers_and_sets_the_tools(self):
        self.created()
        result = self.finish()
        self.assertEqual((result["ok"], result["providers"], result["disabled_toolsets"]),
                         (True, ["my-provider"], ["tts", "connections", "computer_use", "cronjob"]))
        self.assertEqual((self.target / "plugins" / paths.PLUGIN_ID).resolve(), paths.PLUGIN_ROOT.resolve())
        self.assertEqual((self.target / "plugins" / "my-provider").resolve(), (self.home / "plugins" / "my-provider").resolve())
        self.assertFalse((self.target / "plugins" / "other").exists())          # not a model provider
        # Config is changed only through the hermes command, in the new profile.
        self.assertEqual(self.commands, [
            (self.target, ("plugins", "enable", paths.PLUGIN_ID)),
            (self.target, ("plugins", "enable", "my-provider")),
            (self.target, ("config", "set", "agent.disabled_toolsets", '["tts", "connections", "computer_use", "cronjob"]')),
            (self.target, ("skills", "opt-out")),
            (self.target, ("config", "set", "auxiliary.background_review.enabled", "false")),
            (self.target, ("config", "set", "curator.enabled", "false")),
            (self.target, ("config", "set", "approvals.mode", "smart")),
            (self.target, ("config", "set", "terminal.cwd", str((self.target / "workspace").resolve())))])
        self.assertTrue((self.target / "workspace").is_dir())
        self.assertEqual(list((self.target / "workspace").iterdir()), [])
        self.assertEqual(result["workspace"], str((self.target / "workspace").resolve()))
        self.assertIn("You are hermretro", (self.target / "SOUL.md").read_text())
        self.assertEqual(json.loads((self.target / sp.MARKER).read_text())["from_profile"], "work")
        self.assertEqual(sp.describe(self.home, self.target)["studio"],
                         {"name": "hermretro", "exists": True, "installed": True, "ours": True})
        # Nothing in the profile the plugin was installed into was touched.
        self.assertEqual(sorted(p.name for p in (self.home / "plugins").iterdir()), ["my-provider", "other"])

    def test_running_it_again_is_safe_and_keeps_an_edited_soul(self):
        self.created()
        self.finish()
        (self.target / "SOUL.md").write_text("edited by the user")
        again = self.finish()
        self.assertEqual((again["ok"], again["soul_written"]), (True, False))
        self.assertEqual((self.target / "SOUL.md").read_text(), "edited by the user")

    def test_running_it_again_updates_a_soul_left_as_an_older_release_shipped_it(self):
        self.created()
        self.finish()
        older = b"an older shipped soul"
        (self.target / "SOUL.md").write_bytes(older)
        import hashlib
        with unittest.mock.patch.object(sp, "OLDER_SOULS", frozenset({hashlib.sha256(older).hexdigest()})):
            again = self.finish()
        self.assertTrue(again["soul_written"])
        soul = (self.target / "SOUL.md").read_text()
        self.assertIn("chromatic_present_game", soul)
        self.assertIn("games folder", soul)

    def test_the_shipped_soul_uses_the_present_tool_and_the_games_folder(self):
        soul = sp.SOUL_FILE.read_text()
        self.assertIn("chromatic_present_game", soul)
        self.assertNotIn("keep the playable game on screen", soul)
        import hashlib
        self.assertNotIn(hashlib.sha256(soul.encode()).hexdigest(), sp.OLDER_SOULS)

    def test_a_failed_hermes_command_is_reported_and_the_step_can_be_run_again(self):
        self.created()
        def fail(target, *args):
            raise sp.StudioProfileError("HERMES_COMMAND_FAILED", "plugins enable failed")
        with self.assertRaises(sp.StudioProfileError):
            sp.finish(self.home, target=self.target, enabled=[], run=fail)
        self.assertFalse((self.target / sp.MARKER).exists())
        # Linked but not finished: the page must still offer the button, not wait for a profile
        # whose plugin was never switched on.
        self.assertTrue((self.target / "plugins" / paths.PLUGIN_ID).exists())
        self.assertEqual(sp.describe(self.home, self.target)["studio"]["installed"], False)
        self.assertEqual(self.finish()["ok"], True)
        self.assertEqual(sp.describe(self.home, self.target)["studio"]["installed"], True)

    def test_a_hermes_command_that_cannot_start_or_hangs_is_a_plain_error(self):
        import subprocess
        from unittest import mock
        for failure in (FileNotFoundError("hermes"), subprocess.TimeoutExpired("hermes", 180)):
            with mock.patch.object(sp.subprocess, "run", side_effect=failure):
                with self.assertRaises(sp.StudioProfileError) as raised:
                    sp._run_hermes(self.target, "plugins", "enable", "x")
            self.assertEqual(raised.exception.code, "HERMES_COMMAND_FAILED")

    def test_a_profile_that_only_resembles_ours_keeps_its_soul(self):
        self.created(description="hermretro: my own notes")
        with self.assertRaises(sp.StudioProfileError) as raised:
            self.finish()
        self.assertEqual(raised.exception.code, "NAME_TAKEN")
        self.assertEqual((self.target / "SOUL.md").read_text(), "default soul")


if __name__ == "__main__":
    unittest.main()
