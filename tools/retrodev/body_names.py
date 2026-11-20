"""The names a pull request body's 'What changed' quotes that the code does not have: a warning, never a gate.

A body is often written from the plan before the code, and a name the code then changed (`games.rom_path`, renamed
`games.built_rom` while building) stays in the body the owner reads. ship and check's last line name each
backtick-quoted identifier of 'What changed' that appears nowhere in the branch's diff (either side) or its tree,
and each backtick-quoted repository path neither the branch's diff nor its own (non-merge) commits touch: a slash
in it and its top folder one of the repository's (TOPS: `backend/x/y.py`, `tools/`), never a bare file name (`tools.py`, a caller cited as unchanged, or
`games.json`, a runtime data file, are no claim the diff can check). Any such path
there is a claim, whatever the verb (`Fixed`, `Updated`, none), unless a citation clause holds it: from an evidence
phrase (CITATION: `checked against`, `comes from`, `see`, `documents`, `describes`, `how to use`, ...) to the
end of the sentence or a new change clause (a `;`, or `and` with a past-tense verb: `and removed`), so every path of a
cited list (`checked against `a` and `b``) is cited. A path under engine/ never warns (never changed outside an engine
update, so only ever cited). A bare `from` cites nothing: `removed the helper from `x`` claims a change to x.
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


# The repository's top folders a quoted path must start with to be checked against the diff (it must exist too).
TOPS = ("backend", "page", "tools", "tests", "docs", "player", "desktop", "skills", "profile", ".github")


def is_repo_path(word: str, top: Path | None = None) -> bool:
    """A repository path the diff can be checked against: a slash in it, under one of TOPS (that exists in ``top``,
    when given); never a bare file name."""
    first = word.split("/", 1)[0]
    if not PATH.match(word) or "/" not in word or word.startswith("/") or first not in TOPS:
        return False
    return top is None or (top / first).is_dir()


def is_path(word: str) -> bool:
    return bool(PATH.match(word)) and ("/" in word or word.lower().endswith(SUFFIXES)) and not word.startswith("/")


# Where a citation clause starts: words that cite what follows as evidence rather than claim a change to it. A
# hyphenated modifier is not one: 'per-game' or 'see-through' describes the change, it cites nothing.
CITATION = re.compile(
    r"(?<![\w-])(?:checked against|verified (?:in|against)|(?:comes?|came|taken|read|reads|copied) from|source:|see|per|"
    r"as in|cited|based on|documents|describes|explains|how to (?:use|run))(?![\w-])",
    re.I,
)
# Where a new change clause starts, ending a citation clause: a semicolon, or `and` with a past-tense verb.
CLAUSE = re.compile(r";|\band\s+(?=[a-z]+ed\b)", re.I)
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z`(])")


def claims(lines: list[str]) -> list[str]:
    """The section's bullets (a wrapped bullet joined back into one) and paragraphs, each split into sentences."""
    blocks: list[str] = []
    for line in lines:
        if not line.strip():
            blocks.append("")
        elif BULLET.match(line) or not blocks or not blocks[-1]:
            blocks.append(line.strip())
        else:
            blocks[-1] += " " + line.strip()
    return [sentence for block in blocks if block for sentence in SENTENCE_END.split(block)]


def claimed(sentence: str) -> list[str]:
    """The paths ``sentence`` claims a change to: every quoted path outside a citation clause (one that starts at a
    CITATION and runs to the sentence's end or the next CLAUSE); never a path under engine/."""
    marks = sorted(
        [(m.start(), True) for m in CITATION.finditer(sentence)]
        + [(m.start(), False) for m in CLAUSE.finditer(sentence)]
    )
    found = []
    for match in QUOTED.finditer(sentence):
        word = match.group(1).strip()
        cited = [citing for at, citing in marks if at < match.start()]
        if is_repo_path(word) and not (cited and cited[-1]):
            found.append(word)
    return [path for path in found if not path.startswith("engine/") and path != "engine"]


def quoted_paths(text: str) -> list[str]:
    """The repository paths 'What changed' quotes in backticks (`tools/retrodev/sync.py`, `backend/library/`; never
    a bare `sync.py`) in sentences that claim a change to them (claimed), in order, each once; a path with a placeholder or a space in
    it is not one."""
    found = [path for sentence in claims(gates.section_lines(text).get(SECTION, [])) for path in claimed(sentence)]
    return list(dict.fromkeys(found))


def own_commits_files(ctx) -> list[str]:
    """The files the branch's own commits touched (merges left out): a merge of the base can drop a branch's edit
    (a taken-over branch), and the body still describes what the branch did."""
    code, out, _err = repo.run(
        ["git", "log", "--no-merges", "--name-only", "--format=", f"{ctx.remote_base}..HEAD"], ctx.top
    )
    return [line for line in out.splitlines() if line.strip()] if code == 0 else []


def untouched(ctx, text: str | None) -> list[str]:
    """The quoted paths the branch's changes (committed, uncommitted and new files) do not touch, nor its own
    commits before a merge dropped their edit (own_commits_files): no such file is that path, ends with it (a bare
    file name), or lies under it (a folder)."""
    paths = [path for path in quoted_paths(text or "") if is_repo_path(path, Path(ctx.top))]
    changed = repo.changed_files(ctx.top, ctx.remote_base) if paths else []
    if not paths or changed is None:
        return []
    changed = [*changed, *own_commits_files(ctx)]
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
            "a typo, or a change that went elsewhere? check the body against git diff --stat; ignore if the file is only "
            "cited (a warning, not a gate)"
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
