"""The dedicated hermretro profile.

The plugin is installed into whatever profile the user was on. The page then offers one step,
"Create the hermretro profile": the desktop creates the profile with Hermes's own
``profiles.create`` (which shares the user's sign-in and keys), and ``finish`` below makes that
profile a Chromatic one: the plugin linked in and switched on, the user's model-provider plugins
carried over, the unwanted toolsets off, no Hermes default skills except hermes-agent, and the
studio's SOUL in place.

Config is only ever changed through the ``hermes`` command with HERMES_HOME pointing at the new
profile, never by editing its config.yaml here. The profile the plugin was installed into is not
modified at all.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import hermes_api, paths

STUDIO_PROFILE = "hermretro"
DESCRIPTION = "hermretro: Game Boy Color development for the ModRetro Chromatic"
# Toolsets the studio profile does without. Everything else keeps Hermes's defaults.
DISABLED_TOOLSETS = ("tts", "connections", "computer_use", "cronjob")
SOUL_FILE = paths.PLUGIN_ROOT / "profile" / "SOUL.md"
# SHA-256 of every SOUL.md this plugin shipped before the current one. A profile whose SOUL is still
# exactly one of these was never edited by the user, so finishing the profile again updates it.
OLDER_SOULS = frozenset({"27585f72bfd4de1c745b0ba4df21b891577fb3a7eeb3c3faf5ca84314056e385",
                         "5f6b61c41f1be0c5c691243dbd176dd5ff13da82fdf6be432c37ddde3ac67cb3"})
MARKER = Path("plugin-data") / paths.PLUGIN_ID / "studio-profile.json"
# The profile's own empty working folder: new chats in the profile start here (terminal.cwd).
WORKSPACE = "workspace"


class StudioProfileError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def profile_name(home: Path) -> str:
    return home.name if home.parent.name == "profiles" else "default"


def is_studio(name: str | None) -> bool:
    """Whether the plugin's tools, skills, hooks and prompt belong in this profile: only the studio
    profile, unless ``HERMRETRO_EVERY_PROFILE=1`` (plugin development only, never for users)."""
    return name == STUDIO_PROFILE or os.environ.get("HERMRETRO_EVERY_PROFILE") == "1"


def studio_dir() -> Path:
    return hermes_api.profile_dir(STUDIO_PROFILE)


def create_params() -> dict:
    """What the page passes to Hermes's ``profiles.create``."""
    return {"name": STUDIO_PROFILE, "description": DESCRIPTION, "no_skills": True, "share_auth": True,
            "no_alias": True}


def _exists(target: Path) -> bool:
    return target.is_dir() and any((target / name).exists() for name in ("config.yaml", "profile.yaml", "SOUL.md"))


def _ours(target: Path) -> bool:
    if (target / MARKER).is_file():
        return True
    try:
        text = (target / "profile.yaml").read_text(encoding="utf-8")
    except OSError:
        return False
    return DESCRIPTION in text


def _has_plugin(target: Path) -> bool:
    return (target / "plugins" / paths.PLUGIN_ID / "plugin.yaml").is_file()


def _ready(target: Path) -> bool:
    """Finished, not merely linked: the marker is written last, after every command succeeded."""
    return _has_plugin(target) and (target / MARKER).is_file()


def describe(home: Path, target: Path | None = None) -> dict:
    """For the page: which profile is answering, and the state of the studio profile."""
    name = profile_name(home)
    if name == STUDIO_PROFILE:
        return {"name": name, "is_studio": True,
                "studio": {"name": STUDIO_PROFILE, "exists": True, "installed": True, "ours": True}}
    target = target or studio_dir()
    exists = _exists(target)
    return {"name": name, "is_studio": False,
            "studio": {"name": STUDIO_PROFILE, "exists": exists, "installed": exists and _ready(target),
                       "ours": exists and _ours(target)},
            "create": create_params()}


def _provider_plugins(home: Path, enabled: list[str]) -> list[Path]:
    """Model-provider plugins that are on in the profile the plugin was installed into. Without
    them the new profile could not use the model the user works with."""
    found = []
    for name in enabled:
        folder = home / "plugins" / str(name)
        try:
            manifest = (folder / "plugin.yaml").read_text(encoding="utf-8")
        except OSError:
            continue
        if re.search(r"^kind:\s*[\"']?model-provider[\"']?\s*$", manifest, re.MULTILINE):
            found.append(folder)
    return found


def _enabled_plugins() -> list[str]:
    return hermes_api.enabled_plugins()


