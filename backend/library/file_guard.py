"""Where Hermes's file tools may write: never into a game's ``.hermretro/``, and into a library game's folder only from
that game's own conversation, and only a game that has its source. The library's ``pre_tool_call`` (``hooks.py``).

A ``patch`` is read with Hermes's own V4A grammar (``tools/patch_parser.py``, reimplemented here: it is not plugin
API): ``*** Update File:``, ``*** Add File:``, ``*** Delete File:`` and ``*** Move File: a -> b``, with flexible
whitespace, between ``*** Begin Patch`` and ``*** End Patch`` (from the top when there is no Begin). A delete or move
acts on the directory entry itself, so its folder is checked, not what a link there points to. ``..`` is read both
ways (by spelling first, as the engine does, and through links first, as ``Path.resolve`` does).

Hermes resolves a relative path against the chat's own working folder (the terminal's last ``cd``, a Desktop override,
``terminal.cwd``), and ``~`` with the home its subprocesses get; none of that is plugin API, so such a path is refused
and the agent asked for an absolute one. A terminal command is not parsed: this guards the file tools, not the shell.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from . import layout, ownership
from .games import RegistryError

# Hermes's own file-writing tools.
FILE_WRITE_TOOLS = frozenset({"write_file", "patch"})
_BEGIN = re.compile(r"^\*\*\*\s*Begin\s+Patch\s*$")
_END = re.compile(r"^\*\*\*\s*End\s+Patch\s*$")
_WRITES = (re.compile(r"\*\*\*\s*Update\s+File:\s*(.+)"), re.compile(r"\*\*\*\s*Add\s+File:\s*(.+)"))
_DELETE = re.compile(r"\*\*\*\s*Delete\s+File:\s*(.+)")
_MOVE = re.compile(r"\*\*\*\s*Move\s+File:\s*(.+?)\s*->\s*(.+)")


def patch_targets(text: str) -> list[tuple[str, bool]]:
    """``(path, entry)`` for every file a V4A patch names; ``entry`` when the operation acts on the directory entry
    (a delete, a move's source and destination)."""
    lines = [line.removesuffix("\r") for line in text.split("\n")]
    start, end = -1, len(lines)
    for index, line in enumerate(lines):
        if _BEGIN.match(line):
            start = index
        elif _END.match(line):
            end = index
            break
    found: list[tuple[str, bool]] = []
    for line in lines[start + 1 : end]:
        if match := next((m for pattern in _WRITES if (m := pattern.match(line))), None):
            found.append((match.group(1).strip(), False))
        elif match := _DELETE.match(line):
            found.append((match.group(1).strip(), True))
        elif match := _MOVE.match(line):
            found += [(match.group(1).strip(), True), (match.group(2).strip(), True), (match.group(2).strip(), False)]
    return [(path, entry) for path, entry in found if path]


def targets(args: dict) -> list[tuple[str, bool]]:
    """Every file a ``write_file`` or ``patch`` call would write: its ``path``, and a V4A patch's files."""
    found = [(args["path"], False)] if isinstance(args.get("path"), str) and args["path"] else []
    if isinstance(args.get("patch"), str):
        found += patch_targets(args["patch"])
    return found


def _places(named):
    """``(entry, where)`` for each place a named file may resolve to. Both readings of ``..`` count, by spelling
    first (as the engine and ``os.path.normpath`` read it) and through links first (as ``Path.resolve`` reads it):
    either is refused when it lands somewhere this chat may not write."""
    for path, entry in named:
        readings = (
            {ownership.entry_path(path), ownership.entry_path(path, spelling=False)}
            if entry
            else {
                ownership.engine_path(path),
                Path(os.path.realpath(path)),
            }
        )
        for where in sorted(readings):
            yield entry, where


def refusal(args: dict, registry, profile: str, ids) -> str | None:
    """Why this file-tool call may not run (the message for the agent), or None. One registry read serves the whole
    call: the game folders, their records and this chat's binding."""
    named = targets(args)
    if any(path.startswith("~") or not os.path.isabs(path) for path, _entry in named):
        return (
            "In the hermretro studio, write_file and patch take absolute paths: a relative or ~ path could land in a "
            "game's folder. Call it again with the full path. Nothing was changed."
        )
    if not named:
        return None
    try:
        data = registry.load()
    except RegistryError as error:
        return (
            f"hermretro's game library could not be read ({error}), so which game this file belongs to is unknown. "
            "Tell the user; nothing was changed."
        )
    index = ownership.root_index(data["games"])
    records = ownership.identities(ownership.record_dirs(index))
    kind, bound = registry.binding_for(profile, ids, snapshot=data)
    mine = bound.get("id") if kind == "game" and isinstance(bound, dict) else None
    for entry, where in _places(named):
        if any(part.lower() == layout.STATE_DIR for part in where.parts) or ownership.owner_in(records, where):
            return (
                f"{layout.STATE_DIR}/ is hermretro's record of the game (its id and publish record); it cannot be "
                "edited. Leave it as it is."
            )
        found = ownership.owner_in(index, where.parent if entry else where)
        if found is None:
            continue
        identifier, game, root = found
        title = game.get("title") or root.name
        if not ownership.editable(root):
            return f"\"{title}\" ({root}) was installed without its source, so its files are not edited. Nothing was changed."
        if identifier == mine:
            continue
        again = f"To work on \"{title}\", tell the user to open it on the hermretro Build page and continue there."
        if mine is not None:
            own = bound.get("title") or Path(str(bound.get("projectRoot") or "")).name
            return (
                f"{where} is in the game \"{title}\" ({root}), and this conversation belongs to \"{own}\": each game's "
                f"files are written only from its own conversation. Write this game's files only. {again} Nothing "
                "was changed."
            )
        return (
            f"{where} is in the hermretro game \"{title}\" ({root}), whose files are written only from its own "
            f"conversation. {again} Nothing was changed."
        )
    return None
