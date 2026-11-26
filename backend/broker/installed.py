"""Conversations of games installed from a link (``library.installs``).

A game without its source (installed so, or kept from one) has no project to open: its own conversation's worker is
started with that game's folder as its workspace (``GB_STUDIO_WORKSPACE_ROOT``, the engine's authorization for a
standalone ROM), and only ``ROM_ONLY_TOOLS`` run there: reads, the emulator, the hardware tools (behind their own
setting and approval) and closing a preview; a tool not on that list, a new one included, is refused. A ROM a tool
names must be the game's checked ROM, still those bytes (``ROM_CHANGED`` otherwise), and ``flash`` must expect that
very SHA-256.

An installed game never gets a browser copy of its project (``web_build``, ``web_preview``), with its source or
without: GB Studio's custom HTML header setting puts the project's own script in that copy. The player plays its ROM
in hermretro's own player shell instead (``library.plays_in_shell``). A game installed with its source is built only
once the user allowed it (``library.build_allowed``; ``BUILD_NOT_ALLOWED``): building runs its author's code.

Control op ``test_build {root}``: that build, once, in a worker of its own that opens only that game, while the game is
held (``holds.py``, exclusive: no conversation, update or other build has it meanwhile) and its folder locked (no
history restore changes its sources), recorded under that hold as the library's ``testBuild`` and as an ordinary
recorded build (``lastBuild``), so presenting it holds it to its checks like a build in its chat. Stdlib only and no
Hermes imports: the broker runs as ``python -m backend.broker``.
"""

from __future__ import annotations

import os
from pathlib import Path

from .. import library
from .lane import DEFAULT_CALL_TIMEOUT, Denied, Lane, canonical_hash

# What a conversation of a game without its source may run, besides read-only tools and the hardware tools.
ROM_ONLY_TOOLS = frozenset(
    {"emulator_run", "emulator_step", "emulator_replay", "emulator_checkpoint", "emulator_close", "web_preview_close"}
)
# Tools that take the ROM such a conversation works on.
ROM_PATH_TOOLS = frozenset({"rom_inspect", "emulator_run", "emulator_replay", "flash", "play"})
# The engine's browser copy of a project.
BROWSER_COPY = frozenset({"web_build", "web_preview"})
# A test build's hold outlasts its longest engine call.
BUILD_HOLD_SECONDS = DEFAULT_CALL_TIMEOUT + 300
NOT_ALLOWED = (
    "This game was installed with its source from someone else, and building it runs its author's code on this "
    "computer. The user has not allowed that for this version, so it plays the ROM it came with. Tell the user; do not "
    "build it. Nothing was changed."
)