def _link(source: Path, destination: Path) -> str:
    source = source.resolve()
    if destination.is_symlink() or destination.exists():
        if destination.resolve() == source:
            return "linked"
        if (destination / "plugin.yaml").is_file():
            return "own copy"      # installed there for real; leave it
        raise StudioProfileError("LINK_BLOCKED", f"{destination} exists and is not this plugin.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(source, destination, target_is_directory=True)
    except OSError as error:
        raise StudioProfileError(
            "LINK_FAILED", "Hermes could not link the plugin into the new profile on this system "
                           f"({error.strerror or error}).") from error
    return "linked"


def _hermes_command() -> list[str]:
    found = shutil.which("hermes")
    return [found] if found else [sys.executable, "-m", "hermes_cli.main"]


def _run_hermes(target: Path, *arguments: str) -> None:
    environment = {**os.environ, "HERMES_HOME": str(target)}
    try:
        done = subprocess.run([*_hermes_command(), *arguments], env=environment, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise StudioProfileError(
            "HERMES_COMMAND_FAILED", f"`hermes {' '.join(arguments[:2])}` could not be run in the new profile "
                                     f"({type(error).__name__}).") from error
    if done.returncode != 0:
        tail = (done.stderr or done.stdout or "").strip().splitlines()[-3:]
        raise StudioProfileError("HERMES_COMMAND_FAILED",
                                 f"`hermes {' '.join(arguments[:2])}` failed in the new profile: " + " ".join(tail))


def finish(home: Path, *, target: Path | None = None, enabled: list[str] | None = None, run=_run_hermes) -> dict:
    """Make the freshly created studio profile a Chromatic one. Safe to run again."""
    if profile_name(home) == STUDIO_PROFILE:
        return {"ok": True, "profile": STUDIO_PROFILE, "already": True}
    target = target or studio_dir()
    if not _exists(target):
        raise StudioProfileError("NOT_CREATED", "The hermretro profile has not been created yet.")
    if not (_ours(target) or _has_plugin(target)):
        raise StudioProfileError(
            "NAME_TAKEN", f"A profile named {STUDIO_PROFILE} already exists and was not made by Chromatic "
                          "Studio. Rename or remove it, then try again.")

    plugin = _link(paths.PLUGIN_ROOT, target / "plugins" / paths.PLUGIN_ID)
    providers = []
    for folder in _provider_plugins(home, _enabled_plugins() if enabled is None else enabled):
        _link(folder, target / "plugins" / folder.name)
        providers.append(folder.name)

    for name in (paths.PLUGIN_ID, *providers):
        run(target, "plugins", "enable", name)
    run(target, "config", "set", "agent.disabled_toolsets", json.dumps(list(DISABLED_TOOLSETS)))
    # No Hermes default skills, only the essential hermes-agent one (Hermes always keeps it) and the
    # plugin's own. The profile is created with no_skills; this keeps `hermes update` from seeding
    # them later even when the profile was made some other way. Nothing on disk is deleted.
    run(target, "skills", "opt-out")
    # No automatic post-turn self-improvement review: it would write its own skills and memories next
    # to the plugin's (`/refine` still works on request).
    run(target, "config", "set", "auxiliary.background_review.enabled", "false")
    run(target, "config", "set", "curator.enabled", "false")  # nor the weekly skill curator
    # Pinned, not inherited: the approval prompt before anything touches the Chromatic only appears
    # while approvals are on.
    run(target, "config", "set", "approvals.mode", "smart")
    # Every chat in the profile opens in its own workspace folder (an absolute, existing directory is
    # what Hermes accepts as terminal.cwd). Games themselves still go in the plugin's games folder.
    workspace = target / WORKSPACE
    workspace.mkdir(parents=True, exist_ok=True)
    run(target, "config", "set", "terminal.cwd", str(workspace.resolve()))

    marker = target / MARKER
    first_time = not marker.is_file()
    soul = target / "SOUL.md"
    try:
        unedited = hashlib.sha256(soul.read_bytes()).hexdigest() in OLDER_SOULS
    except OSError:
        unedited = False
    write_soul = first_time or unedited  # never overwrite a SOUL the user has since edited
    if write_soul:
        soul.write_text(SOUL_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"made_by": paths.PLUGIN_ID, "version": paths.PLUGIN_VERSION,
                                  "from_profile": profile_name(home), "at": int(time.time())}), encoding="utf-8")
    return {"ok": True, "profile": STUDIO_PROFILE, "plugin": plugin, "providers": providers,
            "disabled_toolsets": list(DISABLED_TOOLSETS), "soul_written": write_soul,
            "workspace": str(workspace.resolve())}
