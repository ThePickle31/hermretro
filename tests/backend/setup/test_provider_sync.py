"""Keeping the studio profile on the installing profile's providers: what is copied, what is kept, the Claude login."""

import json
import sys
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.setup import claude_login, provider_sync  # noqa: E402 - the repository root goes on sys.path first
from tests.support import isolated_home  # noqa: E402 - the repository root goes on sys.path first

DIRECTSDK = claude_login.PLUGIN


def read_config(home):
    try:
        return json.loads((home / "config.yaml").read_text())
    except FileNotFoundError:
        return {}


def read_env(home):
    try:
        lines = (home / ".env").read_text().splitlines()
    except FileNotFoundError:
        return {}
    return dict(line.split("=", 1) for line in lines if "=" in line)


class Profiles(unittest.TestCase):
    """Two profiles, each config.yaml written as JSON, and `hermes config set` played on the studio one."""

    def setUp(self):
        base = isolated_home(self).base
        self.source, self.studio = base / "default", base / "profiles" / "hermretro"
        self.source.mkdir()
        self.studio.mkdir(parents=True)
        self.commands = []
        for name, effect in (
            ("read_profile_config", read_config),
            ("read_profile_env", read_env),
            ("provider_env_keys", lambda: {"OPENROUTER_API_KEY", "OPENROUTER_BASE_URL"}),
        ):
            patch = unittest.mock.patch.object(provider_sync.hermes_api, name, side_effect=effect)
            patch.start()
            self.addCleanup(patch.stop)

    def write(self, home, config=None, env=None):
        if config is not None:
            (home / "config.yaml").write_text(json.dumps(config))
        if env is not None:
            (home / ".env").write_text("".join(f"{key}={value}\n" for key, value in env.items()))

    def run_command(self, *arguments):
        """`hermes config set` in the studio profile: UPPER_SNAKE names go to .env, the rest into config.yaml."""
        self.commands.append(arguments)
        _config, _set, key, text = arguments
        if key.isupper():
            env = read_env(self.studio)
            env[key] = text
            self.write(self.studio, env=env)
            return
        try:
            value = json.loads(text)
        except ValueError:
            value = text
        config = read_config(self.studio)
        tree = config
        *parents, leaf = key.split(".")
        for part in parents:
            tree = tree.setdefault(part, {})
        tree[leaf] = value
        self.write(self.studio, config=config)

    def sync(self, plugins=(), **options):
        return provider_sync.sync(self.source, self.studio, self.run_command, plugins=list(plugins), **options)

    def keys(self):
        return [arguments[2] for arguments in self.commands]


class ProviderSync(Profiles):
    def test_provider_routes_settings_and_keys_are_copied_and_nothing_else(self):
        self.write(
            self.source,
            config={
                "model": {"default": "m1", "provider": "openrouter", "base_url": "https://example.test"},
                "delegation": {"provider": "openrouter", "model": "m2", "max_iterations": 250},
                "fallback_providers": [{"provider": "nous", "model": "m3"}],
                "auxiliary": {"vision": {"provider": "openrouter", "model": "m4", "timeout": 30}},
                "plugins": {
                    "entries": {"my-provider": {"settings": {"region": "eu"}}, "other": {"settings": {"x": 1}}}
                },
                "agent": {"max_turns": 50},
                "terminal": {"cwd": "/somewhere"},
            },
            env={"OPENROUTER_API_KEY": "sk-1", "TELEGRAM_BOT_TOKEN": "bot", "TERMINAL_ENV": "local"},
        )
        result = self.sync(plugins=["my-provider"])
        self.assertEqual(
            self.keys(),
            [
                "model.provider",  # a route's provider first, then the fields that belong to it
                "model.base_url",
                "model.default",
                "fallback_providers",
                "delegation.provider",
                "delegation.max_iterations",
                "delegation.model",
                "auxiliary.vision.provider",
                "auxiliary.vision.model",
                "plugins.entries.my-provider.settings.region",
                "OPENROUTER_API_KEY",
            ],
        )
        self.assertEqual(result["changed"], self.keys())
        self.assertIsNone(result["claude_login"])  # not a DirectSDK profile
        studio = read_config(self.studio)
        self.assertEqual(
            studio["model"], {"provider": "openrouter", "base_url": "https://example.test", "default": "m1"}
        )
        self.assertEqual(studio["auxiliary"], {"vision": {"provider": "openrouter", "model": "m4"}})
        self.assertNotIn("agent", studio)
        self.assertEqual(read_env(self.studio), {"OPENROUTER_API_KEY": "sk-1"})
        # The record says what was copied by hash only: no key or value is written there.
        self.assertNotIn("sk-1", (self.studio / provider_sync.RECORD).read_text())

    def test_a_key_a_copied_provider_entry_reads_from_env_is_copied_too(self):
        self.write(
            self.source,
            config={"custom_providers": [{"name": "local", "api_key": "${LOCAL_LLM_KEY}"}]},
            env={"LOCAL_LLM_KEY": "k", "UNRELATED_TOKEN": "t"},
        )
        self.sync()
        self.assertEqual(self.keys(), ["custom_providers", "LOCAL_LLM_KEY"])

    def test_a_later_change_is_followed_and_one_made_in_the_studio_is_kept(self):
        self.write(self.source, config={"model": {"provider": "a", "default": "m1"}}, env={"OPENROUTER_API_KEY": "k1"})
        self.sync()
        self.assertTrue(provider_sync.is_current(self.source, self.studio))
        self.commands.clear()
        self.assertEqual(self.sync()["changed"], [])  # nothing new: no command

        config = read_config(self.studio)
        config["model"]["default"] = "mine"  # chosen in the studio profile itself
        self.write(self.studio, config=config)
        self.write(self.source, config={"model": {"provider": "b", "default": "m2"}}, env={"OPENROUTER_API_KEY": "k2"})
        self.assertFalse(provider_sync.is_current(self.source, self.studio))
        result = self.sync()
        self.assertEqual(result["changed"], ["model.provider", "OPENROUTER_API_KEY"])
        self.assertEqual(result["kept"], ["model.default"])
        self.assertEqual(read_config(self.studio)["model"], {"provider": "b", "default": "mine"})
        self.assertEqual(read_env(self.studio)["OPENROUTER_API_KEY"], "k2")

    def test_a_profile_made_before_the_sync_keeps_its_own_values_and_gains_the_missing_ones(self):
        self.write(
            self.studio, config={"model": {"provider": "mine", "default": "m0"}}, env={"OPENROUTER_API_KEY": "own"}
        )
        self.write(
            self.source,
            config={"model": {"provider": "a", "default": "m1"}, "delegation": {"provider": "a"}},
            env={"OPENROUTER_API_KEY": "theirs"},
        )
        result = self.sync()
        self.assertEqual(result["changed"], ["delegation.provider"])
        self.assertEqual(result["kept"], ["OPENROUTER_API_KEY", "model.default", "model.provider"])

    def test_nothing_is_removed_when_the_installing_profile_drops_it(self):
        self.write(self.source, config={"delegation": {"provider": "a"}})
        self.sync()
        self.write(self.source, config={})
        self.commands.clear()
        self.sync()
        self.assertEqual(self.commands, [])
        self.assertEqual(read_config(self.studio)["delegation"], {"provider": "a"})


