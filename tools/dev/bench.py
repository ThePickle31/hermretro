"""The benchmark: the games in `bench_games/`, each made by its own one-shot chat in the studio profile, and a report
of what each chat cost and where its time went, read from Hermes's own records.

`run` starts every game at once (`hermes -p hermretro chat --query-file <prompt> --oneshot -Q --reasoning high`),
each with its log in a run folder under `notes/bench/`, and waits for them all; `run.json` there records each game's
process, exit and session. `report` reads the studio profile's `state.db` (read-only) and `logs/errors.log`.
Standard library only; development only; Linux and macOS.
"""

from __future__ import annotations

import json
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from collections import Counter
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

GAMES = Path(__file__).resolve().parent / "bench_games"
RUNS = Path(__file__).resolve().parents[2] / "notes" / "bench"
REASONING = "high"
# Where the agent reads GB Studio's or the engine's source instead of a tool or skill telling it.
SOURCE_MARKERS = ("gb-studio", "modretro-chromatic")
SOURCE_READERS = {"terminal", "read_file", "search_files"}
NORMAL_ENDS = {"cli_close", "agent_close"}
DUPLICATE_DROP = "Removed duplicate tool call"
SESSION_LINE = re.compile(r"^session_id: (\S+)\s*$", re.MULTILINE)


class BenchError(Exception):
    """A run or report that cannot go ahead (no games, no run folder, no state.db)."""


def games(names: list[str]) -> list[Path]:
    """The prompts to run: every one, or those whose name contains one of ``names``."""
    prompts = sorted(GAMES.glob("*.txt"))
    chosen = [prompt for prompt in prompts if not names or any(name in prompt.stem for name in names)]
    if not chosen:
        raise BenchError(f"no game matches {', '.join(names)} (games: {', '.join(p.stem for p in prompts)})")
    return chosen


def command(prompt: Path, profile: str) -> list[str]:
    return ["hermes", "-p", profile, "chat", "--query-file", str(prompt), "--oneshot", "-Q", "--reasoning", REASONING]


def write_record(folder: Path, record: dict) -> None:
    temporary = folder / "run.json.tmp"
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(folder / "run.json")


def logged_session(log: Path) -> str | None:
    """The session id a quiet chat prints after its answer (`session_id: ...`), when it got that far."""
    found = SESSION_LINE.findall(log.read_text(encoding="utf-8", errors="replace")) if log.is_file() else []
    return found[-1] if found else None


def run(prompts: list[Path], profile: str, runs: Path, checkout: Path | None) -> Path:
    """Start every prompt's chat at once, wait for them all and return the run folder."""
    folder = runs / time.strftime("%Y%m%d-%H%M%S")
    folder.mkdir(parents=True)
    record = {
        "started": time.time(),
        "profile": profile,
        "checkout": str(checkout) if checkout else None,
        "commit": commit_of(checkout),
        "reasoning": REASONING,
        "games": {},
    }
    children: dict[str, subprocess.Popen] = {}
    # Stopped with SIGTERM too (a background job's stop), the chats go with it.
    stopped = signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))
    try:
        for prompt in prompts:
            log = folder / f"{prompt.stem}.log"
            with log.open("wb") as out:
                child = subprocess.Popen(
                    command(prompt, profile), cwd=folder, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT
                )
            children[prompt.stem] = child
            record["games"][prompt.stem] = {
                "prompt": prompt.read_text(encoding="utf-8"),
                "log": log.name,
                "pid": child.pid,
                "exit": None,
                "ended": None,
                "session": None,
            }
        write_record(folder, record)
        print(f"running {len(children)} games on {checkout or 'an installed copy'}: {folder}", flush=True)
        lock = threading.Lock()

        def finish(name: str, child: subprocess.Popen) -> None:
            child.wait()
            with lock:
                game = record["games"][name]
                game.update(exit=child.returncode, ended=time.time(), session=logged_session(folder / game["log"]))
                write_record(folder, record)
                print(f"{name}: exited {child.returncode}, session {game['session'] or 'not printed'}", flush=True)

        waiters = [threading.Thread(target=finish, args=item, daemon=True) for item in children.items()]
        for waiter in waiters:
            waiter.start()
        for waiter in waiters:
            waiter.join()
    finally:
        for child in children.values():
            if child.poll() is None:
                child.terminate()
        for child in children.values():
            child.wait(30)
        signal.signal(signal.SIGTERM, stopped)
    return folder


