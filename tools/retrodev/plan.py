"""Steps 2 and 3 of the working agreement: the agent writes a plan, the owner revises it or says start.

    plan new <topic>                       write notes/plans/<topic>.md (git-ignored) from the template
    plan show [topic]                      the plan and its approval (no topic: every plan)
    plan approve <topic> --words "..."     record the owner's go, with the time and their exact words

Plans live in the main checkout's notes/plans/ (git ignores notes/), so every worktree finds the same file.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from . import gates, repo, state
from .output import OWNER, Failure, cmd

TEMPLATE = """# Plan: {topic}

Status: draft for the owner's approval.

Title: <!-- One plain sentence, at most 100 characters, no trailing period: the pull request's title (ship --title). -->

## Goal
<!-- What the change is for, in one or two sentences. -->

## What changes
<!-- The behaviour and the code that change, step by step, in the present tense ('X does Y'): start copies
this section into the pull request body's What changed. -->

## Where files go
<!-- New and moved files, by folder (tools/layout.toml has the map). `python tools/retrodev new <kind> ... --dry-run`
lists the files a new feature, rpc, tool, event, listener, page, tab, slot or contribution writes (it writes
nothing, so it runs on dev too). -->

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
            f"fill in {path} first, show it to the owner, then plan approve again",
        )
    said = title_line(path.read_text(encoding="utf-8"))
    title = gates.title_gate(said or "", f"the Title: line of {path}") if said is not None else None
    if title and not title.ok:  # ship's own title gate: the title is settled before the work starts
        raise Failure(f"the plan's title: {title.message}", f"{title.fix}; then plan approve again")
    if not words or not words.strip():
        raise Failure(
            "an approval records the owner's exact words, so anyone can see who said go and what they said",
            f'python tools/retrodev plan approve {topic} --words "<the owner\'s exact words>"',
            code=OWNER,
        )
    at = state.now()
    mark_approved(path, at[:10], words.strip())
    record = state.load_plan(ctx.top, topic) or {"topic": topic, "created": state.now()}
    record.update(path=str(path), approved={"at": at, "words": words.strip(), "sha256": fingerprint(path)})
    state.save_plan(ctx.top, record)
    ctx.out.say(f"approved {topic}: \"{words.strip()}\"")
    here_body(ctx, topic)
    linked = linked_branches(ctx, topic)
    if linked:
        from . import status, sync  # status imports this module

        stale = {str(tree.branch): tree for tree in repo.worktrees(ctx.main()) if not tree.path.is_dir()}
        for row in linked:
            branch, where = row["branch"], row["worktree"]
            if where:
                behind = status.behind(ctx, Path(where))  # status's rule: sync first while HEAD lacks base commits
                run = sync.runner(ctx, Path(where))  # the newer retrodev while the branch's own copy is older
                sync_prefix = (
                    f"{run} sync (HEAD lacks {behind} commit(s) of {ctx.remote_base}), then " if behind else ""
                )
                ctx.out.say(f"next: {branch} already works under it: {cmd('cd', where)} && {sync_prefix}{run} check")
                continue
            gone = restore_command(ctx, branch, stale.get(branch))
            ctx.out.say(f"next: {branch} already works under it, but its worktree is gone: {gone}")
        ctx.out.say(f"another branch under this plan: python tools/retrodev start <kind>/<topic> --plan {topic}")
    else:
        ctx.out.say(
            f"next: python tools/retrodev start <kind>/{topic}, kind one of: feat (a new ability), fix (a bug), docs "
            "(documentation only), chore (refactors that change no behaviour)"
        )
    ctx.out.set(topic=topic, approved=record["approved"], linked=linked)
    return 0


STATUS = re.compile(r"^Status:.*$", re.M)


def mark_approved(path: Path, day: str, words: str) -> None:
    """The plan's 'Status:' line says the approval (approved <YYYY-MM-DD>: "<words>"), so the file read alone no
    longer says draft; a plan without one in its header is left as it is. Run before the approval's hash is taken."""
    text = path.read_text(encoding="utf-8")
    said = " ".join(words.split())
    line = f'Status: approved {day}: "{said}"'
    head, sep, rest = text.partition("\n## ")  # only the header's line: a section may quote one
    if STATUS.search(head):
        path.write_text(STATUS.sub(lambda _m: line, head, count=1) + sep + rest, encoding="utf-8")


def here_body(ctx, topic: str) -> None:
    """plan approve run in a work branch that works under this plan (any name: a taken-over test/x too): write its
    pull request body now (as start does), from the template and the plan; an existing one is kept."""
    branch = repo.branch(ctx.top)
    if not branch or branch in ctx.policy["branches"]["protected"]:
        return
    record = state.load_branch(ctx.top, branch)
    if gates.plan_for(ctx, branch, record) != topic:
        return
    from . import start  # start imports ship, which imports this module

    ctx.out.set(body=start.body_note(ctx, branch, record))


def title_line(text: str) -> str | None:
    """The plan's 'Title:' line without its template comment ('' when it says nothing), None without one (a plan
    written by hand in another shape)."""
    lines = gates.COMMENT.sub("", text).splitlines()
    return next((line[6:].strip() for line in lines if line.startswith("Title:")), None)


