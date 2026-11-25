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


def write(home, config=None, env=None):
    if config is not None:
        (home / "config.yaml").write_text(json.dumps(config))
    if env is not None:
        (home / ".env").write_text("".join(f"{key}={value}\n" for key, value in env.items()))


def key_path(key):
    """A dotted config key as Hermes splits it; a plugin's name is one part."""
    if key.startswith("plugins.entries."):
        _plugins, _entries, rest = key.split(".", 2)
        name, _, tail = rest.partition(".settings.")
        return ["plugins", "entries", name, *(["settings", tail] if tail else [])]
    return key.split(".")


class Profiles(unittest.TestCase):
    """Two profiles, each config.yaml written as JSON, and `hermes config set|unset` played on the studio one."""

    def setUp(self):
        base = isolated_home(self).base
        self.source, self.studio = base / "default", base / "profiles" / "hermretro"
        self.source.mkdir()
        self.studio.mkdir(parents=True)
        self.commands, self.env_writes = [], []
        for name, effect in (
            ("read_profile_config", read_config),
            ("read_profile_env", read_env),
            ("provider_env_keys", lambda: {"OPENROUTER_API_KEY"}),
            ("set_profile_env", self.set_env),
        ):
            patch = unittest.mock.patch.object(provider_sync.hermes_api, name, side_effect=effect)
            patch.start()
            self.addCleanup(patch.stop)

    def set_env(self, home, name, value):
        self.assertEqual(home, self.studio)
        self.env_writes.append((name, value))
        env = read_env(home)
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
        write(home, env=env)

    def run_command(self, *arguments):
        self.commands.append(arguments)
        _config, action, *rest = arguments
        if rest[0] == "--force":
            rest = rest[1:]
        config = read_config(self.studio)
        tree = config
        *parents, leaf = key_path(rest[0])
        for part in parents:
            tree = tree.setdefault(part, {})
        if action == "unset":
            tree.pop(leaf, None)
        else:
            try:
                tree[leaf] = json.loads(rest[1])
            except ValueError:
                tree[leaf] = rest[1]
        write(self.studio, config=config)

    def sync(self, plugins=(), **options):
        return provider_sync.sync(self.source, self.studio, self.run_command, plugins=list(plugins), **options)


class ProviderSync(Profiles):
    def test_each_provider_unit_is_copied_whole_and_nothing_else(self):
        providers = {"custom.v2": {"base_url": "https://example.test", "api_key": "${CUSTOM_KEY}"}}
        write(
            self.source,
            config={
                "model": {"default": "m1", "provider": "openrouter"},
                "providers": providers,
                "delegation": {"provider": "openrouter", "model": "m2", "max_iterations": 250},
                "auxiliary": {"vision": {"provider": "local", "key_env": "LOCAL_KEY", "timeout": 30}},
                "plugins": {
                    "entries": {"my-provider": {"settings": {"region": "eu"}}, "other": {"settings": {"x": 1}}}
                },
                "agent": {"max_turns": 50},
            },
            env={"OPENROUTER_API_KEY": "sk-1", "CUSTOM_KEY": "c", "LOCAL_KEY": "l", "TELEGRAM_BOT_TOKEN": "bot"},
        )
        result = self.sync(plugins=["my-provider"])
        self.assertEqual(
            self.commands,
            [
                ("config", "set", "auxiliary.vision.provider", "local"),  # a route's provider first
                ("config", "set", "auxiliary.vision.key_env", "LOCAL_KEY"),
                ("config", "set", "delegation.provider", "openrouter"),
                ("config", "set", "delegation.model", "m2"),
                ("config", "set", "--force", "model", '{"default": "m1", "provider": "openrouter"}'),
                ("config", "set", "plugins.entries.my-provider.settings.region", "eu"),
                # A whole mapping, so a provider id with a dot stays one key.
                ("config", "set", "providers", json.dumps(providers)),
            ],
        )
        self.assertEqual(
            result["changed"],
            [
                "auxiliary.vision",
                "delegation",
                "model",
                "plugins.entries.my-provider.settings.region",
                "providers",
                "env:CUSTOM_KEY",
                "env:LOCAL_KEY",
                "env:OPENROUTER_API_KEY",
            ],
        )
        self.assertNotIn("max_iterations", read_config(self.studio)["delegation"])  # not part of the route
        self.assertEqual(read_env(self.studio), {"CUSTOM_KEY": "c", "LOCAL_KEY": "l", "OPENROUTER_API_KEY": "sk-1"})
        self.assertNotIn("sk-1", (self.studio / provider_sync.RECORD).read_text())

    def test_a_later_change_is_followed_and_one_made_in_the_studio_is_kept(self):
        write(
            self.source,
            config={"model": {"provider": "a"}, "delegation": {"provider": "a"}},
            env={"OPENROUTER_API_KEY": "k1"},
        )
        self.sync()
        self.assertTrue(provider_sync.is_current(self.source, self.studio))
        self.commands.clear()
        self.assertEqual(self.sync()["changed"], [])

        config = read_config(self.studio)
        config["model"] = {"provider": "mine"}  # chosen in the studio profile itself
        write(self.studio, config=config)
        write(
            self.source,
            config={"model": {"provider": "b"}, "delegation": {"provider": "b"}},
            env={"OPENROUTER_API_KEY": "k2"},
        )
        self.assertFalse(provider_sync.is_current(self.source, self.studio))
        result = self.sync()
        self.assertEqual((result["changed"], result["kept"]), (["delegation", "env:OPENROUTER_API_KEY"], ["model"]))
        self.assertEqual(read_config(self.studio)["model"], {"provider": "mine"})
        # Even once the installing profile happens to choose the same, the studio's choice stays the user's.
        write(self.source, config={"model": {"provider": "mine"}})
        self.sync()
        write(self.source, config={"model": {"provider": "c"}})
        self.assertIn("model", self.sync()["kept"])
        self.assertEqual(read_config(self.studio)["model"], {"provider": "mine"})

    def test_a_profile_made_before_the_sync_keeps_its_own_values_and_gains_the_missing_ones(self):
        write(self.studio, config={"model": {"provider": "mine"}}, env={"OPENROUTER_API_KEY": "own"})
        write(
            self.source,
            config={"model": {"provider": "a"}, "delegation": {"provider": "a"}},
            env={"OPENROUTER_API_KEY": "theirs"},
        )
        result = self.sync()
        self.assertEqual((result["changed"], result["kept"]), (["delegation"], ["env:OPENROUTER_API_KEY", "model"]))

    def test_what_the_installing_profile_drops_is_dropped_while_the_studio_kept_it_as_copied(self):
        write(self.source, config={"delegation": {"provider": "a", "model": "m"}}, env={"OPENROUTER_API_KEY": "k"})
        self.sync()
        write(self.source, config={}, env={})
        result = self.sync()
        self.assertEqual(result["changed"], ["delegation", "env:OPENROUTER_API_KEY"])
        self.assertEqual(read_config(self.studio)["delegation"], {})
        self.assertEqual(read_env(self.studio), {})

    def test_an_interrupted_sync_resumes_without_taking_its_own_writes_for_the_users(self):
        write(self.source, config={"model": {"provider": "a"}, "providers": {"p": {}}})
        calls = []

        def failing(*arguments):
            calls.append(arguments)
            if len(calls) == 2:
                raise RuntimeError("hermes failed")
            self.run_command(*arguments)

        with self.assertRaises(RuntimeError):
            provider_sync.sync(self.source, self.studio, failing, plugins=[])
        self.assertFalse(provider_sync.is_current(self.source, self.studio))
        result = self.sync()
        self.assertEqual((result["changed"], result["kept"]), (["providers"], []))


