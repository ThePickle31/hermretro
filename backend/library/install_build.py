"""Building a game installed with its source here. Standard library only.

Building runs its author's code on this computer: GB Studio copies the project's own engine (``assets/engine/``) and
plugins into the build and hands project settings to the compiler's shell. So nothing builds it until the user allows
it (``allow``): ``install.json``'s ``buildConsent: {commit, digest, at}`` names the installed commit and the digest of
its source as installed (``sourceDigest``); an update installs another commit, so it asks again. The user's own edits
since do not undo it: what they add is theirs.

Once allowed, the broker builds it once (``test_build``, ``backend/broker/installed.py``) while the game is held, and
records ``testBuild: {sha256, commit, matches, t}`` under that hold: the ROM it built, the commit it was built from,
and whether it is the ROM the game was installed with (``rom.sha256``, the author's ``romSha256`` the install
checked), never what ``game.json`` says now. Without consent the game plays the ROM it shipped with.
"""

from __future__ import annotations

import time
from pathlib import Path

from . import game_card, layout
from .layout import INSTALL_FILE
from .release import installed


@game_card.locked
def allow(root: Path) -> dict:
    """Record the user's consent to build this game here: ``{commit, digest, at}``."""
    record = _source_record(root)
    record["buildConsent"] = {"commit": record.get("commit"), "digest": record.get("sourceDigest"), "at": time.time()}
    layout.write_state(root, INSTALL_FILE, record)
    return record["buildConsent"]


def allowed(root: Path) -> bool:
    """Whether a game made here, or one installed with its source whose consent is for the commit installed, may be
    built. A game installed without its source never is: it has nothing to build."""
    record = installed(root)
    if record is None:
        return True
    if record["mode"] != "game+source":
        return False
    consent = record.get("buildConsent")
    return (
        isinstance(consent, dict)
        and consent.get("commit") == record.get("commit")
        and consent.get("digest") == record.get("sourceDigest")
        and isinstance(consent.get("commit"), str)
    )


@game_card.locked
def record_test_build(root: Path, sha256: str | None, commit: str) -> dict:
    """Record the one build here of a game installed with its source, from ``commit`` (refused when the game is at
    another commit now): ``{sha256, commit, matches, t}``, ``matches`` whether it is the ROM it was installed with
    (None when nothing was built)."""
    record = _source_record(root)
    if record.get("commit") != commit:
        raise ValueError("The game was updated while it was built.")
    installed_with = (record.get("rom") or {}).get("sha256")
    matches = (sha256 == installed_with) if sha256 and isinstance(installed_with, str) else None
    record["testBuild"] = {"sha256": sha256, "commit": commit, "matches": matches, "t": time.time()}
    layout.write_state(root, INSTALL_FILE, record)
    return record["testBuild"]


def test_build(root: Path) -> dict | None:
    """The recorded build here, while it is of the commit installed now; None otherwise."""
    record = installed(root)
    built = (record or {}).get("testBuild")
    return built if isinstance(built, dict) and built.get("commit") == record.get("commit") else None


def _source_record(root: Path) -> dict:
    record = installed(root)
    if record is None or record["mode"] != "game+source":
        raise ValueError("Only a game installed with its source is built here this way.")
    return record
