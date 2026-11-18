"""Step 7: an owner-approved pull request through read-only Codex review rounds, CI on its exact head and the merge.

    land <pr> [--no-review [--reason TEXT]] [--ci-timeout SECONDS] [--dry-run]

It runs until it needs the agent or the owner, or the pull request is merged; run it again and it resumes from the
records (nothing is reviewed twice). It runs for many minutes: start it in the background.

  gates (all reported at once)     the owner's approval of THIS pull request; open, into the base branch (a draft
                                   is marked ready); the worktree's head is the pull request's head and pushed;
                                   clean; check passed on it (land_gates.py)                        else 1, or 3
  the last round was void or invalid twice                                               3 needs the owner
  findings not answered yet                                                              1, naming them
  a round is due (none at this head, under 3 rounds, earlier findings answered)
      probe the reviewer once: unavailable or no review_profile -> reviews skipped (recorded), on to CI
      run the round (minutes; CI runs meanwhile): findings -> 1 'fix' with the next steps;
      void or invalid -> 3; clean -> on to CI
  round 3 had findings, all answered      on to CI with this head, accepted once (never a 4th round)
  3 rounds ran and the head moved past the clean or accepted head        3 the owner decides (--no-review or not)
  CI on the exact head: failing -> 1 with the jobs; still running after --ci-timeout -> 2; every poll and the
  moment before the merge recheck the pull request: closed, merged elsewhere, retargeted or pushed -> 1, no merge
  merge: gh pr merge <n> --squash --delete-branch --match-head-commit <sha>; pull the main checkout (on the base
  branch and clean); gc that branch only; the summary (land_merge.py: a failed step is finished by land again) 0
"""

from __future__ import annotations

from pathlib import Path

from . import ci, gates, github, land_carry, land_gates, land_merge, reviews
from .gates import Gate
from .land_merge import progress
from .output import FAILED, OWNER, Failure
from .review import audit, records
from .review import round as review_round


def decide(rec: dict, sha: str) -> str:
    """records.next_action as land uses it: CI is checked after the reviews, on the exact head."""
    action = records.next_action(rec, True, head=sha)
    if action == "fix" and not reviews.unanswered(rec):
        # Every finding answered and nothing new pushed (each answer disputes its finding with proof): the next
        # round judges the answers.
        return "review"
    return action


def owner_failure(rec: dict, number: int) -> Failure:
    last = [entry for entry in rec.get("rounds", []) if entry.get("void") or entry.get("stopped")][-2:]
    details = []
    for entry in last:
        details += (entry.get("audit") or {}).get("violations", []) + (entry.get("errors") or [])
        if entry.get("stopped"):
            details.append(entry["stopped"])
    return Failure(
        f"the review of #{number} needs the owner: " + ("; ".join(dict.fromkeys(details)) or "the last round stopped"),
        f"show the owner notes/reviews/pr{number}.md (every attempt, its audit and output); they decide whether to "
        f"run land {number} --no-review (merge on green CI) or look into the reviewer",
        code=OWNER,
        data={"action": "needs-owner", "details": details},
    )


def exhausted_failure(rec: dict, number: int, sha: str) -> Failure:
    last = records.valid_rounds(rec)[-1]
    accepted = (rec.get("accepted") or {}).get("head")
    seen = (
        f"the head accepted with round 3's fixes ({accepted[:9]})"
        if accepted
        else f"round 3's head ({last['sha'][:9]})"
    )
    return Failure(
        f"reviews exhausted on #{number}: {records.MAX_ROUNDS} rounds ran and the head moved past {seen} to "
        f"{sha[:9]}: those commits were never reviewed",
        f"the owner decides: python tools/retrodev land {number} --no-review (merge on green CI without a review "
        "of the new commits; recorded), or not",
        code=OWNER,
        data={"action": "reviews-exhausted", "reviewed": accepted or last["sha"], "head": sha},
    )


def unanswered_failure(ctx, rec: dict, number: int) -> Failure:
    left = reviews.unanswered(rec)
    for round_no, index, finding in left:
        ctx.out.say(f"  round {round_no} " + reviews.finding_line(index, finding))
    return Failure(
        "findings not answered yet: " + ", ".join(f"round {r} finding {i}" for r, i, _f in left),
        f"for each: python tools/retrodev answer {number} <round> <index> '<fixed in <sha>: how; or why it is "
        f"wrong, with proof>', then python tools/retrodev land {number}",
        code=FAILED,
        data={"action": "answer", "unanswered": [[r, i] for r, i, _f in left]},
    )


