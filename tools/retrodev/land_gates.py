"""land's gates: what must hold before land starts (all reported at once), and what it rechecks on GitHub on every
CI poll and right before the merge (the pull request can be closed, retargeted or pushed to while land waits).

The owner's approval belongs to one pull request: it is read from that pull request's review record (approve
writes it there with the number), never from the branch, so a replacement pull request from the same branch needs
its own approval. Review-fix pushes to the same pull request keep it.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import gates, github, repo, reviews, ship, sync
from .gates import Gate
from .output import OWNER, Failure, cmd

CONFLICT_WORDS = ("merge conflict", "not mergeable")  # in gh pr merge's error when GitHub cannot merge it


def find_worktree(ctx, branch: str) -> Path | None:
    for tree in repo.worktrees(ctx.main()):
        if tree.branch == branch and tree.path.is_dir():
            return tree.path
    return None


def remote_head(ctx, tree: Path, branch: str) -> str | None:
    out = repo.git(["ls-remote", ctx.remote, f"refs/heads/{branch}"], tree, check=False).strip()
    return out.split()[0] if out else None


def approval_for(ctx, number: int) -> dict | None:
    """The owner's approval of pull request ``number`` (its review record; one without a number predates them)."""
    approval = reviews.load(ctx, number).get("approval")
    return approval if approval and approval.get("pr", number) == number else None


def approval_gate(ctx, number: int) -> Gate:
    approval = approval_for(ctx, number)
    if approval:
        return gates.passed("owner approved", f"{approval['at']}: \"{approval['words']}\"")
    return Gate(
        "owner approved",
        False,
        f"the owner has not approved #{number}: land merges only what the owner approved (an approval of another "
        "pull request from the same branch does not count)",
        f'when the owner approves: python tools/retrodev approve {number} --words "<their exact words>"',
        OWNER,
    )


def base_gate(ctx, info: dict) -> Gate:
    number = info["number"]
    if info.get("baseRefName") == ctx.base:
        return gates.passed("into " + ctx.base)
    return Gate(
        "into " + ctx.base,
        False,
        f"#{number} goes into {info.get('baseRefName')}; changes reach {ctx.base} only through pull requests into it",
        f"gh pr edit {number} --base {ctx.base}, then land again",
    )


def collect_gates(ctx, info: dict, record: dict, tree: Path | None) -> list[Gate]:
    number, branch = info["number"], info["headRefName"]
    found = [approval_gate(ctx, number)]
    found.append(
        gates.passed("pull request open")
        if info.get("state") == "OPEN"
        else Gate("pull request open", False, f"#{number} is {str(info.get('state')).lower()}", f"gh pr view {number}")
    )
    found.append(base_gate(ctx, info))
    found.append(gates.passed("ready for review", "a draft: land marks it ready" if info.get("isDraft") else ""))
    if tree is None:
        found.append(
            Gate(
                "worktree",
                False,
                f"no worktree has {branch} checked out: land checks the tree that passed the checks",
                f"git worktree add <folder> {branch} (or python tools/retrodev status to find it)",
            )
        )
        return found
    wctx = ctx.at(tree)
    local, pr_head = repo.head(tree), info.get("headRefOid")
    if local == pr_head:
        found.append(gates.passed("pull request head is this branch's head", (local or "")[:9]))
    else:
        found.append(
            Gate(
                "pull request head is this branch's head",
                False,
                f"#{number} is at {str(pr_head)[:9]}, {branch} here at {str(local)[:9]}: what is reviewed and merged "
                "must be what passed the checks here",
                ship.again(record) + " (pushes the new commits)"
                if local and pr_head and repo.is_ancestor(tree, pr_head, local)
                else f"git fetch {ctx.remote} && git merge {ctx.remote}/{branch}, then check and ship",
            )
        )
    pushed = remote_head(ctx, tree, branch)
    found.append(
        gates.passed("pushed", f"{ctx.remote}/{branch} at {(pushed or '')[:9]}")
        if pushed and pushed == local
        else Gate(
            "pushed",
            False,
            f"{ctx.remote}/{branch} is at {(pushed or 'nothing')[:9]}, not {str(local)[:9]}",
            ship.again(record),
        )
    )
    found += [gates.committed(wctx), gates.checks_on_tree(wctx, record, repo.tree_digest(tree))]
    return found


def recheck(ctx, number: int, sha: str, view: dict) -> None:
    """Raise unless the pull request is still open, into the base branch and at ``sha`` (gh pr view's fields
    state, baseRefName, headRefOid). --match-head-commit guards only the head: a retarget keeps it."""
    now = view.get("state")
    if now != "OPEN":
        merged = now == "MERGED"
        raise Failure(
            f"#{number} is {str(now).lower()} now"
            + (" (merged by someone else while land waited)" if merged else "")
            + ": land merges only an open pull request, and merged nothing",
            f"python tools/retrodev summary {number}" if merged else f"gh pr view {number}",
        )
    if view.get("baseRefName") != ctx.base:
        raise Failure(
            f"#{number} goes into {view.get('baseRefName')} now (retargeted while land waited); changes reach "
            f"{ctx.base} only through pull requests into it: nothing was merged",
            f"gh pr edit {number} --base {ctx.base}, then python tools/retrodev land {number}",
        )
    if view.get("headRefOid") != sha:
        raise Failure(
            f"the head of #{number} moved from {sha[:9]} to {str(view.get('headRefOid'))[:9]} while waiting for "
            "CI (a push): CI and the reviews must pass on what is merged",
            f"python tools/retrodev land {number} (it reviews and waits for the new head)",
        )


def mergeable(ctx, number: int) -> str | None:
    """GitHub's word on merging the pull request: MERGEABLE, CONFLICTING or UNKNOWN (still computing), or None."""
    code, out, _err = github.gh(ctx, ["pr", "view", str(number), "--json", "mergeable"], check=False)
    try:
        found = json.loads(out) if code == 0 else None
    except json.JSONDecodeError:
        return None
    return found.get("mergeable") if isinstance(found, dict) else None


def conflicted(text: str) -> bool:
    return any(word in (text or "").lower() for word in CONFLICT_WORDS)


def conflict_failure(ctx, info: dict, tree: Path | None) -> Failure:
    """The pull request conflicts with the base branch: merge it in with sync in the worktree, then land again."""
    number = info["number"]
    where = cmd("cd", tree) if tree else "cd <the worktree of " + str(info.get("headRefName")) + ">"
    record = reviews.branch_record(ctx, str(info.get("headRefName")))
    pr = {**(record.get("pr") or {})}
    pr["title"] = pr.get("title") or info.get("title")
    again = ship.again({**record, "pr": pr})  # the recorded title and body (no body recorded: ship's default)
    return Failure(
        f"#{number} has merge conflicts with {ctx.base}: GitHub cannot merge it (nothing was merged)",
        f"{where} && {sync.sync_command(ctx, tree) if tree else 'python tools/retrodev sync'} (it lists the files to resolve; git add them and sync again), then "
        f"python tools/retrodev check, {again}, then {cmd('cd', ctx.main())} && python tools/retrodev land {number}",
        data={"action": "sync", "worktree": str(tree) if tree else None},
    )
