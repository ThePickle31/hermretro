"""Step 7: an owner-approved pull request through read-only Codex review rounds, CI on its exact head and the merge.

    land <pr> [--no-review] [--ci-timeout SECONDS] [--dry-run]

It runs until it needs the agent or the owner, or the pull request is merged; run it again and it resumes from the
records (nothing is reviewed twice). It runs for many minutes: start it in the background.

  gates (all reported at once)     the owner's approval recorded; open, into the base branch (a draft is marked
                                   ready); the worktree's head is the pull request's head and pushed; clean; check
                                   passed on it                                                     else 1, or 3
  the last round was void or invalid twice                                               3 needs the owner
  findings not answered yet                                                              1, naming them
  a round is due (none at this head, under 3 rounds, earlier findings answered)
      probe the reviewer once: unavailable or no review_profile -> reviews skipped (recorded), on to CI
      run the round (minutes; CI runs meanwhile): findings -> 1 'fix' with the next steps;
      void or invalid -> 3; clean -> on to CI
  round 3 had findings, all answered                                     on to CI (never a 4th round)
  CI on the exact head: failing -> 1 with the jobs; still running after --ci-timeout -> 2
  merge: gh pr merge <n> --squash --delete-branch --match-head-commit <sha>; pull the main checkout (on the base
  branch and clean); gc that branch only; the summary                                    0
"""

from __future__ import annotations

from pathlib import Path

from . import ci, gates, gc, github, repo, reviews, state
from .gates import Gate
from .output import FAILED, OWNER, Failure
from .review import audit, records
from .review import round as review_round


def find_worktree(ctx, branch: str) -> Path | None:
    for tree in repo.worktrees(ctx.main()):
        if tree.branch == branch and tree.path.is_dir():
            return tree.path
    return None


def remote_head(ctx, tree: Path, branch: str) -> str | None:
    out = repo.git(["ls-remote", ctx.remote, f"refs/heads/{branch}"], tree, check=False).strip()
    return out.split()[0] if out else None


def collect_gates(ctx, info: dict, record: dict, tree: Path | None) -> list[Gate]:
    number, branch = info["number"], info["headRefName"]
    approval = record.get("approval")
    found = [
        gates.passed("owner approved", f"{approval['at']}: \"{approval['words']}\"")
        if approval
        else Gate(
            "owner approved",
            False,
            f"the owner has not approved #{number}: land merges only what the owner approved",
            f'when the owner approves: python tools/retrodev approve {number} --words "<their exact words>"',
            OWNER,
        )
    ]
    found.append(
        gates.passed("pull request open")
        if info.get("state") == "OPEN"
        else Gate("pull request open", False, f"#{number} is {str(info.get('state')).lower()}", f"gh pr view {number}")
    )
    found.append(
        gates.passed("into " + ctx.base)
        if info.get("baseRefName") == ctx.base
        else Gate(
            "into " + ctx.base,
            False,
            f"#{number} goes into {info.get('baseRefName')}; changes reach {ctx.base} only through pull requests into it",
            f"gh pr edit {number} --base {ctx.base}, then land again",
        )
    )
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
                "python tools/retrodev ship --title '<title>' --body <file> (pushes the new commits)"
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
            "python tools/retrodev ship --title '<title>' --body <file>",
        )
    )
    found += [gates.committed(wctx), gates.checks_on_tree(wctx, record, repo.tree_digest(tree))]
    return found


def progress(ctx, record: dict, step: str, **facts) -> None:
    """Remember the landing's last step in the branch record (status shows it; a rerun resumes from the records)."""
    record["land"] = {"step": step, "at": state.now(), **facts}
    state.save_branch(ctx.top, record)


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


def review_step(ctx, info: dict, tree: Path, record: dict, sha: str, no_review: bool) -> dict:
    number = info["number"]
    root, notes = reviews.root(ctx), reviews.notes(ctx)
    rec = records.note_head(root, number, sha, notes)
    if no_review and not rec.get("skipped"):
        rec = records.mark_skipped(root, number, "land --no-review (the owner's call)", notes)
    action = decide(rec, sha)
    ctx.out.set(review_action=action)
    if action == "needs-owner":
        raise owner_failure(rec, number)
    if reviews.unanswered(rec):
        raise unanswered_failure(ctx, rec, number)
    if action == "review":
        return run_round(ctx, info, tree, record, rec, sha)
    if action == "merge-on-green":
        ctx.out.say(f"reviews skipped ({rec['skipped']['reason']}): merging on green CI")
    elif action == "fix-then-merge":
        ctx.out.say("review round 3's findings are answered: merging on green CI (no 4th round)")
    else:
        ctx.out.say(f"review: {reviews.describe(rec)}; clean on this head")
    return rec


