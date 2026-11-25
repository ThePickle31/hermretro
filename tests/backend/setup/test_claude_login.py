"""The studio profile's Claude login: which folder it shares, the login check and the sign-in."""

import json
import os
import subprocess
import sys
import unittest
import unittest.mock
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.setup import claude_login  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home  # noqa: E402 - the repository root goes on sys.path first


def config_with(folder):
    return {"plugins": {"entries": {claude_login.PLUGIN: {"settings": {"claude_config_dir": folder}}}}}


class InheritedFolder(unittest.TestCase):
    def test_the_installing_profiles_setting_then_its_environment_then_the_default(self):
        self.assertEqual(claude_login.inherited_dir(config_with("/a"), {"CLAUDE_CONFIG_DIR": "/b"}), "/a")
        self.assertEqual(
            claude_login.inherited_dir(
                {}, {"CLAUDE_SUBSCRIPTION_DIRECTSDK_CONFIG_DIR": "/c", "CLAUDE_CONFIG_DIR": "/b"}
            ),
            "/c",
        )
        self.assertEqual(claude_login.inherited_dir({}, {}, macos=False), str(Path.home() / ".claude"))
        # On macOS the default login's Keychain entry is named for an unset CLAUDE_CONFIG_DIR: a second profile, which
        # always sets one, cannot reach it.
        self.assertIsNone(claude_login.inherited_dir({}, {}, macos=True))


class LoginCheck(unittest.TestCase):
    def setUp(self):
        isolated_home(self)
        claude_login._checked.clear()
        self.addCleanup(claude_login._checked.clear)
        self.calls = []

    def claude(self, report):
        def run(command, **options):
            self.calls.append((command, options["env"]))
            return SimpleNamespace(returncode=0, stdout=json.dumps(report), stderr="")

        return run

    def test_claude_code_is_asked_about_exactly_that_login(self):
        run = self.claude({"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty"})
        with unittest.mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk", "CLAUDE_CODE_OAUTH_TOKEN": "other"}):
            self.assertTrue(claude_login.logged_in(folder="/f", run=run, command=lambda: "claude"))
        command, env = self.calls[0]
        self.assertEqual(command, ["claude", "auth", "status", "--json"])
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], "/f")
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", env)
        # Asked again within the minute: the answer is reused.
        self.assertTrue(claude_login.logged_in(folder="/f", run=run, command=lambda: "claude"))
        self.assertEqual(len(self.calls), 1)

    def test_an_empty_login_another_backend_or_no_claude_code_is_not_signed_in(self):
        self.assertFalse(claude_login.logged_in(folder="/a", run=self.claude({"loggedIn": False}), command=lambda: "c"))
        bedrock = self.claude({"loggedIn": True, "apiProvider": "bedrock"})
        self.assertFalse(claude_login.logged_in(folder="/b", run=bedrock, command=lambda: "c"))
        self.assertFalse(claude_login.logged_in(folder="/c", command=lambda: None))

    def test_the_page_is_told_how_the_studio_signs_in(self):
        asked = []

        def check(**login):
            asked.append(login)
            return True

        self.assertEqual(
            claude_login.status(config_with("/f"), {claude_login.TOKEN: "oat"}, check=check),
            {"provider": claude_login.PLUGIN, "signed_in": True, "via": "token"},
        )
        self.assertEqual(
            claude_login.status(config_with("/f"), {}, check=check),
            {"provider": claude_login.PLUGIN, "signed_in": True, "via": "folder"},
        )
        self.assertEqual(asked, [{"token": "oat", "folder": None}, {"token": None, "folder": "/f"}])
        self.assertEqual(
            claude_login.status({}, {}, check=check), {"provider": claude_login.PLUGIN, "signed_in": False, "via": None}
        )


class SignIn(unittest.TestCase):
    def setUp(self):
        self.studio = isolated_home(self).base / "profiles" / "hermretro"
        self.studio.mkdir(parents=True)
        self.calls = []

    def claude(self, returncode=0):
        def run(command, **options):
            self.calls.append((command, options["env"]["CLAUDE_CONFIG_DIR"], options["stdin"]))
            return SimpleNamespace(returncode=returncode, stdout="", stderr="Login cancelled")

        return run

    def sign_in(self, run, signed_in=True, command=lambda: "/usr/bin/claude"):
        return claude_login.sign_in(self.studio, run=run, command=command, check=lambda **_login: signed_in)

    def test_the_login_goes_into_the_studios_own_folder(self):
        folder = self.sign_in(self.claude())
        self.assertEqual(folder, str(self.studio / claude_login.OWN_DIR))
        self.assertEqual(self.calls, [(["/usr/bin/claude", "auth", "login", "--claudeai"], folder, subprocess.DEVNULL)])
        self.assertEqual((self.studio / claude_login.OWN_DIR).stat().st_mode & 0o777, 0o700)

    def test_a_sign_in_that_does_not_finish_is_an_error(self):
        for run, signed_in in ((self.claude(), False), (self.claude(returncode=1), True)):
            with self.subTest(), self.assertRaises(claude_login.SignInError) as raised:
                self.sign_in(run, signed_in)
            self.assertEqual(raised.exception.code, "SIGN_IN_FAILED")

    def test_no_claude_code_is_an_error(self):
        with self.assertRaises(claude_login.SignInError) as raised:
            self.sign_in(self.claude(), command=lambda: None)
        self.assertEqual(raised.exception.code, "CLAUDE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
