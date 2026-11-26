"""The dedicated hermretro profile.

The studio profile is prepared in a private directory, with its initial settings and SOUL in
place, before Hermes or the user can see it. Existing profiles keep their own turn limit and SOUL
edits. Only Hermes config commands write the studio's config.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

from ..hermes import api as hermes_api
from ..system import paths
from . import claude_login, profile_publication, provider_sync

STUDIO_PROFILE = "hermretro"
DESCRIPTION = "hermretro: Game Boy Color development for the ModRetro Chromatic"
# Toolsets the studio profile does without. Everything else keeps Hermes's defaults. code_execution: one-shot chats
# refuse execute_code (nobody is there to approve it) and the chromatic_* tools refuse calls from inside it, so helper
# code runs from a script file in the game's scratch/ folder.
DISABLED_TOOLSETS = ("tts", "connections", "computer_use", "cronjob", "code_execution")
# The profile's marker records the disabled_toolsets the plugin gave it; one from before it did stands for these.
# A profile that still has exactly that list gets this release's when the plugin registers in it
# (refresh_disabled_toolsets); any other list, or none, is the user's.
OLDER_DISABLED_TOOLSETS = frozenset({frozenset({"tts", "connections", "computer_use", "cronjob"})})
SOUL_FILE = paths.PLUGIN_ROOT / "profile" / "SOUL.md"
# SHA-256 of every SOUL.md this plugin shipped before the current one. A profile whose SOUL is still
# exactly one of these was never edited by the user, so it is updated (refresh_soul).
OLDER_SOULS = frozenset(
    {
        "4a5f6954d64a86470419d70d67340d0e0d551aaae10a21bfd24a8d6a241ad1c5",
        "27585f72bfd4de1c745b0ba4df21b891577fb3a7eeb3c3faf5ca84314056e385",
        "5f6b61c41f1be0c5c691243dbd176dd5ff13da82fdf6be432c37ddde3ac67cb3",
        "0d723cea8a6bb62e7819d0a371a802a4481895b1c9de751f8e32ff859ce01218",
        "fc761b6efa1d664e24b9e444be7732b7a42a4b6e985f9b43a48984e25d494749",
    }
)
MARKER = Path("plugin-data") / paths.PLUGIN_ID / "studio-profile.json"
TURN_LIMIT = 1000
# Studio chats grow fast (builds, emulator steps, frames): Hermes compacts them by this many tokens of context at the
# latest (compression.threshold_tokens is a cap: its ratio or the summarizer's window can come first). Set where the
# profile has none or one an earlier release set (OLDER_COMPACT_AT): when it is made or repaired, and when the plugin
# registers in it (refresh_compaction_cap). Any other value, null included (the ratio alone decides), is the user's.
COMPACT_AT_TOKENS = 300_000
OLDER_COMPACT_AT = frozenset({200_000})
# The profile's own empty working folder: new chats in the profile start here (terminal.cwd).
WORKSPACE = "workspace"


def refresh_soul(profile_home: Path) -> bool:
    """Put the shipped SOUL in place of one an earlier release shipped (never one the user has edited, nor a link),
    so the studio profile gets each release's SOUL however the plugin was updated: through the page, with
    ``hermes plugins update`` or as a linked checkout. Answers whether it was written; a failed write raises
    OSError."""
    soul = profile_home / "SOUL.md"
    return _replace_soul(soul, _shipped_before)


def compaction_cap_due(compression) -> bool:
    """Whether a profile's raw ``compression`` section gets ``COMPACT_AT_TOKENS``: it has no ``threshold_tokens`` (an
    explicit null is kept) or one an earlier release set."""
    if compression is None:
        return True
    if not isinstance(compression, dict):
        return False
    if "threshold_tokens" not in compression:
        return True
    cap = compression["threshold_tokens"]
    return isinstance(cap, int) and not isinstance(cap, bool) and cap in OLDER_COMPACT_AT


def refresh_compaction_cap(profile_home: Path) -> bool:
    """Set the compaction cap in the studio profile's config where ``compaction_cap_due``, so the profile gets each
    release's cap however the plugin was updated, as ``refresh_soul`` does the SOUL. Answers whether it was
    written."""
    return _update_config(
        profile_home,
        "compression.threshold_tokens",
        COMPACT_AT_TOKENS,
        lambda config: compaction_cap_due(config.get("compression")),
    )


def _toolset_names(value) -> frozenset[str] | None:
    """A raw ``agent.disabled_toolsets`` as a set of names: Hermes keeps a list or, from ``config set``, its JSON."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if not isinstance(value, list) or not all(isinstance(name, str) for name in value):
        return None
    return frozenset(value)


