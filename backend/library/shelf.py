"""Game objects for the Games shelf and the emulator. Standard library only."""

from __future__ import annotations

from pathlib import Path

from . import freshness, game_card, install_build, layout, play, project, release

# A failed build's error, as recorded in lastBuild and answered by the games RPC.
ERROR_CHARS = 240


def registered_root(entry: dict) -> Path | None:
    """An existing project folder, or None for a confirmed removal."""
    stored = entry.get("projectRoot") if isinstance(entry, dict) else None
    if not isinstance(stored, str) or not stored or "\x00" in stored:
        raise OSError("The game has an invalid project folder in the library.")
    root = Path(stored)
    if not root.is_absolute():
        raise OSError("The game has an invalid project folder in the library.")
    try:
        return root if project.project_exists(root) else None
    except UnicodeEncodeError as error:
        raise OSError("The game has an invalid project folder in the library.") from error


def public_session(binding) -> dict | None:
    if not isinstance(binding, dict) or not isinstance(binding.get("storedId"), str):
        return None
    profile = binding.get("profile")
    return {
        "storedId": binding["storedId"],
        "createdAt": project.timestamp(binding.get("createdAt"), None),
        "profile": profile if isinstance(profile, str) else None,
    }


def chat_link(chat) -> dict | None:
    if not isinstance(chat, dict) or not isinstance(chat.get("sessionId"), str) or not chat["sessionId"]:
        return None
    return {key: value for key in ("sessionId", "conversationId", "profile") if isinstance(value := chat.get(key), str)}


def last_build(entry: dict) -> dict:
    last = entry.get("lastBuild")
    return last if isinstance(last, dict) else {}


def artifacts_for(root: Path, last: dict, *, require_web_rom: bool = False) -> tuple[dict, float | None]:
    """The game's ROM and what its player plays (``project.build_artifacts``). A game without its source has only its
    checked ROM (``play``), never another file found in ``build/``: none when that ROM changed. A game the player's
    shell plays shows that ROM as its playable copy."""
    if play.rom_only_record(root) is not None:
        artifacts = play.shell_artifacts(root, {"rom": None, "webExport": False, "web": None})
        return artifacts, (artifacts["rom"] or {}).get("builtAt")
    shell = play.plays_in_shell(root)
    artifacts, built = project.build_artifacts(root, last, require_web_rom=require_web_rom and not shell)
    return (play.shell_artifacts(root, artifacts) if shell else artifacts), built


def game_details(entry: dict, identifier: str, root: Path, artifacts: dict) -> dict:
    """The player's title, build artifacts and chat routing. No card reads or source walk."""
    chat = entry.get("chat")
    return {
        "id": identifier,
        "title": project.project_title(root, entry.get("title")),
        "projectRoot": str(root),
        **artifacts,
        "chat": chat if isinstance(chat, dict) else None,
        "session": public_session(entry.get("session")),
    }


def describe(entry: dict, identifier: str, root: Path, thumb) -> dict:
    try:
        layout.ensure(root)  # every game the library reads has the game layout
    except OSError:
        pass
    last = last_build(entry)
    artifacts, built = artifacts_for(root, last)
    if play.rom_only_record(root) is not None:  # nothing to build: it is its checked ROM, or that ROM changed
        state = "ready" if artifacts["rom"] else "romChanged"
    elif last.get("ok") is False and (built is None or project.timestamp(last.get("t")) >= built):
        state = "failed"
    elif built is None:
        state = "unbuilt"
    elif freshness.sources_newer_than(root, built):
        state = "changed"
    else:
        state = "ready"
    game = game_details(entry, identifier, root, artifacts)
    card = game_card.public(root)
    cover = game_card.cover_data_url(root) if card and card["hasCover"] else None
    return {
        **game,
        "kind": project.project_kind(root),
        "state": state,
        "thumb": cover or thumb(identifier),
        "cover": bool(cover),
        "card": card,
        "layout": layout.check(root),
        "install": installed_from(root),
        "displayTitle": (card or {}).get("title") or game["title"],
        "error": (str(last.get("error") or "The build failed."))[:ERROR_CHARS] if state == "failed" else None,
        "updatedAt": project.timestamp(entry.get("updatedAt"), None),
    }


def installed_from(root: Path) -> dict | None:
    """Where a game installed from a link came from (``release.installed``), for the page: ``{source, url, ref,
    commit, mode, rom, romSha256, installedAt, edited, testBuild, buildAllowed}`` (``rom``/``romSha256``: the ROM its
    install checked, relative, and its SHA-256; ``testBuild``: the build here of the commit installed,
    ``install_build``, or None; ``buildAllowed``: whether the user allowed building it here); None for a game made
    here."""
    record = release.installed(root)
    if record is None:
        return None
    return {
        "source": record["source"].get("canonical"),
        "url": record["source"].get("url"),
        "ref": record["source"].get("ref"),
        "commit": record.get("commit"),
        "mode": record["mode"],
        "rom": (record.get("rom") or {}).get("path"),
        "installedAt": project.timestamp(record.get("installedAt"), None),
        "edited": release.local_edits(root) is True,
        "romSha256": (record.get("rom") or {}).get("sha256"),  # what the install checked, the author's romSha256
        "testBuild": install_build.test_build(root),
        "buildAllowed": install_build.allowed(root) if record["mode"] == "game+source" else False,
    }


def mark_duplicates(games: list[dict]) -> None:
    """Give each described game ``duplicateId``: the other library folders holding a game with its id (a game folder
    copied by hand), or None. One id is one game: an install of it, an update and its history all go by it. Two
    entries that are the same folder (a link, or another spelling of its name) are not two copies."""
    folders: dict[str, dict[tuple, str]] = {}
    keys = {}
    for game in games:
        root = Path(game["projectRoot"])
        identity = layout.game_identity(root)
        try:
            info = root.stat()
        except OSError:
            continue
        keys[id(game)] = (identity, (info.st_dev, info.st_ino))
        if identity is not None:
            folders.setdefault(identity, {}).setdefault((info.st_dev, info.st_ino), game["projectRoot"])
    for game in games:
        identity, folder = keys.get(id(game), (None, None))
        others = [root for key, root in folders.get(identity or "", {}).items() if key != folder]
        game["duplicateId"] = others or None
