"""Give each bare ``# noqa: E402`` the standard reason (tests/repo/test_noqa.py wants one on every exception).

E402 here always means the same thing: a file puts the repository root on sys.path before importing from it. So
``python tools/check.py fix`` writes that reason in; any other bare code is left for a person to explain. Only a
comment is ever changed: a file that does not tokenize (so its comments cannot be told from its strings) is never
edited, and the report names it for a person to fix by hand.
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


def add_reason(text: str) -> tuple[str, int] | None:
    """``text`` with the reason added to every bare E402 comment, and how many it changed (None: it does not
    tokenize, so nothing is changed: a string's text could look like the comment)."""
    found = comment_lines(text)
    if found is None:
        return None
    lines = text.splitlines(keepends=True)
    changed = 0
    for index, line in enumerate(lines):
        body = line.rstrip("\r\n")
        match = BARE.search(body)
        if match and index + 1 in found:
            lines[index] = body[: match.start()] + FIXED + line[len(body) :]
            changed += 1
    return "".join(lines), changed


def fix(root: Path, names: list[str]) -> tuple[dict[str, int], list[str]]:
    """Add the reason in every .py and .py.tmpl file of ``names`` outside the skipped folders: ({file: lines},
    the files with a bare E402 left as they are because they do not tokenize)."""
    done, skipped = {}, []
    for name in names:
        if not name.endswith((".py", ".py.tmpl")) or name.startswith(SKIPPED):
            continue
        path = root / name
        text = path.read_text(encoding="utf-8")
        if "E402" not in text:
            continue
        result = add_reason(text)
        if result is None:
            if any(BARE.search(line) for line in text.splitlines()):
                skipped.append(name)
            continue
        fixed, count = result
        if count:
            path.write_text(fixed, encoding="utf-8")
            done[name] = count
    return done, skipped


def report(root: Path, names: list[str]) -> str:
    """Fix the files and say what changed and what was skipped, for python tools/check.py fix."""
    done, skipped = fix(root, names)
    out = f"gave {sum(done.values())} bare '# noqa: E402' the standard reason" + "".join(f"\n  {n}" for n in done)
    for name in skipped:
        out += f"\nskipped {name}: it does not tokenize, so its comments cannot be told from its strings"
        out += f"\nFIX: give each bare '# noqa: E402' comment in {name} a reason by hand ('{FIXED}')"
    return out