class InstalledMixin:
    """The Broker's rules for installed games' conversations."""

    def rom_only_root(self, lane: Lane) -> str | None:
        """The folder of this conversation's own game when it is a game without its source (its worker's workspace);
        None otherwise."""
        kind, bound = self.games.binding_for(lane.owner[0], [lane.owner[1], *lane.sessions_seen])
        root = bound.get("projectRoot") if kind == "game" else None
        if not isinstance(root, str) or not os.path.isdir(root) or library.rom_only_record(Path(root)) is None:
            return None
        return os.path.realpath(root)

    def rom_only_allows(self, tool: str) -> bool:
        """Whether a conversation of a game without its source may run ``tool``."""
        return tool in self.read_only or tool in ROM_ONLY_TOOLS or self.classify(tool) == "hardware"

    def guard_installed(self, lane: Lane, tool: str, kind: str, arguments: dict) -> None:
        """Refuse what an installed game's conversation may not do (before the engine is reached, and again once its
        game is selected for it): a browser copy, a build the user did not allow, and for a game without its source
        anything off ``ROM_ONLY_TOOLS`` or a ROM other than its checked one."""
        rom_only = lane.rom_workspace
        selected = Path(lane.selected_root) if lane.selected_root else None
        installed = rom_only or (selected is not None and library.is_installed(selected))
        if installed and tool in BROWSER_COPY:
            raise Denied(
                "INSTALLED_PLAYS_ROM",
                "An installed game plays its ROM in hermretro's own player, never a browser copy of its project (its "
                "project's settings can carry its author's script). Tell the user to press Play on the hermretro Games "
                "page. Nothing was changed.",
            )
        if tool == "rom_build" and selected is not None and not library.build_allowed(selected):
            raise Denied("BUILD_NOT_ALLOWED", NOT_ALLOWED)
        if not rom_only:
            return
        if not self.rom_only_allows(tool):
            raise Denied(
                "INSTALLED_WITHOUT_SOURCE",
                "This game has no source here: it can be played, inspected and installed on a Chromatic, not edited "
                "or built. Nothing was changed.",
            )
        if tool in ROM_PATH_TOOLS:
            self._guard_checked_rom(rom_only, tool, arguments)

    def _guard_checked_rom(self, root: str, tool: str, arguments: dict) -> None:
        checked = library.rom_only_record(Path(root)) or {}
        own = str(Path(root) / checked.get("path", ""))
        value = arguments.get("romPath")
        if isinstance(value, str) and value.strip() and str(library.engine_path(value.strip(), root)) != own:
            raise Denied(
                "ROM_OUTSIDE_GAME",
                f"romPath {value} is not this game's ROM. Use {own}. Nothing was changed.",
            )
        found = library.verified(Path(root))
        if found is None:
            raise Denied(
                "ROM_CHANGED",
                f"This game's ROM ({own}) is no longer the one it was installed with (SHA-256 {checked.get('sha256')}), "
                "so it is not played or installed. Tell the user to update the game. Nothing was changed.",
            )
        expected = arguments.get("expectedSha256")
        if tool == "flash" and expected != found["sha256"]:
            raise Denied(
                "ROM_CHANGED",
                f"expectedSha256 must be this game's checked ROM's, {found['sha256']}. Nothing was changed.",
            )

    def test_build(self, request: dict) -> dict:
        """Build a game installed with its source once (control op ``test_build``): ``{ok, built, sha256, matches,
        commit, error}``."""
        root = request.get("root")
        if not isinstance(root, str) or not os.path.isabs(root):
            raise Denied("INVALID_ARGUMENTS", "test_build takes the game's absolute folder.")
        root = os.path.realpath(root)
        project = library.project_file(Path(root))
        if self.games.game_for_root(root) is None or not library.is_installed(Path(root)) or project is None:
            raise Denied("NOT_INSTALLED_WITH_SOURCE", "test_build builds a library game installed with its source.")
        self._take_hold(root, seconds=BUILD_HOLD_SECONDS)  # GAME_BUSY while anything else has it
        try:
            with library.folder_lock(Path(root)):
                if not library.build_allowed(Path(root)):
                    raise Denied("BUILD_NOT_ALLOWED", NOT_ALLOWED)
                commit = (library.install_record(Path(root)) or {}).get("commit")
                return self._build_once(root, project, commit)
        finally:
            self._release_hold(root)

    def _build_once(self, root: str, project: Path, commit: str) -> dict:
        sources = library.source_digest(Path(root))
        rom = Path(root, library.canonical_rom(Path(root)))
        engine = self.new_engine("chromatic-install-test")
        try:
            live, _pages = engine.list_tools()
            if canonical_hash(live) != self.pinned_hash:
                raise Denied("ENGINE_PIN_MISMATCH", "Live engine contracts differ from the pinned baseline.")
            selected = engine.call_tool("project_select", {"projectPath": str(project)}, timeout=120)
            result = (
                selected
                if selected.get("isError")
                else engine.call_tool("rom_build", {"outputPath": str(rom)}, timeout=DEFAULT_CALL_TIMEOUT)
            )
        finally:
            engine.close()
        structured = result.get("structuredContent") if isinstance(result.get("structuredContent"), dict) else {}
        failed = bool(result.get("isError")) or structured.get("success") is False
        sha256 = None if failed else library.file_sha256(rom) if rom.is_file() else None
        if sources != library.source_digest(Path(root)):  # nothing may change its sources while it is held
            sha256, failed = None, True
        self.games.observe(
            "rom_build",
            {"outputPath": str(rom)},
            {"outputPath": str(rom), **({"sha256": sha256} if sha256 else {}), **structured},
            failed,
            lane_root=root,
            conversation_id=None,
            sources_before=sources,
        )
        receipt = library.record_test_build(Path(root), sha256, commit)
        self.trace(event="install_test_build", root_name=os.path.basename(root), built=sha256 is not None)
        return {"ok": True, "built": sha256 is not None, **receipt, "error": None if sha256 else _error_text(result)}


def _error_text(result: dict) -> str:
    structured = result.get("structuredContent") if isinstance(result.get("structuredContent"), dict) else {}
    texts = [block.get("text") for block in result.get("content") or [] if isinstance(block, dict)]
    return str(structured.get("error") or next((t for t in texts if isinstance(t, str)), None) or "The build failed.")[
        :240
    ]
