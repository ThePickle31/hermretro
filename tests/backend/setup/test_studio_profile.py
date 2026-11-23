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
        for name, options in (
            ("profile_config", {"side_effect": self.read_config}),
            ("default_soul", {"return_value": b"default soul"}),
        ):
            patch = unittest.mock.patch.object(sp.hermes_api, name, **options)
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def created(self, description=sp.DESCRIPTION):
        """What Hermes's profiles.create leaves behind."""
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
            (target / "config.yaml").write_text(json.dumps({"agent": {"max_turns": int(args[3])}}))

    def finish(self):
        return sp.finish(
            self.home,
            target=self.target,
            enabled=["my-provider", "other", "gone"],
            run=self.run_command,
        )

    def test_the_page_is_told_which_profile_answers_and_how_to_create_the_studio_one(self):
        told = sp.describe(self.home, self.target)
        self.assertEqual((told["name"], told["is_studio"]), ("work", False))
        self.assertEqual(
            told["studio"], {"name": "hermretro", "exists": False, "installed": False, "ours": False, "conflict": False}
        )
        self.assertEqual(
            told["create"],
            {
                "name": "hermretro",
                "description": sp.DESCRIPTION,
                "no_skills": True,
                "share_auth": True,
                "no_alias": True,
            },
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

    def test_finishing_links_the_plugin_carries_model_providers_and_sets_the_tools(self):
        self.created()
        result = self.finish()
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
        self.assertEqual(
            self.commands,
            [
                (self.target, ("plugins", "enable", paths.PLUGIN_ID)),
                (self.target, ("plugins", "enable", "my-provider")),
                (
                    self.target,
                    ("config", "set", "agent.disabled_toolsets", '["tts", "connections", "computer_use", "cronjob"]'),
                ),
                (self.target, ("skills", "opt-out")),
                (self.target, ("config", "set", "auxiliary.background_review.enabled", "false")),
                (self.target, ("config", "set", "curator.enabled", "false")),
                (self.target, ("config", "set", "approvals.mode", "smart")),
                (self.target, ("config", "set", "agent.max_turns", "1000")),
                (self.target, ("config", "set", "terminal.cwd", str((self.target / "workspace").resolve()))),
            ],
        )
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

    def test_retry_preserves_each_edited_preference_even_before_setup_seeds_it(self):
        root = self.target.parent
        for failure in (("plugins", "enable"), ("config", "set", "terminal.cwd")):
            edits = ["turn limit", "SOUL"]
            if failure[-1] == "terminal.cwd":
                edits.append("remove limit")
            for edit in edits:
                with self.subTest(failure=failure, edit=edit):
                    self.target = root / f"{failure[-1]}-{edit}"
                    self.created()

                    def fail(target, *args, failure=failure):
                        if args[: len(failure)] == failure:
                            raise sp.StudioProfileError("HERMES_COMMAND_FAILED", "interrupted")
                        self.run_command(target, *args)

                    with self.assertRaises(sp.StudioProfileError):
                        sp.finish(self.home, target=self.target, enabled=[], run=fail)
                    self.assertFalse((self.target / sp.MARKER).exists())

                    soul = self.target / "SOUL.md"
                    if edit == "turn limit":
                        (self.target / "config.yaml").write_text('{"agent": {"max_turns": 61}}')
                    elif edit == "remove limit":
                        (self.target / "config.yaml").write_text('{"agent": {}}')
                    else:
                        soul.write_text("edited in the unfinished profile")

                    self.assertTrue(self.finish()["ok"])
                    self.assertEqual(
                        self.read_config(self.target)["agent"].get("max_turns"),
                        {"turn limit": 61, "SOUL": 1000, "remove limit": None}[edit],
                    )
                    self.assertEqual(
                        soul.read_text(),
                        "edited in the unfinished profile" if edit == "SOUL" else sp.SOUL_FILE.read_text(),
                    )
                    self.assertTrue((self.target / sp.MARKER).is_file())

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
