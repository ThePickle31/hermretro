"""The finishable run's recording: the one run from power-on to the ending that a build report names
(``chromatic_build_report``'s ``finishRun``, ``report_tools.py``). The engine's emulator worker keeps each recorded
attempt as a folder holding ``recording.json``, rewritten when the attempt is created and when it ends, and the
append-only journal ``events.jsonl``, which opens with a ``header`` row and closes with a ``finish`` row (``Recording``
in engine/modretro-chromatic/scripts/emulator_worker.py). Standard library only."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .project import _game_rom, _legacy_rom, file_sha256

# Where the engine puts a recording whose run names no outputPath.
RECORDINGS = Path("artifacts", "playtests")
MANIFEST = "recording.json"
MANIFEST_KIND = "gb-studio-playtest"
MAX_MANIFEST_BYTES = 1024 * 1024
JOURNAL = "events.jsonl"
# The finish row is short; the rows before it can hold a step's frame hashes, so only the tail is read.
MAX_FINISH_ROW_BYTES = 64 * 1024
SESSION_ID = re.compile(r"^[0-9a-f]{32}$")
NEW_RUN = "boot this build's ROM with chromatic_emulator_run restart:true and recording:{}, play it to the ending"
# Where a recording the lookup cannot find lives instead.
ELSEWHERE = (
    "give the recordingPath chromatic_emulator_run returned (a recording with its own outputPath), or for an "
    "archived recording the archivePath chromatic_emulator_recording retrieve returned"
)


def read_manifest(folder: Path) -> dict | None:
    """A recording folder's ``recording.json``, None when the folder holds none."""
    path = folder / MANIFEST
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
            return None
        body = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    return body if isinstance(body, dict) and body.get("kind") == MANIFEST_KIND else None


def _journal_agrees(folder: Path, manifest: dict) -> bool:
    """Whether the folder's ``events.jsonl`` is there and tells the same run as its ``recording.json``: its header
    names the same session and ROM and, once the attempt has ended, its finish row the same status and outcome."""
    path = folder / JOURNAL
    try:
        if path.is_symlink() or not path.is_file():
            return False
        with path.open("rb") as journal:
            header = json.loads(journal.readline(MAX_MANIFEST_BYTES))
            if not isinstance(header, dict) or header.get("kind") != "header":
                return False
            if header.get("sessionId") != manifest.get("sessionId") or header.get("rom") != manifest.get("rom"):
                return False
            if manifest.get("status") == "recording":  # no finish row yet, and the last row may be mid-append
                return True
            journal.seek(max(0, journal.seek(0, os.SEEK_END) - MAX_FINISH_ROW_BYTES))
            last = json.loads(journal.read().rstrip(b"\n").rsplit(b"\n", 1)[-1])
    except (OSError, ValueError):
        return False
    return (
        isinstance(last, dict)
        and last.get("kind") == "finish"
        and all(last.get(key) == manifest.get(key) for key in ("status", "outcome"))
    )


def _folder(root: Path, value: str) -> Path | None:
    """The folder ``value`` names: a path to a recording (absolute or relative to the project, the folder or its
    ``recording.json``), or a recording's session id, looked up in the project's ``artifacts/playtests/``. Raises
    RuntimeError for a ``~user`` no account has."""
    if SESSION_ID.match(value):
        try:
            entries = sorted((root / RECORDINGS).iterdir())
        except OSError:
            return None
        return next((entry for entry in entries if (read_manifest(entry) or {}).get("sessionId") == value), None)
    candidate = root / Path(value).expanduser()  # an absolute value replaces root
    return candidate.parent if candidate.name == MANIFEST else candidate


