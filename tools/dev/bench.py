"""The benchmark: the games in `bench_games/`, each made by its own one-shot chat in the studio profile, and a report
of what each chat cost and where its time went, read from Hermes's own records.

`run` starts every game at once (`hermes -p hermretro chat --query-file <prompt> --oneshot -Q --reasoning high`),
each with its log in a run folder under `notes/bench/`, and waits for them all; `run.json` there records each game's
process, start, exit and session, and the profile home the chats ran in. The running gateway serves those chats with
the plugin code it loaded, so `run` first makes sure that is the code the profile loads now (`current_gateway`).
`report` reads a copy of the studio profile's `state.db` (`snapshot`: nothing in the profile is opened for writing)
and its `logs/errors.log`; `compare` (bench_compare.py) sets two runs' reports side by side.
Standard library only; development only; Linux and macOS.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import local_hermes as hermes

GAMES = Path(__file__).resolve().parent / "bench_games"
RUNS = Path(__file__).resolve().parents[2] / "notes" / "bench"
REASONING = "high"
# Where the agent reads GB Studio's or the engine's source instead of a tool or skill telling it: with a terminal
# command, or with the file tools.
# Before the move to engine/src/ (#230), the engine was under engine/modretro-chromatic/: recorded sessions name it.
SOURCE_MARKERS = ("gb-studio", "modretro-chromatic", "engine/src/", "engine/dist/", "engine/scripts/", ".cache/engine-")
SOURCE_READERS = {"read_file", "search_files"}
NORMAL_ENDS = {"cli_close", "agent_close"}
DUPLICATE_DROP = "Removed duplicate tool call"
SESSION_LINE = re.compile(r"^session_id: (\S+)\s*$", re.MULTILINE)
# How Hermes's logs start each line (hermes_logging.py: logging's `asctime`, local time).
LOG_TIME = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ ", re.MULTILINE)
SNAPSHOT_TRIES = 5
# Set, `hermes chat` talks to the gateway it names instead of this machine's (Hermes's hermes_cli/gateway_client.py).
REMOTE_GATEWAY = "HERMES_TUI_GATEWAY_URL"


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


def current_gateway(root: Path, profile: str, checkout: Path, reload: Callable[[], int]) -> None:
    """Make sure the chats run ``checkout``'s hermretro code as it is now: ``profile`` loads it, and the local gateway
    that serves the chats has it loaded (when it does not, ``reload`` it, non-zero when that failed, and ask again);
    refuse when either cannot be made so."""
    if os.environ.get(REMOTE_GATEWAY, "").strip():
        raise BenchError(f"{REMOTE_GATEWAY} sends the chats to another gateway than the one checked here: unset it")
    link = hermes.plugin_links(root).get(profile)
    loads = link.resolve() if link else None
    if loads != checkout.resolve():
        raise BenchError(
            f"the {profile} profile loads {loads or 'no checkout'}, not {checkout.resolve()}: "
            "python tools/dev live, then run again"
        )
    try:
        stale = hermes.stale_plugin(profile, checkout)
        if stale is None:
            return
        print(f"the gateway runs older hermretro code ({stale}): reloading", flush=True)
        if reload():
            raise BenchError("the reload failed, so the games would run on older code: restart Hermes, then run again")
        stale = hermes.stale_plugin(profile, checkout)
    except hermes.GatewayError as error:
        raise BenchError(f"{error}: the games need a running gateway (hermes -p {profile} gateway ensure)") from error
    if stale is not None:
        raise BenchError(f"after a reload the gateway still runs older hermretro code ({stale}): restart Hermes")


def run(prompts: list[Path], profile: str, home: Path, runs: Path, checkout: Path | None) -> Path:
    """Start every prompt's chat at once in ``profile`` (whose home is ``home``), wait for them all and return the
    run folder."""
    folder = runs / time.strftime("%Y%m%d-%H%M%S")
    folder.mkdir(parents=True)
    record = {
        "started": time.time(),
        "profile": profile,
        "home": str(home.resolve()),
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
                "started": time.time(),
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


@contextmanager
def snapshot(db: Path) -> Iterator[sqlite3.Connection]:
    """A connection to a copy of ``db`` and its write-ahead log, taken while neither changed, in a temporary folder.
    SQLite writes beside any database it opens in WAL mode, even read-only: the `-shm` index, and a `-wal` and `-shm`
    when there are none; `immutable` would miss what the log holds."""
    if not db.is_file():
        raise BenchError(f"no state.db at {db}")
    sources = (db, db.with_name(f"{db.name}-wal"))
    with tempfile.TemporaryDirectory() as temp:
        copies = [Path(temp) / source.name for source in sources]
        for _ in range(SNAPSHOT_TRIES):
            before = [stamp(source) for source in sources]
            for source, copy in zip(sources, copies, strict=True):
                if source.is_file():
                    shutil.copyfile(source, copy)
                else:
                    copy.unlink(missing_ok=True)
            if [stamp(source) for source in sources] == before:
                break
        else:
            raise BenchError(f"{db} changed each time it was copied: run again when Hermes is quieter")
        with closing(sqlite3.connect(copies[0])) as connection:
            connection.row_factory = sqlite3.Row
            yield connection


def stamp(path: Path) -> tuple[int, int] | None:
    """A file's size and change time, None when there is none."""
    try:
        found = path.stat()
    except FileNotFoundError:
        return None
    return found.st_size, found.st_mtime_ns


