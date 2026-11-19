"""Give each bare ``# noqa: E402`` the standard reason (tests/repo/test_noqa.py wants one on every exception).

E402 here always means the same thing: a file puts the repository root on sys.path before importing from it. So
``python tools/check.py fix`` writes that reason in; any other bare code is left for a person to explain.
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

REASON = "the repository root goes on sys.path first"
FIXED = f"# noqa: E402 - {REASON}"
SKIPPED = ("engine/", "tools/npm/")
BARE = re.compile(r"#\s*noqa\s*:\s*E402\s*$")


def comment_lines(text: str) -> set[int] | None:
    """The 1-based lines whose comment is a bare E402 exception (None when the text does not tokenize)."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return None
    return {token.start[0] for token in tokens if token.type == tokenize.COMMENT and BARE.search(token.string)}


def add_reason(text: str) -> tuple[str, int]:
    """``text`` with the reason added to every bare E402 comment, and how many it changed."""
    lines = text.splitlines(keepends=True)
    found = comment_lines(text)  # a template may not tokenize: then every line ending in the bare comment counts
    changed = 0
    for index, line in enumerate(lines):
        body = line.rstrip("\r\n")
        match = BARE.search(body)
        if match and (found is None or index + 1 in found):
            lines[index] = body[: match.start()] + FIXED + line[len(body) :]
            changed += 1
    return "".join(lines), changed


def fix(root: Path, names: list[str]) -> dict[str, int]:
    """Add the reason in every .py and .py.tmpl file of ``names`` outside the skipped folders; {file: lines}."""
    done = {}
    for name in names:
        if not name.endswith((".py", ".py.tmpl")) or name.startswith(SKIPPED):
            continue
        path = root / name
        text = path.read_text(encoding="utf-8")
        if "E402" not in text:
            continue
        fixed, count = add_reason(text)
        if count:
            path.write_text(fixed, encoding="utf-8")
            done[name] = count
    return done


def report(root: Path, names: list[str]) -> str:
    """Fix the files and say what changed, for python tools/check.py fix."""
    done = fix(root, names)
    return f"gave {sum(done.values())} bare '# noqa: E402' the standard reason" + "".join(f"\n  {n}" for n in done)
