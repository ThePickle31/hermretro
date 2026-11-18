"""retrodev's records, kept in <git common dir>/retrodev/ so every worktree shares them and nothing is committed.

    branches/<branch>.json   one per branch: plan, checks and the tree they passed on, the PR and its head
    plans/<topic>.json       one per plan: where it is, and the owner's approval (time and exact words)
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


def drop_branch(cwd: Path | str, branch: str) -> None:
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


def plans(cwd: Path | str) -> list[dict]:
    folder = root(cwd) / "plans"
    found = [_read(path) for path in sorted(folder.glob("*.json"))] if folder.is_dir() else []
    return [record for record in found if record]