class Game(NamedTuple):
    """A game of a run: its session (None when none was found) and when its chat exited (None if not recorded)."""

    session: str | None
    exited: float | None = None


def run_record(folder: Path) -> dict:
    """A run folder's `run.json`."""
    if not (folder / "run.json").is_file():
        raise BenchError(f"{folder} is not a run folder (no run.json)")
    return json.loads((folder / "run.json").read_text(encoding="utf-8"))


def run_sessions(folder: Path, db: sqlite3.Connection) -> dict[str, Game]:
    """Each game of a run and its session: the one its log printed, else the one session with exactly its prompt
    that started while its chat ran (a chat stopped before printing its id)."""
    record = run_record(folder)
    found = {}
    for name, game in record["games"].items():
        session = game.get("session") or logged_session(folder / game["log"])
        if not session:
            started = game.get("started") or record["started"]
            taken = {other.session for other in found.values()}
            session = prompt_session(db, game["prompt"], started, game.get("ended"), taken)
        found[name] = Game(session, game.get("ended"))
    return found


def prompt_session(db: sqlite3.Connection, prompt: str, since: float, until: float | None, taken: set) -> str | None:
    """The session with ``prompt`` as its first message that started between ``since`` and ``until`` (no end
    when the chat's exit was not recorded); None when there is none or more than one."""
    window = "s.started_at >= ?" + (" AND s.started_at <= ?" if until is not None else "")
    rows = db.execute(
        "SELECT s.id, m.content FROM sessions s JOIN messages m ON m.id = ("
        " SELECT MIN(id) FROM messages WHERE session_id = s.id AND role = 'user')"
        f" WHERE {window}",
        (since,) if until is None else (since, until),
    )
    matches = [row["id"] for row in rows if row["id"] not in taken and (row["content"] or "").strip() == prompt.strip()]
    return matches[0] if len(matches) == 1 else None


@dataclass
class Report:
    """What one session cost and where its time went."""

    session: str
    wall: float = 0.0
    running: bool = False
    cost: float = 0.0
    model_calls: int = 0
    auxiliary_calls: int = 0
    tool_calls: int = 0
    steps: int = 0
    builds: int = 0
    failed_builds: int = 0
    compactions: int = 0
    duplicate_drops: int | None = 0  # None: the retained logs begin after the session started
    source_commands: int = 0
    source_reads: int = 0
    restores: int = 0
    ended: str = ""
    errors: Counter = field(default_factory=Counter)


