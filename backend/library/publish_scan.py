"""What a publish must not carry, found before anything leaves the machine: secrets, the user's own folder paths, and
files an install would refuse (``install_git.MAX_FILE_BYTES`` each, ``install_check.MAX_TOTAL_BYTES`` and
``install_check.MAX_FILES`` in all; GitHub's own limit, 100 MB a file, is above them). Code under ``plugins/`` is
listed for the author: an install asks before it builds a game with any. Standard library only.

Only the files a publish holds are read (``release.files``), each opened without following a link anywhere on its
path and read up to the per-file limit. Text (UTF-8, or UTF-16 with its byte-order mark) is read line by line; a ROM's
printable strings are read too; other binary files (art, music) are not. A file that cannot be read is reported.
"""

from __future__ import annotations

import math
import os
import re
import stat
from pathlib import Path

from . import install_check, install_git

MAX_READ_BYTES = install_git.MAX_FILE_BYTES
ROM_SUFFIXES = frozenset({".gb", ".gbc"})
# Binary files a game holds, which hold no text: not read.
BINARY_SUFFIXES = frozenset(
    {".png", ".gif", ".jpg", ".jpeg", ".bmp", ".uge", ".mod", ".wav", ".vgm", ".fur", ".ogg", ".mp3", ".ttf", ".otf"}
)
CODE_SUFFIXES = frozenset({".js", ".mjs", ".cjs", ".ts", ".c", ".h", ".s", ".asm", ".py", ".sh"})
# Tokens with a fixed shape, each bounded so a long line costs little. GitHub App installation tokens (``ghs_``) are
# also long JWTs with dots since 2026 (GitHub's changelog), so that rule takes dots and dashes.
TOKENS = (
    ("a GitHub token", re.compile(r"\bgh[pour]_[A-Za-z0-9]{36,255}\b|\bgithub_pat_[A-Za-z0-9_]{60,255}\b")),
    ("a GitHub App token", re.compile(r"\bghs_[A-Za-z0-9._\-]{36,1024}")),
    ("an AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("a Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,255}")),
    ("a Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("an API key", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_\-]{20,255}")),
    ("a private key", re.compile("-----BEGIN [A-Z ]{0,40}PRIVATE" + r" KEY-----")),
)
# ``name = value`` or ``"name": "value"``: a name starts after a non-name character, so each costs one try.
ASSIGNMENT = re.compile(r"(?<![\w.-])[\"']?([\w.-]{1,64})[\"']?[ \t]{0,8}[:=][ \t]{0,8}[\"']?([^\s\"',;]{1,256})")
PASSWORD_NAMES = ("password", "passwd", "passphrase")
SECRET_NAMES = ("apikey", "api_key", "api-key", "secret", "token", "credential", "private_key", "access_key")
# An absolute path into someone's own folder: it names them and means nothing on another machine. It starts a path
# (not inside a URL such as https://host/home/...).
UNIX_HOME = re.compile(r"(?<![\w.:/-])/(?:home|Users)/([^/\s\"'<>]+)")
WINDOWS_HOME = re.compile(r"(?i)(?<![\w/\\.-])[a-z]:\\{1,2}users\\{1,2}([^\\/\s\"'<>]+)")
PLACEHOLDER_HOMES = frozenset({"shared", "user", "username", "you", "<user>", "$user", "%username%"})
ROM_STRINGS = re.compile(rb"[\x20-\x7e]{6,512}")


