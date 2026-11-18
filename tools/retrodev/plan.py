"""Steps 2 and 3 of the working agreement: the agent writes a plan, the owner revises it or says start.

    plan new <topic>                       write notes/plans/<topic>.md (git-ignored) from the template
    plan show [topic]                      the plan and its approval (no topic: every plan)
    plan approve <topic> --words "..."     record the owner's go, with the time and their exact words

Plans live in the main checkout's notes/plans/ (git ignores notes/), so every worktree finds the same file.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from . import repo, state
from .output import OWNER, Failure

TEMPLATE = """# Plan: {topic}

Status: draft for the owner's approval.

## Goal
<!-- What the change is for, in one or two sentences. -->

## What changes
<!-- The behaviour and the code that change, step by step. -->

## Where files go
<!-- New and moved files, by folder (tools/layout.toml has the map). -->

## How it is tested
<!-- The tests added or changed, and the checks that prove it (python tools/retrodev check). -->

## How the owner and users use it
<!-- Commands, pages or tools, and what they see. -->

## Not in scope
<!-- What this change deliberately leaves out. -->
"""


def plan_file(ctx, topic: str) -> Path:
    return repo.main_checkout(ctx.top) / "notes" / "plans" / f"{state.check_topic(topic)}.md"


def fingerprint(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def new(ctx, topic: str) -> int:
    path = plan_file(ctx, topic)
    record = state.load_plan(ctx.top, topic) or {"topic": topic, "created": state.now()}
    record["path"] = str(path)
    if path.exists():
        ctx.out.say(f"kept: {path} already exists (edit it; nothing was overwritten)")
        created = False
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(TEMPLATE.format(topic=topic), encoding="utf-8")
        ctx.out.say(f"wrote {path}")
        created = True
    state.save_plan(ctx.top, record)
    ctx.out.say(
        f"next: fill it in, show it to the owner; when they say start: python tools/retrodev plan approve "
        f'{topic} --words "<their exact words>"'
    )
    ctx.out.set(topic=topic, path=str(path), created=created)
    return 0


def describe(ctx, topic: str) -> dict:
    path = plan_file(ctx, topic)
    record = state.load_plan(ctx.top, topic) or {}
    approved = record.get("approved")
    changed = bool(approved and approved.get("sha256") and approved["sha256"] != fingerprint(path))
    return {
        "topic": topic,
        "path": str(path),
        "exists": path.is_file(),
        "approved": approved,
        "changed_since_approval": changed,
    }


def known_topics(ctx) -> list[str]:
    folder = repo.main_checkout(ctx.top) / "notes" / "plans"
    on_disk = {path.stem for path in folder.glob("*.md") if state.NAME.match(path.stem)} if folder.is_dir() else set()
    return sorted(on_disk | {record["topic"] for record in state.plans(ctx.top)})


def show(ctx, topic: str | None) -> int:
    if topic is None:
        branch = repo.branch(ctx.top)
        topic = state.load_branch(ctx.top, branch).get("topic") if branch else None
    if topic is None:
        rows = [describe(ctx, name) for name in known_topics(ctx)]
        for row in rows:
            ctx.out.say(f"{row['topic']:<28} {approval_line(row)}  {row['path']}")
        if not rows:
            ctx.out.say("no plans yet: python tools/retrodev plan new <topic>")
        ctx.out.set(plans=rows)
        return 0
    row = describe(ctx, topic)
    if not row["exists"]:
        raise Failure(f"there is no plan file {row['path']}", f"python tools/retrodev plan new {topic}")
    text = Path(row["path"]).read_text(encoding="utf-8")
    ctx.out.say(f"{row['path']}\n{approval_line(row)}\n")
    ctx.out.say(text.rstrip())
    ctx.out.set(**row, text=text)
    return 0


def approval_line(row: dict) -> str:
    approved = row.get("approved")
    if not approved:
        return "not approved"
    line = f"approved {approved['at']}: \"{approved['words']}\""
    return line + (" (the plan changed since; show the owner the change)" if row.get("changed_since_approval") else "")


def approve(ctx, topic: str, words: str | None) -> int:
    path = plan_file(ctx, topic)
    if not path.is_file():
        raise Failure(f"there is no plan file {path} to approve", f"python tools/retrodev plan new {topic}")
    if not words or not words.strip():
        raise Failure(
            "an approval records the owner's exact words, so anyone can see who said go and what they said",
            f'python tools/retrodev plan approve {topic} --words "<the owner\'s exact words>"',
            code=OWNER,
        )
    record = state.load_plan(ctx.top, topic) or {"topic": topic, "created": state.now()}
    record.update(path=str(path), approved={"at": state.now(), "words": words.strip(), "sha256": fingerprint(path)})
    state.save_plan(ctx.top, record)
    ctx.out.say(f"approved {topic}: \"{words.strip()}\"")
    ctx.out.say(f"next: python tools/retrodev start feat/{topic}  (or fix/, docs/, chore/)")
    ctx.out.set(topic=topic, approved=record["approved"])
    return 0
