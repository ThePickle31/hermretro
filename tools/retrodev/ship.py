"""Step 4 ends: push the branch and open its draft pull request (or update the open one).

    ship [--title "<one plain sentence>"] [--body <file>] [--new-body] [--dry-run]

The title defaults to the one recorded for the branch (its pull request's, else the last ship's); with none
recorded ship refuses and its FIX names the plan's title. The body defaults to the one recorded (when that file
still exists), else to notes/pr/<topic>.md in the main checkout (git-ignored, so gc is never blocked by it), which
start (or plan approve inside the linked branch) writes early under a plan. Only when that file does not exist (or
with --new-body) does ship write it from .github/pull_request_template.md, with the
plan's Goal as the Why (with --no-plan or an empty Goal, a visible '<!-- no plan: say why -->' instead) and a line
saying an agent made it (RETRODEV_AGENT names the agent, default Hermes; under the template's '## Made by' when it
has one, else after a closing '---', so it fills no section), and its body gate stops: fill it in, then ship
again. Every gate runs in every ship, a missing title included, so one run reports every refusal. A --dry-run
writes the same skeleton and reports the body gate as 'NO  body: fill in <path>'. Every ship command printed during
or after a dry run is a dry run too (all built by command(); the dry run is recorded before any gate can stop it).

Gates (all reported at once): a work branch; the owner approved its plan (docs and chore may go without one);
a one-line title without a trailing period; a branch that changes at least one file; a body with every section of
the pull request template filled in and a line saying an agent made it; everything committed; `check` passed on
exactly this tree; the branch has commits; the remote branch has not moved away from it.
Then `git push -u <remote> <branch>` (a plain push, never anything that rewrites the remote) and
`gh pr create --draft` with labels from the areas the change touches, or `gh pr edit` on the open one (refused
when that one goes into another branch than the base: the FIX retargets it, ship never does).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from . import body_names, gates, github, plan, repo, reviews, state
from .gates import Gate
from .output import Failure, cmd
from .review import records

TEMPLATE = ".github/pull_request_template.md"
NO_GOAL = "<!-- no plan: say why -->"
SHARED = "<!-- the plan covers several branches: say why this one -->"


def labels(ctx, files: list[str]) -> list[str]:
    """Labels from the areas changed (policy.toml [labels]: .github/*.md and docs/ are documentation, not ci);
    hardware is never automatic."""
    return [label for label, patterns in ctx.policy["labels"].items() if any(repo.matches(f, patterns) for f in files)]


def command(title: str | None = None, body=None, dry_run: bool = False) -> str:
    """The one place a ship command is written: with --dry-run whenever it follows (or is printed by) a dry run,
    so a FIX or next step never turns one into a push."""
    words = ["python", "tools/retrodev", "ship"]
    if title is not None:
        words += ["--title", title]
    if body is not None:
        words += ["--body", body]
    return cmd(*words, *(["--dry-run"] if dry_run else []))


def remote_gate(ctx, branch: str, dry_run: bool = False) -> Gate:
    ref = repo.remote_ref(ctx.remote, branch)
    remote_sha = repo.head(ctx.top, ref)
    if remote_sha and not repo.is_ancestor(ctx.top, remote_sha, "HEAD"):
        return Gate(
            "remote branch not moved",
            False,
            f"{ctx.remote}/{branch} has commits this branch does not (someone pushed); a push must never drop them",
            f"git fetch {ctx.remote} && git merge {ctx.remote}/{branch}, then python tools/retrodev check, then "
            + command(dry_run=dry_run)
            + " (a merge keeps their commits; never a rebase or a forced push)",
        )
    return gates.passed("remote branch not moved", "new branch" if not remote_sha else remote_sha[:9])


def ahead_gate(ctx) -> Gate:
    base = ctx.remote_base
    if not repo.head(ctx.top, base):
        return Gate("has commits", False, f"{base} is unknown here", f"git fetch {ctx.remote}")
    count = int(repo.git(["rev-list", "--count", f"{base}..HEAD"], ctx.top).strip() or 0)
    if not count:
        return Gate("has commits", False, f"the branch has no commits beyond {base}", "commit your change first")
    fork = repo.git(["merge-base", base, "HEAD"], ctx.top, check=False).strip()
    if fork and not repo.git(["diff", "--name-only", fork, "HEAD"], ctx.top).strip():
        return Gate(
            "has commits",
            False,
            f"nothing to ship: the branch changes no file ({count} commit(s), but no change since it left {base})",
            "commit the change itself (commits that undo each other, or empty ones, ship nothing)",
        )
    return gates.passed("has commits", f"{count} beyond {base}")


def base_gate(ctx, existing: dict, dry_run: bool = False) -> Gate:
    """The open pull request goes into the base branch (one opened by hand may point elsewhere, e.g. main)."""
    base, number = existing.get("baseRefName"), existing["number"]
    if base != ctx.base:
        return Gate(
            "pull request into " + ctx.base,
            False,
            f"the open pull request #{number} goes into {base or 'an unknown branch'}; changes reach "
            f"{ctx.base} only through pull requests into it (ship never retargets one itself)",
            f"gh pr edit {number} --base {ctx.base}, then " + command(dry_run=dry_run),
        )
    return gates.passed("pull request into " + ctx.base, f"#{number}")


def default_body(ctx, branch: str | None, record: dict) -> Path:
    """notes/pr/<topic>.md in the main checkout: git-ignored, outside the worktree (gc never keeps it for this)."""
    topic = record.get("topic") or (branch or "").partition("/")[2] or "detached"
    return repo.main_checkout(ctx.top) / "notes" / "pr" / f"{topic}.md"


made_by = gates.made_by  # the attribution line (gates.py, beside the body gate that looks for it)


def plan_sections(ctx, branch: str, record: dict) -> dict[str, list[str]]:
    """The sections of the plan the branch works under ({} with --no-plan or no plan file); template comments are
    no content, so a section the plan left as the template is empty here."""
    named = gates.plan_for(ctx, branch, record)
    path = plan.plan_file(ctx, named) if named and state.NAME.match(named) else None
    return gates.section_lines(path.read_text(encoding="utf-8")) if path and path.is_file() else {}


def plan_goal(ctx, branch: str, record: dict) -> list[str]:
    """The Goal lines of the plan the branch works under ([] with --no-plan, no plan file or an empty Goal)."""
    found = plan_sections(ctx, branch, record)
    return found.get("Goal") or found.get("Goals") or []  # a plan written by hand may say Goals


# The body sections the skeleton fills in from the plan (body heading: the plan's headings, first found wins).
PREFILL = {"What changed": ("What changes",), "Not done": ("Not in scope",)}


plan_title = plan.branch_title  # the plan's Title: line (plan.py), as ship and status offer it
title_note = plan.title_note


def skeleton(ctx, branch: str, record: dict) -> str:
    """The pull request template with the plan's Goal as the Why, its 'What changes' as What changed and its 'Not
    in scope' as Not done (each only when the plan says something there), and the line saying an agent made it."""
    source = ctx.top / TEMPLATE
    sections = ctx.policy["ship"]["sections"]
    text = source.read_text(encoding="utf-8") if source.is_file() else "".join(f"## {s}\n\n" for s in sections)
    several = plan.shared(ctx, branch, record)  # the Goal and Not in scope are the whole plan's, not this PR's
    goal = plan.branch_section(ctx, branch, record) if several else plan_goal(ctx, branch, record)
    why = "\n".join(goal) if goal else SHARED if several else NO_GOAL  # the body gate still finds a placeholder empty
    text = re.sub(r"^## Why[ \t]*\n", lambda m: m.group(0) + why + "\n", text, count=1, flags=re.M)
    found = plan_sections(ctx, branch, record)
    for heading, sources in PREFILL.items():
        if several and heading == "Not done":
            continue
        lines = next((found[name] for name in sources if found.get(name)), [])
        if lines:  # after the heading and its template comments
            at = re.search(rf"^## {re.escape(heading)}[ \t]*\n(?:[ \t]*<!--.*?-->[ \t]*\n)*", text, flags=re.M | re.S)
            if at:
                text = text[: at.end()] + "\n".join(lines) + "\n" + text[at.end() :]
    line = made_by(ctx, record=record)
    made = re.search(r"^## Made by[ \t]*\n(?:[ \t]*<!--.*?-->[ \t]*\n)*", text, flags=re.M | re.S)
    if made:  # the template's own section for it, its comment (who to name) replaced by the line itself
        return text[: made.start()] + "## Made by\n" + line + "\n" + text[made.end() :]
    return text.rstrip("\n") + f"\n\n---\n\n{line}\n"  # after a separator: counted in no section


def write_body(ctx, branch: str, record: dict) -> Path | None:
    """notes/pr/<topic>.md (the path ship reads) from the template and the plan, unless it exists: an existing body
    is never overwritten. The path when it was written now. start and plan approve write it before the first ship,
    so the agent fills it in while building; the body gate still refuses what the plan did not fill in."""
    path = default_body(ctx, branch, record)
    if path.is_file():
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(skeleton(ctx, branch, record), encoding="utf-8")
    return path


def body_file(ctx, title: str, body: str | None, new_body: bool, dry_run: bool, branch, record) -> tuple[Path, bool]:
    """The body to ship: --body, else notes/pr/<topic>.md. Writes that skeleton when it is missing (or with
    --new-body; an existing file is kept), so the agent fills in a file instead of writing one from scratch: the body
    gate then refuses it, beside every other gate, and names the file to fill in (writing a git-ignored note pushes
    nothing)."""
    if body and not new_body:
        path = Path(body).expanduser()
        return (path if path.is_absolute() else ctx.cwd / path), False
    path = default_body(ctx, branch, record)
    if path.is_file() and not new_body:
        ctx.out.say(f"body: {path}")
        return path, False
    if not branch or branch in ctx.policy["branches"]["protected"]:
        return path, False  # the work-branch gate refuses it; nothing is written for dev or main
    written = write_body(ctx, branch, record) is not None
    if not written:
        ctx.out.say(f"kept: {path} exists (nothing was overwritten)")
    else:
        named = gates.plan_for(ctx, branch, record)
        several = plan.shared(ctx, branch, record)
        why = (
            "the plan covers several branches: write this one's Why and Not done"
            if several and not plan.branch_section(ctx, branch, record)
            else "the plan's section for this branch is its Why"
            if several
            else "the plan's Goal is its Why"
            if plan_goal(ctx, branch, record)
            else f"the plan {named} has no Goal to copy: write the Why"
            if named
            else "no plan Goal: write the Why"
        )
        ctx.out.say(f"wrote {path} from {TEMPLATE} ({why})")
    return path, written  # the body gate refuses the unfilled skeleton, beside every other gate


def fill_in(path: Path, title: str, dry_run: bool = False) -> str:
    """The FIX for an unfilled body: fill in the file, then the ship command with this title and body (still a
    --dry-run after a dry run: its FIX never turns it into a push)."""
    shown = title.strip() if title and not gates.title_problems(title) else "<one plain sentence>"
    return f"fill in {path}, then " + command(shown, path, dry_run)


def body_step(ctx, branch: str | None, record: dict) -> str | None:
    """check's last line once the tree passes: before the first ship, while the branch's body (the recorded one,
    else notes/pr/<topic>.md) is missing or fails the body gate, fill it in, then ship."""
    if not branch or branch in ctx.policy["branches"]["protected"] or record.get("pr"):
        return None
    chosen = record.get("body")
    path = Path(chosen) if chosen else default_body(ctx, branch, record)
    title = record.get("title") or plan_title(ctx, branch, record)
    custom = path if path != default_body(ctx, branch, record) else None
    # after a refused ship --dry-run the step stays a dry run: filling the body never turns it into a push
    then = command(title or "<one plain sentence>", custom, bool(record.get("last_ship_dry_run")))
    then += "" if title else title_note(ctx, branch, record)
    if not path.is_file():  # ship writes it from the template and stops: name it all the same
        missing = f"missing: {path}; ship writes it from the template"
        return f"next: fill in the pull request body ({missing}), then {then}{agent_hint(None, record=record)}"
    text = path.read_text(encoding="utf-8")
    problems = gates.body_problems(text, ctx.policy["ship"]["sections"])
    unfilled = [
        found.group(1) for found in map(re.compile(r"'## (.+?)' is (?:empty|missing)").search, problems) if found
    ]
    unfilled += ["the Made by line"] if len(unfilled) < len(problems) else []  # names the agent: section-less
    hint = agent_hint(text, record=record)
    return f"next: fill in {', '.join(unfilled)} in {path}, then {then}{hint}" if problems else None


agent_hint = gates.agent_hint


def again(record: dict, dry_run: bool = False) -> str:
    """The ship command that pushes this branch's next commits, with its recorded title and body (a dry run of it
    after a dry run)."""
    pr = record.get("pr") or {}
    return command(pr.get("title") or record.get("title") or "<title>", record.get("body") or None, dry_run)


def recorded_title(ctx, branch, record: dict, dry_run: bool = False) -> str:
    """The title of a ship without --title: the pull request's, else the last ship's; else a FIX with the plan's."""
    title = (record.get("pr") or {}).get("title") or record.get("title")
    if title:
        return title
    shown = plan_title(ctx, branch, record) if branch else None
    raise Failure(
        "no title: this branch has none recorded yet (the first ship names it)"
        + ("" if shown else title_note(ctx, branch, record)),
        command(shown or "<one plain sentence>", dry_run=dry_run),
    )


def chosen_body(ctx, body: str | None, new_body: bool, branch, record: dict) -> str | None:
    """--body, else the recorded body while its file exists (None: the default notes/pr/<topic>.md)."""
    if new_body:
        return None
    if body:
        path = Path(body).expanduser()
        return str(path if path.is_absolute() else ctx.cwd / path)
    recorded = record.get("body")
    return recorded if recorded and Path(recorded).is_file() else None


def body_digest(path: Path | str) -> str | None:
    """The sha256 of a body file's bytes (None when it is gone): a dry run speaks only for the body it read."""
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def note_dry_run(ctx, record: dict, body_path: Path, ok: bool) -> None:
    """Record a dry run's outcome for status: ok only once every gate has passed, the base gate included."""
    record["dry_run"] = {
        "at": state.now(),
        "tree": repo.tree_digest(ctx.top),
        "body": str(body_path),
        "body_sha256": body_digest(body_path),
        "ok": ok,
    }
    state.save_branch(ctx.top, record)


def run(ctx, title: str | None, body: str | None, dry_run: bool = False, new_body: bool = False) -> int:
    branch = repo.branch(ctx.top)
    record: dict = state.load_branch(ctx.top, branch) if branch else {"checks": {}}
    work = bool(branch) and branch not in ctx.policy["branches"]["protected"]
    if work:  # before anything can stop this ship (the title first): status keeps --dry-run in the ship it names
        record["last_ship_dry_run"] = dry_run
        state.save_branch(ctx.top, record)
    no_title = None  # every other gate still runs without one: all refusals in one run
    if title is None:
        try:
            title = recorded_title(ctx, branch, record, dry_run)
        except Failure as missing:
            title, no_title = "", Gate("title", False, missing.message, missing.fix)
    body = chosen_body(ctx, body, new_body, branch, record)
    if work:
        # status names them in its next ship command, also after a gate stops this one or a dry run returns
        if not gates.title_problems(title):
            record["title"] = title.strip()
        record["body"] = body or str(default_body(ctx, branch, record))
        state.save_branch(ctx.top, record)
    body_path, written = body_file(ctx, title, body, new_body, dry_run, branch, record)
    text = body_path.read_text(encoding="utf-8") if body_path.is_file() else None
    body_gate = gates.body_gate(text, ctx.policy["ship"]["sections"])
    if not body_gate.ok and text is not None:
        if written:  # the dry run wrote the skeleton just now: every section is still to write
            body_gate.message = f"fill in {body_path} (written now from {TEMPLATE})"
        body_gate.fix = fill_in(body_path, title, dry_run)
    body_names.say(ctx, body_names.warning(ctx, text) if body_gate.ok else None)  # a warning, never a gate
    found = [
        gates.on_work_branch(ctx, branch),
        no_title or gates.title_gate(title),
        body_gate,
        gates.committed(ctx),
        gates.checks_on_tree(ctx, record, repo.tree_digest(ctx.top)),
    ]
    if branch and found[0].ok:
        found.insert(1, gates.plan_gate(ctx, branch, record))
        if not dry_run:
            repo.git(["fetch", "--quiet", ctx.remote], ctx.top)
        found += [ahead_gate(ctx), remote_gate(ctx, branch, dry_run)]
    noted = dry_run and bool(branch) and found[0].ok  # status says when the last dry run passed on this tree and body
    if noted and not all(gate.ok for gate in found):
        note_dry_run(ctx, record, body_path, False)
    gates.enforce(ctx, found, "ship")
    assert branch
    title = title.strip()
    changed = repo.changed_files(ctx.top, ctx.remote_base) or []
    chosen = labels(ctx, changed)
    sha = repo.head(ctx.top)
    push = ["git", "push", "-u", ctx.remote, branch]
    try:
        existing = github.open_pr(ctx, branch)
    except Failure as failure:
        if not dry_run:
            raise
        existing = None
        if not isinstance(failure, github.NoGitHub):  # that one printed its note already
            ctx.out.say(f"(could not ask GitHub for an open pull request: {failure.message})")
    if existing:
        into = base_gate(ctx, existing, dry_run)
        if noted and not into.ok:
            note_dry_run(ctx, record, body_path, False)
        gates.enforce(ctx, [into], "ship")
        gh_args = github.edit_args(existing["number"], title, str(body_path))
    else:
        gh_args = github.create_args(ctx.base, branch, title, str(body_path), chosen)
    steps = {"push": push, "gh": ["gh", *gh_args], "labels": chosen, "head": sha, "existing_pr": existing}
    ctx.out.set(**steps, dry_run=dry_run)
    if dry_run:
        if noted:  # the last gate passed: only now does this dry run count
            note_dry_run(ctx, record, body_path, True)
        ctx.out.say("would run:\n  " + cmd(*push) + "\n  " + cmd("gh", *gh_args))
        ctx.out.say("dry run: nothing was pushed or opened")
        return 0
    repo.git(push[1:], ctx.top)
    ctx.out.say(f"pushed {branch} ({sha[:9]})")
    _code, out, _err = github.gh(ctx, gh_args)
    if existing:
        number, url = existing["number"], existing.get("url", "")
        ctx.out.say(f"updated pull request #{number} {url}")
    else:
        url = next((line.strip() for line in out.splitlines() if "/pull/" in line), out.strip())
        number = github.pr_number(url)
        if number is None:
            raise Failure(
                f"gh did not print the new pull request's address: {out.strip()[:200]}",
                f"gh pr list --head {branch} (the pull request may exist; ship again records it)",
            )
        ctx.out.say(f"opened draft pull request #{number} {url}")
    reviews.record_pr(record, number, url, sha, title, at=state.now())
    record["pushed"] = sha
    record["body"] = str(body_path)
    state.save_branch(ctx.top, record)
    review = reviews.load(ctx, number)  # outlives the branch record: stats reads the first ship's time from it
    if not review.get("shipped"):
        review["shipped"] = {"at": state.now(), "head": sha}
        records.save(reviews.root(ctx), review)
    ctx.out.set(pr=record["pr"], approved=bool(review.get("approval")))
    if review.get("approval"):  # a re-ship of fixes after the owner approved: the report was given already
        ctx.out.say(
            f"next: {cmd('cd', ctx.main())} && python tools/retrodev land {number}  (already approved; from the main "
            "checkout: the merge removes the worktree)"
        )
    else:
        ctx.out.say("next: python tools/retrodev report (the step-5 report for the owner)")
    return 0