def commit_of(checkout: Path | None) -> str | None:
    if checkout is None:
        return None
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=checkout, capture_output=True, text=True)
    return done.stdout.strip() or None


def latest_run(runs: Path) -> Path:
    folders = sorted(folder for folder in runs.glob("*") if (folder / "run.json").is_file()) if runs.is_dir() else []
    if not folders:
        raise BenchError(f"no run in {runs} (python tools/dev bench run)")
    return folders[-1]


def connect(db: Path) -> sqlite3.Connection:
    if not db.is_file():
        raise BenchError(f"no state.db at {db}")
    connection = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def run_sessions(folder: Path, db: sqlite3.Connection) -> dict[str, str | None]:
    """Each game of a run and its session: the one its log printed, else the session that started after the run
    began with exactly its prompt (a chat stopped before printing its id)."""
    if not (folder / "run.json").is_file():
        raise BenchError(f"{folder} is not a run folder (no run.json)")
    record = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    sessions = {}
    for name, game in record["games"].items():
        session = game.get("session") or logged_session(folder / game["log"])
        if not session:
            session = prompt_session(db, game["prompt"], record["started"], set(sessions.values()))
        sessions[name] = session
    return sessions


def prompt_session(db: sqlite3.Connection, prompt: str, since: float, taken: set) -> str | None:
    rows = db.execute(
        "SELECT s.id, m.content FROM sessions s JOIN messages m ON m.id = ("
        " SELECT MIN(id) FROM messages WHERE session_id = s.id AND role = 'user')"
        " WHERE s.started_at >= ? ORDER BY s.started_at",
        (since,),
    )
    for row in rows:
        if row["id"] not in taken and (row["content"] or "").strip() == prompt.strip():
            return row["id"]
    return None


@dataclass
class Report:
    """What one session cost and where its time went."""

    session: str
    wall: float = 0.0
    running: bool = False
    cost: float = 0.0
    model_calls: int = 0
    tool_calls: int = 0
    builds: int = 0
    failed_builds: int = 0
    compactions: int = 0
    duplicate_drops: int = 0
    source_reads: int = 0
    restores: int = 0
    ended: str = ""
    errors: Counter = field(default_factory=Counter)


def calls(tool_calls: str | None) -> list[tuple[str, dict]]:
    """Each call an assistant message made, as (tool, arguments), with a `tool_call` envelope's calls unwrapped."""
    found = []
    for item in json.loads(tool_calls or "[]"):
        function = item.get("function") or {}
        arguments = parsed(function.get("arguments"))
        if function.get("name") == "tool_call" and isinstance(arguments.get("calls"), list):
            found += [(inner.get("name", ""), inner.get("arguments") or {}) for inner in arguments["calls"]]
        else:
            found.append((function.get("name", ""), arguments))
    return found


def parsed(text) -> dict:
    if isinstance(text, dict):
        return text
    try:
        value = json.loads(text or "{}")
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def error_code(tool: str, content: str | None) -> str | None:
    """The error code a tool result reports (else its tool, marked as having none), or None when it succeeded."""
    result = parsed(content)
    if not (result.get("isError") or result.get("error") or result.get("status") == "error"):
        return None
    structured = result.get("structuredContent")
    nested = structured.get("code") if isinstance(structured, dict) else None
    return result.get("code") or nested or f"{tool} (no code)"