def scan(root: Path, files: list[str]) -> dict:
    """``{blocking, warnings}`` for the files a publish holds (``files``, relative to ``root``). Each finding is
    ``{code, path, message}`` (``line`` too for text). A blocking finding stops the publish until it is fixed; a
    warning is shown to the author and does not."""
    root = Path(root)
    blocking, warnings, code, total = [], [], [], 0
    for relative in files:
        suffix = Path(relative).suffix.lower()
        if relative.startswith("plugins/") and suffix in CODE_SUFFIXES:
            code.append(relative)
        try:
            data, size = read(root, relative)
        except OSError as error:
            blocking.append(
                _finding("UNREADABLE", relative, f"{relative} cannot be read safely: {error.strerror or error}.")
            )
            continue
        total += size
        if data is None:
            limit = MAX_READ_BYTES // (1024 * 1024)
            blocking.append(
                _finding("FILE_TOO_LARGE", relative, f"{relative} is over {limit} MB; an install refuses it.")
            )
            continue
        if suffix in ROM_SUFFIXES:
            for match in ROM_STRINGS.finditer(data):
                blocking += line_findings(relative, 0, match.group().decode("ascii"))
        elif suffix not in BINARY_SUFFIXES:
            text = decode(data)
            if text is None:
                warnings.append(_finding("NOT_TEXT", relative, f"{relative} is not text this scan can read."))
                continue
            for number, line in enumerate(text.splitlines(), start=1):
                blocking += line_findings(relative, number, line)
    if total > install_check.MAX_TOTAL_BYTES:
        limit = install_check.MAX_TOTAL_BYTES // (1024 * 1024)
        blocking.append(_finding("TOO_LARGE", "", f"The publish holds over {limit} MB; an install refuses it."))
    if len(files) > install_check.MAX_FILES:
        blocking.append(_finding("TOO_MANY", "", f"The publish holds more than {install_check.MAX_FILES} files."))
    if code:
        found = _finding("PLUGIN_CODE", "plugins", "The game's plugins hold code that runs when someone builds it.")
        warnings.append({**found, "files": sorted(code)})
    return {"blocking": blocking, "warnings": warnings}


def read(root: Path, relative: str) -> tuple[bytes | None, int]:
    """``(the file's bytes, its size)``, or ``(None, its size)`` for one over ``MAX_READ_BYTES``. Every folder on the
    way and the file itself are opened without following a link, and the file must be a regular file."""
    parts = Path(relative).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise OSError(0, "not a path inside the game")
    folder = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts[:-1]:
            inner = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=folder)
            os.close(folder)
            folder = inner
        handle = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=folder)
    finally:
        os.close(folder)
    with os.fdopen(handle, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise OSError(0, "not a regular file")
        if info.st_size > MAX_READ_BYTES:
            return None, info.st_size
        data = stream.read(MAX_READ_BYTES + 1)
    return (None if len(data) > MAX_READ_BYTES else data), max(info.st_size, len(data))


def decode(data: bytes) -> str | None:
    """Text as UTF-8 (a byte-order mark allowed) or UTF-16 with its byte-order mark; None for anything else."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        encoding = "utf-16"
    else:
        encoding = "utf-8-sig"
    try:
        return data.decode(encoding)
    except UnicodeDecodeError:
        return None


def line_findings(relative: str, number: int, line: str) -> list[dict]:
    """The secrets and home-folder paths on one line of a file (``number`` 0 for a ROM's strings)."""
    where = f"{relative} line {number}" if number else relative
    found = []
    for label, pattern in TOKENS:
        if pattern.search(line):
            found.append(_line("SECRET", relative, number, f"{where} looks like {label}."))
    for match in ASSIGNMENT.finditer(line):
        name, value = match.group(1).lower(), match.group(2)
        password = any(word in name for word in PASSWORD_NAMES) and len(value) >= 4
        if password or (any(word in name for word in SECRET_NAMES) and looks_random(value)):
            found.append(_line("SECRET", relative, number, f"{where} assigns a secret value to {match.group(1)}."))
    if home_paths(line):
        found.append(_line("HOME_PATH", relative, number, f"{where} names a home folder."))
    return found


def home_paths(line: str) -> bool:
    """Whether ``line`` holds an absolute path into a person's home folder (this user's own first, then anyone's but
    a placeholder's)."""
    own = os.path.expanduser("~").rstrip("/\\")
    if len(own) > 1 and own in line:
        return True
    for pattern in (UNIX_HOME, WINDOWS_HOME):
        for match in pattern.finditer(line):
            if match.group(1).lower() not in PLACEHOLDER_HOMES:
                return True
    return False


def looks_random(value: str) -> bool:
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
    return {**_finding(code, path, message), "line": line or None}
