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


import re

from . import gates, land_carry, repo
from .output import Failure, cmd

REGENERATED = "Regenerate generated files after merging dev"


def regenerate(ctx) -> list[str]:
    """Rebuild the generated files; returns the problems (empty when every generator ran)."""
    problems = []
    for words in ctx.policy["generated"]["regenerate"]:
        command = ctx.command(words)
        code, out, err = repo.run(command, ctx.top, timeout=300)
        if code:
            tail = (out + err).strip().splitlines()[-3:]
            problems.append(f"{ctx.shown(words)} exited {code}: " + " / ".join(tail))
        else:
            ctx.out.say(f"  rebuilt: {ctx.shown(words)}")
    return problems


def generated_changes(ctx) -> list[str]:
    files = ctx.policy["generated"]["files"]
    out = repo.git(["--no-optional-locks", "status", "--porcelain", "--", *files], ctx.top)
    return [line[3:] for line in out.splitlines() if line.strip()]


def older(ctx, path) -> str:
    """Why sync runs from the main checkout: the branch's own tools/retrodev predates the base's (empty when not)."""
    if not repo.head(path, ctx.remote_base):
        return ""
    if not repo.git(["diff", "--name-only", f"HEAD...{ctx.remote_base}", "--", "tools/retrodev"], path, check=False):
        return ""
    return (
        f"; this branch's own tools/retrodev is older than {ctx.remote_base}'s, so the main checkout's runs it, with "
        "sync's conflict hints"
    )


RUNNER = "python tools/retrodev"


def runner(ctx, path) -> str:
    """The retrodev every next step prints for this worktree (takeover, plan approve, status, land): the branch's own
    copy when it is current, else the main checkout's, run inside the worktree until sync brings the branch's copy up
    to date: an older copy lacks newer fixes (sync's conflict hints, plan approve's and status's newer sync step)."""
    if not older(ctx, path):
        return RUNNER
    return cmd("python", ctx.main() / "tools" / "retrodev")


def newer(text: str, run: str) -> str:
    """``text`` with each branch-local retrodev command run by ``run`` (runner's answer) instead."""
    return text.replace(RUNNER + " ", run + " ") if run != RUNNER else text


def sync_command(ctx, path) -> str:
    """The one sync command every next step prints: runner's retrodev."""
    return runner(ctx, path) + " sync"


HUNKS = "edit the hunks; never git checkout --ours/--theirs a whole file: its other hunks were merged and would be lost"


def resume_fix(ctx) -> str:
    return (
        f"resolve each listed source file ({HUNKS}; keep both changes; leave the generated ones, retrodev rebuilds "
        f"them), git add those files, then {sync_command(ctx, ctx.top)} again: it rebuilds the generated files and "
        "finishes the merge, making the merge commit itself (git merge --abort undoes the merge)"
    )


NOT_NAMES = frozenset(
    [
        "def",
        "class",
        "return",
        "import",
        "from",
        "export",
        "const",
        "let",
        "var",
        "function",
        "async",
        "await",
        "if",
        "else",
        "for",
        "while",
        "in",
        "is",
        "not",
        "and",
        "or",
        "with",
        "as",
        "try",
        "except",
        "finally",
        "pass",
        "none",
        "true",
        "false",
        "self",
        "cls",
        "new",
        "this",
        "default",
    ]
)


def conflict_hunks(text: str) -> list[tuple[str, str]]:
    """(this branch's side, the base's side) of each conflict hunk in a file git left markers in (the merge style,
    or diff3/zdiff3 with a '|||||||' common-ancestor part, which belongs to neither side)."""
    hunks, ours, theirs, part = [], [], [], None
    for line in text.splitlines():
        if line.startswith("<<<<<<<"):
            ours, theirs, part = [], [], "ours"
        elif part and line.startswith("|||||||"):
            part = "base"
        elif part and line.startswith("======="):
            part = "theirs"
        elif part and line.startswith(">>>>>>>"):
            hunks.append(("\n".join(ours), "\n".join(theirs)))
            part = None
        elif part == "ours":
            ours.append(line)
        elif part == "theirs":
            theirs.append(line)
    return hunks