def title_skipped(text: str) -> str | None:
    """Why a plan's Title: line is not offered as the --title (check, status and ship then say so): its problems."""
    said = title_line(text)
    return "; ".join(gates.title_problems(said)).replace("the title", "the plan's title") if said else None


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
    before = gates.plan_for(ctx, branch, record) if record else None
    if before and before != topic and state.NAME.match(before):  # relinked: it no longer works under the old plan
        state.forget_plan_branch(ctx.top, before, branch)
    kind, _, named = branch.partition("/")
    record.setdefault("branch", branch)
    record.setdefault("kind", kind)
    record.setdefault("topic", named)
    record.setdefault("worktree", str(repo.toplevel(here)))
    record["plan"] = topic
    record.setdefault("created", state.now())
    state.save_branch(ctx.top, record)
    remember(ctx, branch, record)
    row = describe(ctx, topic)
    ctx.out.say(f"{branch} works under the plan {topic} ({'approved' if row['approved'] else 'NOT approved yet'})")
    ctx.out.set(branch=branch, plan=topic, approved=bool(row["approved"]))
    return 0


LISTS = ("Branches", "PRs", "Pull requests", "Branches/PRs", "Branches and PRs", "Pull requests and branches")


def shared(ctx, branch: str, record: dict) -> bool:
    """The plan covers more than this branch: its Branches/PRs section lists several, or a branch recorded
    earlier (start, plan link, takeover) works under it too. Its Goal, Not in scope and Title then belong to the
    whole plan, not to this branch's pull request."""
    named = gates.plan_for(ctx, branch, record)
    path = plan_file(ctx, named) if named and state.NAME.match(named) else None
    if not named or not path or not path.is_file():
        return False
    found = gates.section_lines(path.read_text(encoding="utf-8"))
    listed = next((found[name] for name in found if name.strip().lower() in {s.lower() for s in LISTS}), [])
    if sum(1 for line in listed if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+\S", line)) > 1:
        return True
    started = started_under(ctx, named)
    mine = min(filter(None, (record.get("created"), started.get(branch))), default=state.now())
    # Another branch started before this one (a record without a time counts), landed and forgotten or not.
    return any(at <= mine for name, at in started.items() if name != branch)


def remember(ctx, branch: str, record: dict) -> None:
    """Note in the plan's own record (state.py) that this branch started under it, so the plan stays shared after
    this branch lands and its record is forgotten. Called by start, plan link and takeover."""
    named = gates.plan_for(ctx, branch, record)
    if named and state.NAME.match(named) and plan_file(ctx, named).is_file():
        state.remember_plan_branch(ctx.top, named, branch, record.get("created") or state.now())


def started_under(ctx, named: str) -> dict[str, str]:
    """Every branch that started under the plan, with the time: the plan record's list (it outlives branch records)
    and the branch records that name it (one recorded before plans kept the list; each is added to the list)."""
    started = dict((state.load_plan(ctx.top, named) or {}).get("branches") or {})
    for other in state.branches(ctx.top):
        name = other.get("branch")
        if not name or gates.plan_for(ctx, name, other) != named:
            continue
        at = other.get("created") or ""
        if name not in started or at < started[name]:
            started[name] = at
            if at:
                state.remember_plan_branch(ctx.top, named, name, at)
    return started


def branch_section(ctx, branch: str, record: dict) -> list[str]:
    """Under a shared plan, the lines of the plan's section for this branch: a '## ' heading naming the branch
    (feat/x) or its topic as a whole word; [] when the plan has none."""
    named = gates.plan_for(ctx, branch, record)
    path = plan_file(ctx, named) if named and state.NAME.match(named) else None
    if not path or not path.is_file():
        return []
    topic = record.get("topic") or branch.partition("/")[2]
    names = [re.escape(branch)] + ([re.escape(topic)] if topic else [])
    pattern = re.compile(rf"(?<![\w/-])(?:{'|'.join(names)})(?![\w/-])")
    found = gates.section_lines(path.read_text(encoding="utf-8"))
    return next((lines for heading, lines in found.items() if pattern.search(heading) and lines), [])


def branch_title(ctx, branch: str, record: dict) -> str | None:
    """The plan's 'Title:' line (the template asks for one plain sentence), else its own title line ('# Plan:
    <words>') when it says more than the topic; None under a shared plan (its title is the whole plan's)."""
    named = gates.plan_for(ctx, branch, record)
    path = plan_file(ctx, named) if named and state.NAME.match(named) else None
    if not path or not path.is_file() or shared(ctx, branch, record):
        return None
    lines = gates.COMMENT.sub("", path.read_text(encoding="utf-8")).splitlines()
    said = next((line[6:].strip() for line in lines if line.startswith("Title:")), "")
    if said and not gates.title_problems(said):
        return said
    first = next((line for line in lines if line.startswith("# ")), "")
    words = first[2:].strip().removeprefix("Plan:").strip()
    return words if words and words != named and not gates.title_problems(words) else None


def title_note(ctx, branch: str | None, record: dict) -> str:
    """' (the plan's Title: line is not offered: <why>)' when the plan has a Title: line ship cannot take, else ''."""
    named = gates.plan_for(ctx, branch, record) if branch else None
    path = plan_file(ctx, named) if named and state.NAME.match(named) else None
    if path and path.is_file() and shared(ctx, branch, record):
        return " (the plan's Title: line is not offered: the plan covers several branches; name this one's change)"
    why = title_skipped(path.read_text(encoding="utf-8")) if path and path.is_file() else None
    return f" (the plan's Title: line is not offered: {why})" if why else ""
