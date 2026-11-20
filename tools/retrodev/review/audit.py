"""Check that a reviewer stayed read-only.

Hermes runs an agent's tools in its gateway, so no OS sandbox around the CLI holds; read-only is enforced by what
the reviewer is given (only the ``file`` toolset) and by checking what it did:

1. Its session's tool calls, read from the reviewer profile's state.db (opened read-only): only read_file and
   search_files, and only on paths inside the round folder. Anything else is a violation.
2. Snapshots before and after of what else it could reach: the pull request's own worktree (``git status
   --porcelain`` and HEAD), the pull request's branch on origin (``git ls-remote origin refs/heads/<branch>``) and a
   digest of the round's own src/ export. Other worktrees are left out: agents at work there change them.

A violation voids the round.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
from collections.abc import Callable
from pathlib import Path

ALLOWED = ("read_file", "search_files")
PATH_KEYS = ("path", "file_path", "filepath", "dir", "directory", "cwd", "root")


class AuditError(RuntimeError):
    """The session cannot be audited (no state.db, or a schema this code does not know)."""


def hermes_root(env=None) -> Path:
    """The default Hermes home: $HERMES_HOME (or the root above it when it names a profile), else ~/.hermes."""
    env = os.environ if env is None else env
    value = env.get("HERMES_HOME")
    if not value:
        return Path.home() / ".hermes"
    home = Path(value).expanduser()
    return home.parent.parent if home.parent.name == "profiles" else home


def state_db(profile: str, env=None) -> Path:
    root = hermes_root(env)
    return root / "state.db" if profile in ("default", "", None) else root / "profiles" / profile / "state.db"


def tool_calls(db: Path, session_ids: list[str]) -> list[dict]:
    """Every tool call the sessions made, in order: [{session, name, args, raw}]."""
    if not Path(db).is_file():
        raise AuditError(f"no session database at {db}")
    conn = sqlite3.connect(f"{Path(db).resolve().as_uri()}?mode=ro", uri=True)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
        if not {"session_id", "tool_calls"} <= columns:
            raise AuditError(f"{db}: table messages lacks session_id or tool_calls (columns: {sorted(columns)})")
        calls = []
        for sid in session_ids:
            rows = conn.execute(
                "SELECT tool_calls FROM messages WHERE session_id = ? AND tool_calls IS NOT NULL ORDER BY id",
                (sid,),
            ).fetchall()
            for (raw,) in rows:
                calls += [dict(call, session=sid) for call in _decode(raw)]
        return calls
    except sqlite3.DatabaseError as e:
        raise AuditError(f"{db}: {e}")
    finally:
        conn.close()


def sessions_exist(db: Path, session_ids: list[str]) -> list[str]:
    """The ids that have at least one message (an id with none was never recorded: the audit cannot vouch)."""
    conn = sqlite3.connect(f"{Path(db).resolve().as_uri()}?mode=ro", uri=True)
    try:
        return [
            sid
            for sid in session_ids
            if conn.execute("SELECT 1 FROM messages WHERE session_id = ? LIMIT 1", (sid,)).fetchone()
        ]
    finally:
        conn.close()


def _decode(raw: str) -> list[dict]:
    try:
        items = json.loads(raw)
    except ValueError:
        return [{"name": "?", "args": {}, "raw": raw[:300]}]
    out = []
    for item in items if isinstance(items, list) else [items]:
        fn = item.get("function", item) if isinstance(item, dict) else {}
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args) if args.strip() else {}
            except ValueError:
                args = {"_unparsed": args}
        out.append({"name": fn.get("name", "?"), "args": args if isinstance(args, dict) else {"_value": args}})
    return out


def inside(path: str, folder: Path) -> bool:
    """Is ``path`` (absolute, ~, or relative to ``folder``, the reviewer's working folder) inside ``folder``?"""
    p = Path(os.path.expanduser(path))
    if not p.is_absolute():
        p = folder / p
    real, base = os.path.realpath(p), os.path.realpath(folder)
    return real == base or real.startswith(base.rstrip(os.sep) + os.sep)


def check_calls(calls: list[dict], round_dir: Path) -> list[str]:
    """The violations among ``calls``: a tool other than read_file/search_files, or a path outside ``round_dir``."""
    violations = []
    for n, call in enumerate(calls):
        name, args = call.get("name"), call.get("args") or {}
        if name not in ALLOWED:
            violations.append(f"call {n}: tool {name!r} is not allowed ({_short(args)})")
            continue
        for key in PATH_KEYS:
            value = args.get(key)
            if value is None:
                continue
            if not isinstance(value, str) or not inside(value, round_dir):
                violations.append(f"call {n}: {name} {key}={value!r} is outside {round_dir}")
        if "_unparsed" in args or "_value" in args:
            violations.append(f"call {n}: {name} arguments could not be read ({_short(args)})")
    return violations


def _short(args) -> str:
    return json.dumps(args, ensure_ascii=False)[:200]


# Snapshots


def tree_digest(folder: Path) -> str:
    """A digest of every file's path, mode and bytes (symlinks by target) under ``folder``."""
    h = hashlib.sha256()
    folder = Path(folder)
    if not folder.exists():
        return "missing"
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames.sort()
        rel_dir = os.path.relpath(dirpath, folder)
        h.update(f"d {rel_dir}\0".encode())
        for name in sorted(filenames):
            path = Path(dirpath) / name
            rel = os.path.join(rel_dir, name)
            if path.is_symlink():
                h.update(f"l {rel} {os.readlink(path)}\0".encode())
                continue
            st = path.stat()
            h.update(f"f {rel} {st.st_mode & 0o777}\0".encode())
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
    return h.hexdigest()


def _git(cwd, *args) -> str:
    proc = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, encoding="utf-8", errors="replace")
    return proc.stdout if proc.returncode == 0 else f"(git {' '.join(args)} failed: {proc.stderr.strip()})"