def calls(tool_calls: str | None) -> list[tuple[str, dict]]:
    """Each call an assistant message made, as (tool, arguments), with a `tool_call` envelope's calls unwrapped.
    Arguments may be stored as objects or as JSON text, at either level; anything else counts as no arguments."""
    found = []
    for item in decoded(tool_calls, list):
        function = item.get("function") if isinstance(item, dict) else None
        function = function if isinstance(function, dict) else {}
        arguments = decoded(function.get("arguments"), dict)
        inner = decoded(arguments.get("calls"), list)
        if function.get("name") == "tool_call" and inner:
            found += [
                (str(call.get("name") or ""), decoded(call.get("arguments"), dict))
                for call in inner
                if isinstance(call, dict)
            ]
        else:
            found.append((str(function.get("name") or ""), arguments))
    return found


def decoded(value, kind: type):
    """``value`` as ``kind`` (dict or list): itself, or the JSON text it holds; an empty one otherwise."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return kind()
    return value if isinstance(value, kind) else kind()


def error_code(tool: str, content: str | None) -> str | None:
    """The error code a tool result reports (else its tool, marked as having none), or None when it succeeded.
    A compiler failure reports only `success: false` in its structured content."""
    result = decoded(content, dict)
    structured = decoded(result.get("structuredContent"), dict)
    failed = result.get("isError") or result.get("error") or result.get("status") == "error"
    if not (failed or result.get("success") is False or structured.get("success") is False):
        return None
    return result.get("code") or structured.get("code") or f"{tool} (no code)"


def report(db: sqlite3.Connection, session: str, drops: Drops, exited: float | None = None) -> Report:
    """One session's report; ``exited`` is when its chat exited, the end of a session a stopped chat left open."""
    found = Report(session=session)
    row = db.execute("SELECT * FROM sessions WHERE id = ?", (session,)).fetchone()
    if row is None:
        found.ended = "no such session"
        return found
    found.duplicate_drops = drops.of(session, row["started_at"])
    last = db.execute("SELECT MAX(timestamp) FROM messages WHERE session_id = ?", (session,)).fetchone()[0]
    found.running = row["ended_at"] is None and exited is None
    found.wall = (row["ended_at"] or exited or last or row["started_at"]) - row["started_at"]
    # Every model call and its cost, the auxiliary ones (compaction summaries) too: the session's own columns
    # leave those out.
    usage = db.execute(
        "SELECT SUM(api_call_count), SUM(CASE WHEN task != '' THEN api_call_count ELSE 0 END),"
        " SUM(estimated_cost_usd) FROM session_model_usage WHERE session_id = ?",
        (session,),
    ).fetchone()
    found.model_calls = usage[0] or row["api_call_count"] or 0
    found.auxiliary_calls = usage[1] or 0
    found.cost = usage[2] or row["estimated_cost_usd"] or 0.0
    # Stored messages, not the session's counts: those count only what is still active after a compaction.
    for tool, content in unique(db, session, "tool", "tool_name, content"):
        found.tool_calls += 1
        code = error_code(tool, content)
        if code:
            found.errors[code] += 1
        if tool == "chromatic_rom_build":
            found.builds += 1
            found.failed_builds += bool(code)
    for (tool_calls,) in unique(db, session, "assistant", "tool_calls", "tool_calls IS NOT NULL"):
        for tool, arguments in calls(tool_calls):
            source = any(marker in json.dumps(arguments) for marker in SOURCE_MARKERS)
            found.steps += tool == "chromatic_emulator_step"
            found.source_commands += tool == "terminal" and source
            found.source_reads += tool in SOURCE_READERS and source
            found.restores += tool == "chromatic_emulator_checkpoint" and arguments.get("action") == "restore"
    found.compactions = len(unique(db, session, "user", "id", "_compressed_summary = 1"))
    found.ended = ending(db, session, row["end_reason"], found.running)
    return found