def first_name(text: str) -> str | None:
    """The hunk's first identifier that is not a keyword: what git log -S can follow to where the block went."""
    return next((w for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text) if w.lower() not in NOT_NAMES), None)


def moved_hints(ctx, files: list[str]) -> list[str]:
    """For each conflict hunk whose base side is empty (dev removed or moved that block): where to look for it."""
    hints = []
    for name in files:
        path = ctx.top / name
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        for ours, theirs in conflict_hunks(text):
            if theirs.strip() or not ours.strip():
                continue
            found = first_name(ours)
            log = f"git log -p {ctx.remote_base}" + (f" -S{found}" if found else "")  # the whole tree: tests move too
            hints.append(
                f"{name}: {ctx.base} removed this block; if it moved, `{log}` finds where; apply your change there "
                "and drop this side"
            )
    return list(dict.fromkeys(hints))


def with_hints(ctx, files: list[str]) -> str:
    hints = moved_hints(ctx, files)
    return resume_fix(ctx) + ("; " + "; ".join(hints) if hints else "")


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
            f"fix what the generator says, then {sync_command(ctx, ctx.top)} again (it finishes the merge)",
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
        raise Failure(f"the merge is still open; still unresolved: {', '.join(other)}", with_hints(ctx, other))
    ctx.out.say("the merge is open and its sources are resolved: rebuilding the generated files")
    added = new_lines(ctx, generated)
    if added:
        limit = ctx.policy.get("land", {}).get("max_sync_resolution_lines", 20)
        files = ", ".join(sorted(added))
        ctx.out.say(
            f"warning: the resolution adds {sum(added.values())} line(s) neither side had ({files}): new work belongs "
            f"in its own commit after sync (a resolution over {limit} lines needs a full review round at land)"
        )
        ctx.out.set(new_lines=added)
    return finish(ctx, left, resumed=True)


def _side(ctx, rev: str, name: str) -> list[str] | None:
    """The lines of ``name`` at ``rev`` ("" for the index): [] when it is not there, None when it is binary."""
    data = repo.blob(ctx.top, f"{rev}:{name}")
    if data is None:
        return []
    content = repo.text(data)
    return None if content is None else content.splitlines()


def conflicted(ctx) -> list[str] | None:
    """The paths the open merge conflicted on (git merge-tree of HEAD and MERGE_HEAD redoes it without touching the
    index: once they are resolved and added, git keeps no list of them); None when git's answer cannot be read."""
    code, out, _err = repo.run(
        ["git", "merge-tree", "--write-tree", "--name-only", "-z", "HEAD", "MERGE_HEAD"], ctx.top
    )
    parsed = land_carry.merge_tree_output(code, out)
    return None if parsed is None else parsed[1]


def new_lines(ctx, generated: set[str]) -> dict[str, int]:
    """{file: lines} the resolved conflicts hold that neither this branch (HEAD) nor the base (MERGE_HEAD) had: work
    written into the merge instead of a commit of its own. Only files that were in conflict count (git merged the
    rest by itself); blank lines, generated files and binary files (never decoded as text) do not."""
    staged = repo.git(["diff", "--cached", "--name-only", "-z", "HEAD"], ctx.top, check=False).split("\0")
    hit = conflicted(ctx)
    found = {}
    for name in staged:
        if not name or name in generated or (hit is not None and name not in hit):
            continue
        sides = [_side(ctx, rev, name) for rev in ("", "HEAD", "MERGE_HEAD")]
        if any(side is None for side in sides):
            continue  # binary on some side: not lines
        merged, ours, theirs = sides
        known = set(ours or []) | set(theirs or [])
        count = sum(1 for line in merged or [] if line.strip() and line not in known)
        if count:
            found[name] = count
    return found


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
                with_hints(ctx, other),
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
