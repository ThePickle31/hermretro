"""Step 6: the owner approves a pull request once; and the author's answers to a review round's findings.

    approve <pr> --words "<the owner's exact words>"
    answer <pr> <round> <index> "<text>"        one finding: the fix's commit, or a reasoned refusal with proof
    answer <pr> <round> --all "<text>"          every finding of that round

approve records the time, the words, the pull request's number and its head at that moment in the branch record
(found by the pull request's head branch) and its review record, and marks a draft ready for review (gh pr ready).
From then on `land` takes that pull request (and review-fix pushes to it) through the review rounds, CI and the
merge with no further approval. The approval belongs to that number: a replacement pull request from the same
branch needs its own (ship moves the old one to the branch record's history).
"""

from __future__ import annotations

from . import land_gates, repo, reviews, state
from .github import gh
from .output import OWNER, Failure, cmd
from .review import records


def approve(ctx, number: int, words: str | None, scope: dict | None = None) -> int:
    """``scope`` (release run's: scope release, the version) is part of the approval from the moment it is saved,
    before any GitHub call that can fail; an ordinary approval has none."""
    if not words or not words.strip():
        raise Failure(
            "an approval records the owner's exact words, so anyone can see who approved the merge and what they said",
            f'python tools/retrodev approve {number} --words "<the owner\'s exact words>"',
            code=OWNER,
        )
    info = reviews.pr_view(ctx, number)
    if info.get("state") != "OPEN":
        raise Failure(
            f"pull request #{number} is {str(info.get('state')).lower()}, not open: there is nothing to approve",
            f"gh pr view {number} (a merged one needs no approval: python tools/retrodev summary {number})",
        )
    branch = info["headRefName"]
    approval = {
        "at": state.now(),
        "words": words.strip(),
        "head": info["headRefOid"],
        "pr": number,
        "url": info.get("url"),
        **(scope or {}),
    }
    record = reviews.branch_record(ctx, branch)
    reviews.record_pr(record, number, info.get("url"), info["headRefOid"], info.get("title"))
    record["approval"] = approval
    state.save_branch(ctx.top, record)
    review = reviews.load(ctx, number)
    review["approval"] = approval
    reviews.save(ctx, review)
    ctx.out.say(f"approved #{number} ({branch} at {approval['head'][:9]}): \"{approval['words']}\"")
    readied = False
    if info.get("isDraft"):
        gh(ctx, ["pr", "ready", str(number)])
        readied = True
        ctx.out.say(f"marked #{number} ready for review (it was a draft)")
    ctx.out.say(
        f"next: {cmd('cd', ctx.main())} && python tools/retrodev land {number}  (from the main checkout: the merge removes "
        "the worktree; in the background: reviews and CI take many minutes)"
    )
    ctx.out.set(pr=number, branch=branch, approval=approval, readied=readied)
    return 0


def answer(ctx, number: int, round_no: int, index: int | None, text: str | None, every: str | None = None) -> int:
    words = every if every is not None else text
    usage = (
        f"python tools/retrodev answer {number} {round_no} <index> '<fixed in <sha>: how>' "
        f"(or --all '<text>' for every finding of the round)"
    )
    if (every is None) == (index is None) or (every is not None and text is not None):
        raise Failure("answer takes either a finding's index and its text, or --all and one text", usage)
    if not words or not words.strip():
        raise Failure("an answer says how the finding was fixed (the commit) or why it is wrong, with proof", usage)
    record = reviews.load(ctx, number)
    entry = next((r for r in reversed(record["rounds"]) if r["round"] == round_no and not r.get("void")), None)
    if entry is None or entry.get("result") is None:
        valid = [r["round"] for r in records.valid_rounds(record)]
        raise Failure(
            f"pull request #{number} has no valid review round {round_no} (valid rounds: {valid or 'none'})",
            f"python tools/retrodev status, or the record notes/reviews/pr{number}.md",
        )
    count = len(reviews.findings(entry))
    indexes = list(range(count)) if every is not None else [int(index or 0)]
    if not count:
        raise Failure(
            f"round {round_no} of #{number} was clean: nothing to answer", f"python tools/retrodev land {number}"
        )
    for n in indexes:
        try:
            record = records.answer(
                number, round_no, n, words.strip(), repo=ctx.top, root=reviews.root(ctx), notes=reviews.notes(ctx)
            )
        except IndexError:
            raise Failure(f"round {round_no} has {count} finding(s), numbered 0 to {count - 1}; no {n}", usage)
    left = reviews.unanswered(record)
    ctx.out.say(f"answered finding(s) {', '.join(map(str, indexes))} of round {round_no} on #{number}")
    where = pr_stage(ctx, number, entry.get("sha"))
    if where == "merged":
        ctx.out.say(f"#{number} is already merged. next: python tools/retrodev summary {number}")
    elif left:
        ctx.out.say("still unanswered: " + ", ".join(f"round {r} finding {i}" for r, i, _f in left))
    elif where == "shipped":
        ctx.out.say(
            f"the fixes are shipped (the head moved past the reviewed one). next: python tools/retrodev land {number}"
        )
    else:
        ctx.out.say(f"next: commit, check and ship the fixes, then python tools/retrodev land {number}")
    ctx.out.set(pr=number, round=round_no, answered=indexes, unanswered=[[r, i] for r, i, _f in left], stage=where)
    return 0


def pr_stage(ctx, number: int, reviewed: str | None) -> str:
    """'merged'; 'shipped' (the local head is pushed as the pull request's head, and it is not the reviewed head);
    else 'fixing'. Unknown (gh unreachable) counts as 'fixing': the answer is recorded either way."""
    try:
        info = reviews.pr_view(ctx, number, "state,headRefName,headRefOid")
    except Failure:
        return "fixing"
    if info.get("state") == "MERGED":
        return "merged"
    tree = land_gates.find_worktree(ctx, info.get("headRefName") or "")
    pushed = info.get("headRefOid")
    if tree and pushed and repo.head(tree) == pushed and pushed != reviewed and not repo.dirty(tree):
        return "shipped"
    return "fixing"