def report(db: sqlite3.Connection, session: str, drops: Counter) -> Report:
    found = Report(session=session, duplicate_drops=drops[session])
    row = db.execute("SELECT * FROM sessions WHERE id = ?", (session,)).fetchone()
    if row is None:
        found.ended = "no such session"
        return found
    last = db.execute("SELECT MAX(timestamp) FROM messages WHERE session_id = ?", (session,)).fetchone()[0]
    found.running = row["ended_at"] is None
    found.wall = (row["ended_at"] or last or row["started_at"]) - row["started_at"]
    found.model_calls = row["api_call_count"] or 0
    # Every model call's cost, the compaction summaries' too (the session's own column leaves those out).
    usage = db.execute("SELECT SUM(estimated_cost_usd) FROM session_model_usage WHERE session_id = ?", (session,))
    found.cost = usage.fetchone()[0] or row["estimated_cost_usd"] or 0.0
    # Rows, not the session's counts: those count only what is still active after a compaction.
    for tool, content in db.execute(
        "SELECT tool_name, content FROM messages WHERE session_id = ? AND role = 'tool'", (session,)
    ):
        found.tool_calls += 1
        code = error_code(tool, content)
        if code:
            found.errors[code] += 1
        if tool == "chromatic_rom_build":
            found.builds += 1
            found.failed_builds += bool(code)
    for (tool_calls,) in db.execute(
        "SELECT tool_calls FROM messages WHERE session_id = ? AND role = 'assistant' AND tool_calls IS NOT NULL",
        (session,),
    ):
        for tool, arguments in calls(tool_calls):
            text = json.dumps(arguments)
            found.source_reads += tool in SOURCE_READERS and any(marker in text for marker in SOURCE_MARKERS)
            found.restores += tool == "chromatic_emulator_checkpoint" and arguments.get("action") == "restore"
    found.compactions = db.execute(
        "SELECT COUNT(*) FROM messages WHERE session_id = ? AND role = 'user' AND _compressed_summary = 1", (session,)
    ).fetchone()[0]
    found.ended = ending(db, session, row["end_reason"])
    return found


def ending(db: sqlite3.Connection, session: str, reason: str | None) -> str:
    """`yes` when the chat closed after a final answer, else what happened instead."""
    final = db.execute(
        "SELECT finish_reason FROM messages WHERE session_id = ? AND role = 'assistant' ORDER BY id DESC LIMIT 1",
        (session,),
    ).fetchone()
    answered = final is not None and final["finish_reason"] == "stop"
    if reason in NORMAL_ENDS and answered:
        return "yes"
    if reason is None:
        return "no (still open)"
    return f"no ({reason}{'' if answered else ', no final answer'})"


def duplicate_drops(logs: Path) -> Counter:
    """How many identical tool calls Hermes dropped in each session (`[<session>] ... Removed duplicate tool call`)."""
    drops = Counter()
    for log in sorted(logs.glob("errors.log*")):
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            if DUPLICATE_DROP in line and (match := re.search(r"\[([^\]\s]+)\]", line)):
                drops[match.group(1)] += 1
    return drops


def minutes(seconds: float) -> str:
    return f"{int(seconds // 60)}m{int(seconds % 60):02d}s"


ROWS = (
    ("wall time", lambda r: minutes(r.wall) + (" (running)" if r.running else "")),
    ("cost (estimated)", lambda r: f"${r.cost:.2f}"),
    ("model calls", lambda r: str(r.model_calls)),
    ("tool calls", lambda r: str(r.tool_calls)),
    ("builds", lambda r: f"{r.builds} ({r.failed_builds} failed)" if r.failed_builds else str(r.builds)),
    ("compactions", lambda r: str(r.compactions)),
    ("duplicate drops", lambda r: str(r.duplicate_drops)),
    ("engine source reads", lambda r: str(r.source_reads)),
    ("checkpoint restores", lambda r: str(r.restores)),
    ("tool errors", lambda r: str(sum(r.errors.values()))),
    ("ended normally", lambda r: r.ended),
)


def table(reports: dict[str, Report]) -> str:
    """One column per game, one row per measure, then each game's tool errors by code."""
    names = list(reports)
    cells = [["", *names]] + [[label, *(value(reports[name]) for name in names)] for label, value in ROWS]
    widths = [max(len(row[column]) for row in cells) for column in range(len(cells[0]))]
    lines = ["  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip() for row in cells]
    for name in names:
        found = reports[name]
        lines.append("")
        lines.append(f"{name}: {found.session}")
        lines += [f"  {code} x{count}" for code, count in found.errors.most_common()] or ["  no tool errors"]
    return "\n".join(lines)


def reports(profile_home: Path, folder: Path | None = None, ids: list[str] | None = None) -> dict[str, Report]:
    """The report of each game of the run in ``folder``, or of each session in ``ids``."""
    drops = duplicate_drops(profile_home / "logs")
    with closing(connect(profile_home / "state.db")) as db:
        sessions = {session[:14]: session for session in ids} if ids else run_sessions(folder, db)
        return {
            name: report(db, session, drops) if session else Report(session="none found", ended="no session")
            for name, session in sessions.items()
        }
