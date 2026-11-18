"""check --watch: run the checks, then again on every file change, commit or clean/dirty change (Ctrl+C stops).

Before each run the checkout's policy.toml is read again, so a trigger added while watching adds its check at
once (a pass is recorded only for what the current policy requires). --again forces the first run; later runs
rerun only the checks whose inputs changed.
"""

from __future__ import annotations

import time

from . import checks, config, repo
from .output import Failure


def snapshot(ctx) -> dict[str, object]:
    """(mtime, size) of every file a commit would hold, plus HEAD and whether the tree is clean: what --watch compares.

    A commit touches no file, yet it lets the install checks run (they wait for a clean, committed tree).
    """
    out = repo.git(["ls-files", "-z", "--cached", "--others", "--exclude-standard"], ctx.top)
    found: dict[str, object] = {}
    for name in filter(None, out.split("\0")):
        try:
            info = (ctx.top / name).stat()
        except OSError:
            continue
        found[name] = (info.st_mtime_ns, info.st_size)
    found[":HEAD"] = repo.head(ctx.top)
    found[":clean"] = not repo.dirty(ctx.top)
    return found


def changed_since(before: dict, after: dict) -> list[str]:
    return sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))


def watch(
    ctx,
    names: list[str],
    full: bool = False,
    again: bool = False,
    interval: float = 0.5,
    rounds: int | None = None,
    sleep=time.sleep,
) -> int:
    """Run the checks, then again whenever a file changes or a commit is made (only the affected ones rerun).

    ``again`` ignores earlier passes on the first run only. ``rounds`` stops after that many runs and ``sleep``
    replaces time.sleep: a test drives the loop with them.
    """
    try:
        seen, done = snapshot(ctx), 0
        while True:
            try:
                ctx.policy = config.load_policy(ctx.top)  # the rules as they are now, not as they were at start
                checks.run(ctx, names, again=again and done == 0, full=full)
            except Failure as failure:
                ctx.out.say(failure.message + "\nFIX: " + failure.fix)
            done += 1
            if rounds is not None and done >= rounds:
                return 0
            ctx.out.say("watching for changes (Ctrl+C stops) ...")
            while not (changed := changed_since(seen, snapshot(ctx))):
                sleep(interval)
            sleep(interval)  # let a save that writes several files finish
            seen = snapshot(ctx)
            shown = [{":HEAD": "HEAD (a commit)", ":clean": "clean/dirty"}.get(name, name) for name in changed]
            ctx.out.say(f"changed: {', '.join(shown[:5])}" + (" ..." if len(shown) > 5 else ""))
    except KeyboardInterrupt:
        return 0
