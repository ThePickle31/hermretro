"""A pull request body's `## ` sections, read and rewritten the same way (a heading inside fenced code is no
heading, and the last section may end without a newline), and the Review section a review writes into it.
Standard library only."""

from __future__ import annotations

import re

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def unfenced(text: str):
    """Each line of text (newline kept), and whether it is outside fenced code, as CommonMark reads fences: one opens
    on three or more backticks or tildes (a backtick fence's info string has no backtick, so ```a``` is inline code)
    and closes on the same marker, at least as long, with nothing after it."""
    fence = ""  # the open fence's marker, or ''
    for line in text.splitlines(keepends=True):
        match = FENCE.match(line.rstrip("\n"))
        if match and not fence:
            if match.group(1)[0] == "~" or "`" not in match.group(2):
                fence = match.group(1)
                yield line, False
                continue
        elif (
            match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence) and not match.group(2).strip()
        ):
            fence = ""
            yield line, False
            continue
        yield line, not fence


def sections(body: str) -> list[tuple[str | None, int, int]]:
    """(heading name, start, end) of each part of body, in order: the text before the first heading has name None,
    each `## <name>` section runs from its heading to the next one outside fenced code, or to the end."""
    found: list[tuple[str | None, int, int]] = []
    name: str | None = None
    start = offset = 0
    for line, outside in unfenced(body):
        if outside and line.startswith("## "):
            found.append((name, start, offset))
            name, start = line[3:].strip(), offset
        offset += len(line)
    found.append((name, start, len(body)))
    return found


def section(body: str, name: str) -> str:
    """The text of the section called name, without its heading, or ''."""
    for found, start, end in sections(body):
        if found == name:
            return body[start:end].split("\n", 1)[1].strip() if "\n" in body[start:end] else ""
    return ""


def replace_section(body: str, name: str, text: str) -> str:
    """body with the section called name holding text instead, or with it added at the end."""
    new = f"## {name}\n{text.strip()}\n"
    for found, start, end in sections(body):
        if found == name:
            rest = body[end:]
            return body[:start] + new + ("\n" + rest if rest else "")
    return body.rstrip() + "\n\n" + new


def review_text(records: list[dict]) -> str:
    """The Review section: a line per pass with its tier, models and outcome (or, with none, that the change is light
    and not reviewed), the answers that left something as it was, and what is left for after the merge."""
    if not records:
        return "Tier light · not reviewed."
    passes = []
    for record in records:
        models = record["model"] + (f" + {record['security_model']}" if record.get("security_model") else "")
        tally: dict[str, int] = {}
        for o in record["outcomes"]:
            key = f"{o['label']} {o['answer']}"
            tally[key] = tally.get(key, 0) + 1
        said = ", ".join(f"{count} {key}" for key, count in tally.items()) or "no findings"
        passes.append(f"pass {record['pass']}, {record.get('tier') or 'standard'} ({models}): {said}")
    line = " · ".join(passes)
    lines = [line[:1].upper() + line[1:] + "."]
    kept = [
        (r["pass"], o)
        for r in records
        for o in r["outcomes"]
        if o["answer"] in ("wrong", "intentional", "declined", "kept")
    ]
    left = [o for r in records for o in r["outcomes"] if o["answer"] == "noted"]
    if kept:
        lines += ["", "Answered without a change:"]
        lines += [f"- Pass {n}, {o['label']} {o['answer']}: {o['what']} — {o['reason']}" for n, o in kept]
    if left:
        lines += ["", "Left for after the merge:"] + [f"- {o['label']}: {o['what']}" for o in left]
    return "\n".join(lines)
