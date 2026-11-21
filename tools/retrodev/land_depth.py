"""How many review rounds a pull request gets before its answered findings merge (land).

One round: the head that answers round 1's findings merges on green CI without another round. Rounds 2 and 3 of
every pull request cost most of the time between approval and merge and found few serious problems, so a further
round is kept for where those were:

  a file matching policy.toml [land] second_round is changed    2 rounds (the second reviews the fixes)
  a round had a high-severity finding                           the round after it reviews the fix
  the changed files cannot be read (no merge base, a git error) 2 rounds: what this cannot judge is reviewed
  the head changes a second_round file the last reviewed head   one more round: no reviewer saw that change
  did not change

never more than records.MAX_ROUNDS. depth['same_patch'] says the head's patch (its diff since it left the base
branch, hunk by hunk) is the one the last round reviewed, or cannot be compared: an empty commit or a clean merge of
the base branch is no fix, so records.next_action does not take such a push for one. The answer is recomputed on every land from the current head and findings (a
later push that touches a second_round file raises it) and kept in the review record as record['depth'] =
{rounds, why}, which records.next_action reads and the readable copy (notes/reviews/pr<N>.md) shows.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from . import repo, reviews
from .review import records


def changed(ctx, tree: Path | None, sha: str) -> list[str] | None:
    """Files the pull request changes at ``sha`` since it left the base branch; None when that cannot be read."""
    if tree is None or not sha:
        return None
    point = repo.git(["merge-base", ctx.remote_base, sha], tree, check=False).strip()
    if not point:
        return None
    code, out, _err = repo.run(["git", "diff", "--no-renames", "--name-only", "-z", point, sha], tree)
    return None if code else sorted(name for name in out.split("\0") if name)


def patch(ctx, tree: Path | None, sha: str) -> str | None:
    """A digest of what the pull request changes at ``sha``: its diff since the base branch without context, blob
    names or line numbers, so the base branch moving under it changes nothing. None when it cannot be read."""
    if tree is None or not sha:
        return None
    point = repo.git(["merge-base", ctx.remote_base, sha], tree, check=False).strip()
    if not point:
        return None
    code, out, _err = repo.run(["git", "diff", "--no-renames", "--binary", "-U0", point, sha], tree)
    if code:
        return None
    kept = ["@@" if line.startswith("@@") else line for line in out.splitlines() if not line.startswith("index ")]
    return hashlib.sha256("\n".join(kept).encode("utf-8", "surrogateescape")).hexdigest()


def risky(ctx, tree: Path | None, sha: str) -> list[str] | None:
    """The pull request's changed files at ``sha`` that match [land] second_round; None when they cannot be read."""
    files = changed(ctx, tree, sha)
    if files is None:
        return None
    return [name for name in files if repo.matches(name, ctx.policy.get("land", {}).get("second_round", []))]


def decide(ctx, tree: Path | None, rec: dict, sha: str) -> dict:
    """{'rounds': n, 'why': text, 'same_patch': bool} for the pull request as it stands."""
    rounds, why = 1, "one round: no high-severity finding, no file under policy.toml [land] second_round"
    found = risky(ctx, tree, sha)
    done = records.valid_rounds(rec)
    seen = done[-1]["sha"] if done else None
    if found is None:
        rounds, why = 2, "a second round: the pull request's changed files could not be read"
    elif found:
        more = f" and {len(found) - 1} more" if len(found) > 1 else ""
        rounds, why = 2, f"a second round: it changes {found[0]}{more} (policy.toml [land] second_round)"
        before = risky(ctx, tree, seen) if seen and seen != sha else found
        unseen = found if before is None else [name for name in found if name not in before]
        if unseen and len(done) + 1 > rounds:
            rounds = len(done) + 1
            why = f"another round: it now changes {unseen[0]}, which round {len(done)}'s head did not change"
    high = [
        entry["round"]
        for entry in records.valid_rounds(rec)
        if any(finding.get("severity") == "high" for finding in reviews.findings(entry))
    ]
    if high and high[-1] + 1 > rounds:
        rounds = high[-1] + 1
        why = f"round {high[-1]} had a high-severity finding: round {rounds} reviews its fix"
    if rounds > records.MAX_ROUNDS:
        rounds, why = records.MAX_ROUNDS, why + f" (but {records.MAX_ROUNDS} rounds is the limit)"
    now = patch(ctx, tree, sha) if seen and seen != sha else ""
    same = bool(seen) and seen != sha and (now is None or now == patch(ctx, tree, seen))
    return {"rounds": rounds, "why": why, "same_patch": same}


def apply(ctx, tree: Path | None, rec: dict, sha: str, save: bool = True) -> dict:
    """The review record with its depth brought up to date (written only when it changed and ``save``)."""
    found = decide(ctx, tree, rec, sha)
    if rec.get("depth") != found:
        rec["depth"] = found
        if save:
            reviews.save(ctx, rec)
    return rec
