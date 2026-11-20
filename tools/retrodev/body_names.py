"""The names a pull request body's 'What changed' quotes that the code does not have: a warning, never a gate.

A body is often written from the plan before the code, and a name the code then changed (`games.rom_path`, renamed
`games.built_rom` while building) stays in the body the owner reads. ship and check's last line name each
backtick-quoted identifier of 'What changed' that appears nowhere in the branch's diff (either side) or its tree.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import gates, repo

SECTION = "What changed"
QUOTED = re.compile(r"`([^`\n]+)`")
# An identifier, dotted or not, maybe called: `rom_path`, `games.rom_path`, `host.library_game_for()`.
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:\(\))?$")


def quoted_identifiers(text: str) -> list[str]:
    """The identifiers 'What changed' quotes in backticks, in order, each once. Only names that look like code (an
    underscore, a dot or a capital inside: `rom_path`, `games.x`, `useQuery`), so a quoted plain word is never one."""
    lines = gates.section_lines(text).get(SECTION, [])
    found = []
    for line in lines:
        for quoted in QUOTED.findall(line):
            word = quoted.strip()
            if IDENTIFIER.match(word) and re.search(r"[_.]|[a-z][A-Z]", word.removesuffix("()")):
                found.append(word)
    return list(dict.fromkeys(found))


def last_part(name: str) -> str:
    """The part the code spells out: `games.rom_path` is `rom_path` in games.py (def rom_path, games.rom_path(...))."""
    return name.removesuffix("()").rsplit(".", 1)[-1]


def missing(ctx, text: str | None) -> list[str]:
    """The quoted identifiers whose last part is in neither the branch's diff against the base (removed lines
    count: the body may describe a removal) nor any tracked file of the working tree."""
    names = quoted_identifiers(text or "")
    if not names:
        return []
    diff = repo.run(["git", "diff", f"{ctx.remote_base}...HEAD"], ctx.top)[1]
    gone = []
    for name in names:
        word = last_part(name)
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9_])", diff):
            continue
        if repo.run(["git", "grep", "-q", "-w", "-F", "-e", word, "--"], ctx.top)[0] == 0:
            continue
        gone.append(name)
    return gone


def warning(ctx, text: str | None) -> str | None:
    """The one warning line (None when every quoted identifier is in the diff or the tree)."""
    gone = missing(ctx, text)
    if not gone:
        return None
    listed = ", ".join(f"`{name}`" for name in gone)
    return (
        f"warning: the body's 'What changed' names {listed}, which appear(s) nowhere in the branch's diff or tree: "
        "renamed while building? check the body still matches the code (a warning, not a gate)"
    )


def body_warning(ctx, branch: str | None, record: dict) -> str | None:
    """check's last line once the body passes its gate (the recorded body, else notes/pr/<topic>.md): the warning
    above, or None."""
    from . import ship  # ship imports this module

    if not branch or branch in ctx.policy["branches"]["protected"]:
        return None
    chosen = record.get("body")
    path = Path(chosen) if chosen else ship.default_body(ctx, branch, record)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    return None if gates.body_problems(text, ctx.policy["ship"]["sections"]) else warning(ctx, text)


def say(ctx, line: str | None) -> None:
    if line:
        ctx.out.say(line)
        ctx.out.set(body_warning=line)
