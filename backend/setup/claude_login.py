"""The studio profile's Claude login, for the Claude Subscription DirectSDK provider plugin.

DirectSDK runs Claude Code, which keeps its login in a config directory: ``<dir>/.credentials.json`` on Linux, a
Keychain entry on macOS. The plugin refuses a profile other than the one Hermes was started for unless that profile
names its own login (its ``claude_config_dir`` setting, or ``CLAUDE_CODE_OAUTH_TOKEN`` in its .env), so the studio
profile is given the login of the profile hermretro was installed into (``inherited_dir``).

On macOS Claude Code names the Keychain entry after the directory whenever ``CLAUDE_CONFIG_DIR`` is set
(``Claude Code-credentials-<first 8 hex digits of its SHA-256>``), even to ``~/.claude``: a login made with it unset
(``Claude Code-credentials``) can only be reached with it unset, which the plugin never does for a second profile.
That case needs a login of the studio's own (``sign_in``). Whether a login works is asked of Claude Code itself
(``claude auth status``), which reads the file or the Keychain as it will when the plugin runs it.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from ..hermes import api as hermes_api
from ..system import host

PLUGIN = "claude-subscription-directsdk-experimental"
SETTING = f"plugins.entries.{PLUGIN}.settings.claude_config_dir"
TOKEN = "CLAUDE_CODE_OAUTH_TOKEN"
# The environment the plugin falls back to, in its own order, when the setting is empty.
_DIR_ENV = ("CLAUDE_SUBSCRIPTION_DIRECTSDK_CONFIG_DIR", "CLAUDE_CONFIG_DIR")
# What would make Claude Code answer for a login other than the one asked about: an API key, another backend, another
# folder. The plugin refuses or replaces the same ones.
_NOT_THIS_LOGIN = (
    *_DIR_ENV,
    TOKEN,
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
)
# The studio's own login folder, made by sign_in.
OWN_DIR = "claude"
_SIGN_IN_SECONDS = 600
# The Setup page asks for the status often; Claude Code is asked at most this often per login.
_CHECK_SECONDS = 60
_checked: dict = {}


def uses_plugin(config: dict) -> bool:
    return PLUGIN in (((config.get("plugins") or {}).get("enabled")) or [])


def setting(config: dict) -> str:
    entry = (((config.get("plugins") or {}).get("entries") or {}).get(PLUGIN) or {}).get("settings") or {}
    value = entry.get("claude_config_dir")
    return value.strip() if isinstance(value, str) else ""


def inherited_dir(source_config: dict, environ, *, macos: bool | None = None) -> str | None:
    """The login folder the studio profile can share with the installing profile, as the plugin would pick it there
    (its setting, then the environment); with Claude Code's default login, ``~/.claude`` on Linux and None on macOS
    (out of reach: the module's docstring)."""
    chosen = setting(source_config) or next(
        (environ[name].strip() for name in _DIR_ENV if (environ.get(name) or "").strip()), ""
    )
    if chosen:
        return os.path.expanduser(chosen)
    return None if (host.MACOS if macos is None else macos) else str(Path.home() / ".claude")


def claude_command() -> str | None:
    """Claude Code, as the plugin finds it: its command variable, PATH, then the usual install folders (an app started
    from the Dock or a desktop launcher gets a bare PATH)."""
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


def _environment(*, token: str | None = None, folder: str | None = None) -> dict:
    environment = {name: value for name, value in os.environ.items() if name not in _NOT_THIS_LOGIN}
    if token:
        environment[TOKEN] = token
    if folder:
        environment["CLAUDE_CONFIG_DIR"] = folder
    return environment


def logged_in(
    *, token: str | None = None, folder: str | None = None, run=subprocess.run, command=claude_command
) -> bool:
    """Whether Claude Code has a subscription login with this token or in this folder (`claude auth status`)."""
    key = (hashlib.sha256((token or "").encode("utf-8")).hexdigest(), folder)
    cached = _checked.get(key)
    if cached is not None and time.monotonic() - cached[0] < _CHECK_SECONDS:
        return cached[1]
    executable = command()
    answer = False
    if executable is not None:
        try:
            done = run(
                [executable, "auth", "status", "--json"],
                env=_environment(token=token, folder=folder),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=30,
            )
            report = json.loads(done.stdout or "{}")
            answer = bool(report.get("loggedIn")) and report.get("apiProvider", "firstParty") == "firstParty"
        except (OSError, subprocess.TimeoutExpired, ValueError, AttributeError):
            answer = False
    _checked[key] = (time.monotonic(), answer)
    return answer


def status(config: dict, env: dict, *, check=None) -> dict:
    """For the page: whether the studio profile can sign in to Claude, and how."""
    token = (env.get(TOKEN) or "").strip() or None
    folder = setting(config)
    if not token and not folder:
        return {"provider": PLUGIN, "signed_in": False, "via": None}
    asked = (check or logged_in)(token=token, folder=None if token else os.path.expanduser(folder))
    return {"provider": PLUGIN, "signed_in": asked, "via": "token" if token else "folder"}


def state(studio_home: Path) -> dict | None:
    """``status`` of the studio profile when it uses DirectSDK; None when it does not, or with no Hermes to read it."""
    try:
        config = hermes_api.read_profile_config(studio_home)
        if not uses_plugin(config):
            return None
        return status(config, hermes_api.read_profile_env(studio_home))
    except Exception:  # noqa: BLE001 - no Hermes here (tests, the broker) or an unreadable profile: unknown
        return None


def sign_in(studio_home: Path, *, run=subprocess.run, command=claude_command, check=None) -> str:
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
            env=_environment(folder=str(folder)),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=_SIGN_IN_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise SignInError("SIGN_IN_TIMEOUT", "The Claude sign-in was not finished in time.") from error
    except OSError as error:
        raise SignInError("SIGN_IN_FAILED", f"Claude Code could not be started ({error.strerror or error}).") from error
    _checked.clear()
    if done.returncode != 0 or not (check or logged_in)(folder=str(folder)):
        tail = (done.stderr or done.stdout or "").strip().splitlines()[-1:]
        raise SignInError("SIGN_IN_FAILED", " ".join(["The Claude sign-in did not finish.", *tail]))
    return str(folder)


class SignInError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