def unique(db: sqlite3.Connection, session: str, role: str, columns: str, where: str = "1") -> list[tuple]:
    """``columns`` of each of the session's ``role`` messages once, in order. Hermes stores more than one copy of a
    message: a compaction copies the messages before it (the same `message_uid`, `compacted` 1), and a prune leaves a
    stub in the original row with the full message in a later one. Each message counts once, as its full copy wherever
    that sits: for a tool result the first that is not one of Hermes's shortened forms (each starts with `[`, its own
    test for a summary stub), for tool calls the longest (Hermes cuts oversized arguments short). A tool result is one
    per call occurrence (`tool_call_uid`; a provider can reuse a `tool_call_id` later), else per `tool_call_id`;
    anything else is one per `message_uid`."""
    stored = {column for _cid, column, *_ in db.execute("PRAGMA table_info(messages)")}
    call = ("tool_call_uid, " if "tool_call_uid" in stored else "") + "tool_call_id, "
    key = f"COALESCE({call if role == 'tool' else ''}message_uid, id)"
    full = "COALESCE(content, '') LIKE '[%', LENGTH(COALESCE(tool_calls, '')) DESC, id"
    return db.execute(
        f"SELECT {columns} FROM (SELECT *, MIN(id) OVER (PARTITION BY {key}) AS slot,"
        f" ROW_NUMBER() OVER (PARTITION BY {key} ORDER BY {full}) AS copy"
        f" FROM messages WHERE session_id = ? AND role = ? AND {where}) WHERE copy = 1 ORDER BY slot",
        (session, role),
    ).fetchall()


def ending(db: sqlite3.Connection, session: str, reason: str | None, running: bool) -> str:
    """`yes` when the chat closed after a final answer, else what happened instead."""
    final = db.execute(
        "SELECT finish_reason FROM messages WHERE session_id = ? AND role = 'assistant' ORDER BY id DESC LIMIT 1",
        (session,),
    ).fetchone()
    answered = final is not None and final["finish_reason"] == "stop"
    if reason in NORMAL_ENDS and answered:
        return "yes"
    if reason is None:
        return "no (still open)" if running else "no (chat exited, session left open)"
    return f"no ({reason}{'' if answered else ', no final answer'})"


class Drops(NamedTuple):
    """The identical tool calls Hermes dropped in each session, as far as the retained logs go back: ``since`` is the
    time of their first line (None when they hold none, so none rotated out)."""

    counts: Counter
    since: float | None

    def of(self, session: str, started: float) -> int | None:
        """``session``'s drops; None when the logs begin after it started (its first lines may have rotated out)."""
        return self.counts[session] if self.since is None or self.since <= started else None


def duplicate_drops(logs: Path) -> Drops:
    """How many identical tool calls Hermes dropped in each session (`[<session>] ... Removed duplicate tool call`)
    in `errors.log` and the copies it rotated into, and when the oldest of those begins."""
    drops, firsts = Counter(), []
    for log in sorted(logs.glob("errors.log*")):
        text = log.read_text(encoding="utf-8", errors="replace")
        if first := LOG_TIME.search(text):
            firsts.append(time.mktime(time.strptime(first.group(1), "%Y-%m-%d %H:%M:%S")))
        for line in text.splitlines():
            if DUPLICATE_DROP in line and (match := re.search(r"\[([^\]\s]+)\]", line)):
                drops[match.group(1)] += 1
    return Drops(drops, min(firsts, default=None))


def shown(value: int | None) -> str:
    return "unknown" if value is None else str(value)


def minutes(seconds: float) -> str:
    return f"{int(seconds // 60)}m{int(seconds % 60):02d}s"


ROWS = (
    ("wall time", lambda r: minutes(r.wall) + (" (running)" if r.running else "")),
    ("cost (estimated)", lambda r: f"${r.cost:.2f}"),
    (
        "model calls",
        lambda r: f"{r.model_calls} ({r.auxiliary_calls} auxiliary)" if r.auxiliary_calls else str(r.model_calls),
    ),
    ("tool calls", lambda r: str(r.tool_calls)),
    ("step calls", lambda r: str(r.steps)),
    ("builds", lambda r: f"{r.builds} ({r.failed_builds} failed)" if r.failed_builds else str(r.builds)),
    ("compactions", lambda r: str(r.compactions)),
    ("duplicate drops", lambda r: shown(r.duplicate_drops)),
    ("source commands", lambda r: str(r.source_commands)),
    ("source file reads", lambda r: str(r.source_reads)),
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
    with snapshot(profile_home / "state.db") as db:
        found = {session[:14]: Game(session) for session in ids} if ids else run_sessions(folder, db)
        return {
            name: report(db, game.session, drops, game.exited)
            if game.session
            else Report(session="none found", ended="no session")
            for name, game in found.items()
        }
