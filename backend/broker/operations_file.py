"""``chromatic_scene_apply``'s operations file: hermretro's own ``operationsPath`` argument, read here in place of
inline ``operations`` before the engine sees the call.

A long batch written inline is one huge tool call the model has to produce in a single message; as a file it can be
written, checked and rewritten like any other. The file must be inside the game's project or the chat's Hermes
scratch folder (``<Hermes home>/cache/scratch``, sent by the gateway as ``policy.scratch_dir``).

Containment is judged by filesystem identity, not by spelling: the folder must be one of the resolved path's
ancestors (the same device and inode), which holds on case-insensitive and case-sensitive volumes alike. The file is
then opened from a descriptor of that folder one component at a time, following no links, so a component replaced
after the check cannot lead outside it, and at most ``MAX_BYTES`` + 1 bytes are read from that same descriptor.
"""

from __future__ import annotations

import json
import math
import os
import stat
from pathlib import Path

from .lane import Denied

ARGUMENT = "operationsPath"
MAX_BYTES = 1024 * 1024
# Far deeper than any batch of operations nests, far shallower than what Python's recursion limit lets the broker
# parse and send on.
MAX_DEPTH = 100
_FOLDER = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
_STEP = _FOLDER | os.O_NOFOLLOW
# Not blocking: a named pipe in the file's place opens at once and is then refused as not a regular file.
_FILE = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


def scene_apply_arguments(root: str | None, arguments: dict, scratch: str | None) -> dict:
    """``arguments`` with ``operationsPath`` replaced by the ``operations`` its file holds: a JSON list of operations,
    or an object whose ``operations`` is that list. A relative path is read from the project folder. Refuses (code
    ``OPERATIONS_FILE``) a file outside the project and the scratch folder, a missing, oversized or unreadable one,
    JSON with non-finite numbers or nested deeper than ``MAX_DEPTH``, and both forms at once."""
    if ARGUMENT not in arguments:
        return arguments
    arguments = dict(arguments)
    asked = arguments.pop(ARGUMENT)
    if "operations" in arguments:
        raise Denied("OPERATIONS_FILE", f"Give operations or {ARGUMENT}, not both.")
    if not isinstance(asked, str) or not asked.strip():
        raise Denied("OPERATIONS_FILE", f"{ARGUMENT} must be the path of a JSON file.")
    folders = [folder for folder in (root, scratch) if folder]
    try:
        if not Path(asked).is_absolute() and not root:
            raise ValueError("a relative path needs a selected project")
        path = Path(root or "", asked).resolve()
        text = _read_beneath(folders, path, asked)
    except (OSError, ValueError) as error:
        raise Denied("OPERATIONS_FILE", f"{asked} cannot be used as an operations file ({error}).") from None
    return {**arguments, "operations": _operations(text, asked)}


def _read_beneath(folders: list[str], path: Path, asked: str) -> bytes:
    """The first ``MAX_BYTES`` + 1 bytes of ``path``, opened beneath whichever of ``folders`` contains it."""
    for folder in folders:
        try:
            directory = os.open(folder, _FOLDER)
        except OSError:
            continue
        try:
            parts = _parts_below(path, os.fstat(directory))
            if parts is not None:
                return _open_and_read(directory, parts, asked)
        finally:
            os.close(directory)
    places = " or ".join(folders)
    raise Denied("OPERATIONS_FILE", f"{asked} is not inside {places}. Write the operations file there.")


def _parts_below(path: Path, folder: os.stat_result) -> tuple[str, ...] | None:
    """``path``'s components below the ancestor that is ``folder`` itself (same device and inode), or None."""
    for ancestor in path.parents:
        try:
            found = os.stat(ancestor)
        except OSError:
            continue
        if (found.st_dev, found.st_ino) == (folder.st_dev, folder.st_ino):
            return path.relative_to(ancestor).parts
    return None


def _open_and_read(directory: int, parts: tuple[str, ...], asked: str) -> bytes:
    """Walks ``parts`` down from ``directory`` without following a link at any step, then reads the regular file."""
    opened: list[int] = []
    try:
        for part in parts[:-1]:
            opened.append(os.open(part, _STEP, dir_fd=opened[-1] if opened else directory))
        handle = os.open(parts[-1], _FILE, dir_fd=opened[-1] if opened else directory)
        opened.append(handle)
        if not stat.S_ISREG(os.fstat(handle).st_mode):
            raise Denied("OPERATIONS_FILE", f"{asked} is not a file.")
        chunks, size = [], 0
        while size <= MAX_BYTES and (chunk := os.read(handle, MAX_BYTES + 1 - size)):
            chunks.append(chunk)
            size += len(chunk)
    except (FileNotFoundError, NotADirectoryError):
        raise Denied("OPERATIONS_FILE", f"{asked} is not a file.") from None
    finally:
        for descriptor in opened:
            os.close(descriptor)
    if size > MAX_BYTES:
        raise Denied("OPERATIONS_FILE", f"{asked} is larger than 1 MiB. Split the batch into several calls.")
    return b"".join(chunks)


def _operations(text: bytes, asked: str) -> list:
    try:
        data = json.loads(text.decode("utf-8"), parse_constant=_not_finite, parse_float=_finite)
    except RecursionError:
        raise Denied("OPERATIONS_FILE", f"{asked} nests deeper than {MAX_DEPTH} levels.") from None
    except (UnicodeDecodeError, ValueError) as error:
        raise Denied("OPERATIONS_FILE", f"{asked} could not be read as JSON: {error}") from None
    if _depth(data) > MAX_DEPTH:
        raise Denied("OPERATIONS_FILE", f"{asked} nests deeper than {MAX_DEPTH} levels.")
    operations = data.get("operations") if isinstance(data, dict) else data
    if not isinstance(operations, list):
        raise Denied(
            "OPERATIONS_FILE", f"{asked} must hold a JSON list of operations, or an object with an operations list."
        )
    return operations


def _not_finite(name: str):
    raise ValueError(f"{name} is not a JSON number")


def _finite(text: str) -> float:
    number = float(text)
    if not math.isfinite(number):
        raise ValueError(f"{text} is too large for a number")
    return number


def _depth(value) -> int:
    """How deeply lists and objects nest in ``value``, counted without recursion."""
    deepest, pending = 0, [(value, 1)]
    while pending:
        value, depth = pending.pop()
        children = value.values() if isinstance(value, dict) else value if isinstance(value, list) else None
        if children is None:
            continue
        deepest = max(deepest, depth)
        if depth > MAX_DEPTH:
            break
        pending.extend((child, depth + 1) for child in children)
    return deepest
