"""Where a change stands, and the one next step.

    status [--json]

On a work branch: its record (plan and approval, checks on the current tree, the pull request, the pushed head,
CI) and the next step as one line. In the main checkout: every open record and worktree.
"""

from __future__ import annotations

import os

from . import gates, github, plan, repo, reviews, ship, state, sync
from .output import cmd


NOTHING_NEXT = "next: python tools/retrodev plan new <topic> (docs/chore: start <kind>/<topic> --no-plan)"


def plan_steps(facts: dict) -> str | None:
    """The exact plan commands a branch that needs a plan still lacks (None once it is approved, or for docs/chore),
    each run by the branch's runner (sync.runner: the newer retrodev while the branch's own copy is older)."""
    steps = _plan_steps(facts)
    return sync.newer(steps, facts.get("runner") or sync.RUNNER) if steps else steps


def _plan_steps(facts: dict) -> str | None:
    if not facts.get("needs_plan") or facts.get("plan_approved"):
        return None
    topic = facts.get("plan") or facts.get("topic") or "<topic>"
    approve = f'python tools/retrodev plan approve {topic} --words "<the owner\'s exact words>"'
    if facts.get("plan_exists") is False:
        return f"python tools/retrodev plan new {topic}, fill it in, show the owner, then {approve}"
    return f"show the owner notes/plans/{topic}.md; when they say start: {approve}"


def next_step(facts: dict) -> str:
    """The one next command for a branch (_next_step), each retrodev command in it run by the branch's runner."""
    return sync.newer(_next_step(facts), facts.get("runner") or sync.RUNNER)


