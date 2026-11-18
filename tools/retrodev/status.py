"""Where a change stands, and the one next step.

    status [--json]

On a work branch: its record (plan and approval, checks on the current tree, the pull request, the pushed head,
CI) and the next step as one line. In the main checkout: every open record and worktree.
"""

from __future__ import annotations

from . import gates, github, plan, repo, reviews, state


def next_step(facts: dict) -> str:
    """The one next command for a branch, from its facts (pure: the tests drive it directly)."""
    topic = facts.get("plan") or facts.get("topic") or "<topic>"
    if facts.get("protected"):
        return "next: python tools/retrodev start <kind>/<topic> (work happens in a worktree on its own branch)"
    if facts.get("needs_plan") and not facts.get("plan_approved"):
        return (
            f"next: show the owner notes/plans/{topic}.md; when they say start: python tools/retrodev plan "
            f'approve {topic} --words "<their exact words>"'
        )
    if not facts.get("checks_passed"):
        return "next: python tools/retrodev check"
    if facts.get("dirty"):
        return "next: git add -A && git commit -m '<what changed>' (the checks passed on these changes)"
    if not facts.get("pr"):
        return "next: python tools/retrodev ship --title '<one plain sentence>' --body <file>"
    if facts.get("head") != facts.get("pushed"):
        return "next: python tools/retrodev ship --title '<title>' --body <file> (pushes the new commits)"
    pr = facts["pr"]
    if facts.get("unanswered"):
        first = facts["unanswered"][0]
        return (
            f"next: fix the review findings, check and ship, then python tools/retrodev answer {pr} {first[0]} <index> "
            f"'<fixed in <sha>: how>' for each ({len(facts['unanswered'])} open), then python tools/retrodev land {pr}"
        )
    if facts.get("approved"):
        return f"next: python tools/retrodev land {pr} (in the background: reviews, CI and the merge take minutes)"
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


def branch_facts(ctx, branch: str, path, record: dict, with_ci: bool = True) -> dict:
    named = branch.partition("/")[2]
    topic = record.get("topic") or (named if state.NAME.match(named) else None)
    plan_topic = record.get("plan") or topic
    plan_row = plan.describe(ctx, plan_topic) if plan_topic else None
    pr = (record.get("pr") or {}).get("number")
    jobs = github.checks(ctx, pr) if pr and with_ci else None
    review = reviews.load(ctx, pr) if pr else None
    return {
        "branch": branch,
        "path": str(path),
        "topic": topic,
        "plan": plan_topic,
        "protected": branch in ctx.policy["branches"]["protected"],
        "needs_plan": gates.plan_for(ctx, branch, record) is not None,  # ship's own rule
        "plan_approved": bool(plan_row and plan_row["approved"]),
        "plan_changed": bool(plan_row and plan_row["changed_since_approval"]),
        "checks_passed": record.get("passed_tree") == repo.tree_digest(path),
        "dirty": bool(repo.dirty(path)),
        "pr": pr,
        "pr_url": (record.get("pr") or {}).get("url"),
        "head": repo.head(path),
        "pushed": record.get("pushed"),
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
    if facts["plan"]:
        approval = "approved" if facts["plan_approved"] else "NOT approved"
        say(f"  plan:   {facts['plan']} ({approval}" + ("; changed since" if facts["plan_changed"] else "") + ")")
    say(f"  checks: {'passed on this tree' if facts['checks_passed'] else 'not passed on this tree'}")
    say(f"  tree:   {'uncommitted changes' if facts['dirty'] else 'committed'}; head {(facts['head'] or '')[:9]}")
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
                "next": "no worktree; its branch is kept (git worktree add <folder> <branch> to go on; gc removes "
                "it once merged)",
            }
        rows.append(facts)
        ctx.out.say(f"  {name:<34} {facts['path'] or '-'}\n    {facts['next']}")
    if not rows:
        ctx.out.say("  no work in progress: python tools/retrodev plan new <topic>")
    ctx.out.set(main=str(main), branch=branch, branches=rows)
    return 0