def branch_of(worktree: Path) -> str | None:
    out = _git(worktree, "symbolic-ref", "--short", "-q", "HEAD").strip()
    return None if not out or out.startswith("(git") else out


def ls_remote_branch(repo: Path, branch: str | None, remote: str = "origin") -> str:
    """The remote's own ref for ``branch`` (``git ls-remote <remote> refs/heads/<branch>``)."""
    if not branch:
        return "(no branch)"
    return _git(repo, "ls-remote", remote, f"refs/heads/{branch}").strip()


def snapshot(
    worktree: Path,
    src: Path,
    branch: str | None = None,
    ls_remote: Callable[[Path, str | None], str] | None = None,
) -> dict:
    """What a file-only reviewer could have changed besides its audited tool calls: the PR's own worktree (files
    and HEAD), the PR's branch on the remote, and the round's src/ export.

    Other worktrees are not watched: agents working there in parallel change them, which voided clean rounds; the
    tool-call audit is what proves the reviewer wrote nothing anywhere."""
    worktree = Path(worktree)
    branch = branch or branch_of(worktree)
    status = _git(worktree, "status", "--porcelain", "--untracked-files=all")
    return {
        "worktree": str(worktree),
        "head": _git(worktree, "rev-parse", "HEAD").strip(),
        "status": status,
        "changed_files": _changed_digest(worktree, status),
        "branch": branch,
        "remote": (ls_remote or ls_remote_branch)(worktree, branch),
        "src": tree_digest(src),
    }


def _changed_digest(worktree: Path, status: str) -> str:
    """A digest of the files git status lists (a second edit of an already changed file keeps its status line)."""
    h = hashlib.sha256()
    for line in status.splitlines():
        name = line[3:].split(" -> ")[-1].strip('"')
        path = worktree / name
        h.update(f"{name}\0".encode())
        if path.is_file() and not path.is_symlink():
            h.update(path.read_bytes())
    return h.hexdigest()


def compare(before: dict, after: dict) -> list[str]:
    changes = []
    tree = before.get("worktree")
    if before.get("head") != after.get("head"):
        changes.append(f"HEAD of the pull request's worktree {tree} changed")
    if before.get("status") != after.get("status") or before.get("changed_files") != after.get("changed_files"):
        changes.append(f"files of the pull request's worktree {tree} changed")
    if before.get("remote") != after.get("remote"):
        changes.append(f"the branch {before.get('branch')} on origin changed")
    if before.get("src") != after.get("src"):
        changes.append("the round's src/ export changed")
    return changes


def audit(
    *,
    profile: str,
    session_ids: list[str],
    round_dir: Path,
    before: dict,
    after: dict,
    db: Path | None = None,
    env=None,
    unaudited: int = 0,
) -> dict:
    """Audit one round. Returns {ok, violations, calls, db}; any violation voids the round. ``unaudited``: how
    many of the round's reviewer runs printed no session id (their tool calls are unknown, even when a later run
    of the same round succeeded)."""
    violations = compare(before, after)
    if unaudited:
        violations.append(
            f"{unaudited} reviewer run(s) of this round printed no session id, so their tool calls cannot be audited"
        )
    calls: list[dict] = []
    db = Path(db) if db else state_db(profile, env)
    if not session_ids and not unaudited:
        violations.append("the reviewer printed no session id, so its tool calls cannot be audited")
    else:
        try:
            calls = tool_calls(db, session_ids)
            missing = sorted(set(session_ids) - set(sessions_exist(db, session_ids)))
            if missing:
                violations.append(f"session(s) {', '.join(missing)} not found in {db}")
        except AuditError as e:
            violations.append(f"cannot audit the session: {e}")
        violations += check_calls(calls, Path(round_dir))
    tools: dict[str, int] = {}
    for call in calls:
        tools[call["name"]] = tools.get(call["name"], 0) + 1
    return {
        "ok": not violations,
        "violations": violations,
        "calls": len(calls),
        "tools": tools,
        "db": str(db),
        "watched": {"worktree": before.get("worktree"), "branch": before.get("branch")},
    }
