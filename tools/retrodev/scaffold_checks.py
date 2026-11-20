"""The checks `new` runs right after writing (scaffold.py's apply): without the placeholder gate, and a lint failure
that is not in new's own files said as the tree's own instead of new's.
"""

from __future__ import annotations

import sys

from . import checks, repo, state
from .output import Failure

# The page kinds touch no Python the unit tests import (page/, tests/page/registry.test.mjs, the generated bundle):
# their own checks are these, and `check` runs unit before ship. The backend kinds keep unit.
PAGE_CHECKS = ("lint", "bundle", "page")
SCAFFOLD_CHECK = "RETRODEV_SCAFFOLD_CHECK"  # tests/repo/test_placeholders.py skips its gate while it is set
# Only lint can fail on the tree's own files: a unit or page failure names tests new's code may break, so it is new's.
MAY_PRE_EXIST = "lint"


def relint(ctx, written: set[str]) -> tuple[bool, list[str]]:
    """new's own files linted alone, by `python tools/check.py lint-files` (tools/py/lint_tools.py: the very
    commands and settings of check.py's lint): (passed, what it said). Passed only when every tool those files need
    was there, ran, and found nothing; a missing tool, a crash, or no answer at all is a failure."""
    command = [sys.executable, "tools/check.py", "lint-files", *sorted(written)]
    code, stdout, stderr = repo.run(command, ctx.top, timeout=600)
    said = [line for line in (stdout + stderr).strip().splitlines() if line.strip()]
    return code == 0, said or [f"tools/check.py lint-files exited {code} and said nothing"]


def unproven(ctx, rows: list[dict], names: list[str]) -> list[str]:
    """The asked checks that neither passed nor failed: skipped (a tool is missing, or the tree fails another check
    first) or with no row at all. Such a check proves nothing about new's files, so a pre-existing lint failure
    beside it never makes new's run a pass. Only a check policy.toml lets skip (`may_skip`) is not one."""
    may_skip = set(ctx.policy["checks"].get("may_skip", []))
    states = {row.get("name"): row.get("state") for row in rows}
    return [name for name in names if states.get(name) not in ("ok", "FAILED") and name not in may_skip]


def validate(ctx, names: list[str], written: set[str] | None = None) -> None:
    """The checks right after writing the stubs: without the placeholder gate (the stubs are not filled in yet), so
    their results are not kept as passes (the branch's own record is put back: `check` runs the gate before ship).
    When lint is the only failure, new's own files are linted again, alone: a pass there makes the failure the
    tree's own (said as such, and new's scaffold stands), but only when every other asked check passed (a skipped
    one proves nothing, so new's run still fails)."""
    branch = repo.branch(ctx.top)
    kept = state.load_branch(ctx.top, branch)
    try:  # the gate's switch goes only to the checks' processes: os.environ is shared by every thread
        checks.run(ctx, names, env={SCAFFOLD_CHECK: "1"})
    except Failure:
        rows = ctx.out.data.get("checks") or []
        failed = [row.get("name") for row in rows if row.get("state") == "FAILED"]
        if failed != [MAY_PRE_EXIST]:
            raise
        skipped = unproven(ctx, rows, names)
        if skipped:
            ctx.out.say(
                f"not run, so new's files are not proven: {', '.join(skipped)} (a skipped check proves nothing; "
                "python tools/retrodev doctor names what is missing)"
            )
            ctx.out.set(unproven=skipped)
            raise
        passed, said = relint(ctx, written or set())
        for line in said:
            ctx.out.say(("" if passed else "new's own lint: ") + line)
        if not passed:
            ctx.out.set(own_lint=said)
            raise
        ctx.out.say("pre-existing on this tree (not from new): the lint failure above, in files new did not write")
        ctx.out.set(pre_existing=["lint"])
        ctx.out.say(
            "the scaffold stays. Fix the lint failure above in a commit of its own (python tools/check.py fix for "
            "formatting), then python tools/retrodev check"
        )
    finally:
        state.save_branch(ctx.top, kept)
