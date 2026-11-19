"""Count the lines two versions of a file differ in, leaving out changes only to comments or whitespace.

land_carry counts a sync merge's conflict resolution against [land] max_sync_resolution_lines. A resolution that
only touches comments (adding a reason to a noqa, rewording a note) or spacing changes no behaviour, so it counts 0:
each line is compared with its comment removed (Python and its templates: '#'; JavaScript: '//', outside strings)
and all whitespace dropped, and lines left empty are left out. Other files are compared without their whitespace.

A conflicted file is compared with git's merge of its sides as code (merge_code): when the two sides differ only in
comments there, that merge is clean, so a resolution that keeps both sides' code and either side's comments counts
0, where the conflict markers and the side left out would otherwise count every line of the hunk.
"""

from __future__ import annotations

import difflib
import io
import tempfile
import tokenize
from pathlib import Path

from . import repo

HASH = (".py", ".py.tmpl", ".pyi")
SLASHES = (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx")


def strip_comment(line: str, marker: str, quotes: str) -> str:
    """``line`` up to its comment ``marker`` outside the quotes (one line: a string never spans lines here)."""
    quote, index = None, 0
    while index < len(line):
        char = line[index]
        if quote:
            if char == "\\":
                index += 1
            elif char == quote:
                quote = None
        elif char in quotes:
            quote = char
        elif line.startswith(marker, index):
            return line[:index]
        index += 1
    return line


def python_code(text: str) -> list[str]:
    """Each line of Python ``text`` without its comment (tokenize; a file it cannot read: line by line)."""
    lines = text.splitlines()
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return [strip_comment(line, "#", "'\"") for line in lines]
    for token in tokens:
        if token.type == tokenize.COMMENT and token.start[0] <= len(lines):
            row, col = token.start
            lines[row - 1] = lines[row - 1][:col]
    return lines


def code(name: str, text: str) -> list[str]:
    """What counts in ``text``: its non-empty lines without comments and whitespace."""
    if name.endswith(HASH):
        lines = python_code(text)
    elif name.endswith(SLASHES):
        lines = [strip_comment(line, "//", "'\"`") for line in text.splitlines()]
    else:
        lines = text.splitlines()
    return [kept for kept in ("".join(line.split()) for line in lines) if kept]


def count(before: list[str], after: list[str]) -> int:
    """Lines removed plus lines added between two lists of code lines (as git's numstat counts them)."""
    matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
    return sum((i2 - i1) + (j2 - j1) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal")


def changed(name: str, before: str, after: str) -> int:
    """Lines of code removed plus added between two versions of the file ``name``."""
    return count(code(name, before), code(name, after))


def merge_code(cwd: Path, name: str, ours: str, base: str, theirs: str) -> list[str] | None:
    """git merge-file of the three versions' code (comments and whitespace gone); None when that conflicts too."""
    with tempfile.TemporaryDirectory(prefix="retrodev-merge-") as folder:
        paths = []
        for side, text in (("ours", ours), ("base", base), ("theirs", theirs)):
            path = Path(folder) / side
            path.write_text("".join(line + "\n" for line in code(name, text)), encoding="utf-8")
            paths.append(str(path))
        exit_code, out, _err = repo.run(["git", "merge-file", "-p", *paths], cwd)
    return out.splitlines() if exit_code == 0 else None