def _next_step(facts: dict) -> str:
    """The one next command for a branch, from its facts (pure: the tests drive it directly). A branch behind the
    base syncs first, before any plan step (the plan step follows it in the same line)."""
    topic = facts.get("plan") or facts.get("topic") or "<topic>"
    if facts.get("protected"):
        return "next: python tools/retrodev start <kind>/<topic> (work happens in a worktree on its own branch)"
    syncing = facts.get("sync") or "python tools/retrodev sync"  # sync.sync_command: the newer retrodev
    if facts.get("merging"):  # an open sync merge: only sync finishes it (rebuilds generated files, commits)
        if facts.get("merge_unresolved"):
            return (
                f"next: resolve the conflict hunks in {', '.join(facts['merge_unresolved'])} ({sync.HUNKS}), "
                + cmd("git", "add", *facts["merge_unresolved"])
                + f", then {syncing} (it rebuilds the generated files and makes the merge commit)"
            )
        return f"next: {syncing} (the merge's sources are resolved: it rebuilds the generated files and makes the merge commit)"
    planned = plan_steps(facts)
    if facts.get("behind"):
        lacks = f"HEAD lacks {facts['behind']} commit(s) of {facts.get('base') or 'origin/dev'}"
        after = planned or "python tools/retrodev check"
        first = ""  # a taken-over branch without a plan: what dev changed in its files, read before sync merges it
        if facts.get("overlap") and planned and facts.get("plan_exists") is False:
            first = read_first(facts["overlap"], facts.get("base") or "origin/dev") + ", then "
        if facts.get("dirty"):
            return (
                "next: "
                + cmd("git", "add", "-A")
                + " && "
                + cmd("git", "commit", "-m", "<what changed>")
                + f", then {first}{syncing} ({lacks}; sync merges only a committed tree), then {after}"
            )
        return f"next: {first}{syncing} ({lacks}), then {after}"
    if planned and facts.get("plan_exists") is False:
        return f"next: python tools/retrodev plan new {topic} (no plan is written yet; the owner approves one first)"
    if planned:
        return (
            f"next: show the owner notes/plans/{topic}.md; when they say start: python tools/retrodev plan "
            f'approve {topic} --words "<their exact words>"'
        )
    if not facts.get("checks_passed"):
        return "next: python tools/retrodev check"
    if facts.get("dirty"):
        return (
            "next: "
            + cmd("git", "add", "-A")
            + " && "
            + cmd("git", "commit", "-m", "<what changed>")
            + (" (the checks passed on these changes)")
        )
    if not facts.get("pr") and facts.get("body"):
        title = facts.get("title") or "<one plain sentence>"
        if not facts.get("body_ok"):  # the body as it is now wins over any earlier dry run
            why = " (fill in every section of the body first)"
        elif facts.get("dry_run_passed"):
            why = f" (ship --dry-run passed at {facts['dry_run_passed']})"
        else:
            why = " (the body passes ship's body gate)"
        dry = bool(facts.get("last_ship_dry_run"))  # a dry run's next step stays one: status never makes it a push
        if dry:
            why += "; the last ship was a dry run: without --dry-run the same command pushes and opens the pull request"
        return "next: " + ship.command(title, facts["body"], dry) + why + no_title(facts)
    if not facts.get("pr"):
        dry = bool(facts.get("last_ship_dry_run"))
        return (
            "next: "
            + ship.command(facts.get("title") or "<one plain sentence>", dry_run=dry)
            + no_title(facts)
            + f" (no body yet: ship writes notes/pr/{facts.get('topic') or '<topic>'}.md from the template when it is "
            + "missing, then stops for it to be filled in"
            + ("; the last ship was a dry run: without --dry-run the same command pushes" if dry else "")
            + ")"
        )
    if facts.get("head") != facts.get("pushed"):
        again = facts.get("ship_again") or ship.command(dry_run=bool(facts.get("last_ship_dry_run")))
        if facts.get("last_ship_dry_run"):  # with a pull request too: status never turns a dry run into a push
            return (
                f"next: {again} (the last ship was a dry run: without --dry-run the same command pushes the "
                "new commits)"
            )
        return f"next: {again} (pushes the new commits)"
    pr = facts["pr"]
    # land runs from the main checkout: the merge removes this worktree
    land = (cmd("cd", facts["main"]) + " && " if facts.get("main") else "") + f"python tools/retrodev land {pr}"
    if facts.get("unanswered"):
        first = facts["unanswered"][0]
        return (
            f"next: fix the review findings, check and ship, then python tools/retrodev answer {pr} {first[0]} <index> "
            f"'<fixed in <sha>: how>' for each ({len(facts['unanswered'])} open), then {land}"
        )
    if facts.get("approved"):
        return f"next: {land} (in the background: reviews, CI and the merge take minutes)"
    ci = facts.get("ci")
    if ci == "pending":
        return f"next: wait for CI (gh pr checks {facts['pr']} --watch), then python tools/retrodev report"
    if ci == "failing":
        return (
            f"next: read the failure (gh pr checks {facts['pr']}; gh run view <run> --log-failed), fix it, "
            "check and ship again"
        )
    return (
        f"next: python tools/retrodev report, and give the owner the step-5 report; when they approve: "
        f'python tools/retrodev approve {pr} --words "<their exact words>"'
    )


def no_title(facts: dict) -> str:
    """Why the plan's Title: line is not the title offered (too long, a period), while no title is."""
    return "" if facts.get("title") else facts.get("title_note") or ""


def overlap(ctx, path) -> list[str]:
    """The files this branch changes that the base branch also changed since they parted (none when not behind)."""
    base = ctx.remote_base
    if not repo.head(path, base):
        return []
    ours = repo.git(["diff", "--name-only", f"{base}...HEAD"], path, check=False).splitlines()
    theirs = set(repo.git(["diff", "--name-only", f"HEAD...{base}"], path, check=False).splitlines())
    return [name for name in ours if name in theirs]


def read_first(files: list[str], base: str, before: str = "writing the plan") -> str:
    """Read what the base changed in the branch's files before planning: sync's merge makes that diff empty."""
    shown = cmd("git", "diff", f"HEAD...{base}", "--", *files)
    log = cmd("git", "log", "--oneline", f"HEAD..{base}", "--", *files)  # which commits, and why
    return f"read `{shown}` and `{log}` before {before} ({base} changed these files of the branch too)"


def behind(ctx, path) -> int:
    """Commits of the base branch this branch lacks, from the cached remote ref (no fetch: status stays offline)."""
    if not repo.head(path, ctx.remote_base):
        return 0
    counted = repo.git(["rev-list", "--count", f"HEAD..{ctx.remote_base}"], path, check=False).strip()
    return int(counted) if counted.isdigit() else 0