def refresh_disabled_toolsets(profile_home: Path) -> bool:
    """Put ``DISABLED_TOOLSETS`` in place of the list the plugin gave the profile before, as ``refresh_compaction_cap``
    does the cap, at most once: the marker records the list given (by creation, repair or this), so a list the user
    sets afterwards stays theirs, an earlier release's included. Answers whether it was written."""
    marker = _read_marker(profile_home)
    if marker is None:
        return False
    given = _toolset_names(marker.get("disabled_toolsets"))
    if given == frozenset(DISABLED_TOOLSETS):
        return False
    givens = OLDER_DISABLED_TOOLSETS if given is None else {given}

    def due(config: dict) -> bool:
        agent = config.get("agent")
        return isinstance(agent, dict) and _toolset_names(agent.get("disabled_toolsets")) in givens

    if not _update_config(profile_home, "agent.disabled_toolsets", list(DISABLED_TOOLSETS), due):
        return False
    paths.write_json_atomic(
        profile_home / MARKER, {**marker, "disabled_toolsets": list(DISABLED_TOOLSETS)}, indent=None
    )
    return True


def _update_config(profile_home: Path, key: str, value, due: Callable[[dict], bool]) -> bool:
    """Set one dotted ``key`` in the profile's config.yaml where ``due`` holds for the config as written. Never through
    a link (Hermes would write its target, maybe another profile's config) nor over a change made meanwhile: Hermes
    has no lock on the file, so it is read again just before the write and, if it changed, left for the next time."""
    read = hermes_api.read_profile_config(profile_home)
    if not due(read):
        return False
    if hermes_api.read_profile_config(profile_home) != read or (profile_home / "config.yaml").is_symlink():
        return False
    hermes_api.write_profile_config_key(profile_home, key, value)
    return True


