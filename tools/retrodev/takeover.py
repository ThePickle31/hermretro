"""Take over a teammate's pushed branch: a worktree tracking it, set up as `start` sets one up.

    takeover <branch> [--no-setup]

Fetches, then makes <worktree_root>/<topic> on a local <branch> that tracks <remote>/<branch> (made from it; a
local branch of that name must not exist yet), runs start's setup (npm ci, the ruff setup) and records the branch
as start does. It never needs the main checkout on dev: nothing there changes but git's worktree list. The next
steps: while HEAD lacks commits of the base, read its diff of the files both changed (before the plan: sync's merge
empties it); the plan (plan new and plan approve, while the branch has no approved one); sync (the main checkout's
retrodev when the branch's own copy is older than the base's: it lacks newer sync fixes); then check. While the
branch's copy is older, every one of these retrodev commands is the main checkout's, run in the worktree.
"""

from __future__ import annotations

from . import gates, plan, repo, start, state, status, sync
from .gates import Gate
from .output import Failure, cmd


def topic_of(branch: str) -> str:
    """The folder and record topic: what follows <kind>/ (or the whole name), as a plan topic would be written."""
    named = branch.partition("/")[2] or branch
    return named if state.NAME.match(named) else "-".join(part for part in named.replace("/", "-").split("-") if part)


def run(ctx, branch: str, setup: bool = True) -> int:
    main = ctx.main()
    if not branch or branch in ctx.policy["branches"]["protected"]:
        raise Failure(
            f"'{branch}' is not a work branch to take over (dev and main take changes only through pull requests)",
            "python tools/retrodev takeover <kind>/<topic> (the teammate's pushed branch)",
        )
    topic = topic_of(branch)
    if not all(state.NAME.match(part) for part in branch.split("/")) or not state.NAME.match(topic):
        # state.branch_path's rule, before the fetch, the local branch, the worktree or setup: nothing to undo
        raise Failure(
            f"'{branch}' cannot name a retrodev record (each part lowercase letters, digits, dots, dashes or "
            "underscores); nothing was fetched or made",
            f"ask the teammate to push it under a name like feat/{topic.lower() or '<topic>'}, then python "
            "tools/retrodev takeover <that branch>",
        )
    path = ctx.worktree_root() / topic
    repo.git(["fetch", "--quiet", ctx.remote], main)
    remote = f"{ctx.remote}/{branch}"
    exists = repo.ok(["show-ref", "--verify", "-q", f"refs/heads/{branch}"], main)
    gates.enforce(
        ctx,
        [
            gates.passed("pushed", remote)
            if repo.head(main, repo.remote_ref(ctx.remote, branch))
            else Gate("pushed", False, f"{remote} does not exist after the fetch", f"git ls-remote {ctx.remote}"),
            Gate(
                "no local branch yet",
                False,
                f"a local {branch} exists already (taken over before, or started here)",
                plan.restore_command(ctx, branch) + " (or python tools/retrodev status in the main checkout)",
            )
            if exists
            else gates.passed("no local branch yet", branch),
            Gate("worktree folder is free", False, f"{path} already exists", f"remove {path}, or take over elsewhere")
            if path.exists()
            else gates.passed("worktree folder is free", str(path)),
        ],
        f"takeover {branch}",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    repo.git(["worktree", "add", "--quiet", "--track", "-b", branch, str(path), remote], main)
    ctx.out.say(f"worktree {path} on {branch}, tracking {remote} ({(repo.head(path) or '')[:9]})")
    setup_results = start.run_setup(ctx, path) if setup else []
    record = state.load_branch(main, branch)
    kind = branch.partition("/")[0] if "/" in branch else ""
    record.update(
        branch=branch,
        kind=kind,
        topic=topic,
        worktree=str(path),
        base=ctx.remote_base,
        created=state.now(),
        start_sha=repo.head(path),
        taken_over=remote,
    )
    state.save_branch(main, record)
    steps = next_steps(ctx, branch, path, record, topic)
    kinds = ctx.policy["branches"]["kinds"]
    if kind not in kinds:  # ship, land and CI read no branch kind (release notes group by labels): it keeps its name
        ctx.out.say(
            f"note: '{kind or branch}' is not one of this repository's kinds ({', '.join(kinds)}); {branch} keeps its "
            "name: ship, land and CI accept any work branch (the pull request's title and labels are what the "
            "release notes use). To rename it anyway, before plan approve: "
            + cmd("git", "branch", "-m", branch, f"fix/{topic}")
            + " && "
            + cmd("git", "push", "-u", ctx.remote, f"fix/{topic}")
            + f", then python tools/retrodev plan link {topic} there"
        )
        ctx.out.set(kind_note=True)
    for step in steps:
        ctx.out.say("next: " + step)
    ctx.out.set(path=str(path), branch=branch, topic=topic, tracking=remote, setup=setup_results, next=steps)
    return 0


def next_steps(ctx, branch: str, path, record: dict, topic: str) -> list[str]:
    """Every retrodev command in them is run by sync.runner: the main checkout's while the branch's own copy is older
    (its plan approve and status would print the older sync step), until sync brings the branch's copy up to date."""
    run = sync.runner(ctx, path)
    return [sync.newer(step, run) for step in _next_steps(ctx, branch, path, record)]


def _next_steps(ctx, branch: str, path, record: dict) -> list[str]:
    steps = [cmd("cd", path)]
    behind = status.behind(ctx, path)
    both = status.overlap(ctx, path) if behind else []
    named = gates.plan_for(ctx, branch, record)
    planned = named and state.NAME.match(named) and not gates.plan_approved(ctx, named).ok
    if both:  # sync's merge empties this diff: read it while it still shows what dev did to the branch's files
        steps.append(status.read_first(both, ctx.remote_base, "writing the plan" if planned else "sync merges it"))
    if planned and named:
        if not plan.plan_file(ctx, named).is_file():
            steps.append(f"python tools/retrodev plan new {named} (say what the branch does and what is left)")
        steps.append(
            f"show the owner notes/plans/{named}.md; when they say start: python tools/retrodev plan approve {named} "
            '--words "<their exact words>" (it also writes the pull request body)'
        )
    if behind:
        steps.append(
            f"{sync.sync_command(ctx, path)} (HEAD lacks {behind} commit(s) of {ctx.remote_base}{sync.older(ctx, path)})"
        )
    steps.append("python tools/retrodev check")
    return steps
