"""Bring the base branch's new commits into this branch: a merge (never a rebase, never a rewrite of history).

    sync

Conflicts only in generated files (policy.toml [generated]: the page bundle, the frame script, the page's RPC
names, the registration snapshot) are resolved here: the base branch's side is taken, the files are rebuilt from
the merged sources and the merge is finished. Any other conflict stops with the list of source files and leaves
the merge open: resolve those (never the generated ones), git add them and run sync again, which rebuilds the
generated files and finishes the merge itself (no git commit by hand). After a clean merge the generated files are
rebuilt anyway, and committed if they changed, so they always match the merged sources.
"""

from __future__ import annotations

import shlex

from . import gates, repo
from .output import Failure

REGENERATED = "Regenerate generated files after merging dev"


def regenerate(ctx) -> list[str]:
    """Rebuild the generated files; returns the problems (empty when every generator ran)."""
    problems = []
    for words in ctx.policy["generated"]["regenerate"]:
        command = ctx.command(words)
        code, out, err = repo.run(command, ctx.top, timeout=300)
        if code:
            tail = (out + err).strip().splitlines()[-3:]
            problems.append(f"{shlex.join(words)} exited {code}: " + " / ".join(tail))
        else:
            ctx.out.say(f"  rebuilt: {shlex.join(words)}")
    return problems


def generated_changes(ctx) -> list[str]:
    files = ctx.policy["generated"]["files"]
    out = repo.git(["--no-optional-locks", "status", "--porcelain", "--", *files], ctx.top)
    return [line[3:] for line in out.splitlines() if line.strip()]


RESUME = (
    "resolve each listed source file (keep both changes; leave the generated ones, retrodev rebuilds them), "
    "git add those files, then python tools/retrodev sync again: it rebuilds the generated files and finishes the "
    "merge, making the merge commit itself (git merge --abort undoes the merge)"
)


def merging(ctx) -> bool:
    return repo.run(["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"], ctx.top)[0] == 0


def unresolved(ctx) -> list[str]:
    return repo.git(["diff", "--name-only", "--diff-filter=U"], ctx.top).split()


def finish(ctx, conflicts: list[str], resumed: bool = False) -> int:
    """Take the base's side of the conflicted generated files, rebuild every generated file, commit the merge."""
    base = ctx.remote_base
    if conflicts:
        repo.git(["checkout", "--theirs", "--", *conflicts], ctx.top)
    problems = regenerate(ctx)
    if problems:
        raise Failure(
            "could not rebuild the generated files: " + "; ".join(problems),
            "fix what the generator says, then python tools/retrodev sync again (it finishes the merge)",
        )
    repo.git(["add", "--", *conflicts, *generated_changes(ctx)], ctx.top)
    repo.git(["commit", "--no-edit", "--quiet"], ctx.top)
    done = "finished the merge" if resumed else f"merged {base}"
    ctx.out.say(f"{done}; rebuilt the generated files" + (f" ({', '.join(conflicts)} conflicted)" if conflicts else ""))
    ctx.out.set(merged=True, resolved=conflicts, resumed=resumed, head=repo.head(ctx.top))
    return _next(ctx)


def resume(ctx) -> int:
    """A merge left open by a source conflict: once the sources are resolved and added, finish it."""
    generated = set(ctx.policy["generated"]["files"])
    left = unresolved(ctx)
    other = [name for name in left if name not in generated]
    ctx.out.set(conflicts=left, other=other)
    if other:
        raise Failure(f"the merge is still open; still unresolved: {', '.join(other)}", RESUME)
    ctx.out.say("the merge is open and its sources are resolved: rebuilding the generated files")
    return finish(ctx, left, resumed=True)


def run(ctx) -> int:
    branch = repo.branch(ctx.top)
    if merging(ctx):
        gates.enforce(ctx, [gates.on_work_branch(ctx, branch)], "sync")
        return resume(ctx)
    gates.enforce(ctx, [gates.on_work_branch(ctx, branch), gates.committed(ctx)], "sync")
    repo.git(["fetch", "--quiet", ctx.remote], ctx.top)
    base = ctx.remote_base
    before = repo.head(ctx.top)
    merge_code, merge_out, merge_err = repo.run(["git", "merge", "--no-edit", base], ctx.top)
    generated = set(ctx.policy["generated"]["files"])
    if merge_code:
        conflicts = unresolved(ctx)
        if not conflicts:
            raise Failure(
                f"git merge {base} failed: {(merge_err or merge_out).strip()}",
                "git merge --abort, then read git's message and run git merge yourself",
            )
        other = [name for name in conflicts if name not in generated]
        ctx.out.set(conflicts=conflicts, other=other)
        if other:
            raise Failure(
                f"merging {base} conflicts in files only a person can merge: {', '.join(other)}"
                + (
                    f" (and generated ones retrodev rebuilds: {', '.join(sorted(set(conflicts) - set(other)))})"
                    if len(other) < len(conflicts)
                    else ""
                ),
                RESUME,
            )
        ctx.out.say(f"conflicts only in generated files ({', '.join(conflicts)}): taking {base}'s side, rebuilding")
        return finish(ctx, conflicts)
    after = repo.head(ctx.top)
    if after == before:
        ctx.out.say(f"already up to date with {base}")
        ctx.out.set(merged=False, head=after)
        return 0
    ctx.out.say(f"merged {base} ({(merge_out.strip().splitlines() or [''])[0]})")
    problems = regenerate(ctx)
    if problems:
        raise Failure(
            "merged, but could not rebuild the generated files: " + "; ".join(problems),
            "fix what the generator says, run it again, then commit the generated files",
        )
    changed = generated_changes(ctx)
    if changed:
        repo.git(["add", "--", *changed], ctx.top)
        repo.git(["commit", "--quiet", "-m", REGENERATED], ctx.top)
        ctx.out.say(f"committed rebuilt generated files: {', '.join(changed)}")
    ctx.out.set(merged=True, regenerated=changed, head=repo.head(ctx.top))
    return _next(ctx)


def _next(ctx) -> int:
    ctx.out.say("next: python tools/retrodev check, then ship again")
    return 0