def _read_marker(profile_home: Path) -> dict | None:
    try:
        marker = json.loads((profile_home / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return marker if isinstance(marker, dict) else None


def _read_soul(soul: str | Path, directory: int | None = None) -> bytes | None:
    """Read a plain SOUL file without following a link or waiting on a pipe."""
    try:
        handle = os.open(soul, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=directory)
    except OSError:
        return None
    with os.fdopen(handle, "rb") as reader:
        try:
            if stat.S_ISREG(os.fstat(reader.fileno()).st_mode):
                return reader.read()
        except OSError:
            pass
    return None


def _shipped_before(soul: Path) -> bool:
    data = _read_soul(soul)
    return data is not None and hashlib.sha256(data).hexdigest() in OLDER_SOULS


def _replace_soul(soul: Path, can_replace: Callable[[Path], bool]) -> bool:
    """Replace a matching SOUL atomically, keeping its mode and rechecking before the swap."""
    if not can_replace(soul):
        return False
    try:
        mode = stat.S_IMODE(soul.stat().st_mode)
    except OSError:
        mode = 0o644  # a new file, readable as one written the usual way
    handle, partial = tempfile.mkstemp(dir=soul.parent, prefix=".SOUL.md.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as writer:
            writer.write(SOUL_FILE.read_bytes())
        os.chmod(partial, mode)
        if not can_replace(soul):
            Path(partial).unlink()
            return False
        os.replace(partial, soul)
    except BaseException:
        Path(partial).unlink(missing_ok=True)
        raise
    return True


class StudioProfileError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def profile_name(home: Path) -> str:
    return home.name if home.parent.name == "profiles" else "default"


def installed_in(root: Path | None = None) -> dict:
    """Where this copy of the plugin is installed: ``{"profile": name, "linked": False}`` for a copy Hermes installed
    into ``<home>/plugins/`` (the profile that updates it), ``{"profile": None, "linked": True}`` for a checkout linked
    in from elsewhere (Hermes does not update those). The studio profile only links that copy, so the path is resolved."""
    root = (root or paths.PLUGIN_ROOT).resolve()
    if root.parent.name != "plugins":
        return {"profile": None, "linked": True}
    return {"profile": profile_name(root.parent.parent), "linked": False}


def is_studio(name: str | None) -> bool:
    """Whether the plugin's tools, skills, hooks and prompt belong in this profile: only the studio
    profile, unless ``HERMRETRO_EVERY_PROFILE=1`` (plugin development only, never for users)."""
    return name == STUDIO_PROFILE or os.environ.get("HERMRETRO_EVERY_PROFILE") == "1"


def studio_dir() -> Path:
    return hermes_api.profile_dir(STUDIO_PROFILE)


def _exists(target: Path) -> bool:
    return not target.is_symlink() and target.is_dir() and hermes_api.profile_has_identity(target)


def _ours(target: Path) -> bool:
    if (target / MARKER).is_file():
        return True
    try:
        text = (target / "profile.yaml").read_text(encoding="utf-8")
    except OSError:
        return False
    return DESCRIPTION in text


def studio_is_ours() -> bool:
    """Whether the profile named ``hermretro`` is the one this plugin made (never a profile of the user's own that
    happens to have the name)."""
    target = studio_dir()
    return _exists(target) and not hermes_api.profile_is_deleted(target) and _ours(target)


def _has_plugin(target: Path) -> bool:
    return (target / "plugins" / paths.PLUGIN_ID / "plugin.yaml").is_file()


def is_finished(target: Path) -> bool:
    """Finished, not merely linked: the marker is written last, after every command succeeded."""
    return _has_plugin(target) and (target / MARKER).is_file()


def _can_resume(target: Path) -> bool:
    try:
        with profile_publication.profiles_directory(target) as (target, profiles):
            entry = profile_publication.profile_entry(target, profiles)
            return (
                entry is not None
                and stat.S_ISDIR(entry.st_mode)
                and is_finished(target)
                and profile_publication.Tombstone(target, profiles).matches_receipt(entry)
            )
    except OSError:
        return False


def describe(home: Path, target: Path | None = None) -> dict:
    """For the page: which profile is answering, and the state of the studio profile."""
    name = profile_name(home)
    if name == STUDIO_PROFILE:
        return {
            "name": name,
            "is_studio": True,
            "studio": {
                "name": STUDIO_PROFILE,
                "exists": True,
                "installed": True,
                "ours": True,
                "claude_login": claude_login.state(home),
            },
        }
    target = target or studio_dir()
    exists = _exists(target)
    deleted = exists and hermes_api.profile_is_deleted(target)
    resumable = deleted and _can_resume(target)
    ours = resumable or (exists and not deleted and _ours(target))
    return {
        "name": name,
        "is_studio": False,
        "studio": {
            "name": STUDIO_PROFILE,
            "exists": exists,
            "installed": exists and not deleted and is_finished(target),
            "ours": ours,
            # Someone else's profile has the name: finishing it would be refused (NAME_TAKEN), so the page says so
            # before it downloads anything.
            "conflict": exists and not resumable and (deleted or (not ours and not _has_plugin(target))),
            "claude_login": claude_login.state(target) if exists and not deleted and is_finished(target) else None,
        },
    }


def provider_plugins(home: Path, enabled: list[str]) -> list[Path]:
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
            return "own copy"  # installed there for real; leave it
        raise StudioProfileError("LINK_BLOCKED", f"{destination} exists and is not this plugin.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(source, destination, target_is_directory=True)
    except OSError as error:
        raise StudioProfileError(
            "LINK_FAILED",
            f"Hermes could not link the plugin into the new profile on this system ({error.strerror or error}).",
        ) from error
    return "linked"


def link_providers(home: Path, target: Path, enabled: list[str], run, *, check=lambda: None) -> list[str]:
    """Link the installing profile's model-provider plugins into the studio profile; answers their names. A copy
    Hermes installed into the studio profile on its own drifts from the installing profile's version, so it is replaced
    by the link, keeping the studio's own settings for it (removing a plugin drops them)."""
    providers = []
    for folder in provider_plugins(home, enabled):
        check()
        destination = target / "plugins" / folder.name
        if _link(folder, destination) == "own copy" and _installed_by_hermes(target, folder.name):
            entry = ((hermes_api.read_profile_config(target).get("plugins") or {}).get("entries") or {}).get(
                folder.name
            )
            run("plugins", "remove", folder.name)
            _link(folder, destination)
            if entry:
                run("config", "set", f"plugins.entries.{folder.name}", json.dumps(entry))
        providers.append(folder.name)
    return providers


def _installed_by_hermes(profile_home: Path, name: str) -> bool:
    try:
        installed = json.loads((profile_home / "plugins" / ".install-metadata.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(installed, dict) and name in installed


def _hermes_command() -> list[str]:
    found = shutil.which("hermes")
    return [found] if found else [sys.executable, "-m", "hermes_cli.main"]


def run_hermes(target: Path, *arguments: str) -> None:
    environment = {**os.environ, "HERMES_HOME": str(target)}
    try:
        done = subprocess.run(
            [*_hermes_command(), *arguments],
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise StudioProfileError(
            "HERMES_COMMAND_FAILED",
            f"`hermes {' '.join(arguments[:2])}` could not be run in the new profile ({type(error).__name__}).",
        ) from error
    if done.returncode != 0:
        tail = (done.stderr or done.stdout or "").strip().splitlines()[-3:]
        raise StudioProfileError(
            "HERMES_COMMAND_FAILED", f"`hermes {' '.join(arguments[:2])}` failed in the new profile: " + " ".join(tail)
        )


# One finish at a time in this process: the install, Setup's button, Build's Repair and the in-app update can all
# ask at once, and the hermes config commands must never run concurrently on one profile. A call made while
# another runs waits for it and shares its answer (or its error) instead of running every command again.
_finishing = threading.Lock()
_flight: dict = {}


def finish(home: Path, **options) -> dict:
    """Make the studio profile a Chromatic one. Concurrent calls in this process share the result."""
    with _finishing:
        flight = _flight.get("current")
        leader = flight is None
        if leader:
            flight = _flight["current"] = {"done": threading.Event()}
    if not leader:
        flight["done"].wait()
        if "error" in flight:
            raise flight["error"]
        return {**flight["answer"], "shared": True}
    try:
        flight["answer"] = _finish(home, **options)
        return flight["answer"]
    except BaseException as error:
        flight["error"] = error
        raise
    finally:
        with _finishing:
            _flight.pop("current", None)
        flight["done"].set()


def _finish(
    home: Path, *, target: Path | None = None, enabled: list[str] | None = None, run=run_hermes, create: bool = False
) -> dict:
    if profile_name(home) == STUDIO_PROFILE:
        return {"ok": True, "profile": STUDIO_PROFILE, "already": True}
    target = target or studio_dir()
    if create:
        target.parent.mkdir(parents=True, exist_ok=True)
    elif not target.parent.is_dir():
        raise _not_created()
    try:
        with profile_publication.profiles_directory(target) as (pinned, profiles):
            expected = profile_publication.profile_entry(pinned, profiles) if not create else None
            profile_publication.lock_profiles(profiles)
            if not create:
                profile_publication.require_entry(pinned, profiles, expected)

            def run_in_profile(directory, *args):
                # Hermes uses the lexical profiles/ parent to find the shared Hermes root.
                profile_publication.require_profiles_directory(target.parent, profiles, follow_symlinks=True)
                run(target.parent / directory.name, *args)

            return _finish_locked(home, pinned, enabled, run_in_profile, create, profiles)
    except FileExistsError:
        raise _name_taken() from None


def _finish_locked(home: Path, target: Path, enabled: list[str] | None, run, create: bool, profiles: int) -> dict:
    expected = profile_publication.profile_entry(target, profiles)
    deleted = profile_publication.Tombstone(target, profiles)
    if expected is not None and not stat.S_ISDIR(expected.st_mode):
        raise _name_taken()
    exists = expected is not None and hermes_api.profile_has_identity(target)
    profile_publication.require_entry(target, profiles, expected)
    if not exists:
        if not create:
            raise _not_created()
        return _create(home, target, enabled, run, profiles, deleted)

    ready = is_finished(target)
    if deleted.identity is not None:
        if not ready or not deleted.matches_receipt(expected):
            raise _name_taken()
        deleted.clear(expected)
        hermes_api.notify_profile_created(target)
        return {"ok": True, "profile": STUDIO_PROFILE, "already": True}

    with profile_publication.open_profile(target, profiles, expected) as directory:

        def check():
            profile_publication.require_entry(target, profiles, expected)
            deleted.check()
            if not hermes_api.profile_has_identity(target) or not (_ours(target) or _has_plugin(target)):
                raise _name_taken()

        check()
        if create and ready:
            return {"ok": True, "profile": STUDIO_PROFILE, "already": True}
        soul = target / "SOUL.md"
        keep_missing = not os.path.lexists(soul)
        try:
            return _configure(home, target, enabled, run, workspace=(target / WORKSPACE).resolve(), check=check)
        finally:
            # Every CLI subprocess can seed Hermes's own SOUL while initializing its home.
            if keep_missing and (seed := hermes_api.default_soul()) is not None:
                profile_publication.discard_generated_file(
                    soul, directory, lambda path, parent: _read_soul(path, parent) == seed
                )


def _not_created() -> StudioProfileError:
    return StudioProfileError("NOT_CREATED", "The hermretro profile has not been created yet.")


def _name_taken() -> StudioProfileError:
    return StudioProfileError(
        "NAME_TAKEN",
        f"A profile named {STUDIO_PROFILE} already exists and was not made by Chromatic "
        "Studio. Rename or remove it, then try again.",
    )


def _create(
    home: Path, target: Path, enabled: list[str] | None, run, profiles: int, deleted: profile_publication.Tombstone
) -> dict:
    # A leftover can have its own workspace link. Start fresh chat in the new profile itself.
    workspace = target / WORKSPACE
    expected = profile_publication.creation_candidate(target, profiles, deleted)
    # Hermes ignores dot-prefixed directories. Publish the preferences and finish marker
    # together so a retry can tell a cleared setting from an unseeded one.
    with tempfile.TemporaryDirectory(dir=target.parent, prefix=f".{target.name}-") as directory:
        staging = Path(directory)
        hermes_api.prepare_profile(staging, description=DESCRIPTION, soul=SOUL_FILE.read_text(encoding="utf-8"))
        run(staging, "config", "set", "agent.max_turns", str(TURN_LIMIT))
        answer = _configure(home, staging, enabled, run, workspace=workspace)
        deleted.record(staging)
        profile_publication.publish(staging, target, expected, profiles, deleted)
    hermes_api.notify_profile_created(target)
    return {**answer, "soul_written": True}


def _configure(
    home: Path, target: Path, enabled: list[str] | None, run, *, workspace: Path, check=lambda: None
) -> dict:
    def configure(*args):
        check()
        run(target, *args)

    check()
    plugin = _link(paths.PLUGIN_ROOT, target / "plugins" / paths.PLUGIN_ID)
    providers = link_providers(home, target, _enabled_plugins() if enabled is None else enabled, configure, check=check)
    for name in (paths.PLUGIN_ID, *providers):
        configure("plugins", "enable", name)
    with provider_sync.lock:
        synced = provider_sync.sync(home, target, configure, plugins=providers)
    configure("config", "set", "agent.disabled_toolsets", json.dumps(list(DISABLED_TOOLSETS)))
    # No Hermes default skills, only the essential hermes-agent one (Hermes always keeps it) and the
    # plugin's own. The profile is created with no_skills; this keeps `hermes update` from seeding
    # them later even when the profile was made some other way. Nothing on disk is deleted.
    configure("skills", "opt-out")
    # No automatic post-turn self-improvement review: it would write its own skills and memories next
    # to the plugin's (`/refine` still works on request).
    configure("config", "set", "auxiliary.background_review.enabled", "false")
    configure("config", "set", "curator.enabled", "false")  # nor the weekly skill curator
    # Pinned, not inherited: the approval prompt before anything touches the Chromatic only appears
    # while approvals are on.
    configure("config", "set", "approvals.mode", "smart")
    if compaction_cap_due(hermes_api.read_profile_config(target).get("compression")):
        configure("config", "set", "compression.threshold_tokens", str(COMPACT_AT_TOKENS))
    # Every chat in the profile opens in its own workspace folder (an absolute, existing directory is
    # what Hermes accepts as terminal.cwd). Games themselves still go in the plugin's games folder.
    check()
    (target / WORKSPACE).mkdir(parents=True, exist_ok=True)
    configure("config", "set", "terminal.cwd", str(workspace))

    check()
    write_soul = refresh_soul(target)
    check()
    marker = target / MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps(
            {
                "made_by": paths.PLUGIN_ID,
                "version": paths.PLUGIN_VERSION,
                "from_profile": profile_name(home),
                "at": int(time.time()),
                "disabled_toolsets": list(DISABLED_TOOLSETS),
            }
        ),
        encoding="utf-8",
    )
    return {
        "ok": True,
        "profile": STUDIO_PROFILE,
        "plugin": plugin,
        "providers": providers,
        "provider_sync": synced,
        "disabled_toolsets": list(DISABLED_TOOLSETS),
        "soul_written": write_soul,
        "workspace": str(workspace),
    }
