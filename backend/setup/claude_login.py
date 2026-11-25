"""The studio profile's Claude login, for the Claude Subscription DirectSDK provider plugin.

DirectSDK runs Claude Code, which keeps its login in a config directory: ``<dir>/.credentials.json`` on Linux, a
Keychain entry on macOS. The plugin refuses a profile other than the one Hermes was started for unless that profile
names its own login (its ``claude_config_dir`` setting, or ``CLAUDE_CODE_OAUTH_TOKEN`` in its .env), so the studio
profile is given the login of the profile hermretro was installed into.

On macOS Claude Code names the Keychain entry after the directory whenever ``CLAUDE_CONFIG_DIR`` is set, even to
``~/.claude``: a login made with it unset can only be reached with it unset, which the plugin never does for a second
profile. That case needs a login of the studio's own (``sign_in``).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import unicodedata
from pathlib import Path

from ..hermes import api as hermes_api
from ..system import host

PLUGIN = "claude-subscription-directsdk-experimental"
SETTING = f"plugins.entries.{PLUGIN}.settings.claude_config_dir"
TOKEN = "CLAUDE_CODE_OAUTH_TOKEN"
# The environment the plugin falls back to, in its own order, when the setting is empty.
_DIR_ENV = ("CLAUDE_SUBSCRIPTION_DIRECTSDK_CONFIG_DIR", "CLAUDE_CONFIG_DIR")
# The studio's own login folder, made by sign_in.
OWN_DIR = "claude"
_KEYCHAIN = "Claude Code-credentials"
_SIGN_IN_SECONDS = 600


def uses_plugin(config: dict) -> bool:
    return PLUGIN in (((config.get("plugins") or {}).get("enabled")) or [])


def setting(config: dict) -> str:
    entry = (((config.get("plugins") or {}).get("entries") or {}).get(PLUGIN) or {}).get("settings") or {}
    value = entry.get("claude_config_dir")
    return value.strip() if isinstance(value, str) else ""


def selected_dir(config: dict, environ) -> str | None:
    """The directory Claude Code would get for this profile, as the plugin picks it; None for Claude Code's default."""
    chosen = setting(config) or next((environ[name] for name in _DIR_ENV if (environ.get(name) or "").strip()), "")
    return os.path.expanduser(chosen) if chosen else None


def keychain_service(directory: str | None) -> str:
    """Claude Code's Keychain entry for a config directory (``None``: ``CLAUDE_CONFIG_DIR`` unset)."""
    if directory is None:
        return _KEYCHAIN
    digest = hashlib.sha256(unicodedata.normalize("NFC", directory).encode("utf-8")).hexdigest()
    return f"{_KEYCHAIN}-{digest[:8]}"


def _keychain_has(service: str) -> bool:
    """Whether the login Keychain has the entry. Asks for its attributes only, never the secret, so macOS shows no
    prompt."""
    try:
        done = subprocess.run(
            ["security", "find-generic-password", "-s", service],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def signed_in(directory: str | None, *, macos: bool | None = None, keychain=_keychain_has) -> bool:
    """Whether Claude Code has a login for this config directory. On macOS it falls back to the file when the Keychain
    cannot be used, so either counts there."""
    folder = Path(directory) if directory else Path.home() / ".claude"
    if (folder / ".credentials.json").is_file():
        return True
    return (host.MACOS if macos is None else macos) and keychain(keychain_service(directory))


def plan(source_config: dict, studio_config: dict, studio_env: dict, environ, *, macos: bool | None = None) -> dict:
    """What the studio profile's login should become: ``{"set": dir}`` to point it at a directory, ``{"keep": how}``
    when it already names its own, ``{"sign_in": True}`` when only a login of its own can work."""
    if (studio_env.get(TOKEN) or "").strip():
        return {"keep": "token"}
    if setting(studio_config):
        return {"keep": "folder"}
    chosen = selected_dir(source_config, environ)
    if chosen is not None:
        return {"set": chosen}
    if not (host.MACOS if macos is None else macos):
        return {"set": str(Path.home() / ".claude")}
    return {"sign_in": True}


def status(studio_config: dict, studio_env: dict, **options) -> dict:
    """For the page: whether the studio profile can sign in to Claude."""
    if (studio_env.get(TOKEN) or "").strip():
        return {"provider": PLUGIN, "signed_in": True, "via": "token"}
    chosen = setting(studio_config)
    if not chosen:
        return {"provider": PLUGIN, "signed_in": False, "via": None}
    return {"provider": PLUGIN, "signed_in": signed_in(os.path.expanduser(chosen), **options), "via": "folder"}


def state(studio_home: Path) -> dict | None:
    """``status`` of the studio profile when it uses DirectSDK; None when it does not, or with no Hermes to read it."""
    try:
        config = hermes_api.read_profile_config(studio_home)
        if not uses_plugin(config):
            return None
        return status(config, hermes_api.read_profile_env(studio_home))
    except Exception:  # noqa: BLE001 - no Hermes here (tests, the broker) or an unreadable profile: unknown
        return None


def claude_command() -> str | None:
    """Claude Code, as the plugin finds it: its command setting's variable, PATH, then the usual install folders (an
    app started from the Dock or a desktop launcher gets a bare PATH)."""
    chosen = os.environ.get("CLAUDE_SUBSCRIPTION_DIRECTSDK_COMMAND")
    if chosen:
        return chosen
    found = shutil.which("claude")
    if found:
        return found
    for folder in (Path.home() / ".local" / "bin", Path("/opt/homebrew/bin"), Path("/usr/local/bin")):
        if (folder / "claude").is_file():
            return str(folder / "claude")
    return None


def sign_in(studio_home: Path, *, run=subprocess.run, command=claude_command) -> str:
    """Make the studio profile a Claude login of its own: Claude Code's sign-in, in the browser, into the studio's own
    folder. Answers the folder; raises ``SignInError`` when there is no login afterwards."""
    executable = command()
    if executable is None:
        raise SignInError("CLAUDE_NOT_FOUND", "Claude Code is not installed, so there is nothing to sign in with.")
    folder = studio_home / OWN_DIR
    folder.mkdir(mode=0o700, exist_ok=True)
    try:
        done = run(
            [executable, "auth", "login", "--claudeai"],
            env={**os.environ, "CLAUDE_CONFIG_DIR": str(folder)},
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=_SIGN_IN_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise SignInError("SIGN_IN_TIMEOUT", "The Claude sign-in was not finished in time.") from error
    except OSError as error:
        raise SignInError("SIGN_IN_FAILED", f"Claude Code could not be started ({error.strerror or error}).") from error
    if done.returncode != 0 or not signed_in(str(folder)):
        tail = (done.stderr or done.stdout or "").strip().splitlines()[-1:]
        raise SignInError("SIGN_IN_FAILED", " ".join(["The Claude sign-in did not finish.", *tail]))
    return str(folder)


class SignInError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
