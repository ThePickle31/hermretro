"""Count the lines two versions of a file differ in, leaving out changes that are only to comments.

land_carry counts a sync merge's conflict resolution against [land] max_sync_resolution_lines. A resolution that
only touches comments (adding a reason to a noqa, rewording a note) changes no behaviour, so it counts 0. The rules
stay conservative, since a change they wrongly leave out skips a review:

- Python (and its templates): the whole file goes through tokenize, and each line is compared as its tokens (type
  and text) without comments and blank lines, together with its nesting depth (INDENT/DEDENT). So spacing between
  tokens is ignored, while string contents and indentation that changes what a block holds count; a string over
  several lines counts on each line. A file tokenize cannot read is compared line by line, exactly.
- JavaScript: a whole-line '//' comment is left out, and only in a file with no backtick at all (a template literal
  can hold text that looks like a comment); every other line is compared exactly.
- Other files: line by line, exactly.

A conflicted file is compared with git's merge of its sides as code (merge_code): when the two sides differ only in
comments there, that merge is clean, so a resolution that keeps both sides' code and either side's comments counts
0, where the conflict markers and the side left out would otherwise count every line of the hunk.
"""

from __future__ import annotations

import difflib
import io
import json
import tempfile
import tokenize
from pathlib import Path

from . import repo

HASH = (".py", ".py.tmpl", ".pyi")
SLASHES = (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx")
SKIPPED = (tokenize.COMMENT, tokenize.NL, tokenize.ENCODING, tokenize.ENDMARKER)
BY_TYPE = (tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE)  # their text is spacing; the depth tracks INDENT


def python_code(text: str) -> list[str] | None:
    """Each line of Python ``text`` as its nesting depth and tokens, comments left out (None: tokenize failed)."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return None
    rows: dict[int, list] = {}
    depth = {}
    level = 0
    for token in tokens:
        if token.type == tokenize.INDENT:
            level += 1
        elif token.type == tokenize.DEDENT:
            level -= 1
        if token.type in SKIPPED:
            continue
        name = tokenize.tok_name[token.type]
        text_parts = [""] if token.type in BY_TYPE else token.string.split("\n")
        for offset, part in enumerate(text_parts):  # a token over several lines counts on each of them
            row = token.start[0] + offset
            rows.setdefault(row, []).append([name, part])
            depth.setdefault(row, level)
    return [json.dumps([depth[row], rows[row]], ensure_ascii=True) for row in sorted(rows)]


def javascript_code(text: str) -> list[str]:
    """JavaScript ``text``'s lines, whole-line '//' comments left out only when it has no template literal."""
    lines = text.splitlines()
    if "`" in text:
        return lines
    kept, previous = [], ""
    for line in lines:
        if not (line.lstrip().startswith("//") and not previous.endswith("\\")):
            kept.append(line)
        previous = line
    return kept


def code(name: str, text: str) -> list[str]:
    """What counts in ``text``: its lines as compared (see the module's rules)."""
    if name.endswith(HASH):
        lines = python_code(text)
        return text.splitlines() if lines is None else lines
    if name.endswith(SLASHES):
        return javascript_code(text)
    return text.splitlines()


def count(before: list[str], after: list[str]) -> int:
    """Lines removed plus lines added between two lists of code lines (as git's numstat counts them)."""
    matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
    return sum((i2 - i1) + (j2 - j1) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal")


def changed(name: str, before: str, after: str) -> int:
    """Lines of code removed plus added between two versions of the file ``name``."""
    return count(code(name, before), code(name, after))


def merge_code(cwd: Path, name: str, ours: str, base: str, theirs: str) -> list[str] | None:
    """git merge-file of the three versions' code (as code() compares it); None when that conflicts too."""
    with tempfile.TemporaryDirectory(prefix="retrodev-merge-") as folder:
        paths = []
        for side, text in (("ours", ours), ("base", base), ("theirs", theirs)):
            path = Path(folder) / side
            path.write_text("".join(line + "\n" for line in code(name, text)), encoding="utf-8")
            paths.append(str(path))
        exit_code, out, _err = repo.run(["git", "merge-file", "-p", *paths], cwd)
    return out.splitlines() if exit_code == 0 else None
