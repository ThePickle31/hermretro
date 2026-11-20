"""Step 4 begins: a worktree on a new branch from the freshest base branch, set up and ready.

    start <kind>/<topic> [--no-plan] [--no-setup]

Refuses unless the plan <topic> is approved (docs/ and chore/ may pass --no-plan for small changes), and while
the main checkout is off the base branch or has uncommitted changes (a checkout Hermes loads as its live plugin
stays on dev, and its changes are the owner's). The worktree goes to the configured worktree_root.
"""

from __future__ import annotations


from pathlib import Path

from . import gates, repo, state
from .gates import Gate
from .output import OWNER, Failure, cmd


def worktree_path(ctx, topic: str) -> Path:
    return ctx.worktree_root() / topic


def main_checkout_gate(ctx) -> Gate:
    main = ctx.main()
    branch = repo.branch(main)
    if branch != ctx.base:
        return Gate(
            "main checkout on the base branch",
            False,
            f"{main} is on '{branch}', not '{ctx.base}' (a checkout Hermes loads stays on {ctx.base})",
            f"ask the owner to switch {main} back to {ctx.base} ({cmd('git', '-C', main, 'switch', ctx.base)})",
            OWNER,
        )
    changes = repo.dirty(main)
    if changes:
        return Gate(
            "main checkout clean",
            False,
            f"{main} has {len(changes)} uncommitted change(s); they are the owner's and must not be mixed in",
            f"ask the owner to commit, stash or remove them ({cmd('git', '-C', main, 'status')})",
            OWNER,
        )
    return gates.passed("main checkout on the base branch and clean", str(main))


def run_setup(ctx, path: Path) -> list[dict]:
    """The new worktree's one-time setup (pinned npm tools, ruff); a failure is reported, never fatal."""
    results = []
    for words in ctx.policy["setup"]["commands"]:
        command = ctx.command(words)
        code, out, err = repo.run(command, path, timeout=600)
        tail = (out + err).strip().splitlines()[-1:]
        results.append({"command": ctx.shown(words), "ok": code == 0, "detail": tail[0] if tail else ""})
        ctx.out.say(f"  {'ok' if code == 0 else 'FAILED'}  {ctx.shown(words)}" + (f"  {tail[0]}" if tail else ""))
        if code:
            ctx.out.say(f"      FIX: {cmd('cd', path)} && {cmd(*command)}  (then python tools/retrodev doctor)")
    return results


def run(ctx, name: str, no_plan: bool = False, setup: bool = True, plan_topic: str | None = None) -> int:
    kinds = ctx.policy["branches"]["kinds"]
    kind, topic = gates.parse_branch(name, kinds)
    plan_topic = state.check_topic(plan_topic) if plan_topic else topic  # one plan may cover several branches
    checks = []
    if no_plan and kind not in ctx.policy["branches"]["no_plan"]:
        raise Failure(
            f"--no-plan is only for small {' and '.join(ctx.policy['branches']['no_plan'])} changes; a {kind} change "
            "starts from a plan the owner approved",
            f"python tools/retrodev plan new {topic}, then ask the owner",
            code=OWNER,
        )
    checks.append(gates.passed("plan", "--no-plan (small change)") if no_plan else gates.plan_approved(ctx, plan_topic))
    checks.append(main_checkout_gate(ctx))
    path = worktree_path(ctx, topic)
    main = ctx.main()
    exists = repo.ok(["show-ref", "--verify", "-q", f"refs/heads/{name}"], main)
    checks.append(
        Gate(
            "branch is new",
            False,
            f"the branch {name} already exists",
            "python tools/retrodev status (or pick another topic)",
        )
        if exists
        else gates.passed("branch is new", name)
    )
    checks.append(
        Gate("worktree folder is free", False, f"{path} already exists", f"remove {path}, or pick another topic")
        if path.exists()
        else gates.passed("worktree folder is free", str(path))
    )
    gates.enforce(ctx, checks, f"start {name}")
    repo.git(["fetch", "--quiet", ctx.remote], main)
    base = ctx.remote_base
    if not repo.head(main, base):
        raise Failure(
            f"{base} does not exist after the fetch", f"{cmd('git', '-C', main, 'fetch', ctx.remote)}; check the remote"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    # --no-track: the branch must never push to the base branch; ship sets its own upstream.
    repo.git(["worktree", "add", "--quiet", "--no-track", "-b", name, str(path), base], main)
    ctx.out.say(f"worktree {path} on {name} from {base} ({repo.head(path)[:9]})")
    setup_results = run_setup(ctx, path) if setup else []
    state.keep_plan_branch(main, name, ctx.policy["branches"]["no_plan"])  # a stale record it replaces
    record = state.load_branch(main, name)
    record.update(
        branch=name,
        kind=kind,
        topic=topic,
        plan=None if no_plan else plan_topic,
        worktree=str(path),
        base=base,
        created=state.now(),
        start_sha=repo.head(path),
    )
    agent = gates.agent_name(gates.environment(ctx))
    if agent:  # a later plan approve or ship (new processes, maybe without the variable) still names it
        record["agent"] = agent
    state.save_branch(main, record)
    if not no_plan:
        from . import plan  # ship imports plan; start stays importable on its own

        plan.remember(ctx, name, record)  # the plan keeps the branch after land or gc forgets this record
    body = body_note(ctx, name, record, no_plan)  # --no-plan too: the template, so one ship --dry-run checks it
    ctx.out.say(str(path))
    fill = f" (fill in {body} as you go: notes/ is in the main checkout, shared by every worktree)" if body else ""
    ctx.out.say(f"next: {cmd('cd', path)}, build{fill}, then python tools/retrodev check")
    ctx.out.set(path=str(path), branch=name, topic=topic, setup=setup_results, body=body)
    return 0


def body_note(ctx, branch: str, record: dict, no_plan: bool = False) -> str | None:
    """Write the pull request body (notes/pr/<topic>.md, the file ship reads) from the template and the plan, so the
    first ship --dry-run finds a body to check instead of writing one and stopping; an existing one is kept."""
    from . import ship  # ship imports gates and plan; start stays importable on its own

    written = ship.write_body(ctx, branch, record)
    if written:
        several = ship.plan.shared(ctx, branch, record)
        mine = several and ship.plan.branch_section(ctx, branch, record)
        copied = (
            "the template; no plan, so every section is yours, its Why first"
            if no_plan
            else "What changed from the plan, Why from its section for this branch; it covers several branches, so "
            "Not done and the title are yours to write"
            if mine
            else "What changed from the plan; it covers several branches, so Why, Not done and the title are yours "
            "to write"
            if several
            else "Why, What changed and Not done from the plan"
        )
        ctx.out.say(
            f"wrote {written}: the pull request body ({copied}); fill in the "
            "rest while you build, ship refuses it until every section says something"
            + gates.agent_hint(written.read_text(encoding="utf-8"), gates.environment(ctx), record)
        )
    return str(written or ship.default_body(ctx, branch, record))