def find_recording(root: Path, value: str, field: str = "finishRun") -> tuple[Path | None, dict | None, str | None]:
    """The recording ``value`` names (see ``_folder``): ``(its real folder, its recording.json, None)``, or
    ``(None, None, why it is none)``, ``field`` naming the argument in that answer: it must be a recording inside the
    project whose journal tells the same run as its manifest."""
    try:
        folder = _folder(root, value)
        real = folder.resolve() if folder is not None else None
        inside = real is not None and real.is_relative_to(root.resolve())
    except (OSError, RuntimeError):
        return None, None, f"{field}: {value} is not a usable path."
    if real is None:
        return None, None, f"{field}: no recording in {RECORDINGS.as_posix()}/ has the session id {value}: {ELSEWHERE}."
    if not inside:
        return None, None, f"{field}: {value} is outside the project."
    manifest = read_manifest(real)
    if manifest is None:
        return (
            None,
            None,
            (
                f"{field}: {value} is no recording (the folder chromatic_emulator_run's recording:{{}} made): {ELSEWHERE}."
            ),
        )
    if not _journal_agrees(real, manifest):
        return (
            None,
            None,
            (
                f"{field}: {value} has no {JOURNAL}, or one that does not match its {MANIFEST}, so it shows no run: "
                f"{NEW_RUN}, and name that recording."
            ),
        )
    return real, manifest, None


def current_rom(root: Path, field: str = "finishRun") -> tuple[Path | None, str | None, str | None]:
    """The game's ROM as it is now: ``(its path, its SHA-256, None)``, or ``(None, None, why there is none)``."""
    game = _game_rom(root) or _legacy_rom(root)
    if game is None:
        return None, None, f"{field}: this game has no ROM in build/ to check the recording against."
    try:
        return game[0], file_sha256(game[0]), None
    except OSError:
        return None, None, f"{field}: {game[0].relative_to(root).as_posix()} could not be read."


def played_rom(manifest: dict) -> str | None:
    """The SHA-256 of the ROM a recording played, from its recording.json."""
    return manifest["rom"].get("sha256") if isinstance(manifest.get("rom"), dict) else None


def unfinished(manifest: dict, value: str, field: str = "finishRun") -> str | None:
    """Why the attempt ``manifest`` describes (``value`` names it) is no single run from power-on that has ended:
    it is still recording or restored a checkpoint. None when it is one."""
    if manifest.get("status") == "recording":
        return (
            f"{field}: {value} is still recording, so it shows no finished run yet: stop it with "
            'chromatic_emulator_recording {"action":"stop","outcome":...} first.'
        )
    branches = manifest.get("branches") if isinstance(manifest.get("branches"), list) else []
    if any(isinstance(branch, dict) and branch.get("checkpointId") for branch in branches):
        return (
            f"{field}: {value} restored a checkpoint, so it is no single run from power-on: {NEW_RUN} with no "
            "restores, and name that recording."
        )
    return None


def read_run(root: Path, value: str) -> tuple[dict | None, str | None]:
    """The recorded run ``value`` names as the report keeps it (``recordingPath``, ``sessionId``, ``status``,
    ``frames``, ``outcome`` when it was stopped with one), or (None, why it is no finishable run of this build):
    it must be a recording inside the project, of the game's ROM as it is now, that restored no checkpoint and
    has ended."""
    real, manifest, why = find_recording(root, value)
    if why:
        return None, why
    game, rom, why = current_rom(root)
    if why:
        return None, why
    played = played_rom(manifest)
    if played != rom:
        return None, (
            f"finishRun: {value} played another ROM ({str(played or 'unknown')[:12]}), not this build's "
            f"{game.relative_to(root).as_posix()} ({rom[:12]}): {NEW_RUN}, and name that recording."
        )
    why = unfinished(manifest, value)
    if why:
        return None, why
    run = {
        "recordingPath": str(real),
        "sessionId": manifest.get("sessionId"),
        "status": manifest.get("status"),
        "frames": manifest.get("totalFrames"),
    }
    if manifest.get("outcome"):
        run["outcome"] = manifest["outcome"]
    return run, None
