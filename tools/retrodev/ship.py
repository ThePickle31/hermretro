"""Step 4 ends: push the branch and open its draft pull request (or update the open one).

    ship --title "<one plain sentence>" --body <file> [--dry-run]

Gates (all reported at once): a work branch; the owner approved its plan (docs and chore may go without one);
a one-line title without a trailing period; a body with every section of the pull request template filled in
and a line saying an agent made it; everything committed;
`check` passed on exactly this tree; the branch has commits; the remote branch has not moved away from it.
Then `git push -u <remote> <branch>` (a plain push, never anything that rewrites the remote) and
`gh pr create --draft` with labels from the areas the change touches, or `gh pr edit` on the open one (refused
when that one goes into another branch than the base: the FIX retargets it, ship never does).
"""

from __future__ import annotations

from pathlib import Path

from . import gates, github, repo, reviews, state
from .gates import Gate
from .output import Failure
from .review import records


def labels(ctx, files: list[str]) -> list[str]:
    """Labels from the areas changed (policy.toml [labels]); docs get none, hardware is never automatic."""
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


def run(ctx, title: str, body: str, dry_run: bool = False) -> int:
    branch = repo.branch(ctx.top)
    record = state.load_branch(ctx.top, branch) if branch else {"checks": {}}
    body_path = Path(body).expanduser()
    if not body_path.is_absolute():
        body_path = ctx.cwd / body_path
    text = body_path.read_text(encoding="utf-8") if body_path.is_file() else None
    found = [
        gates.on_work_branch(ctx, branch),
        gates.title_gate(title),
        gates.body_gate(text, ctx.policy["ship"]["sections"]),
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
        ctx.out.say(f"(could not ask GitHub for an open pull request: {failure.message})")
    if existing:
        gates.enforce(ctx, [base_gate(ctx, existing)], "ship")
        gh_args = github.edit_args(existing["number"], title, str(body_path))
    else:
        gh_args = github.create_args(ctx.base, branch, title, str(body_path), chosen)
    plan = {"push": push, "gh": ["gh", *gh_args], "labels": chosen, "head": sha, "existing_pr": existing}
    ctx.out.set(**plan, dry_run=dry_run)
    if dry_run:
        ctx.out.say("would run:\n  " + " ".join(push) + "\n  " + " ".join(_quoted(["gh", *gh_args])))
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
    state.save_branch(ctx.top, record)
    review = reviews.load(ctx, number)  # outlives the branch record: stats reads the first ship's time from it
    if not review.get("shipped"):
        review["shipped"] = {"at": state.now(), "head": sha}
        records.save(reviews.root(ctx), review)
    ctx.out.set(pr=record["pr"])
    ctx.out.say("next: python tools/retrodev report (the step-5 report for the owner)")
    return 0


def _quoted(words: list[str]) -> list[str]:
    return [f"'{word}'" if (" " in word or not word) else word for word in words]
