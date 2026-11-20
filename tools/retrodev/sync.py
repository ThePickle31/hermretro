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

import difflib

from . import gates, land_carry, repo, sync_moved
from .sync_rewrite import AMBIGUOUS, new_location, rewritten_from
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
        f"finishes the merge, making the merge commit itself (git merge --abort undoes the merge); if {ctx.base} "
        f"rewrote the code your side changed, take {ctx.base}'s lines in the merge and redo your change on top in "
        "its own commit after sync"
    )


def conflict_hunks(text: str) -> list[tuple[int, int, str, str]]:
    """(first line, last line, this branch's side, the base's side) of each conflict hunk in a file git left markers
    in (the merge style, or diff3/zdiff3 with a '|||||||' common-ancestor part, which belongs to neither side); the
    lines are the markers' own, 1-based."""
    hunks, ours, theirs, part, start = [], [], [], None, 0
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("<<<<<<<"):
            ours, theirs, part, start = [], [], "ours", number
        elif part and line.startswith("|||||||"):
            part = "base"
        elif part and line.startswith("======="):
            part = "theirs"
        elif part and line.startswith(">>>>>>>"):
            hunks.append((start, number, "\n".join(ours), "\n".join(theirs)))
            part = None
        elif part == "ours":
            ours.append(line)
        elif part == "theirs":
            theirs.append(line)
    return hunks


MIN_DISTINCT = 8  # characters: a shorter line (`return 2`, `)`) is in too many files to say where a block went
TRIED_LINES = 5  # git grep runs per hunk at most


def distinctive_lines(ours: str) -> list[str]:
    """The hunk's lines that say where a block went, longest first: each appears once in the hunk and is long
    enough to be found in few files."""
    lines = [line.strip() for line in ours.splitlines()]
    once = [line for line in dict.fromkeys(lines) if lines.count(line) == 1 and len(line) >= MIN_DISTINCT]
    return sorted(once, key=len, reverse=True)


def moved_to(ctx, name: str, ours: str) -> tuple[str | None, str | None]:
    """(the file on the base branch that holds the hunk's most distinctive line, that line) by `git grep -l -F`,
    trying the longest lines first; (None, the longest line) when no other file has any of them. A generated file
    (policy.toml [generated]: the page bundle holds every page source's lines) is never the answer: nobody edits it."""
    lines = distinctive_lines(ours)
    generated = set(ctx.policy["generated"]["files"])
    for line in lines[:TRIED_LINES]:
        code, stdout, _err = repo.run(["git", "grep", "-l", "-F", "-e", line, ctx.remote_base, "--"], ctx.top)
        files = [hit.partition(":")[2] for hit in stdout.splitlines() if hit.strip()] if code == 0 else []
        files = [found for found in files if found and found != name and found not in generated]
        if files:
            return files[0], line
    return None, lines[0] if lines else None


def rewrite_hint(ctx, name: str, first: int, last: int, ours: str, theirs: str) -> str | None:
    """The hint for a hunk where dev rewrote the block HEAD changed (rewritten_from), or None."""
    base, dev = _side(ctx, ":1", name), _side(ctx, "MERGE_HEAD", name)
    if not base or not dev:
        return None
    changed = rewritten_from(ours, theirs, base, dev)
    if not changed:
        return None
    where = new_location(name, changed, dev, base) or (moved_to(ctx, name, "\n".join(changed))[0] or name)
    if where == AMBIGUOUS:
        return (
            f"{name}:{first}-{last}: {ctx.base} rewrote this block (see git diff HEAD...{ctx.remote_base} -- {name}); "
            f"take {ctx.base}'s side, then redo your change where it belongs now in its own commit after sync"
        )
    return (
        f"{name}:{first}-{last}: {ctx.base} rewrote this block; take {ctx.base}'s side, then redo your change in "
        f"{where} in its own commit after sync"
    )


