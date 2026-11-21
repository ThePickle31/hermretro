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
  depth['same_patch']  no commit of the pull request's own since the last reviewed head changes what a reviewer is
                       shown (an empty commit, a merge of the base branch, a rebuilt generated file), or that
                       cannot be told: no fix was pushed, so findings above low that were only disputed still get
                       their judging round The answer is recomputed on every land from the current head and findings (a
later push that touches a second_round file raises it) and kept in the review record as record['depth'] =
{rounds, why}, which records.next_action reads and the readable copy (notes/reviews/pr<N>.md) shows.
"""

from __future__ import annotations

from pathlib import Path

from . import land_carry, repo, reviews
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


def same_patch(ctx, tree: Path | None, seen: str | None, sha: str) -> bool:
    """Whether no fix was pushed since the reviewed head ``seen``, or that cannot be told. A fix is a commit of the
    pull request's own (not a merge, not the base branch's) that changes a file a reviewer is shown
    (inputs.EXCLUDED: generated files and lockfiles are not), on a head whose shown files differ from ``seen``'s.
    So an empty commit, a rebuilt bundle, a merge of the base branch (whatever it does to the pull request's diff)
    and a change taken back again are none; a change made inside a merge's conflict resolution is none either, the
    careful side: it costs a round."""
    if not seen or seen == sha:
        return False
    if tree is None:
        return True
    code, _out, _err = repo.run(["git", "diff", "--quiet", "--no-renames", seen, sha, *inputs.pathspec()], tree)
    if code != 1:
        return True  # 0: nothing a reviewer is shown differs; else it cannot be told
    try:
        if not repo.is_ancestor(tree, seen, sha):
            return True
        own = repo.git(["rev-list", "--no-merges", sha, "^" + seen, "^" + ctx.remote_base], tree).split()
        for commit in own:
            names = repo.git(["diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "--no-renames", commit], tree)
            if any(name and name not in inputs.EXCLUDED for name in names.split("\0")):
                return False
    except (repo.GitError, ValueError):
        return True
    return True


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


def shown(rec: dict, action: str | None = None) -> dict:
    """The depth as answers report it, with ``total``: the rounds due, already run or about to run (``action`` is
    'review'), whichever is most: a round that judges disputed findings, or reviews a later push, is beyond
    ``rounds``."""
    depth = rec.get("depth") or {}
    ran = len(records.valid_rounds(rec)) + (1 if action == "review" else 0)
    return {**depth, "total": min(records.MAX_ROUNDS, max(records.depth(rec), ran))}


def standing(ctx, tree: Path | None, rec: dict, sha: str, save: bool = True) -> dict:
    """The record with its depth up to date and, where a review may stand for ``sha``, the carry (land_carry). A
    head that must be reviewed itself (depth['unseen']) gets no carry recorded or announced."""
    rec = apply(ctx, tree, rec, sha, save)
    if rec["depth"]["unseen"] and len(records.valid_rounds(rec)) < records.MAX_ROUNDS:
        return rec
    return land_carry.carry(ctx, tree, rec, sha, save=save)


def apply(ctx, tree: Path | None, rec: dict, sha: str, save: bool = True) -> dict:
    """The review record with its depth brought up to date (written only when it changed and ``save``)."""
    found = decide(ctx, tree, rec, sha)
    if rec.get("depth") != found:
        rec["depth"] = found
        if save:
            reviews.save(ctx, rec)
    return rec