def findings_failure(ctx, number: int, round_no: int, result: dict) -> Failure:
    items = result.get("findings") or []
    ctx.out.say(f"review round {round_no}: {len(items)} finding(s)")
    for n, finding in enumerate(items):
        ctx.out.say("  " + reviews.finding_line(n, finding))
    last = round_no >= records.MAX_ROUNDS
    steps = [
        "fix each finding (or, when one is wrong, prove it: a test or command output)",
        "python tools/retrodev check",
        "git add -A && git commit -m '<what the fixes change>'",
        "python tools/retrodev ship --title '<the title>' --body <file>",
        f"python tools/retrodev answer {number} {round_no} <index> '<fixed in <sha>: how>' for each of 0..{len(items) - 1}",
        f"python tools/retrodev land {number}"
        + (
            " (round 3 was the last: it merges on green CI, no 4th round)"
            if last
            else f" (round {round_no + 1} reviews the fixes)"
        ),
    ]
    ctx.out.say("next:")
    for n, step in enumerate(steps, 1):
        ctx.out.say(f"  {n}. {step}")
    return Failure(
        f"review round {round_no} of #{number} has {len(items)} finding(s) to fix",
        "follow the numbered steps above, then land again",
        code=FAILED,
        data={"action": "fix", "round": round_no, "findings": items, "last_round": last},
    )


def run_round(ctx, info: dict, tree: Path, record: dict, rec: dict, sha: str) -> dict:
    """Probe the reviewer, then run one round. Returns the review record; raises on findings or a void round."""
    number, branch = info["number"], info["headRefName"]
    root, notes = reviews.root(ctx), reviews.notes(ctx)
    settings = reviews.settings(ctx)
    run = ctx.fakes.get("review_run")
    if settings["profile"]:
        ctx.out.say(
            f"probing the reviewer ({settings['provider']} {settings['model']}, profile {settings['profile']}) ..."
        )
    probe = review_round.landing_probe(settings, run)
    if probe.get("available"):
        records.add_probe(root, number, probe, notes)
        ctx.out.say(f"reviewer available ({probe.get('seconds')} s)")
    round_no = records.next_round(rec)
    if probe.get("available"):
        ctx.out.say(
            f"review round {round_no} of {records.MAX_ROUNDS} on {sha[:9]}: running (minutes; CI runs meanwhile)"
        )
        progress(ctx, record, "reviewing", round=round_no, head=sha)
    result = review_round.run_round(
        tree,
        number,
        sha,
        settings,
        title=info.get("title", ""),
        goal=reviews.goal(ctx, gates.plan_for(ctx, branch, record), info.get("body") or ""),
        base=ctx.remote_base,
        mechanical=reviews.mechanical(ctx, tree, ctx.remote_base, sha),
        probe=probe,
        run=run,
        ls_remote=ctx.fakes.get("ls_remote") or (lambda path, name: audit.ls_remote_branch(path, name, ctx.remote)),
        root=root,
        notes=notes,
        db=ctx.fakes.get("review_db"),
        branch=branch,
    )
    rec = records.load(root, number)
    status = result["status"]
    if status == "skipped":
        ctx.out.say(f"reviews skipped: {rec['skipped']['reason']}; merging on green CI (recorded)")
        return rec
    if status in ("void", "invalid", "limit"):
        raise owner_failure(rec, number)
    if result["result"]["verdict"] == "findings":
        progress(ctx, record, "fix", round=round_no, head=sha)
        raise findings_failure(ctx, number, round_no, result["result"])
    ctx.out.say(f"review round {round_no}: clean")
    return rec


NO_REVIEW = "land --no-review"


def review_step(
    ctx, info: dict, tree: Path, record: dict, sha: str, no_review: bool, reason: str | None = None
) -> dict:
    number = info["number"]
    root, notes = reviews.root(ctx), reviews.notes(ctx)
    rec = records.note_head(root, number, sha, notes)
    if no_review and not rec.get("skipped"):
        # Who decided is not known here (an agent can pass --no-review too), so only the reason given is recorded.
        rec = records.mark_skipped(root, number, (reason or "").strip() or NO_REVIEW, notes)
    rec = land_carry.carry(ctx, tree, rec, sha)
    action = decide(rec, sha)
    ctx.out.set(review_action=action)
    if action == "needs-owner":
        raise owner_failure(rec, number)
    if action == "reviews-exhausted":
        raise exhausted_failure(rec, number, sha)
    if reviews.unanswered(rec):
        raise unanswered_failure(ctx, rec, number)
    if action == "review":
        return run_round(ctx, info, tree, record, rec, sha)
    if action == "merge-on-green":
        ctx.out.say(f"reviews skipped ({rec['skipped']['reason']}): merging on green CI")
    elif action == "fix-then-merge":
        rec = records.accept_head(root, number, sha, notes)
        ctx.out.say(
            f"review round 3's findings are answered: merging {sha[:9]} on green CI (no 4th round; a later push "
            "needs the owner)"
        )
    else:
        seen = records.reviewed_as(rec, sha)
        ctx.out.say(f"review: {reviews.describe(rec)}; clean on " + ("this head" if seen == sha else seen[:9]))
    return rec


