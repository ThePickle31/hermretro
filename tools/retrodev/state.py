"""retrodev's records, kept in <git common dir>/retrodev/ so every worktree shares them and nothing is committed.

    branches/<branch>.json   one per branch: plan, checks and the tree they passed on, the PR and its head
    plans/<topic>.json       one per plan: where it is, the owner's approval (time and exact words) and the branches
                             that started under it (kept when land or gc forgets their branch records)
    releases/<version>.json  one per release: the owner's words, its pull request, commit and steps done
    config.toml              personal settings (config.py)

Writes are atomic (a temp file in the same folder, then a rename), so a crash never leaves half a record.
RETRODEV_STATE_DIR moves the whole folder elsewhere (a sandbox, or a trial that must leave the checkout alone).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path

from . import repo
from .output import Failure

NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def root(cwd: Path | str) -> Path:
    override = os.environ.get("RETRODEV_STATE_DIR")
    return Path(override).expanduser().resolve() if override else repo.common_dir(cwd) / "retrodev"


def override_warning() -> str | None:
    """A line naming RETRODEV_STATE_DIR when it is set: a leaked override silently redirects every record."""
    value = os.environ.get("RETRODEV_STATE_DIR")
    if not value:
        return None
    return (
        f"warning: RETRODEV_STATE_DIR={value} moves retrodev's records out of the main checkout's .git/retrodev "
        "(meant for a sandbox or trial; if it leaked into this shell: unset RETRODEV_STATE_DIR)"
    )


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def _read(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise Failure(
            f"the record {path} is not valid JSON (edited by hand, or written by something else)",
            f"remove {path} (retrodev starts that record again), then run the command again",
        )


def _write(path: Path, record: dict) -> dict:
    record["updated"] = now()
    write_atomic(path, json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def check_topic(topic: str) -> str:
    if not NAME.match(topic or ""):
        raise Failure(
            f"'{topic}' is not a usable topic: it names the plan file, the branch and the worktree folder",
            "use lowercase letters, digits and dashes, e.g. retrodev-core",
        )
    return topic


def branch_path(cwd: Path | str, branch: str) -> Path:
    parts = branch.split("/")
    if not all(NAME.match(part) for part in parts):
        raise Failure(f"'{branch}' cannot name a record", "use a branch like feat/<topic>")
    return root(cwd).joinpath("branches", *parts[:-1], parts[-1] + ".json")


def load_branch(cwd: Path | str, branch: str) -> dict:
    return _read(branch_path(cwd, branch)) or {"branch": branch, "checks": {}}


def save_branch(cwd: Path | str, record: dict) -> dict:
    return _write(branch_path(cwd, record["branch"]), record)


def plan_named(record: dict, branch: str, no_plan: list[str] | tuple[str, ...]) -> str | None:
    """The plan a branch record works under (gates.plan_for): the one it names, else (feat, fix: every kind not in
    policy.toml's no_plan) the one its topic names; None when started with --no-plan."""
    kind, _, topic = branch.partition("/")
    named = record.get("plan")
    if named is None and (record.get("kind") or kind) not in no_plan:
        named = record.get("topic") or topic
    return named


def keep_plan_branch(cwd: Path | str, branch: str, no_plan: list[str] | tuple[str, ...]) -> None:
    """Before a branch record is forgotten or replaced: the plan it names keeps the branch in its branches map. A
    record from before plans kept that map is otherwise lost with it, and the plan's next branch would take the
    whole plan's Goal, Not in scope and Title as its own. Its time is kept ('' when it had none: started first)."""
    path = branch_path(cwd, branch)
    try:
        record = _read(path) if path.is_file() else None
    except Failure:  # an unreadable record names nothing; drop_branch still removes it
        record = None
    named = plan_named(record, branch, no_plan) if record else None
    if named and NAME.match(named) and load_plan(cwd, named) is not None:
        remember_plan_branch(cwd, named, branch, record.get("created") or "")


def drop_branch(cwd: Path | str, branch: str, no_plan: list[str] | tuple[str, ...]) -> None:
    """The only way a branch record goes (land and gc): its plan keeps the branch first (keep_plan_branch)."""
    keep_plan_branch(cwd, branch, no_plan)
    branch_path(cwd, branch).unlink(missing_ok=True)


def branches(cwd: Path | str) -> list[dict]:
    folder = root(cwd) / "branches"
    found = [_read(path) for path in sorted(folder.rglob("*.json"))] if folder.is_dir() else []
    return [record for record in found if record]


def plan_path(cwd: Path | str, topic: str) -> Path:
    return root(cwd) / "plans" / (check_topic(topic) + ".json")


def load_plan(cwd: Path | str, topic: str) -> dict | None:
    return _read(plan_path(cwd, topic))


def save_plan(cwd: Path | str, record: dict) -> dict:
    return _write(plan_path(cwd, record["topic"]), record)


def remember_plan_branch(cwd: Path | str, topic: str, branch: str, at: str) -> dict:
    """Note in the plan's record that a branch started under it (the earliest time seen wins). Nothing removes it:
    a plan stays shared after its first branch lands and land or gc forgets that branch's record."""
    record = load_plan(cwd, topic) or {"topic": topic, "created": now()}
    started = record.setdefault("branches", {})
    if branch in started and started[branch] <= at:
        return record
    started[branch] = at
    return save_plan(cwd, record)


def forget_plan_branch(cwd: Path | str, topic: str, branch: str) -> None:
    """Only for plan link moving a branch to another plan: the old plan no longer counts it."""
    record = load_plan(cwd, topic)
    if record and branch in (record.get("branches") or {}):
        del record["branches"][branch]
        save_plan(cwd, record)


def release_path(cwd: Path | str, version: str) -> Path:
    if not NAME.match(version or ""):
        raise Failure(f"'{version}' is not a version", "use the form 0.0.N (or 0.0.N-rc.M)")
    return root(cwd) / "releases" / (version + ".json")


def load_release(cwd: Path | str, version: str) -> dict | None:
    return _read(release_path(cwd, version))


def save_release(cwd: Path | str, record: dict) -> dict:
    return _write(release_path(cwd, record["version"]), record)


def plans(cwd: Path | str) -> list[dict]:
    folder = root(cwd) / "plans"
    found = [_read(path) for path in sorted(folder.glob("*.json"))] if folder.is_dir() else []
    return [record for record in found if record]
