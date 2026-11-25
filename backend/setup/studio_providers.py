"""Keeping a finished studio profile on the installing profile's providers after setup, and its Claude sign-in.

Setup itself syncs while it configures the profile (studio_profile._configure); this runs the same sync later, in the
background, whenever the installing profile changed (provider_sync.is_current), from either profile's side.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from ..hermes import api as hermes_api
from . import claude_login, provider_sync, studio_profile

logger = logging.getLogger(__name__)


def sync_pair(home: Path) -> tuple[Path, Path] | None:
    """``(installing profile, studio profile)`` from either side: the profile that made the studio profile (its finish
    marker's ``from_profile``), never another one the plugin is also installed in, and never a deleted studio."""
    studio = home if studio_profile.profile_name(home) == studio_profile.STUDIO_PROFILE else studio_profile.studio_dir()
    if not studio_profile.is_finished(studio) or hermes_api.profile_is_deleted(studio):
        return None
    try:
        made_by = json.loads((studio / studio_profile.MARKER).read_text(encoding="utf-8"))["from_profile"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if studio != home and made_by != studio_profile.profile_name(home):
        return None
    source = home if studio != home else hermes_api.profile_dir(made_by)
    return (source, studio) if source != studio else None


def sync_soon(home: Path) -> None:
    """Copy what changed in the installing profile's providers, in the background (each copy is a Hermes command)."""
    try:
        pair = sync_pair(home)
    except Exception:  # noqa: BLE001 - no Hermes to find the profiles with (tests, an older Hermes): nothing to sync
        logger.debug("hermretro could not find the profiles to sync providers between", exc_info=True)
        return
    if pair is not None and not provider_sync.is_current(*pair):
        threading.Thread(target=_sync, args=pair, name="hermretro-provider-sync", daemon=True).start()


def _sync(source: Path, studio: Path) -> None:
    if not provider_sync.lock.acquire(blocking=False):
        return  # a sync or a finish is already running
    try:

        def run(*arguments):
            studio_profile.run_hermes(studio, *arguments)

        enabled = [
            str(name) for name in (hermes_api.read_profile_config(source).get("plugins") or {}).get("enabled") or []
        ]
        # A provider plugin turned on in the installing profile since setup: linked and on before its route is copied.
        plugins = studio_profile.link_providers(source, studio, enabled, run)
        on = (hermes_api.read_profile_config(studio).get("plugins") or {}).get("enabled") or []
        for name in plugins:
            if name not in on:
                run("plugins", "enable", name)
        provider_sync.sync(source, studio, run, plugins=plugins)
    except Exception:  # noqa: BLE001 - a failed sync leaves the profile as it was; setup's Repair runs it again
        logger.warning("hermretro could not bring the hermretro profile's providers up to date", exc_info=True)
    finally:
        provider_sync.lock.release()


def sign_in_to_claude(home: Path) -> dict:
    """Give the studio profile a Claude login of its own (claude_login.sign_in) and select it."""
    pair = sync_pair(home)
    if pair is None:
        raise studio_profile.StudioProfileError("NOT_CREATED", "The hermretro profile has not been created yet.")
    studio = pair[1]
    folder = claude_login.sign_in(studio)
    with provider_sync.lock:
        studio_profile.run_hermes(studio, "config", "set", claude_login.SETTING, folder)
    return {"ok": True, "claude_login": claude_login.state(studio)}
