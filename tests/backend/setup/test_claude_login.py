"""The studio profile's Claude login: Claude Code's Keychain naming, the login check and the sign-in."""

import hashlib
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.setup import claude_login  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home  # noqa: E402 - the repository root goes on sys.path first


class KeychainName(unittest.TestCase):
    def test_the_default_login_has_the_plain_name_and_any_named_folder_a_hashed_one(self):
        # Claude Code 2.1.331: no suffix only while CLAUDE_CONFIG_DIR is unset; otherwise the first 8 hex digits of
        # the folder's SHA-256, even for ~/.claude itself.
        self.assertEqual(claude_login.keychain_service(None), "Claude Code-credentials")
        folder = "/Users/u/.claude"
        digest = hashlib.sha256(folder.encode()).hexdigest()[:8]
        self.assertEqual(claude_login.keychain_service(folder), f"Claude Code-credentials-{digest}")


class LoginCheck(unittest.TestCase):
    def setUp(self):
        self.folder = isolated_home(self).base / "claude"
        self.folder.mkdir()

    def test_linux_reads_the_credentials_file(self):
        self.assertFalse(claude_login.signed_in(str(self.folder), macos=False))
        (self.folder / ".credentials.json").write_text("{}")
        self.assertTrue(claude_login.signed_in(str(self.folder), macos=False))

    def test_macos_asks_the_keychain_for_the_entry_of_that_folder(self):
        asked = []

        def keychain(service):
            asked.append(service)
            return True

        self.assertTrue(claude_login.signed_in(str(self.folder), macos=True, keychain=keychain))
        self.assertEqual(asked, [claude_login.keychain_service(str(self.folder))])

    def test_the_page_is_told_how_the_studio_signs_in(self):
        self.assertEqual(
            claude_login.status({}, {claude_login.TOKEN: "oat"}),
            {"provider": claude_login.PLUGIN, "signed_in": True, "via": "token"},
        )
        self.assertEqual(
            claude_login.status({}, {}), {"provider": claude_login.PLUGIN, "signed_in": False, "via": None}
        )
        config = {"plugins": {"entries": {claude_login.PLUGIN: {"settings": {"claude_config_dir": str(self.folder)}}}}}
        self.assertFalse(claude_login.status(config, {}, macos=False)["signed_in"])


class SignIn(unittest.TestCase):
    def setUp(self):
        self.studio = isolated_home(self).base / "profiles" / "hermretro"
        self.studio.mkdir(parents=True)
        self.calls = []

    def claude(self, signs_in=True, returncode=0):
        def run(command, **options):
            self.calls.append((command, options["env"]["CLAUDE_CONFIG_DIR"], options["stdin"]))
            if signs_in:
                (Path(options["env"]["CLAUDE_CONFIG_DIR"]) / ".credentials.json").write_text("{}")
            return SimpleNamespace(returncode=returncode, stdout="", stderr="Login cancelled")

        return run

    def sign_in(self, run, command=lambda: "/usr/bin/claude"):
        original = claude_login.host.MACOS
        claude_login.host.MACOS = False
        self.addCleanup(setattr, claude_login.host, "MACOS", original)
        return claude_login.sign_in(self.studio, run=run, command=command)

    def test_the_login_goes_into_the_studios_own_folder(self):
        folder = self.sign_in(self.claude())
        self.assertEqual(folder, str(self.studio / claude_login.OWN_DIR))
        self.assertEqual(self.calls, [(["/usr/bin/claude", "auth", "login", "--claudeai"], folder, subprocess.DEVNULL)])
        self.assertEqual((self.studio / claude_login.OWN_DIR).stat().st_mode & 0o777, 0o700)

    def test_a_sign_in_that_does_not_finish_is_an_error(self):
        for run in (self.claude(signs_in=False), self.claude(returncode=1)):
            with self.subTest(), self.assertRaises(claude_login.SignInError) as raised:
                self.sign_in(run)
            self.assertEqual(raised.exception.code, "SIGN_IN_FAILED")

    def test_no_claude_code_is_an_error(self):
        with self.assertRaises(claude_login.SignInError) as raised:
            self.sign_in(self.claude(), command=lambda: None)
        self.assertEqual(raised.exception.code, "CLAUDE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
