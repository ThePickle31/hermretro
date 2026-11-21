"""How many review rounds a pull request gets before its answered findings merge (land).

One round: the head that answers round 1's findings merges on green CI without another round. Rounds 2 and 3 of
every pull request cost most of the time between approval and merge and found few serious problems, so a further
round is kept for where those were:

  a file matching policy.toml [land] second_round is changed    2 rounds (the second reviews the fixes)
  a round had a high-severity finding                           the round after it reviews the fix
  the changed files cannot be read (no merge base, a git error) 2 rounds: what this cannot judge is reviewed

never more than records.MAX_ROUNDS. Two more facts go with it, both read by records.next_action:

  depth['unseen']      second_round files the head changes that the last reviewed head did not (a later push, or a
                       merge of the base branch that moved an edited file there): the head is reviewed itself, no
                       clean, accepted or carried review stands for it, until MAX_ROUNDS ran
  depth['same_patch']  the head shows a reviewer nothing new since the last reviewed head (an empty commit, a clean
                       merge of the base branch, a rebuilt generated file), or that cannot be told: no fix was
                       pushed, so findings above low that were only disputed still get their judging round The answer is recomputed on every land from the current head and findings (a
later push that touches a second_round file raises it) and kept in the review record as record['depth'] =
{rounds, why}, which records.next_action reads and the readable copy (notes/reviews/pr<N>.md) shows.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from . import repo, reviews
from .review import inputs, records


def changed(ctx, tree: Path | None, sha: str) -> list[str] | None:
    """Files the pull request changes at ``sha`` since it left the base branch; None when that cannot be read."""
    if tree is None or not sha:
        return None
    point = repo.git(["merge-base", ctx.remote_base, sha], tree, check=False).strip()
    if not point:
        return None
    code, out, _err = repo.run(["git", "diff", "--no-renames", "--name-only", "-z", point, sha], tree)
    return None if code else sorted(name for name in out.split("\0") if name)


def base_of(ctx, tree: Path, sha: str) -> str:
    return repo.git(["merge-base", ctx.remote_base, sha], tree, check=False).strip()


def digest(ctx, tree: Path, sha: str) -> str | None:
    """What the reviewer is shown of the pull request at ``sha`` (inputs.pathspec: generated files and lockfiles
    left out), without context, blob names or line numbers, so the base branch moving under it changes nothing."""
    point = base_of(ctx, tree, sha)
    code, out, _err = repo.run(["git", "diff", "--no-renames", "--binary", "-U0", point, sha, *inputs.pathspec()], tree)
    if not point or code:
        return None
    kept = ["@@" if line.startswith("@@") else line for line in out.splitlines() if not line.startswith("index ")]
    return hashlib.sha256("\n".join(kept).encode("utf-8", "surrogateescape")).hexdigest()


def same_patch(ctx, tree: Path | None, seen: str | None, sha: str) -> bool:
    """Whether ``sha`` changes nothing a reviewer is shown since the reviewed head ``seen`` (no fix was pushed), or
    that cannot be told. On the same base the two trees are compared directly, generated files aside; after a merge
    of the base branch their patches are (so a fix that only moves the same lines elsewhere then reads as none: the
    careful side, it costs a round)."""
    if not seen or seen == sha:
        return False
    if tree is None:
        return True
    if base_of(ctx, tree, seen) and base_of(ctx, tree, seen) == base_of(ctx, tree, sha):
        code, _out, _err = repo.run(["git", "diff", "--quiet", "--no-renames", seen, sha, *inputs.pathspec()], tree)
        return code != 1  # 1: they differ; anything else but 0 cannot be told
    now = digest(ctx, tree, sha)
    return now is None or now == digest(ctx, tree, seen)


def risky(ctx, tree: Path | None, sha: str) -> list[str] | None:
    """The pull request's changed files at ``sha`` that match [land] second_round; None when they cannot be read."""
    files = changed(ctx, tree, sha)
    if files is None:
        return None
    return [name for name in files if repo.matches(name, ctx.policy.get("land", {}).get("second_round", []))]


def decide(ctx, tree: Path | None, rec: dict, sha: str) -> dict:
    """{'rounds', 'why', 'same_patch', 'unseen'} for the pull request as it stands."""
    rounds, why = 1, "one round: no high-severity finding, no file under policy.toml [land] second_round"
    found = risky(ctx, tree, sha)
    done = records.valid_rounds(rec)
    seen = done[-1]["sha"] if done else None
    unseen: list[str] = []
    if found is None:
        rounds, why = 2, "a second round: the pull request's changed files could not be read"
    elif found:
        more = f" and {len(found) - 1} more" if len(found) > 1 else ""
        rounds, why = 2, f"a second round: it changes {found[0]}{more} (policy.toml [land] second_round)"
        before = risky(ctx, tree, seen) if seen and seen != sha else found
        unseen = found if before is None else [name for name in found if name not in before]
    high = [
        entry["round"]
        for entry in done
        if any(finding.get("severity") == "high" for finding in reviews.findings(entry))
    ]
    if high and high[-1] + 1 > rounds:
        rounds = high[-1] + 1
        why = f"round {high[-1]} had a high-severity finding: round {rounds} reviews its fix"
    if rounds > records.MAX_ROUNDS:
        rounds, why = records.MAX_ROUNDS, why + f" (but {records.MAX_ROUNDS} rounds is the limit)"
    if unseen:
        why += f"; this head is reviewed itself: {unseen[0]} is new since round {len(done)}'s head"
    return {"rounds": rounds, "why": why, "same_patch": same_patch(ctx, tree, seen, sha), "unseen": unseen}


def shown(rec: dict) -> dict:
    """The depth as answers report it, with ``total``: the rounds due or already run, whichever is more (a round
    that judged disputed findings, or reviewed a later push, is beyond ``rounds``)."""
    depth = rec.get("depth") or {}
    return {**depth, "total": max(records.depth(rec), len(records.valid_rounds(rec)))}


def apply(ctx, tree: Path | None, rec: dict, sha: str, save: bool = True) -> dict:
    """The review record with its depth brought up to date (written only when it changed and ``save``)."""
    found = decide(ctx, tree, rec, sha)
    if rec.get("depth") != found:
        rec["depth"] = found
        if save:
            reviews.save(ctx, rec)
    return rec
