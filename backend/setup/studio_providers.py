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
    """``(installing profile, studio profile)`` from either side, once the studio profile is finished."""
    if studio_profile.profile_name(home) == studio_profile.STUDIO_PROFILE:
        studio = home
        try:
            marker = json.loads((home / studio_profile.MARKER).read_text(encoding="utf-8"))
            source = hermes_api.profile_dir(marker["from_profile"])
        except (OSError, ValueError, KeyError, TypeError):
            return None
    else:
        source, studio = home, studio_profile.studio_dir()
    return (source, studio) if source != studio and studio_profile.is_finished(studio) else None


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
        enabled = ((hermes_api.read_profile_config(source).get("plugins") or {}).get("enabled")) or []
        plugins = [folder.name for folder in studio_profile.provider_plugins(source, [str(name) for name in enabled])]
        provider_sync.sync(
            source, studio, lambda *arguments: studio_profile.run_hermes(studio, *arguments), plugins=plugins
        )
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
