"""A pull request body's `## ` sections, read and rewritten the same way (a heading inside fenced code is no
heading, and the last section may end without a newline), and the Review section a review writes into it.
Standard library only."""

from __future__ import annotations

import re

FENCE = re.compile(r"^\s*(```|~~~)")


def sections(body: str) -> list[tuple[str | None, int, int]]:
    """(heading name, start, end) of each part of body, in order: the text before the first heading has name None,
    each `## <name>` section runs from its heading to the next one outside fenced code, or to the end."""
    found: list[tuple[str | None, int, int]] = []
    name: str | None = None
    start = offset = 0
    fenced = False
    for line in body.splitlines(keepends=True):
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced and line.startswith("## "):
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


def review_text(tier_name: str, records: list[dict]) -> str:
    """The Review section: a line per pass (or that a light change is not reviewed), the answers that left something
    as it was, and what is left for after the merge."""
    if not records:
        return f"Tier {tier_name} · not reviewed." if tier_name == "light" else "Under review."
    passes = []
    for record in records:
        models = record["model"] + (f" + {record['security_model']}" if record.get("security_model") else "")
        tally: dict[str, int] = {}
        for o in record["outcomes"]:
            key = f"{o['label']} {o['answer']}"
            tally[key] = tally.get(key, 0) + 1
        said = ", ".join(f"{count} {key}" for key, count in tally.items()) or "no findings"
        passes.append(f"pass {record['pass']} ({models}): {said}")
    lines = [f"Tier {tier_name} · " + " · ".join(passes) + "."]
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
