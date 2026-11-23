"""The dedicated hermretro profile: what the page is told, and what finishing it does."""

import json
import os
import stat
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.system import paths  # noqa: E402 - the repository root goes on sys.path first
from backend.setup import studio_profile as sp  # noqa: E402 - the repository root goes on sys.path first


class StudioProfile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / "profiles" / "work"  # where the user installed the plugin
        self.target = root / "profiles" / sp.STUDIO_PROFILE
        (self.home / "plugins" / "my-provider").mkdir(parents=True)
        (self.home / "plugins" / "my-provider" / "plugin.yaml").write_text("name: my-provider\nkind: model-provider\n")
        (self.home / "plugins" / "other").mkdir()
        (self.home / "plugins" / "other" / "plugin.yaml").write_text("name: other\nkind: tool\n")
        self.commands = []
        self.notifications = []
        for name, effect in (
            ("prepare_profile", self.prepare_profile),
            ("notify_profile_created", self.notifications.append),
        ):
            patch = unittest.mock.patch.object(sp.hermes_api, name, side_effect=effect)
            patch.start()
            self.addCleanup(patch.stop)

    @staticmethod
    def prepare_profile(staging, *, description, soul):
        (staging / "profile.yaml").write_text(f"description: '{description}'\n")
        (staging / "SOUL.md").write_text(soul)
        (staging / "config.yaml").write_text('{"model": {"provider": "example"}}')

    def tearDown(self):
        self.tmp.cleanup()

    def created(self, description=sp.DESCRIPTION):
        """An existing profile created before setup staged its preferences."""
        self.target.mkdir(parents=True)
        (self.target / "profile.yaml").write_text(f"description: '{description}'\n")
        (self.target / "SOUL.md").write_text("default soul")
        (self.target / "config.yaml").write_text("{}")

    @staticmethod
    def read_config(target):
        return json.loads((target / "config.yaml").read_text())

    def run_command(self, target, *args):
        self.commands.append((target, args))
        if args[:3] == ("config", "set", "agent.max_turns"):
            config = self.read_config(target)
            config.setdefault("agent", {})["max_turns"] = int(args[3])
            (target / "config.yaml").write_text(json.dumps(config))

    def finish(self, *, create=False, run=None):
        return sp.finish(
            self.home,
            target=self.target,
            enabled=["my-provider", "other", "gone"],
            run=run or self.run_command,
            create=create,
        )

    def test_the_page_is_told_which_profile_answers_and_whether_the_studio_exists(self):
        told = sp.describe(self.home, self.target)
        self.assertEqual((told["name"], told["is_studio"]), ("work", False))
        self.assertEqual(
            told["studio"], {"name": "hermretro", "exists": False, "installed": False, "ours": False, "conflict": False}
        )
        self.assertTrue(sp.describe(self.target)["is_studio"])
        self.assertEqual(sp.profile_name(Path(self.tmp.name)), "default")

    def test_the_page_is_told_which_profile_installed_the_copy_it_runs(self):
        root = Path(self.tmp.name)
        installed = self.home / "plugins" / "hermretro"
        installed.mkdir()
        self.assertEqual(sp.installed_in(installed), {"profile": "work", "linked": False})
        (root / "plugins" / "hermretro").mkdir(parents=True)
        self.assertEqual(sp.installed_in(root / "plugins" / "hermretro"), {"profile": "default", "linked": False})
        # The studio profile links the installed copy in: the update still runs where it was installed.
        (self.target / "plugins").mkdir(parents=True)
        (self.target / "plugins" / "hermretro").symlink_to(installed, target_is_directory=True)
        self.assertEqual(sp.installed_in(self.target / "plugins" / "hermretro"), {"profile": "work", "linked": False})
        # A development checkout linked in from elsewhere: Hermes does not update it.
        checkout = root / "projects" / "hermretro"
        checkout.mkdir(parents=True)
        self.assertEqual(sp.installed_in(checkout), {"profile": None, "linked": True})

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

    def test_creation_links_the_plugin_carries_model_providers_and_sets_the_tools(self):
        result = self.finish(create=True)
        self.assertEqual(
            (result["ok"], result["providers"], result["disabled_toolsets"]),
            (True, ["my-provider"], ["tts", "connections", "computer_use", "cronjob"]),
        )
        self.assertEqual((self.target / "plugins" / paths.PLUGIN_ID).resolve(), paths.PLUGIN_ROOT.resolve())
        self.assertEqual(
            (self.target / "plugins" / "my-provider").resolve(), (self.home / "plugins" / "my-provider").resolve()
        )
        self.assertFalse((self.target / "plugins" / "other").exists())  # not a model provider
        # Config is changed only through the hermes command, in the new profile.
        staging = self.commands[0][0]
        self.assertEqual(staging.parent, self.target.parent)
        self.assertTrue(staging.name.startswith(".hermretro-"))
        self.assertFalse(staging.exists())
        self.assertEqual(
            self.commands,
            [
                (staging, ("config", "set", "agent.max_turns", "1000")),
                (staging, ("plugins", "enable", paths.PLUGIN_ID)),
                (staging, ("plugins", "enable", "my-provider")),
                (
                    staging,
                    ("config", "set", "agent.disabled_toolsets", '["tts", "connections", "computer_use", "cronjob"]'),
                ),
                (staging, ("skills", "opt-out")),
                (staging, ("config", "set", "auxiliary.background_review.enabled", "false")),
                (staging, ("config", "set", "curator.enabled", "false")),
                (staging, ("config", "set", "approvals.mode", "smart")),
                (staging, ("config", "set", "terminal.cwd", str((self.target / "workspace").resolve()))),
            ],
        )
        self.assertEqual(
            self.read_config(self.target), {"model": {"provider": "example"}, "agent": {"max_turns": 1000}}
        )
        self.assertEqual(self.notifications, [self.target])
        self.assertTrue((self.target / "workspace").is_dir())
        self.assertEqual(list((self.target / "workspace").iterdir()), [])
        self.assertEqual(result["workspace"], str((self.target / "workspace").resolve()))
        self.assertIn("You are hermretro", (self.target / "SOUL.md").read_text())
        self.assertEqual(json.loads((self.target / sp.MARKER).read_text())["from_profile"], "work")
        self.assertEqual(
            sp.describe(self.home, self.target)["studio"],
            {"name": "hermretro", "exists": True, "installed": True, "ours": True, "conflict": False},
        )
        # Nothing in the profile the plugin was installed into was touched.
        self.assertEqual(sorted(p.name for p in (self.home / "plugins").iterdir()), ["my-provider", "other"])

    def test_running_it_again_is_safe_and_keeps_an_edited_soul(self):
        self.created()
        self.finish()
        (self.target / "SOUL.md").write_text("edited by the user")
        (self.target / "config.yaml").write_text('{"agent": {"max_turns": 47}}')
        self.commands.clear()
        again = self.finish()
        self.assertFalse(any("agent.max_turns" in args for _target, args in self.commands))
        self.assertEqual((again["ok"], again["soul_written"]), (True, False))
        self.assertEqual((self.target / "SOUL.md").read_text(), "edited by the user")
        self.assertEqual(self.read_config(self.target)["agent"]["max_turns"], 47)

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
        self.assertEqual(soul, sp.SOUL_FILE.read_text())

    def test_an_older_shipped_soul_is_replaced_and_any_other_kept(self):
        import hashlib

        self.target.mkdir(parents=True)
        soul = self.target / "SOUL.md"
        older = b"an older shipped soul"
        with unittest.mock.patch.object(sp, "OLDER_SOULS", frozenset({hashlib.sha256(older).hexdigest()})):
            self.assertFalse(sp.refresh_soul(self.target), "no SOUL: nothing is written")
            self.assertFalse(soul.exists())
            soul.write_bytes(older)
            self.assertTrue(sp.refresh_soul(self.target))
            self.assertEqual(soul.read_bytes(), sp.SOUL_FILE.read_bytes())
            self.assertFalse(sp.refresh_soul(self.target), "the current SOUL is left alone")
            soul.write_text("edited by the user")
            self.assertFalse(sp.refresh_soul(self.target))
            self.assertEqual(soul.read_text(), "edited by the user")
            mine = self.target / "my-soul.md"
            mine.write_bytes(older)
            soul.unlink()
            soul.symlink_to(mine)
            self.assertFalse(sp.refresh_soul(self.target), "a link is the user's own arrangement")
            self.assertTrue(soul.is_symlink())
            soul.unlink()
            os.mkfifo(soul)
            self.assertFalse(sp.refresh_soul(self.target), "a pipe is never read (it would wait for a writer)")
            soul.unlink()
        self.assertEqual([path.name for path in self.target.iterdir() if path.name.endswith(".tmp")], [])

    def test_a_refreshed_soul_keeps_its_permissions(self):
        import hashlib

        self.target.mkdir(parents=True)
        soul = self.target / "SOUL.md"
        older = b"an older shipped soul"
        soul.write_bytes(older)
        soul.chmod(0o640)
        with unittest.mock.patch.object(sp, "OLDER_SOULS", frozenset({hashlib.sha256(older).hexdigest()})):
            self.assertTrue(sp.refresh_soul(self.target))
        self.assertEqual(stat.S_IMODE(soul.stat().st_mode), 0o640)

    def test_an_edit_made_while_the_soul_is_being_refreshed_is_kept(self):
        import hashlib

        self.target.mkdir(parents=True)
        soul = self.target / "SOUL.md"
        older = b"an older shipped soul"
        soul.write_bytes(older)
        checks = []
        real = sp._shipped_before

        def edited_after_the_first_check(path):
            answer = real(path)
            checks.append(answer)
            if len(checks) == 1:
                soul.write_text("edited by the user")
            return answer

        with (
            unittest.mock.patch.object(sp, "OLDER_SOULS", frozenset({hashlib.sha256(older).hexdigest()})),
            unittest.mock.patch.object(sp, "_shipped_before", edited_after_the_first_check),
        ):
            self.assertFalse(sp.refresh_soul(self.target))
        self.assertEqual(soul.read_text(), "edited by the user")
        self.assertEqual([path.name for path in self.target.iterdir()], ["SOUL.md"])

    def test_finishing_again_reports_a_soul_it_could_not_update(self):
        import hashlib

        self.created()
        self.finish()
        older = b"an older shipped soul"
        (self.target / "SOUL.md").write_bytes(older)
        with (
            unittest.mock.patch.object(sp, "OLDER_SOULS", frozenset({hashlib.sha256(older).hexdigest()})),
            unittest.mock.patch.object(sp.os, "replace", side_effect=PermissionError("read-only")),
        ):
            with self.assertRaises(PermissionError):
                self.finish()
        self.assertEqual((self.target / "SOUL.md").read_bytes(), older)
        self.assertEqual([path.name for path in self.target.iterdir() if path.name.endswith(".tmp")], [])

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

    def test_interruption_after_seeding_leaves_no_editable_profile_until_retry(self):
        def interrupted(staging, *args):
            self.run_command(staging, *args)
            if args[:3] == ("config", "set", "agent.max_turns"):
                self.assertEqual(self.read_config(staging)["agent"]["max_turns"], 1000)
                self.assertFalse(self.target.exists())
                raise sp.StudioProfileError("HERMES_COMMAND_FAILED", "interrupted after persist")

        with self.assertRaises(sp.StudioProfileError):
            self.finish(create=True, run=interrupted)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.target.parent.iterdir()), [self.home])
        self.assertEqual(self.notifications, [])
        self.assertTrue(self.finish(create=True)["ok"])
        self.assertEqual(self.read_config(self.target)["agent"]["max_turns"], 1000)

    def test_retry_after_publication_keeps_a_cleared_limit_and_an_edited_soul(self):
        with unittest.mock.patch.object(sp.hermes_api, "notify_profile_created", side_effect=OSError("lost reply")):
            with self.assertRaises(OSError):
                self.finish(create=True)
        self.assertTrue((self.target / sp.MARKER).is_file())
        config = {"agent": {"other_setting": 61}}
        (self.target / "config.yaml").write_text(json.dumps(config))
        soul = self.target / "SOUL.md"
        soul.write_text("edited by the user")
        self.commands.clear()
        self.assertTrue(self.finish(create=True)["ok"])
        self.assertEqual(self.commands, [])
        self.assertEqual(self.read_config(self.target), config)
        self.assertEqual(soul.read_text(), "edited by the user")

    def test_an_interrupted_old_setup_does_not_reseed_a_cleared_limit_or_soul(self):
        self.created()
        (self.target / "config.yaml").write_text('{"agent": {}}')
        (self.target / "SOUL.md").unlink()
        self.assertTrue(self.finish()["ok"])
        self.assertFalse(any("agent.max_turns" in args for _target, args in self.commands))
        self.assertNotIn("max_turns", self.read_config(self.target)["agent"])
        self.assertFalse((self.target / "SOUL.md").exists())

    def test_repair_keeps_a_missing_soul_even_when_the_cli_seeds_its_own_default(self):
        self.created()
        soul = self.target / "SOUL.md"
        soul.unlink()

        def run(target, *args):
            self.run_command(target, *args)
            if not soul.exists():
                soul.write_bytes(b"Hermes default")

        with unittest.mock.patch.object(sp.hermes_api, "default_soul", return_value=b"Hermes default"):
            self.assertTrue(self.finish(run=run)["ok"])
        self.assertFalse(soul.exists())

    def test_a_profile_published_by_someone_else_during_setup_is_preserved(self):
        def race(staging, *args):
            self.run_command(staging, *args)
            if args[:3] == ("config", "set", "agent.max_turns"):
                self.created(description="my own profile")
                (self.target / "config.yaml").write_text('{"agent": {"max_turns": 61}}')

        with self.assertRaises(sp.StudioProfileError) as raised:
            self.finish(create=True, run=race)
        self.assertEqual(raised.exception.code, "NAME_TAKEN")
        self.assertEqual(self.notifications, [])
        self.assertEqual(self.read_config(self.target), {"agent": {"max_turns": 61}})
        self.assertEqual((self.target / "SOUL.md").read_text(), "default soul")

    def test_a_deleted_leftover_keeps_its_files_and_the_new_studio_gets_fresh_defaults(self):
        (self.target / "logs").mkdir(parents=True)
        (self.target / "logs" / "old.log").write_text("old runtime data")
        (self.target / "workspace").symlink_to(self.home)
        marker = sp.hermes_api.profile_tombstone(self.target)
        marker.parent.mkdir()
        marker.write_text("deleted")

        created = self.finish(create=True)

        self.assertTrue(created["ok"])
        self.assertEqual(created["workspace"], str((self.target / "workspace").resolve()))
        self.assertFalse(marker.exists())
        [archive] = self.target.parent.glob(".hermretro-deleted-*")
        self.assertEqual((archive / self.target.name / "logs" / "old.log").read_text(), "old runtime data")
        self.assertEqual(self.read_config(self.target)["agent"]["max_turns"], 1000)
        self.assertEqual(self.notifications, [self.target])

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