def moved_hints(ctx, files: list[str]) -> list[str]:
    """For each conflict hunk whose base side is empty (dev removed or moved that block): where it went (the
    base's file holding the hunk's most distinctive line) and how to resolve it; for a hunk dev rewrote into a much
    longer block (rewrite_hint): take dev's side and where to redo the change."""
    hints = []
    for name in files:
        path = ctx.top / name
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        parts = sync_moved.base_parts(text)
        for index, (first, last, ours, theirs) in enumerate(conflict_hunks(text)):
            if theirs.strip() and ours.strip():
                rewrite = rewrite_hint(ctx, name, first, last, ours, theirs)
                hints += [rewrite] if rewrite else []
                continue
            if not ours.strip():
                continue
            # the base's version of what dev removed: the branch's own new lines were never on dev
            part = parts[index] if index < len(parts) else ""
            had = sync_moved.base_lines(ctx, name, ours, part, text, first, last)
            # never the branch's own lines: they can be in an unrelated dev file, naming a wrong destination
            where = moved_to(ctx, name, "\n".join(had))[0] if had else None
            line = (distinctive_lines("\n".join(had)) or [None])[0] if had else None
            commit = None
            if line and not where:  # moved and changed: the commit that removed it, and where it added a copy
                where, commit = sync_moved.taken_over(ctx, name, line)
            log = cmd("git", "log", "-p", ctx.remote_base, f"-S{line}") if line else ""  # the whole tree
            if where:
                hints.append(
                    f"{name}:{first}-{last}: {ctx.base} moved this block to {where}"
                    + (f" in {commit}" if commit else " (or deleted it)")
                    + f"; first check whether {ctx.base}'s version there already does what your lines did; if it "
                    "does, add only a test that pins it"
                    + f"; delete the HEAD side of this hunk, git add, sync again, then add your lines in {where} in a "
                    "new commit" + (f" (`{log}` shows the move)" if log else "")
                )
            else:
                hints.append(
                    f"{name}:{first}-{last}: {ctx.base} deleted this block (no other file on {ctx.remote_base} has its "
                    "lines"
                    + (f"; if it moved and changed, `{log}` finds where" if log else "")
                    + "); delete the HEAD side of this hunk, git add, sync again, then redo your change where it "
                    "belongs now in a new commit" + (f" ({ctx.base} removed these lines in {commit})" if commit else "")
                )
    return list(dict.fromkeys(hints))


def conflict_failure(ctx, message: str, files: list[str]) -> Failure:
    """The failure for source conflicts: each hunk's own instruction (moved_hints) on its own line under the message,
    before the general FIX text, so the per-hunk steps are read first and none is buried at the end of a paragraph."""
    hints = moved_hints(ctx, files)
    ctx.out.set(hunks=hints)
    fix = resume_fix(ctx) + ("; first do what each hunk's line above says" if hints else "")
    return Failure("\n".join([message, *hints]), fix)


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
        raise conflict_failure(ctx, f"the merge is still open; still unresolved: {', '.join(other)}", other)
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
        count = unseen_lines(merged or [], ours or [], theirs or [])
        if count:
            found[name] = count
    return found


def unseen_lines(merged: list[str], ours: list[str], theirs: list[str]) -> int:
    """How many non-blank lines of ``merged`` hold a word neither side had there. Compared as each side's words in
    order (lines joined, spaces collapsed), so rewrapping a paragraph that merges a one-line edit from each side adds
    nothing: every word of it lines up with one side or the other."""
    words = [(index, word) for index, line in enumerate(merged) for word in line.split()]
    sequence = [word for _index, word in words]
    seen: set[int] = set()
    for side in (ours, theirs):
        matcher = difflib.SequenceMatcher(None, " ".join(side).split(), sequence, autojunk=False)
        for block in matcher.get_matching_blocks():
            seen.update(range(block.b, block.b + block.size))
    return len({index for at, (index, _word) in enumerate(words) if at not in seen})


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
            raise conflict_failure(
                ctx,
                f"merging {base} conflicts in files only a person can merge: {', '.join(other)}"
                + (
                    f" (and generated ones retrodev rebuilds: {', '.join(sorted(set(conflicts) - set(other)))})"
                    if len(other) < len(conflicts)
                    else ""
                ),
                other,
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
    """status's next step for this branch (a plan still to write or approve comes first); its bare check step
    names the ship after it: `ship` before the branch has a pull request, `ship again` once it has one."""
    from . import state, status  # status imports this module

    branch = repo.branch(ctx.top)
    record = state.load_branch(ctx.top, branch) if state.branch_path(ctx.top, branch).is_file() else {}
    facts = status.branch_facts(ctx, branch, ctx.top, record, with_ci=False)
    line = status.next_step(facts)
    if line.endswith(" check"):
        line += ", then ship again" if facts.get("pr") else ", then ship"
    ctx.out.say(line)
    ctx.out.set(next=line)
    return 0
