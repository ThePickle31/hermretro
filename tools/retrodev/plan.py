"""Steps 2 and 3 of the working agreement: the agent writes a plan, the owner revises it or says start.

    plan new <topic>                       write notes/plans/<topic>.md (git-ignored) from the template
    plan show [topic]                      the plan and its approval (no topic: every plan)
    plan approve <topic> --words "..."     record the owner's go, with the time and their exact words

Plans live in the main checkout's notes/plans/ (git ignores notes/), so every worktree finds the same file.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from . import gates, repo, state
from .output import OWNER, Failure, cmd

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
        f"next: fill in every section (edit it in place: {path}), show it to the owner; when they say start: "
        f'python tools/retrodev plan approve {topic} --words "<their exact words>"'
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
        record = state.load_branch(ctx.top, branch) if branch else {}
        topic = record.get("plan") or record.get("topic")  # the plan it works under, which may cover several
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
    empty = unfilled(path.read_text(encoding="utf-8"))
    if empty:
        raise Failure(
            f"the plan {path} is still the template: "
            + ", ".join(f"'## {name}'" for name in empty)
            + " hold only its comments (the owner approves what the plan says, as ship needs a filled-in body)",
            f"fill in notes/plans/{topic}.md first ({path}), show it to the owner, then plan approve again",
        )
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
    linked = linked_branches(ctx, topic)
    if linked:
        stale = {str(tree.branch): tree for tree in repo.worktrees(ctx.main()) if not tree.path.is_dir()}
        for row in linked:
            branch, where = row["branch"], row["worktree"]
            if where:
                ctx.out.say(f"next: {branch} already works under it: {cmd('cd', where)} && python tools/retrodev check")
                continue
            gone = restore_command(ctx, branch, stale.get(branch))
            ctx.out.say(f"next: {branch} already works under it, but its worktree is gone: {gone}")
        ctx.out.say(f"another branch under this plan: python tools/retrodev start <kind>/<topic> --plan {topic}")
    else:
        ctx.out.say(
            f"next: python tools/retrodev start <kind>/{topic}, kind one of: feat (a new ability), fix (a bug), docs "
            "(documentation only), chore (refactors of tests, tools and CI that change no behaviour)"
        )
    ctx.out.set(topic=topic, approved=record["approved"], linked=linked)
    return 0


def unfilled(text: str) -> list[str]:
    """The plan's sections with nothing but the template's comments (a plan in another shape keeps its own
    headings: only an empty one counts), or ['the whole plan'] when it says nothing at all."""
    sections = gates.section_lines(text)
    if not sections:
        bare = [line for line in gates.COMMENT.sub("", text).splitlines() if line.strip() and not line.startswith("#")]
        return [] if bare else ["the whole plan"]
    return [name for name, lines in sections.items() if not lines]


def restore_command(ctx, branch: str, registered=None) -> str:
    """The command (run in the main checkout) that brings back a branch's worktree: at the folder git still has
    registered, after a prune (a folder deleted by hand stays registered, and git worktree add refuses it until
    then), or where start puts it."""
    folder = registered.path if registered else ctx.worktree_root() / branch.partition("/")[2]
    prune = "git worktree prune && " if registered else ""
    add = cmd("git", "worktree", "add", folder, branch)
    return f"{prune}{add} && {cmd('cd', folder)} && python tools/retrodev status"


def linked_branches(ctx, topic: str) -> list[dict]:
    """The branches working under this plan: recorded ones (named by --plan or plan link, or by their own topic)
    and any local <kind>/<topic> branch (one made by hand has no record), with their worktree (None when gone)."""
    trees = {str(tree.branch): str(tree.path) for tree in repo.worktrees(ctx.main()) if tree.path.is_dir()}
    names = set()
    for record in state.branches(ctx.top):
        branch = record.get("branch")
        if branch and (record.get("plan") or record.get("topic")) == topic:
            names.add(branch)
    kinds = ctx.policy["branches"]["kinds"]
    local = repo.git(["for-each-ref", "--format=%(refname:short)", "refs/heads/"], ctx.top, check=False).split()
    names |= {name for name in local if name.partition("/")[0] in kinds and name.partition("/")[2] == topic}
    return [{"branch": branch, "worktree": trees.get(branch) or None} for branch in sorted(names)]


def link(ctx, topic: str) -> int:
    """Record that the current branch works under an approved plan (a plan may cover several branches)."""
    topic = state.check_topic(topic)
    here = ctx.cwd
    branch = repo.branch(here)
    if not branch or branch in ctx.policy["branches"]["protected"]:
        raise Failure(
            f"{branch or 'a detached HEAD'} is not a work branch; a plan is linked from the branch that does the work",
            "cd into the branch's worktree (python tools/retrodev status in the main checkout lists them)",
        )
    if not plan_file(ctx, topic).is_file():
        raise Failure(f"there is no plan '{topic}'", f"python tools/retrodev plan new {topic}")
    record = state.load_branch(ctx.top, branch)
    kind, _, named = branch.partition("/")
    record.setdefault("branch", branch)
    record.setdefault("kind", kind)
    record.setdefault("topic", named)
    record.setdefault("worktree", str(repo.toplevel(here)))
    record["plan"] = topic
    state.save_branch(ctx.top, record)
    row = describe(ctx, topic)
    ctx.out.say(f"{branch} works under the plan {topic} ({'approved' if row['approved'] else 'NOT approved yet'})")
    ctx.out.set(branch=branch, plan=topic, approved=bool(row["approved"]))
    return 0
