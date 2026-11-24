"""Game objects for the Games shelf and the emulator. Standard library only."""

from __future__ import annotations

from pathlib import Path

from . import freshness, game_card, layout, project

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
    artifacts, built = project.build_artifacts(root, last)
    if last.get("ok") is False and (built is None or project.timestamp(last.get("t")) >= built):
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
        "displayTitle": (card or {}).get("title") or game["title"],
        "error": (str(last.get("error") or "The build failed."))[:ERROR_CHARS] if state == "failed" else None,
        "updatedAt": project.timestamp(entry.get("updatedAt"), None),
    }
