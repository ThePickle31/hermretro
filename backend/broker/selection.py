"""One game, one conversation (the Build page): which projects a conversation may open, the game it works on
selected for it, and the refusal of calls on a game that is not the conversation's own.

Stdlib only and no Hermes imports: the broker runs as `python -m backend.broker`.
"""

from __future__ import annotations

import os
from pathlib import Path

from .. import library
from ..system import paths
from .engine import EngineProcess
from .lane import WRITE_PATH_KEYS, Denied, Lane, _same_folder


class SelectionMixin:
    """The Broker's project selection and game ownership."""

    def _selection_target(self, lane: Lane, tool: str, arguments: dict) -> str | None:
        """The project root a selector would work on: the selected project, or the new folder, resolved as the engine
        resolves it (trimmed; a relative path against the project the conversation has open)."""
        path = arguments.get("projectPath") if tool == "project_select" else arguments.get("destinationPath")
        if not isinstance(path, str) or not path.strip():
            return None
        path = path.strip()
        if path.startswith("~") or (not os.path.isabs(path) and not lane.selected_root):
            raise Denied(
                "INVALID_ARGUMENTS",
                f"{'projectPath' if tool == 'project_select' else 'destinationPath'} must be an absolute path "
                "here. Nothing was changed.",
            )
        real = str(library.engine_path(path, lane.selected_root))  # ``..`` first, then links, as the engine does
        return os.path.dirname(real) if tool == "project_select" and os.path.isfile(real) else real

    def _project_holding(self, target: str) -> str | None:
        """The game folder ``target`` would be made inside: a library game's existing folder above it, or a folder
        above it holding a GB Studio project (one another chat is making right now is not in the library yet).
        ``target`` itself is the engine's to refuse: it only makes a project in a new folder."""
        game = self.games.owning_game(str(Path(target).parent))
        if game is not None:
            return os.path.realpath(game["projectRoot"])
        for folder in Path(target).parents:
            try:
                if any(folder.glob("*.gbsproj")):
                    return str(folder)
            except OSError:
                continue
        return None

    def guard_selection(self, owner: tuple[str, str], lane: Lane, tool: str, arguments: dict) -> None:
        """A library game is opened and edited only from its own conversation: a game's conversation works on that game
        only, a New Game conversation only makes its new project, and any other chat makes new projects (each becomes
        that chat's game) but opens no library game."""
        profile, conversation = owner
        kind, bound = self.games.binding_for(profile, [conversation, *lane.sessions_seen])
        target = self._selection_target(lane, tool, arguments)
        if kind == "game":
            mine = os.path.realpath(bound["projectRoot"])
            title = bound.get("title") or os.path.basename(mine)
            if tool == "project_select" and target == mine:
                return
            if not os.path.isdir(mine):
                raise Denied(
                    "GAME_FOLDER_MISSING",
                    f"This conversation belongs to the game \"{title}\", but its folder {mine} no longer "
                    "exists (moved or deleted). Tell the user; this conversation can continue once the "
                    "folder is back where it was. Nothing was changed.",
                )
            what = "create another project" if tool != "project_select" else "open another project"
            raise Denied(
                "ONE_GAME_PER_CONVERSATION",
                f"This conversation belongs to the game \"{title}\" ({mine}), and each hermretro game "
                f"has its own conversation, so it cannot {what}. Tell the user: to make a different "
                "game, start one with New Game on the hermretro Build page; to work on another game, "
                "open that game on the Build page. Nothing was changed.",
            )
        if tool != "project_select":
            holder = self._project_holding(target) if target else None
            if holder is not None:
                where = os.path.realpath(paths.games_dir())
                inside = where == holder or where.startswith(holder.rstrip(os.sep) + os.sep)
                raise Denied(
                    "INSIDE_ANOTHER_GAME",
                    f"{target} is inside the game folder {holder}. A new game gets a folder of its own. "
                    + (
                        "hermretro's games folder is itself inside that folder, so tell the user; do not make the "
                        "game there."
                        if inside
                        else "Leave destinationPath out to make it in the hermretro games folder."
                    )
                    + " Nothing was changed.",
                )
            return
        if kind == "pending":
            # A New Game conversation makes its own project: one it opened would stay selected after the new project
            # claims the conversation, and its edits and builds would go there.
            raise Denied(
                "NEW_GAME_ONLY",
                "This conversation is for a new game, so it opens no existing project. Create the new game's "
                "project with chromatic_project_create or chromatic_project_create_blank. To work on an existing "
                "game, tell the user to open it on the hermretro Build page. Nothing was changed.",
            )
        # The game itself, or the game whose folder holds it (a project inside a game's folder is that game's files).
        entry = self.games.owning_game(target) if target else None
        if isinstance(entry, dict):
            title = entry.get("title") or os.path.basename(target)
            raise Denied(
                "GAME_CHAT_ONLY",
                f"\"{title}\" is a hermretro game, and a game is worked on only in its own conversation. Tell the "
                f"user to open \"{title}\" on the hermretro Build page and continue there. Nothing was changed.",
            )

    def ownership_refusal(self, lane: Lane, snapshot: dict | None = None) -> Denied | None:
        """Why this chat may not work on the project its worker has open: the library game holding it is not this
        chat's own (another conversation's, or none since Stop editing). None when it may, or nothing is open, or the
        project is in no library game."""
        if not lane.selected_root:
            return None
        data = self.games.load() if snapshot is None else snapshot
        game = self.games.owning_game(lane.selected_root, snapshot=data)
        if game is None:
            return None
        kind, bound = self.games.binding_for(lane.owner[0], [lane.owner[1], *lane.sessions_seen], snapshot=data)
        if kind == "game" and bound.get("id") == game["id"]:
            return None
        title = game.get("title") or os.path.basename(game["projectRoot"])
        return Denied(
            "GAME_CHAT_ONLY",
            f"\"{title}\" is no longer this conversation's game: a game is worked on only in its own conversation. "
            f"Tell the user to open \"{title}\" on the hermretro Build page and continue there. Nothing was changed.",
        )

    def guard_ownership(self, lane: Lane, arguments: dict) -> None:
        """Before a call that changes a project or runs its game: refuse it unless the open project is this chat's own
        game, and refuse a path argument that lands in another game's folder (a library game inside this one's)."""
        data = self.games.load()
        refusal = self.ownership_refusal(lane, data)
        if refusal is not None:
            self._release_root(lane)  # let the game's own conversation write at once
            raise refusal
        if not lane.selected_root:
            return
        mine = self.games.owning_game(lane.selected_root, snapshot=data)
        for key in WRITE_PATH_KEYS:
            value = arguments.get(key)
            if not isinstance(value, str) or not value.strip() or value.strip().startswith("~"):
                continue
            found = self.games.owning_game(str(library.engine_path(value.strip(), lane.selected_root)), snapshot=data)
            if found is not None and (mine is None or found["id"] != mine["id"]):
                title = found.get("title") or os.path.basename(found["projectRoot"])
                raise Denied(
                    "INSIDE_ANOTHER_GAME",
                    f"{key} {value} is in the game \"{title}\" ({found['projectRoot']}), not this conversation's "
                    "game: each game's files are written only from its own conversation. Give a path in this game's "
                    f"own folder. To work on \"{title}\", tell the user to open it on the hermretro Build page. "
                    "Nothing was changed.",
                )

    def confirm_selection(self, lane: Lane) -> None:
        """After a successful selection: the project the worker really has open must be this chat's own game. One
        another chat claimed first (two chats bringing the same project into the library at once) is closed again."""
        refusal = self.ownership_refusal(lane)
        if refusal is None:
            return
        self._release_root(lane)
        lane.selected_root = lane.selected_project_path = None
        self.close_lane_engine(lane, "selection_not_owned")
        raise refusal

    def select_bound_game(self, lane: Lane, engine: EngineProcess) -> None:
        """A game's conversation works on its game: selected for it when nothing is, and again when another project
        is (a New Game conversation whose new project claimed it after it had opened something else). When its worker
        still has another project open, nothing runs for it."""
        kind, bound = self.games.binding_for(lane.owner[0], [lane.owner[1], *lane.sessions_seen])
        if kind != "game" or not os.path.isdir(bound.get("projectRoot") or "") or lane.rom_workspace:
            return  # (a game without its source has no project: its worker's workspace is its folder)
        root = bound["projectRoot"]
        if not _same_folder(lane.selected_root, root) and getattr(lane, "auto_select_failed", None) != lane.generation:
            self._select_game(lane, engine, bound)  # a failure is not repeated on every call with this worker
        if lane.selected_root and not _same_folder(lane.selected_root, root):
            title = bound.get("title") or os.path.basename(root)
            raise Denied(
                "ONE_GAME_PER_CONVERSATION",
                f"This conversation belongs to the game \"{title}\" ({root}), but its game worker has "
                f"{lane.selected_root} open and could not switch, so nothing runs here. Tell the user; the worker is "
                "replaced once this conversation has been idle for a while. Nothing was changed.",
            )

    def _select_game(self, lane: Lane, engine: EngineProcess, bound: dict) -> None:
        root = bound["projectRoot"]
        project = library.project_file(Path(root))
        try:
            result = engine.call_tool("project_select", {"projectPath": str(project or root)}, timeout=60)
            if result.get("isError"):
                raise RuntimeError("the engine refused the selection")
        except Exception as error:
            lane.auto_select_failed = lane.generation
            self.trace(event="auto_select_failed", owner_key=lane.key, error=f"{type(error).__name__}: {error}"[:200])
            return
        try:
            self._sync_selection(lane)
        except Exception as error:
            # The selection itself succeeded: take the root from its result, as call() does.
            self.trace(event="selection_sync_failed", owner_key=lane.key, error=str(error)[:200])
            selected = result.get("structuredContent")
            if isinstance(selected, dict) and selected.get("projectRoot"):
                self._apply_selection(lane, selected)
        self.trace(event="auto_select", owner_key=lane.key)
        title = bound.get("title") or os.path.basename(root)
        notice = (
            f"hermretro selected this conversation's game \"{title}\" ({root}) for you: this "
            "conversation works on that game only."
        )
        lane.pending_notice = f"{lane.pending_notice} {notice}" if lane.pending_notice else notice