def open_merge(ctx, path) -> tuple[bool, list[str]]:
    """Whether a merge is open in this checkout (git resolves MERGE_HEAD in a worktree's own git folder), and its
    still-unresolved source files (the generated ones are sync's to rebuild)."""
    if repo.run(["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"], path)[0]:
        return False, []
    generated = set(ctx.policy["generated"]["files"])
    left = repo.git(["diff", "--name-only", "--diff-filter=U"], path, check=False).split()
    return True, [name for name in left if name not in generated]


def body_ok(ctx, body: str | None) -> bool:
    """The recorded body passes ship's own body gate (gates.body_problems)."""
    if not body or not os.path.isfile(body):
        return False
    with open(body, encoding="utf-8") as handle:
        return not gates.body_problems(handle.read(), ctx.policy["ship"]["sections"])


def dry_run_passed(record: dict, tree: str, body: str | None) -> str | None:
    """When the last ship --dry-run passed every gate on exactly this tree and this body (path and content), its
    time."""
    last = record.get("dry_run") or {}
    if not (last.get("ok") and last.get("tree") == tree and body and last.get("body") == body):
        return None
    return last.get("at") if last.get("body_sha256") == ship.body_digest(body) else None


def branch_facts(ctx, branch: str, path, record: dict, with_ci: bool = True) -> dict:
    named = branch.partition("/")[2]
    topic = record.get("topic") or (named if state.NAME.match(named) else None)
    plan_topic = record.get("plan") or topic
    plan_row = plan.describe(ctx, plan_topic) if plan_topic else None
    pr = (record.get("pr") or {}).get("number")
    jobs = github.checks(ctx, pr) if pr and with_ci else None
    review = reviews.load(ctx, pr) if pr else None
    body = record.get("body") or str(ship.default_body(ctx, branch, record))
    shown = body if not pr and os.path.isfile(body) else None
    tree = repo.tree_digest(path)
    merging, merge_unresolved = open_merge(ctx, path)
    return {
        "merging": merging,
        "merge_unresolved": merge_unresolved,
        "body": shown,
        "body_ok": body_ok(ctx, shown),
        "dry_run_passed": dry_run_passed(record, tree, shown) if shown else None,
        "last_ship_dry_run": bool(record.get("last_ship_dry_run")),
        "title": (record.get("pr") or {}).get("title") or record.get("title") or ship.plan_title(ctx, branch, record),
        "title_note": ship.title_note(ctx, branch, record),
        "behind": behind(ctx, path),
        "sync": sync.sync_command(ctx, path) if behind(ctx, path) or merging else None,
        "runner": sync.runner(ctx, path),
        "overlap": overlap(ctx, path) if record.get("taken_over") and behind(ctx, path) else [],
        "base": ctx.remote_base,
        "branch": branch,
        "path": str(path),
        "main": str(ctx.main()),
        "topic": topic,
        "plan": plan_topic,
        "protected": branch in ctx.policy["branches"]["protected"],
        "needs_plan": gates.plan_for(ctx, branch, record) is not None,  # ship's own rule
        "plan_exists": bool(plan_row and plan_row["exists"]) if plan_row else None,
        "plan_approved": bool(plan_row and plan_row["approved"]),
        "plan_changed": bool(plan_row and plan_row["changed_since_approval"]),
        "checks_passed": record.get("passed_tree") == tree,
        "dirty": bool(repo.dirty(path)),
        "pr": pr,
        "pr_url": (record.get("pr") or {}).get("url"),
        "head": repo.head(path),
        "pushed": record.get("pushed"),
        "ship_again": ship.again(record, bool(record.get("last_ship_dry_run"))),
        "ci": github.ci_summary(jobs) if pr and with_ci else None,
        "ci_jobs": jobs or [],
        "approved": record.get("approval"),
        "review": reviews.describe(review) if review else None,
        "unanswered": [[r, i] for r, i, _f in reviews.unanswered(review)] if review else [],
        "landing": record.get("land"),
    }


