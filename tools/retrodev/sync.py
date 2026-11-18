"""Bring the base branch's new commits into this branch: a merge (never a rebase, never a rewrite of history).

    sync

Conflicts only in generated files (policy.toml [generated]: the page bundle, the frame script, the page's RPC
names, the registration snapshot) are resolved here: the base branch's side is taken, the files are rebuilt from
the merged sources and the merge is finished. Any other conflict stops with the list of files and leaves the
merge open for you to resolve. After a clean merge the generated files are rebuilt anyway, and committed if they
changed, so they always match the merged sources.
"""

from __future__ import annotations

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
            problems.append(f"{' '.join(words)} exited {code}: " + " / ".join(tail))
        else:
            ctx.out.say(f"  rebuilt: {' '.join(words)}")
    return problems


def generated_changes(ctx) -> list[str]:
    files = ctx.policy["generated"]["files"]
    out = repo.git(["--no-optional-locks", "status", "--porcelain", "--", *files], ctx.top)
    return [line[3:] for line in out.splitlines() if line.strip()]


def run(ctx) -> int:
    branch = repo.branch(ctx.top)
    gates.enforce(ctx, [gates.on_work_branch(ctx, branch), gates.committed(ctx)], "sync")
    repo.git(["fetch", "--quiet", ctx.remote], ctx.top)
    base = ctx.remote_base
    before = repo.head(ctx.top)
    merge_code, merge_out, merge_err = repo.run(["git", "merge", "--no-edit", base], ctx.top)
    generated = set(ctx.policy["generated"]["files"])
    if merge_code:
        conflicts = repo.git(["diff", "--name-only", "--diff-filter=U"], ctx.top).split()
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
                "edit each file to keep both changes, git add them, git commit --no-edit, then python tools/retrodev "
                "sync again (or git merge --abort to undo)",
            )
        ctx.out.say(f"conflicts only in generated files ({', '.join(conflicts)}): taking {base}'s side, rebuilding")
        repo.git(["checkout", "--theirs", "--", *conflicts], ctx.top)
        problems = regenerate(ctx)
        if problems:
            raise Failure(
                "could not rebuild the generated files: " + "; ".join(problems),
                "fix what the generator says, run it again, git add the files, git commit --no-edit",
            )
        repo.git(["add", "--", *conflicts, *generated_changes(ctx)], ctx.top)
        repo.git(["commit", "--no-edit", "--quiet"], ctx.top)
        ctx.out.say(f"merged {base}; resolved {len(conflicts)} generated file(s) by rebuilding them")
        ctx.out.set(merged=True, resolved=conflicts, head=repo.head(ctx.top))
        return _next(ctx)
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