def merge(ctx, info: dict, sha: str, record: dict, jobs: list[dict]) -> int:
    number, branch = info["number"], info["headRefName"]
    main = ctx.at(ctx.main())
    subject = f"{info['title']} (#{number})"
    args = ["pr", "merge", str(number), "--squash", "--delete-branch", "--match-head-commit", sha, "--subject", subject]
    ctx.out.say(f"merging #{number} at {sha[:9]}: gh {' '.join(args[:7])} ...")
    code, out, err = github.gh(main, args, check=False)
    if code and github.pr_state(main, number) != "MERGED":
        raise Failure(
            f"gh pr merge {number} failed: {(err or out).strip()[:300]}",
            f"gh pr view {number} (a head that moved is refused by --match-head-commit: land again)",
        )
    if code:
        ctx.out.say(f"merged (gh also said: {(err or out).strip()[:200]})")
    rec = reviews.load(ctx, number)
    rec["merged"] = {"at": state.now(), "head": sha, "subject": subject, "ci": [j.get("name") for j in jobs]}
    rec.setdefault("approval", record.get("approval"))
    reviews.save(ctx, rec)
    progress(ctx, record, "merged", head=sha)
    ctx.out.say(f"merged #{number} into {ctx.base} (squash)")
    tops = ctx.main()
    if repo.branch(tops) == ctx.base and not repo.dirty(tops):
        repo.git(["pull", "--ff-only", "--quiet", ctx.remote, ctx.base], tops)
        ctx.out.say(f"updated the main checkout {tops} ({ctx.base} at {(repo.head(tops) or '')[:9]})")
    else:
        ctx.out.say(f"left the main checkout {tops} alone (not on {ctx.base}, or uncommitted changes): pull it later")
    gc.run(main, only=branch)
    ctx.out.say(f"next: python tools/retrodev summary {number} (the step-8 note for the owner)")
    ctx.out.set(merged=True, head=sha, action="merged")
    return 0


def run(ctx, number: int, no_review: bool = False, ci_timeout: float | None = None, dry_run: bool = False) -> int:
    info = reviews.pr_view(ctx, number)
    branch = info["headRefName"]
    ctx.out.say(f"land #{number}: {info.get('title')} ({branch}, {info.get('url')})")
    ctx.out.set(pr=number, branch=branch, head=info.get("headRefOid"), dry_run=dry_run)
    if info.get("state") == "MERGED":
        rec = reviews.load(ctx, number)
        ctx.out.say(f"review: {reviews.describe(rec)}")
        ctx.out.say(f"#{number} is already merged. next: python tools/retrodev summary {number}")
        ctx.out.set(action="merged", review=reviews.rounds(rec))
        return 0
    record = reviews.branch_record(ctx, branch)
    tree = find_worktree(ctx, branch) if branch else None
    found = collect_gates(ctx, info, record, tree)
    if dry_run:
        return dry(ctx, info, found, record)
    gates.enforce(ctx, found, "land")
    assert tree is not None
    sha = info["headRefOid"]
    if info.get("isDraft"):
        github.gh(ctx, ["pr", "ready", str(number)])
        ctx.out.say(f"marked #{number} ready for review")
    rec = review_step(ctx, info, tree, record, sha, no_review)
    if rec.get("approval") is None and record.get("approval"):
        rec["approval"] = record["approval"]
        reviews.save(ctx, rec)
    timeout = float(ci_timeout if ci_timeout is not None else ctx.policy.get("land", {}).get("ci_timeout", 1500))
    progress(ctx, record, "waiting for CI", head=sha)
    ctx.out.say(f"waiting for CI on {sha[:9]} (up to {int(timeout)} s) ...")
    jobs = ci.wait(ctx, number, sha, timeout)
    return merge(ctx, info, sha, record, jobs)


def dry(ctx, info: dict, found: list[Gate], record: dict) -> int:
    """Print the gates and what land would do next; change nothing."""
    number = info["number"]
    code = 0
    try:
        gates.enforce(ctx, found, "land")
    except Failure as failure:
        code = failure.code
        ctx.out.say(f"gates: {failure.message}")
    rec = reviews.load(ctx, number)
    action = decide(rec, info.get("headRefOid") or "")
    if reviews.unanswered(rec):
        action = "answer"
    words = {
        "review": f"probe the reviewer, then run review round {records.next_round(rec)}",
        "answer": "stop: findings not answered yet",
        "needs-owner": "stop: the last round needs the owner",
        "merge-on-green": "wait for CI, then merge (reviews skipped)",
        "fix-then-merge": "wait for CI, then merge (round 3 answered)",
        "merge": "wait for CI, then merge (the last round is clean on this head)",
    }
    ctx.out.say(f"review: {reviews.describe(rec)}")
    ctx.out.say(f"would: {words.get(action, action)}" + ("" if not code else " (once the gates pass)"))
    ctx.out.say("dry run: nothing was reviewed, readied or merged")
    ctx.out.set(action=action, review=reviews.rounds(rec), landing=record.get("land"))
    return code