def show_branch(ctx, facts: dict) -> None:
    say = ctx.out.say
    say(f"branch {facts['branch']}  ({facts['path']})")
    if plan_steps(facts):  # up front: nothing ships without it
        missing = "none written" if facts.get("plan_exists") is False else "NOT approved"
        kind = facts["branch"].split("/")[0]
        say(
            f"  plan:   {facts['plan']} ({missing}): a {kind} branch ships only under an approved plan: {plan_steps(facts)}"
        )
    elif not facts.get("needs_plan") and not facts.get("plan_exists"):
        say("  plan:   none needed (docs/chore)")
    elif facts["plan"] and facts.get("plan_exists") is False:
        say(f"  plan:   {facts['plan']} (none written)")
    elif facts["plan"]:
        approval = "approved" if facts["plan_approved"] else "NOT approved"
        say(f"  plan:   {facts['plan']} ({approval}" + ("; changed since" if facts["plan_changed"] else "") + ")")
    say(f"  checks: {'passed on this tree' if facts['checks_passed'] else 'not passed on this tree'}")
    say(f"  tree:   {'uncommitted changes' if facts['dirty'] else 'committed'}; head {(facts['head'] or '')[:9]}")
    if facts.get("merging"):
        say("  merge:  open (a sync stopped on conflicts)")
    if facts.get("behind"):
        say(f"  behind {ctx.remote_base}: {facts['behind']} commits ({facts['sync']})")
    if facts["pr"]:
        pushed = "pushed" if facts["pushed"] == facts["head"] else "NOT pushed"
        say(f"  pr:     #{facts['pr']} {facts['pr_url'] or ''} (head {pushed}); CI {facts['ci']}")
        approval = facts.get("approved")
        say("  owner:  " + (f"approved {approval['at']}: \"{approval['words']}\"" if approval else "not approved yet"))
        say(f"  review: {facts.get('review')}")
        if facts.get("landing"):
            say(f"  land:   {facts['landing'].get('step')} ({facts['landing'].get('at')})")
    else:
        say("  pr:     none")
    say(facts["next"])


def run(ctx) -> int:
    branch = repo.branch(ctx.top)
    main = ctx.main()
    warning = state.override_warning()
    if warning:
        ctx.out.say(warning)
        ctx.out.set(state_override=os.environ["RETRODEV_STATE_DIR"])
    if branch and branch not in ctx.policy["branches"]["protected"]:
        record = state.load_branch(ctx.top, branch) if state.branch_path(ctx.top, branch).is_file() else {}
        facts = branch_facts(ctx, branch, ctx.top, record)
        facts["next"], facts["plan_steps"] = next_step(facts), plan_steps(facts)
        show_branch(ctx, facts)
        ctx.out.set(**facts)
        return 0
    trees = {str(tree.branch): tree for tree in repo.worktrees(main) if not tree.main}
    records = {record["branch"]: record for record in state.branches(main) if record.get("branch")}
    rows = []
    ctx.out.say(f"main checkout {main} on {branch}" + (" (uncommitted changes)" if repo.dirty(main) else ""))
    for name in sorted(set(trees) | set(records)):
        tree, record = trees.get(name), records.get(name, {})
        if tree and tree.path.is_dir():
            facts = branch_facts(ctx, name, tree.path, record, with_ci=False)
            facts["next"] = next_step(facts)
        else:
            facts = {
                "branch": name,
                "path": None,
                "next": f"no worktree; its branch is kept: to go on, {plan.restore_command(ctx, name, tree)} "
                "(gc removes it once merged)",
            }
        rows.append(facts)
        ctx.out.say(f"  {name:<34} {facts['path'] or '-'}")
        if facts.get("behind"):
            ctx.out.say(f"    behind {ctx.remote_base}: {facts['behind']} commits ({facts['sync']})")
        ctx.out.say(f"    {facts['next']}")
    if not rows:
        ctx.out.say("  no work in progress")
        ctx.out.say(NOTHING_NEXT)
    ctx.out.set(main=str(main), branch=branch, branches=rows, **({} if rows else {"next": NOTHING_NEXT}))
    return 0
