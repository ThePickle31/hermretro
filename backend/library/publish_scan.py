"""What a publish must not carry, found before anything leaves the machine: secrets, the user's own folder paths, and
files too large for an install to take (``install_git.MAX_FILE_BYTES`` each, ``install_check.MAX_TOTAL_BYTES`` and
``install_check.MAX_FILES`` in all; GitHub's own limit, 100 MB a file, is above them). Code under ``plugins/`` is
listed for the author: an install asks before it builds a game with any. Standard library only; reads only the files a
publish holds (``release.files``).
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path

from . import install_check, install_git

# Text is read from files up to this size; larger ones are the ROM, art or music, which hold no text worth reading.
MAX_TEXT_BYTES = 2 * 1024 * 1024
# Tokens with a fixed shape (GitHub, AWS, Slack, Google, OpenAI-style and Anthropic-style keys) and key blocks.
_TOKENS = (
    ("a GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b")),
    ("an AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("a Slack token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b")),
    ("a Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("an API key", re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_\-]{20,}\b")),
    ("a private key", re.compile("-----BEGIN [A-Z ]*PRIVATE" + r" KEY-----")),
)
# A value assigned to a name that says it is secret: reported when it looks random (``_random``).
_ASSIGNED = re.compile(
    r"(?i)[\"']?[\w.-]*(?:api[_-]?key|secret|token|passw(?:or)?d|credential)[\w.-]*[\"']?\s*[:=]\s*[\"']?"
    r"([A-Za-z0-9_\-+/=.]{16,})"
)
# An absolute path into someone's own folder: it names them and means nothing on another machine.
_HOME_PATHS = re.compile(r"(?:/home/|/Users/|[A-Za-z]:\\{1,2}Users\\{1,2})[^/\\\s\"'<>]+")
_SHARED_HOMES = frozenset({"Shared", "runner", "user", "username", "you", "me", "<user>", "USER"})
_CODE_SUFFIXES = frozenset({".js", ".mjs", ".cjs", ".ts", ".c", ".h", ".s", ".asm", ".py", ".sh"})


def scan(root: Path, files: list[str]) -> dict:
    """``{blocking, warnings}`` for the files a publish holds (``files``, relative to ``root``). Each finding is
    ``{code, path, message}`` (``line`` too for text). A blocking finding stops the publish until it is fixed; a
    warning is shown to the author and does not."""
    root = Path(root)
    blocking, warnings = [], []
    total = 0
    code = []
    for relative in files:
        path = root / relative
        try:
            size = path.stat().st_size
        except OSError:
            continue
        total += size
        if size > install_git.MAX_FILE_BYTES:
            limit = install_git.MAX_FILE_BYTES // (1024 * 1024)
            blocking.append(
                _finding("FILE_TOO_LARGE", relative, f"{relative} is over {limit} MB; an install refuses it.")
            )
        if relative.startswith("plugins/") and Path(relative).suffix.lower() in _CODE_SUFFIXES:
            code.append(relative)
        if size <= MAX_TEXT_BYTES:
            blocking += _text_findings(path, relative)
    if total > install_check.MAX_TOTAL_BYTES:
        limit = install_check.MAX_TOTAL_BYTES // (1024 * 1024)
        blocking.append(_finding("TOO_LARGE", "", f"The publish holds over {limit} MB; an install refuses it."))
    if len(files) > install_check.MAX_FILES:
        blocking.append(_finding("TOO_MANY", "", f"The publish holds more than {install_check.MAX_FILES} files."))
    if code:
        warnings.append(
            {
                **_finding("PLUGIN_CODE", "plugins", "The game's plugins hold code that runs when someone builds it."),
                "files": sorted(code),
            }
        )
    return {"blocking": blocking, "warnings": warnings}


def _text_findings(path: Path, relative: str) -> list[dict]:
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    found = []
    own = os.path.expanduser("~")
    for number, line in enumerate(text.splitlines(), start=1):
        for label, pattern in _TOKENS:
            if pattern.search(line):
                found.append(_line("SECRET", relative, number, f"{relative} line {number} looks like {label}."))
        for match in _ASSIGNED.finditer(line):
            if _random(match.group(1)):
                found.append(_line("SECRET", relative, number, f"{relative} line {number} looks like a secret value."))
        for match in _HOME_PATHS.finditer(line):
            if re.split(r"[/\\]+", match.group(0).rstrip("/\\"))[-1] not in _SHARED_HOMES:
                found.append(_line("HOME_PATH", relative, number, f"{relative} line {number} names a home folder."))
        if len(own) > 1 and own in line and not _HOME_PATHS.search(line):
            found.append(_line("HOME_PATH", relative, number, f"{relative} line {number} names your home folder."))
    return found


def _random(value: str) -> bool:
    """Whether ``value`` looks like a generated secret rather than a word or a setting: long, mixed and high in
    entropy."""
    if len(value) < 16 or value.isalpha() or value.isdigit():
        return False
    counts = {character: value.count(character) for character in set(value)}
    entropy = -sum(n / len(value) * math.log2(n / len(value)) for n in counts.values())
    return entropy >= 3.5


def _finding(code: str, path: str, message: str) -> dict:
    return {"code": code, "path": path, "message": message}


def _line(code: str, path: str, line: int, message: str) -> dict:
    return {**_finding(code, path, message), "line": line}
