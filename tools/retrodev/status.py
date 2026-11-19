"""Where a change stands, and the one next step.

    status [--json]

On a work branch: its record (plan and approval, checks on the current tree, the pull request, the pushed head,
CI) and the next step as one line. In the main checkout: every open record and worktree.
"""

from __future__ import annotations

import os

from . import gates, github, plan, repo, reviews, ship, state, sync
from .output import cmd


def next_step(facts: dict) -> str:
    """The one next command for a branch, from its facts (pure: the tests drive it directly)."""
    topic = facts.get("plan") or facts.get("topic") or "<topic>"
    if facts.get("protected"):
        return "next: python tools/retrodev start <kind>/<topic> (work happens in a worktree on its own branch)"
    if facts.get("needs_plan") and not facts.get("plan_approved") and facts.get("plan_exists") is False:
        return f"next: python tools/retrodev plan new {topic} (no plan is written yet; the owner approves one first)"
    if facts.get("needs_plan") and not facts.get("plan_approved"):
        return (
            f"next: show the owner notes/plans/{topic}.md; when they say start: python tools/retrodev plan "
            f'approve {topic} --words "<their exact words>"'
        )
    if facts.get("merging"):  # an open sync merge: only sync finishes it (rebuilds generated files, commits)
        if facts.get("merge_unresolved"):
            return (
                f"next: resolve the conflict hunks in {', '.join(facts['merge_unresolved'])} ({sync.HUNKS}), "
                + cmd("git", "add", *facts["merge_unresolved"])
                + ", then python tools/retrodev sync (it rebuilds the generated files and makes the merge commit)"
            )
        return "next: python tools/retrodev sync (the merge's sources are resolved: it rebuilds the generated files and makes the merge commit)"
    if facts.get("behind"):
        lacks = f"HEAD lacks {facts['behind']} commit(s) of {facts.get('base') or 'origin/dev'}"
        if facts.get("dirty"):
            return (
                "next: "
                + cmd("git", "add", "-A")
                + " && "
                + cmd("git", "commit", "-m", "<what changed>")
                + f", then python tools/retrodev sync ({lacks}; sync merges only a committed tree), then check"
            )
        return f"next: python tools/retrodev sync ({lacks}), then python tools/retrodev check"
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
        return "next: " + cmd("python", "tools/retrodev", "ship", "--title", title, "--body", facts["body"]) + why
    if not facts.get("pr"):
        return (
            "next: "
            + cmd("python", "tools/retrodev", "ship", "--title", facts.get("title") or "<one plain sentence>")
            + f" (the first ship writes the body to fill in: notes/pr/{facts.get('topic') or '<topic>'}.md)"
        )
    if facts.get("head") != facts.get("pushed"):
        return f"next: {facts.get('ship_again') or 'python tools/retrodev ship'} (pushes the new commits)"
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
        "title": (record.get("pr") or {}).get("title") or record.get("title") or ship.plan_title(ctx, branch, record),
        "behind": behind(ctx, path),
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
        "ship_again": ship.again(record),
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
    if not facts.get("needs_plan") and not facts.get("plan_exists"):
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
        say(f"  behind {ctx.remote_base}: {facts['behind']} commits (python tools/retrodev sync)")
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
        facts["next"] = next_step(facts)
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
            ctx.out.say(f"    behind {ctx.remote_base}: {facts['behind']} commits (python tools/retrodev sync)")
        ctx.out.say(f"    {facts['next']}")
    if not rows:
        ctx.out.say("  no work in progress: python tools/retrodev plan new <topic>")
    ctx.out.set(main=str(main), branch=branch, branches=rows)
    return 0
