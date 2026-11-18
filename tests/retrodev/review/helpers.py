"""Shared pieces for the review engine's tests: temp git repositories, a crafted state.db, a fake Hermes."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from retrodev.review.runner import Completed  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GIT = [
    "git",
    "-c",
    "user.name=u",
    "-c",
    "user.email=u@example.invalid",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "init.defaultBranch=dev",
    "-c",
    "core.hooksPath=/dev/null",
]


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def git(repo: Path, *args: str) -> str:
    return subprocess.run([*GIT, "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def write(repo: Path, files: dict) -> None:
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def commit(repo: Path, message: str, files: dict) -> str:
    write(repo, files)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD").strip()


def make_repo(base: Path) -> dict:
    """A repo with dev (origin/dev points at it) and a PR branch of three commits touching generated files too."""
    repo = base / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    dev = commit(repo, "Start", {"README.md": "hello\n", "backend/a.py": "A = 1\n", "desktop/plugin.js": "gen0\n"})
    git(repo, "update-ref", "refs/remotes/origin/dev", dev)
    git(repo, "checkout", "-q", "-b", "feat/x")
    c1 = commit(
        repo,
        "Add b",
        {
            "backend/b.py": "B = 2\n",
            "desktop/plugin.js": "gen1\n",
            "tools/npm/package-lock.json": "{}\n",
            "tests/repo/registration.json": "[]\n",
        },
    )
    c2 = commit(repo, "Format", {"backend/a.py": "A = 1  \n"})
    c3 = commit(repo, "Use b", {"backend/c.py": "from .b import B\n", "page/app/rpc-names.js": "x\n"})
    return {"repo": repo, "dev": dev, "commits": [c1, c2, c3]}


def make_db(path: Path, sessions: dict) -> Path:
    """A state.db whose messages table holds ``sessions`` = {session id: [(tool name, args dict), ...]}."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    conn = sqlite3.connect(path)
    # A throwaway file: no fsync and no journal file (a synced commit cost ~30 ms, a land test's whole setup).
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA journal_mode = MEMORY")
    conn.execute(
        "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, role TEXT NOT NULL,"
        " content TEXT, tool_calls TEXT, tool_name TEXT, timestamp REAL NOT NULL DEFAULT 0)"
    )
    for sid, calls in sessions.items():
        conn.execute("INSERT INTO messages (session_id, role, content) VALUES (?, 'user', 'brief')", (sid,))
        for n, (name, args) in enumerate(calls):
            raw = [{"id": f"c{n}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]
            conn.execute(
                "INSERT INTO messages (session_id, role, tool_calls) VALUES (?, 'assistant', ?)", (sid, json.dumps(raw))
            )
            conn.execute("INSERT INTO messages (session_id, role, tool_name) VALUES (?, 'tool', ?)", (sid, name))
    conn.commit()
    conn.close()
    return path


class FakeHermes:
    """A process runner that answers each call with the next canned output and remembers the commands."""

    def __init__(self, *outputs, returncode=0, timed_out=False, on_call=None):
        self.outputs = list(outputs)
        self.calls = []
        self.returncode, self.timed_out, self.on_call = returncode, timed_out, on_call

    def __call__(self, cmd, cwd, timeout):
        self.calls.append({"cmd": cmd, "cwd": Path(cwd), "timeout": timeout})
        if self.on_call:
            self.on_call(cmd, Path(cwd))
        out = self.outputs.pop(0) if self.outputs else ""
        return Completed(self.returncode, out, 0.01, self.timed_out)