class ClaudeLogin(Profiles):
    """The studio profile gets a Claude login DirectSDK accepts, and follows the installing profile's."""

    def directsdk(self, settings=None, env=None):
        config = {"plugins": {"enabled": [DIRECTSDK], "entries": {DIRECTSDK: {"settings": settings or {}}}}}
        write(self.source, config=config, env=env or {})
        if not (self.studio / "config.yaml").exists():
            write(self.studio, config={"plugins": {"enabled": [DIRECTSDK]}})

    def sync(self, macos=False, environ=None, signed_in=True):
        options = {"macos": macos, "check": lambda **_login: signed_in}
        return super().sync(plugins=[DIRECTSDK], environ=environ or {}, login_options=options)

    def setting_commands(self):
        return [arguments for arguments in self.commands if claude_login.SETTING in arguments]

    def test_linux_uses_the_default_login_folder(self):
        self.directsdk()
        result = self.sync()
        self.assertEqual(
            self.setting_commands(), [("config", "set", claude_login.SETTING, str(Path.home() / ".claude"))]
        )
        self.assertEqual(result["claude_login"], {"provider": DIRECTSDK, "signed_in": True, "via": "folder"})

    def test_a_folder_the_installing_profile_names_is_used_as_written_on_both_systems(self):
        for macos in (False, True):
            with self.subTest(macos=macos):
                self.commands.clear()
                (self.studio / "config.yaml").unlink(missing_ok=True)
                (self.studio / provider_sync.RECORD).unlink(missing_ok=True)
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
        self.assertEqual(self.setting_commands(), [("config", "set", claude_login.SETTING, "/opt/claude")])

    def test_macos_with_the_default_login_asks_for_a_sign_in_of_its_own(self):
        # That login's Keychain entry is out of reach once any folder is named (claude_login's docstring).
        self.directsdk()
        result = self.sync(macos=True, signed_in=False)
        self.assertEqual(self.setting_commands(), [])
        self.assertEqual(result["claude_login"], {"provider": DIRECTSDK, "signed_in": False, "via": None})

    def test_a_token_is_copied_and_is_enough(self):
        self.directsdk(env={claude_login.TOKEN: "oat-1"})
        result = self.sync(macos=True)
        self.assertEqual((self.commands, self.env_writes), ([], [(claude_login.TOKEN, "oat-1")]))
        self.assertEqual(result["claude_login"], {"provider": DIRECTSDK, "signed_in": True, "via": "token"})

    def test_a_copied_folder_follows_the_installing_profile_and_the_studios_own_sign_in_stays(self):
        self.directsdk(settings={"claude_config_dir": "/old"})
        self.sync()
        self.directsdk(settings={"claude_config_dir": "/new"})
        self.sync()
        self.assertEqual(claude_login.setting(read_config(self.studio)), "/new")
        self.directsdk()  # back to Claude Code's default login, which a second profile cannot reach on macOS
        self.sync(macos=True, signed_in=False)
        self.assertEqual(claude_login.setting(read_config(self.studio)), "")

        config = read_config(self.studio)
        config["plugins"]["entries"][DIRECTSDK] = {"settings": {"claude_config_dir": "/studio/claude"}}  # sign_in's
        write(self.studio, config=config)
        self.directsdk(settings={"claude_config_dir": "/other"})
        self.assertIn("claude_config_dir", self.sync()["kept"])
        self.assertEqual(claude_login.setting(read_config(self.studio)), "/studio/claude")


if __name__ == "__main__":
    unittest.main()
