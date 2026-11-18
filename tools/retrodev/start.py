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
from .output import OWNER, Failure


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
            f"ask the owner to switch {main} back to {ctx.base} (git -C {main} switch {ctx.base})",
            OWNER,
        )
    changes = repo.dirty(main)
    if changes:
        return Gate(
            "main checkout clean",
            False,
            f"{main} has {len(changes)} uncommitted change(s); they are the owner's and must not be mixed in",
            f"ask the owner to commit, stash or remove them (git -C {main} status)",
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
        results.append({"command": " ".join(words), "ok": code == 0, "detail": tail[0] if tail else ""})
        ctx.out.say(f"  {'ok' if code == 0 else 'FAILED'}  {' '.join(words)}" + (f"  {tail[0]}" if tail else ""))
        if code:
            ctx.out.say(f"      FIX: cd {path} && {' '.join(command)}  (then python tools/retrodev doctor)")
    return results


def run(ctx, name: str, no_plan: bool = False, setup: bool = True) -> int:
    kinds = ctx.policy["branches"]["kinds"]
    kind, topic = gates.parse_branch(name, kinds)
    checks = []
    if no_plan and kind not in ctx.policy["branches"]["no_plan"]:
        raise Failure(
            f"--no-plan is only for small {' and '.join(ctx.policy['branches']['no_plan'])} changes; a {kind} change "
            "starts from a plan the owner approved",
            f"python tools/retrodev plan new {topic}, then ask the owner",
            code=OWNER,
        )
    checks.append(gates.passed("plan", "--no-plan (small change)") if no_plan else gates.plan_approved(ctx, topic))
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
        raise Failure(f"{base} does not exist after the fetch", f"git -C {main} fetch {ctx.remote}; check the remote")
    path.parent.mkdir(parents=True, exist_ok=True)
    # --no-track: the branch must never push to the base branch; ship sets its own upstream.
    repo.git(["worktree", "add", "--quiet", "--no-track", "-b", name, str(path), base], main)
    ctx.out.say(f"worktree {path} on {name} from {base} ({repo.head(path)[:9]})")
    setup_results = run_setup(ctx, path) if setup else []
    record = state.load_branch(main, name)
    record.update(
        branch=name,
        kind=kind,
        topic=topic,
        plan=None if no_plan else topic,
        worktree=str(path),
        base=base,
        created=state.now(),
        start_sha=repo.head(path),
    )
    state.save_branch(main, record)
    ctx.out.say(str(path))
    ctx.out.say(f"next: cd {path}, build, then python tools/retrodev check")
    ctx.out.set(path=str(path), branch=name, topic=topic, setup=setup_results)
    return 0