class ClaudeLogin(Profiles):
    """The studio profile gets a Claude login DirectSDK accepts (claude_login.plan)."""

    def directsdk(self, settings=None, env=None):
        config = {"plugins": {"enabled": [DIRECTSDK], "entries": {DIRECTSDK: {"settings": settings or {}}}}}
        self.write(self.source, config=config, env=env or {})
        self.write(self.studio, config={"plugins": {"enabled": [DIRECTSDK]}})

    def sync(self, plugins=(DIRECTSDK,), macos=False, environ=None, signed_in=True):
        with unittest.mock.patch.object(claude_login, "signed_in", return_value=signed_in):
            return super().sync(plugins=plugins, environ=environ or {}, login_options={"macos": macos})

    def test_linux_uses_the_default_login_folder(self):
        self.directsdk()
        result = self.sync()
        self.assertEqual(self.commands, [("config", "set", claude_login.SETTING, str(Path.home() / ".claude"))])
        self.assertEqual(result["claude_login"], {"provider": DIRECTSDK, "signed_in": True, "via": "folder"})

    def test_a_folder_the_installing_profile_names_is_used_as_written_on_both_systems(self):
        for macos in (False, True):
            with self.subTest(macos=macos):
                self.commands.clear()
                self.directsdk(settings={"claude_config_dir": " ~/work-claude ", "claude_code_telemetry": False})
                self.sync(macos=macos)
                self.assertEqual(
                    self.commands,
                    [
                        ("config", "set", f"plugins.entries.{DIRECTSDK}.settings.claude_code_telemetry", "false"),
                        ("config", "set", claude_login.SETTING, str(Path.home() / "work-claude")),
                    ],
                )

    def test_a_folder_from_the_environment_is_used_like_the_plugin_does(self):
        self.directsdk()
        self.sync(macos=True, environ={"CLAUDE_CONFIG_DIR": "/opt/claude"})
        self.assertEqual(self.commands, [("config", "set", claude_login.SETTING, "/opt/claude")])

    def test_macos_with_the_default_login_asks_for_a_sign_in_of_its_own(self):
        # That login's Keychain entry is out of reach once any folder is named (claude_login's docstring).
        self.directsdk()
        result = self.sync(macos=True)
        self.assertEqual(self.commands, [])
        self.assertEqual(result["claude_login"], {"provider": DIRECTSDK, "signed_in": False, "via": None})

    def test_a_token_is_copied_and_is_enough(self):
        self.directsdk(env={claude_login.TOKEN: "oat-1"})
        result = self.sync(macos=True)
        self.assertEqual(self.commands, [("config", "set", claude_login.TOKEN, "oat-1")])
        self.assertEqual(result["claude_login"], {"provider": DIRECTSDK, "signed_in": True, "via": "token"})

    def test_a_login_the_studio_already_names_is_kept(self):
        self.directsdk(settings={"claude_config_dir": "/theirs"})
        config = read_config(self.studio)
        config["plugins"]["entries"] = {DIRECTSDK: {"settings": {"claude_config_dir": "/own"}}}
        self.write(self.studio, config=config)
        result = self.sync(signed_in=False)
        self.assertEqual(self.commands, [])
        self.assertEqual(result["claude_login"], {"provider": DIRECTSDK, "signed_in": False, "via": "folder"})


if __name__ == "__main__":
    unittest.main()
