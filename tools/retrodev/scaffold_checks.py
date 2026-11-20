"""The checks `new` runs right after writing (scaffold.py's apply): without the placeholder gate, and a failure only in
files new did not write said as the tree's own instead of new's.
"""

from __future__ import annotations

import re

from . import checks, repo, state
from .output import Failure

# The page kinds touch no Python the unit tests import (page/, tests/page/registry.test.mjs, the generated bundle):
# their own checks are these, and `check` runs unit before ship. The backend kinds keep unit.
PAGE_CHECKS = ("lint", "bundle", "page")
SCAFFOLD_CHECK = "RETRODEV_SCAFFOLD_CHECK"  # tests/repo/test_placeholders.py skips its gate while it is set


FILE_NAMED = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)+[\w.-]+\.\w+)")  # a repository path a check's failure names


def blame(ctx, rows: list[dict], written: set[str]) -> tuple[list[str], list[str]]:
    """(the failed checks whose failure may be new's, the files the others name, none of which new wrote). A failure
    that names no file of the tree counts as new's."""
    mine, theirs = [], []
    for row in rows:
        if row.get("state") != "FAILED":
            continue
        lines = [*str(row.get("detail", "")).splitlines(), *row.get("more", [])]
        said = "\n".join(line for line in lines if "FIX:" not in line)
        files = [f for f in dict.fromkeys(FILE_NAMED.findall(said)) if (ctx.top / f).is_file()]
        if not files or any(f in written for f in files):
            mine.append(row["name"])
        else:
            theirs += [f for f in files if f not in theirs]
    return mine, theirs


def validate(ctx, names: list[str], written: set[str] | None = None) -> None:
    """The checks right after writing the stubs: without the placeholder gate (the stubs are not filled in yet), so
    their results are not kept as passes (the branch's own record is put back: `check` runs the gate before ship).
    A failure only in files new did not write is the tree's own: said as such, and new's scaffold stands."""
    branch = repo.branch(ctx.top)
    kept = state.load_branch(ctx.top, branch)
    try:  # the gate's switch goes only to the checks' processes: os.environ is shared by every thread
        checks.run(ctx, names, env={SCAFFOLD_CHECK: "1"})
    except Failure:
        mine, theirs = blame(ctx, ctx.out.data.get("checks") or [], written or set())
        for name in theirs:
            ctx.out.say(f"pre-existing on this tree (not from new): {name}")
        ctx.out.set(pre_existing=theirs)
        if mine or not theirs:
            raise
        ctx.out.say(
            "new's own files pass; the scaffold stays. Fix the files above in a commit of their own (python "
            "tools/check.py fix for formatting), then python tools/retrodev check"
        )
    finally:
        state.save_branch(ctx.top, kept)
