"""Step 4 ends: push the branch and open its draft pull request (or update the open one).

    ship [--title "<one plain sentence>"] [--body <file>] [--new-body] [--dry-run]

The title defaults to the one recorded for the branch (its pull request's, else the last ship's); with none
recorded ship refuses and its FIX names the plan's title. The body defaults to the one recorded (when that file
still exists), else to notes/pr/<topic>.md in the main checkout (git-ignored, so gc is never blocked by it). When
that file does not exist yet (or with --new-body), ship writes it from .github/pull_request_template.md, with the
plan's Goal as the Why (with --no-plan or an empty Goal, a visible '<!-- no plan: say why -->' instead) and a line
saying an agent made it (RETRODEV_AGENT names the agent, default Hermes; under the template's '## Made by' when it
has one, else after a closing '---', so it fills no section), and stops: fill it in, then ship again. A --dry-run
writes the same skeleton (a git-ignored note, not a push) and reports the body gate as 'NO  body: fill in <path>',
its FIX the real ship command with this title.

Gates (all reported at once): a work branch; the owner approved its plan (docs and chore may go without one);
a one-line title without a trailing period; a branch that changes at least one file; a body with every section of the pull request template filled in
and a line saying an agent made it; everything committed;
`check` passed on exactly this tree; the branch has commits; the remote branch has not moved away from it.
Then `git push -u <remote> <branch>` (a plain push, never anything that rewrites the remote) and
`gh pr create --draft` with labels from the areas the change touches, or `gh pr edit` on the open one (refused
when that one goes into another branch than the base: the FIX retargets it, ship never does).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from . import gates, github, plan, repo, reviews, state
from .gates import Gate
from .output import Failure, cmd

from .review import records

TEMPLATE = ".github/pull_request_template.md"
NO_GOAL = "<!-- no plan: say why -->"


def labels(ctx, files: list[str]) -> list[str]:
    """Labels from the areas changed (policy.toml [labels]: .github/*.md and docs/ are documentation, not ci);
    hardware is never automatic."""
    return [label for label, patterns in ctx.policy["labels"].items() if any(repo.matches(f, patterns) for f in files)]


def remote_gate(ctx, branch: str) -> Gate:
    ref = repo.remote_ref(ctx.remote, branch)
    remote_sha = repo.head(ctx.top, ref)
    if remote_sha and not repo.is_ancestor(ctx.top, remote_sha, "HEAD"):
        return Gate(
            "remote branch not moved",
            False,
            f"{ctx.remote}/{branch} has commits this branch does not (someone pushed); a push must never drop them",
            f"git fetch {ctx.remote} && git merge {ctx.remote}/{branch}, then python tools/retrodev check and ship "
            "again (a merge keeps their commits; never a rebase or a forced push)",
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


def base_gate(ctx, existing: dict) -> Gate:
    """The open pull request goes into the base branch (one opened by hand may point elsewhere, e.g. main)."""
    base, number = existing.get("baseRefName"), existing["number"]
    if base != ctx.base:
        return Gate(
            "pull request into " + ctx.base,
            False,
            f"the open pull request #{number} goes into {base or 'an unknown branch'}; changes reach "
            f"{ctx.base} only through pull requests into it (ship never retargets one itself)",
            f"gh pr edit {number} --base {ctx.base}, then ship again",
        )
    return gates.passed("pull request into " + ctx.base, f"#{number}")


def default_body(ctx, branch: str | None, record: dict) -> Path:
    """notes/pr/<topic>.md in the main checkout: git-ignored, outside the worktree (gc never keeps it for this)."""
    topic = record.get("topic") or (branch or "").partition("/")[2] or "detached"
    return repo.main_checkout(ctx.top) / "notes" / "pr" / f"{topic}.md"


def owner(ctx) -> str:
    url = repo.git(["remote", "get-url", ctx.remote], ctx.top, check=False).strip()
    found = re.search(r"github\.com[:/]([^/]+)/", url)
    account = found.group(1) if found else ctx.get("github_account")
    return f"@{account}" if account else "the owner"


def plan_goal(ctx, branch: str, record: dict) -> list[str]:
    """The Goal lines of the plan the branch works under ([] with --no-plan, no plan file or an empty Goal)."""
    named = gates.plan_for(ctx, branch, record)
    path = plan.plan_file(ctx, named) if named and state.NAME.match(named) else None
    found = gates.section_lines(path.read_text(encoding="utf-8")) if path and path.is_file() else {}
    return found.get("Goal") or found.get("Goals") or []  # a plan written by hand may say Goals


def plan_title(ctx, branch: str, record: dict) -> str | None:
    """The plan's own title line ('# Plan: <words>'), when it says more than the topic."""
    named = gates.plan_for(ctx, branch, record)
    path = plan.plan_file(ctx, named) if named and state.NAME.match(named) else None
    if not path or not path.is_file():
        return None
    first = next((line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("# ")), "")
    words = first[2:].strip().removeprefix("Plan:").strip()
    return words if words and words != named and not gates.title_problems(words) else None


def skeleton(ctx, branch: str, record: dict) -> str:
    """The pull request template with the plan's Goal as the Why and the line saying an agent made it."""
    source = ctx.top / TEMPLATE
    sections = ctx.policy["ship"]["sections"]
    text = source.read_text(encoding="utf-8") if source.is_file() else "".join(f"## {s}\n\n" for s in sections)
    goal = plan_goal(ctx, branch, record)
    why = "\n".join(goal) if goal else NO_GOAL  # a visible placeholder: the body gate still finds the Why empty
    text = re.sub(r"^## Why[ \t]*\n", lambda m: m.group(0) + why + "\n", text, count=1, flags=re.M)
    agent = os.environ.get("RETRODEV_AGENT") or "Hermes"
    line = f"Made by an agent ({agent}) for {owner(ctx)}."
    made = re.search(r"^## Made by[ \t]*\n(?:[ \t]*<!--.*?-->[ \t]*\n)*", text, flags=re.M | re.S)
    if made:  # the template's own section for it (after its comments)
        return text[: made.end()] + line + "\n" + text[made.end() :]
    return text.rstrip("\n") + f"\n\n---\n\n{line}\n"  # after a separator: counted in no section


def body_file(ctx, title: str, body: str | None, new_body: bool, dry_run: bool, branch, record) -> tuple[Path, bool]:
    """The body to ship: --body, else notes/pr/<topic>.md. Writes that skeleton when it is missing (or with
    --new-body; an existing file is kept), so the agent fills in a file instead of writing one from scratch: a real
    ship stops there, a dry run goes on and its body gate says which file to fill in (writing a git-ignored note
    pushes nothing)."""
    if body and not new_body:
        path = Path(body).expanduser()
        return (path if path.is_absolute() else ctx.cwd / path), False
    path = default_body(ctx, branch, record)
    if path.is_file() and not new_body:
        ctx.out.say(f"body: {path}")
        return path, False
    if not branch or branch in ctx.policy["branches"]["protected"]:
        return path, False  # the work-branch gate refuses it; nothing is written for dev or main
    written = not path.is_file()
    if path.is_file():
        ctx.out.say(f"kept: {path} exists (nothing was overwritten)")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(skeleton(ctx, branch, record), encoding="utf-8")
        named = gates.plan_for(ctx, branch, record)
        why = (
            "the plan's Goal is its Why"
            if plan_goal(ctx, branch, record)
            else f"the plan {named} has no Goal to copy: write the Why"
            if named
            else "no plan Goal: write the Why"
        )
        ctx.out.say(f"wrote {path} from {TEMPLATE} ({why})")
    if dry_run:
        return path, written
    raise Failure(f"the pull request body {path} is not filled in yet", fill_in(path, title))


def fill_in(path: Path, title: str) -> str:
    """The FIX for an unfilled body: fill in the file, then the real ship command with this title and body."""
    shown = title.strip() if title and not gates.title_problems(title) else "<one plain sentence>"
    return f"fill in {path}, then " + cmd("python", "tools/retrodev", "ship", "--title", shown, "--body", path)


def again(record: dict) -> str:
    """The ship command that pushes this branch's next commits, with its recorded title and body."""
    pr = record.get("pr") or {}
    words = ["python", "tools/retrodev", "ship", "--title", pr.get("title") or record.get("title") or "<title>"]
    if record.get("body"):
        words += ["--body", record["body"]]
    return cmd(*words)


def recorded_title(ctx, branch, record: dict) -> str:
    """The title of a ship without --title: the pull request's, else the last ship's; else a FIX with the plan's."""
    title = (record.get("pr") or {}).get("title") or record.get("title")
    if title:
        return title
    shown = (plan_title(ctx, branch, record) if branch else None) or "<one plain sentence>"
    raise Failure(
        "no title: this branch has none recorded yet (the first ship names it)",
        cmd("python", "tools/retrodev", "ship", "--title", shown),
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


def run(ctx, title: str | None, body: str | None, dry_run: bool = False, new_body: bool = False) -> int:
    branch = repo.branch(ctx.top)
    record: dict = state.load_branch(ctx.top, branch) if branch else {"checks": {}}
    if title is None:
        title = recorded_title(ctx, branch, record)
    body = chosen_body(ctx, body, new_body, branch, record)
    if branch and branch not in ctx.policy["branches"]["protected"]:
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
        body_gate.fix = fill_in(body_path, title)
    found = [
        gates.on_work_branch(ctx, branch),
        gates.title_gate(title),
        body_gate,
        gates.committed(ctx),
        gates.checks_on_tree(ctx, record, repo.tree_digest(ctx.top)),
    ]
    if branch and found[0].ok:
        found.insert(1, gates.plan_gate(ctx, branch, record))
        if not dry_run:
            repo.git(["fetch", "--quiet", ctx.remote], ctx.top)
        found += [ahead_gate(ctx), remote_gate(ctx, branch)]
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
        gates.enforce(ctx, [base_gate(ctx, existing)], "ship")
        gh_args = github.edit_args(existing["number"], title, str(body_path))
    else:
        gh_args = github.create_args(ctx.base, branch, title, str(body_path), chosen)
    plan = {"push": push, "gh": ["gh", *gh_args], "labels": chosen, "head": sha, "existing_pr": existing}
    ctx.out.set(**plan, dry_run=dry_run)
    if dry_run:
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
