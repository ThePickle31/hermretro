"""The names a pull request body's 'What changed' quotes that the code does not have: a warning, never a gate.

A body is often written from the plan before the code, and a name the code then changed (`games.rom_path`, renamed
`games.built_rom` while building) stays in the body the owner reads. ship and check's last line name each
backtick-quoted identifier of 'What changed' that appears nowhere in the branch's diff (either side) or its tree,
and each backtick-quoted file path (a slash in it, or a known suffix) the branch's diff does not touch.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import gates, repo

SECTION = "What changed"
QUOTED = re.compile(r"`([^`\n]+)`")
# An identifier, dotted or not, maybe called: `rom_path`, `games.rom_path`, `host.library_game_for()`.
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:\(\))?$")


# A file suffix a quoted name is taken as a path by (`ship.py` is a file, not the identifier `ship.py`).
SUFFIXES = (".py", ".js", ".mjs", ".md", ".toml", ".yaml", ".yml", ".json", ".tmpl", ".css", ".html", ".sh", ".txt")
PATH = re.compile(r"^[\w.@-]+(?:/[\w.@-]+)*/?$")


def is_path(word: str) -> bool:
    return bool(PATH.match(word)) and ("/" in word or word.lower().endswith(SUFFIXES)) and not word.startswith("/")


def quoted_paths(text: str) -> list[str]:
    """The file paths 'What changed' quotes in backticks (`tools/retrodev/sync.py`, `sync.py`, `backend/library/`),
    in order, each once; a path with a placeholder or a space in it is not one."""
    found = [
        quoted.strip()
        for line in gates.section_lines(text).get(SECTION, [])
        for quoted in QUOTED.findall(line)
        if is_path(quoted.strip())
    ]
    return list(dict.fromkeys(found))


def untouched(ctx, text: str | None) -> list[str]:
    """The quoted paths the branch's changes (committed, uncommitted and new files) do not touch: no changed file is
    that path, ends with it (a bare file name), or lies under it (a folder)."""
    paths = quoted_paths(text or "")
    changed = repo.changed_files(ctx.top, ctx.remote_base) if paths else []
    if not paths or changed is None:
        return []
    return [
        path
        for path in paths
        if not any(
            name == path or name.endswith("/" + path) or name.startswith(path.rstrip("/") + "/") for name in changed
        )
    ]


def quoted_identifiers(text: str) -> list[str]:
    """The identifiers 'What changed' quotes in backticks, in order, each once. Only names that look like code (an
    underscore, a dot or a capital inside: `rom_path`, `games.x`, `useQuery`), so a quoted plain word is never one."""
    lines = gates.section_lines(text).get(SECTION, [])
    found = []
    for line in lines:
        for quoted in QUOTED.findall(line):
            word = quoted.strip()
            if is_path(word):
                continue  # a file: quoted_paths
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
    """The warning (None when every quoted identifier is in the diff or the tree and every quoted path is in the
    branch's diff): a line for the identifiers, a line for the paths."""
    lines = []
    gone = missing(ctx, text)
    if gone:
        listed = ", ".join(f"`{name}`" for name in gone)
        lines.append(
            f"warning: the body's 'What changed' names {listed}, which appear(s) nowhere in the branch's diff or tree: "
            "renamed while building? check the body still matches the code (a warning, not a gate)"
        )
    away = untouched(ctx, text)
    if away:
        listed = ", ".join(f"`{path}`" for path in away)
        lines.append(
            f"warning: the body's 'What changed' names the file(s) {listed}, which the branch's diff does not touch: "
            "a typo, or a change that went elsewhere? check the body against git diff --stat (a warning, not a gate)"
        )
    return "\n".join(lines) or None


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
