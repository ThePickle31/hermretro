"""What a contributor's branch does by hand to the real tree, for test_scaffold_tree.py's nested guard: a test that
pins those lines' current text (rather than comparing with what it read, or using a probe) fails there, in CI.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

NOTE = " (x)"  # harmless: after the sentence, so new's README edits still find their list
NOTED = ("- RPCs", "- Tools")


def note_feature_readmes(tree: Path) -> list[str]:
    """Append NOTE to every real feature README's RPCs, Tools and 'Listens to' lines; the files changed."""
    changed = []
    for readme in sorted(tree.glob("backend/*/README.md")):
        lines = readme.read_text(encoding="utf-8").split("\n")
        noted = [line + NOTE if line.startswith(NOTED) or "Listens to" in line else line for line in lines]
        if noted != lines:
            readme.write_text("\n".join(noted), encoding="utf-8")
            changed.append(str(readme.relative_to(tree)))
    return changed


def one_line_events(door: str, entries: dict[str, str]) -> str:
    """A front door with its EVENTS written on one line, holding ``entries``, as a contributor may write it."""
    node = next(
        n
        for n in ast.parse(door).body
        if isinstance(n, ast.Assign | ast.AnnAssign) and "EVENTS" in ast.unparse(n).split("=")[0]
    )
    lines = door.split("\n")
    one = "EVENTS = {" + ", ".join(f"{json.dumps(name)}: {json.dumps(doc)}" for name, doc in entries.items()) + "}"
    return "\n".join([*lines[: node.lineno - 1], one, *lines[node.end_lineno :]])


def line_of(text: str, start: str) -> str:
    """The first line of ``text`` starting with ``start`` (what a test reads before new edits it)."""
    return next(line for line in text.splitlines() if line.startswith(start))