def stop_on_conflict(ctx, info: dict, tree: Path) -> None:
    """A pull request GitHub cannot merge is reported at once (UNKNOWN, still computing, goes on)."""
    if land_gates.mergeable(ctx, info["number"]) == "CONFLICTING":
        raise land_gates.conflict_failure(ctx, info, tree)


def run(
    ctx,
    number: int,
    no_review: bool = False,
    ci_timeout: float | None = None,
    dry_run: bool = False,
    reason: str | None = None,
) -> int:
    if reason is not None and not no_review:
        raise Failure(
            "--reason says why the reviews were skipped, so it only goes with --no-review",
            f"python tools/retrodev land {number} --no-review --reason '...', or leave --reason out",
        )
    info = reviews.pr_view(ctx, number)
    branch = info["headRefName"]
    ctx.out.say(f"land #{number}: {info.get('title')} ({branch}, {info.get('url')})")
    ctx.out.set(pr=number, branch=branch, head=info.get("headRefOid"), dry_run=dry_run)
    if info.get("state") == "MERGED":
        rec = reviews.load(ctx, number)
        if land_merge.unfinished(rec):
            if dry_run:
                left = [step for step in ("pulled", "gc") if not (rec.get("landing") or {}).get(step)]
                ctx.out.say(f"#{number} is merged; still to do after the merge: {', '.join(left)}")
                ctx.out.say("dry run: nothing was changed; python tools/retrodev land " + f"{number} finishes them")
                ctx.out.set(action="finish", left=left)
                return 0
            ctx.out.say(f"#{number} is merged; finishing the steps after the merge (it is not merged again)")
            return land_merge.finish(ctx, number, rec)
        ctx.out.say(f"review: {reviews.describe(rec)}")
        ctx.out.say(f"#{number} is already merged. next: python tools/retrodev summary {number}")
        ctx.out.set(action="merged", review=reviews.rounds(rec))
        return 0
    record = reviews.branch_record(ctx, branch)
    tree = land_gates.find_worktree(ctx, branch) if branch else None
    found = land_gates.collect_gates(ctx, info, record, tree)
    if dry_run:
        return dry(ctx, info, found, record, tree)
    gates.enforce(ctx, found, "land")
    assert tree is not None
    sha = info["headRefOid"]
    stop_on_conflict(ctx, info, tree)
    if info.get("isDraft"):
        github.gh(ctx, ["pr", "ready", str(number)])
        ctx.out.say(f"marked #{number} ready for review")
    review_step(ctx, info, tree, record, sha, no_review, reason)
    timeout = float(ci_timeout if ci_timeout is not None else ctx.policy.get("land", {}).get("ci_timeout", 1500))
    stop_on_conflict(ctx, info, tree)
    progress(ctx, record, "waiting for CI", head=sha)
    ctx.out.say(f"waiting for CI on {sha[:9]} (up to {int(timeout)} s) ...")
    jobs = ci.wait(ctx, number, sha, timeout)
    return land_merge.merge(ctx, info, sha, record, jobs)


def dry(ctx, info: dict, found: list[Gate], record: dict, tree: Path | None = None) -> int:
    """Print the gates and what land would do next; change nothing."""
    number = info["number"]
    code = 0
    try:
        gates.enforce(ctx, found, "land")
    except Failure as failure:
        code = failure.code
        ctx.out.say(f"gates: {failure.message}")
    rec = land_carry.carry(ctx, tree, reviews.load(ctx, number), info.get("headRefOid") or "", save=False)
    action = decide(rec, info.get("headRefOid") or "")
    if reviews.unanswered(rec):
        action = "answer"
    words = {
        "review": f"probe the reviewer, then run review round {records.next_round(rec)}",
        "answer": "stop: findings not answered yet",
        "needs-owner": "stop: the last round needs the owner",
        "reviews-exhausted": "stop: 3 rounds ran and the head moved past the reviewed one; the owner decides",
        "merge-on-green": "wait for CI, then merge (reviews skipped)",
        "fix-then-merge": "wait for CI, then merge (round 3 answered; this head is the one accepted)",
        "merge": "wait for CI, then merge (the last round is clean on this head)",
    }
    ctx.out.say(f"review: {reviews.describe(rec)}")
    ctx.out.say(f"would: {words.get(action, action)}" + ("" if not code else " (once the gates pass)"))
    ctx.out.say("dry run: nothing was reviewed, readied or merged")
    ctx.out.set(action=action, review=reviews.rounds(rec), landing=record.get("land"))
    return code
