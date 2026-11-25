"""`bench compare`: each game's report in a run beside the same game's in an earlier run, every measure's change,
and the games that got clearly worse.

The earlier run is the one named, else the newest finished run that started before it in the same folder and made
exactly its games (the games running beside each other share the machine and the subscription, so another set changes
every chat's time). A game got clearly worse when it no longer ended normally, or, when both runs' chats ended
normally, when a judged measure rose by at least its floor and by more than its share of the earlier value (MEASURES);
the other measures move with how a game was made more than with how well, so they are shown only. A game is not
judged when either run cannot speak for it (`unjudged`). Reads what `report` reads, read-only. Standard library only;
development only; Linux and macOS.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import bench
from bench import BenchError, Report

WORSE, UNJUDGED = 1, 2  # the exit when a game got clearly worse, else when one could not be judged


class Measure(NamedTuple):
    """One row of the comparison; ``floor`` None when it is shown but not judged. A value of None is unknown."""

    label: str
    value: Callable[[Report], float | None]
    shown: Callable[[float], str]
    floor: float | None = None
    share: float = 0.0


def count(value: float) -> str:
    return str(int(value))


def dollars(cents: float) -> str:
    return f"${cents / 100:.2f}"


MEASURES = (
    Measure("wall time", lambda r: r.wall, bench.minutes, floor=300, share=0.25),
    # In whole cents, so a rise of exactly the floor is one ($7.20 to $9.20 is not $1.99999).
    Measure("cost (estimated)", lambda r: round(r.cost * 100), dollars, floor=200, share=0.25),
    Measure("model calls", lambda r: r.model_calls, count, floor=20, share=0.25),
    Measure("tool calls", lambda r: r.tool_calls, count, floor=40, share=0.25),
    Measure("step calls", lambda r: r.steps, count),
    Measure("builds", lambda r: r.builds, count),
    Measure("failed builds", lambda r: r.failed_builds, count, floor=2, share=0.5),
    Measure("compactions", lambda r: r.compactions, count, floor=2, share=0.5),
    Measure("duplicate drops", lambda r: r.duplicate_drops, count, floor=5, share=0.5),
    Measure("source commands", lambda r: r.source_commands, count, floor=3, share=0.5),
    Measure("source file reads", lambda r: r.source_reads, count, floor=3, share=0.5),
    Measure("checkpoint restores", lambda r: r.restores, count),
    Measure("tool errors", lambda r: sum(r.errors.values()), count, floor=3, share=0.5),
)
ENDED = "ended normally"
NORMAL = "yes"
MISSING = {"no session", "no such session"}


def finished(record: dict) -> bool:
    """Whether every chat of a run has exited: `run` records each exit when it comes."""
    return all(game.get("ended") is not None for game in record.get("games", {}).values())


def previous_run(run: Path) -> Path:
    """The newest finished run that started before ``run`` in its folder and made exactly its games."""
    record = bench.run_record(run)
    wanted, started = set(record.get("games") or {}), record.get("started")
    if started is None:
        raise BenchError(f"{run} records no start: name the run to compare with, --against FOLDER")
    candidates = []
    for folder in run.parent.iterdir():
        if folder == run or not (folder / "run.json").is_file():
            continue
        earlier = bench.run_record(folder)
        when = earlier.get("started")
        if when is not None and when < started and set(earlier.get("games") or {}) == wanted and finished(earlier):
            candidates.append((when, folder))
    if not candidates:
        raise BenchError(
            f"no finished run before {run.name} in {run.parent} made exactly {', '.join(sorted(wanted))}: "
            "name one with --against FOLDER"
        )
    return max(candidates)[1]


def unjudged(folder: Path, profile_home: Path, reports: dict[str, Report]) -> dict[str, str]:
    """Why a game of the run in ``folder`` cannot be judged, for each that cannot: the run was made in another profile
    home than the one read, its chat had not exited when the run was last recorded (still running, or its run was
    stopped), or its session is not in the profile's `state.db`."""
    record = bench.run_record(folder)
    home, profile = record.get("home"), record.get("profile")
    if home:
        elsewhere = f"made in {home}, not {profile_home}" if Path(home).resolve() != profile_home.resolve() else ""
    else:  # recorded before runs named their home
        elsewhere = f"made in the {profile} profile, not {profile_home.name}" if profile != profile_home.name else ""
    reasons = {}
    for name, game in record["games"].items():
        if elsewhere:
            reasons[name] = elsewhere
        elif game.get("ended") is None:
            reasons[name] = "its chat had not exited"
        elif reports[name].ended in MISSING:
            reasons[name] = f"{reports[name].ended} in {profile_home / 'state.db'}"
    return reasons


def change(measure: Measure, before: float | None, after: float | None) -> str:
    if before is None or after is None:
        return ""
    delta = after - before
    if not delta:
        return ""
    share = f" ({delta / before:+.0%})" if before else ""
    return ("+" if delta > 0 else "-") + measure.shown(abs(delta)) + share


def worse(measure: Measure, before: float | None, after: float | None) -> bool:
    if measure.floor is None or before is None or after is None:
        return False
    rise = after - before
    return rise >= measure.floor and rise > before * measure.share


def judged(before: Report, after: Report) -> list[str]:
    """The rows that got clearly worse from ``before`` to ``after``: the ending alone when it did, the measures only
    when both chats ended normally (and of those, only the ones known in both)."""
    if after.ended != NORMAL:
        return [ENDED] if before.ended == NORMAL else []
    if before.ended != NORMAL:
        return []
    return [measure.label for measure in MEASURES if worse(measure, measure.value(before), measure.value(after))]


def described(label: str, before: Report, after: Report) -> str:
    if label == ENDED:
        return f"{ENDED} {before.ended} -> {after.ended}"
    measure = next(measure for measure in MEASURES if measure.label == label)
    return f"{label} {change(measure, measure.value(before), measure.value(after))}"


def value_shown(measure: Measure, value: float | None) -> str:
    return "unknown" if value is None else measure.shown(value)


def game_table(name: str, columns: tuple[str, str], before: Report, after: Report, flagged: list[str]) -> list[str]:
    """One game's rows: each measure in the earlier run, in this one, its change, and `worse` where it got so; then
    both sessions and the error codes whose count changed."""
    cells = [[name, *columns, "change"]]
    for measure in MEASURES:
        old, new = measure.value(before), measure.value(after)
        mark = "  worse" if measure.label in flagged else ""
        cells.append(
            [measure.label, value_shown(measure, old), value_shown(measure, new), change(measure, old, new) + mark]
        )
    cells.append([ENDED, before.ended, after.ended, "worse" if ENDED in flagged else ""])
    widths = [max(len(row[column]) for row in cells) for column in range(len(cells[0]))]
    lines = ["  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip() for row in cells]
    lines.append(f"sessions: {before.session} -> {after.session}")
    codes = sorted(code for code in before.errors | after.errors if before.errors[code] != after.errors[code])
    if codes:
        lines.append("errors: " + ", ".join(f"{code} {before.errors[code]} -> {after.errors[code]}" for code in codes))
    return lines


def named(folder: Path) -> str:
    commit = bench.run_record(folder).get("commit")
    return f"{folder.name} ({commit[:7]})" if commit else folder.name


def compare(profile_home: Path, run: Path, against: Path) -> tuple[str, int]:
    """The comparison of the games both runs made, and its exit: WORSE when a game got clearly worse, else UNJUDGED
    when one could not be judged, else 0."""
    if run.resolve() == against.resolve():
        raise BenchError(f"{run} is compared with itself: name an earlier run with --against FOLDER")
    after, before = bench.reports(profile_home, run), bench.reports(profile_home, against)
    shared = [name for name in after if name in before]
    if not shared:
        raise BenchError(f"{run.name} and {against.name} made no game in common")
    lines = [f"run      {named(run)}", f"against  {named(against)}"]
    alone = [
        f"only in {side}: {', '.join(names)}"
        for side, games in (("run", after), ("against", before))
        if (names := [name for name in games if name not in shared])
    ]
    if alone:
        lines.append(f"workload differs, so contention does too: {'; '.join(alone)}")
    reasons = {name: [] for name in shared}
    for side, folder, reports in (("run", run, after), ("against", against, before)):
        for name, reason in unjudged(folder, profile_home, reports).items():
            if name in reasons:
                reasons[name].append(f"{side}: {reason}")
    flagged = {name: [] if reasons[name] else judged(before[name], after[name]) for name in shared}
    for name in shared:
        lines += ["", *game_table(name, (against.name, run.name), before[name], after[name], flagged[name])]
        if reasons[name]:
            lines.append(f"not judged: {'; '.join(reasons[name])}")
        elif {before[name].ended, after[name].ended} != {NORMAL}:
            lines.append("measures not judged: a chat did not end normally")
    worst = [name for name in shared if flagged[name]]
    lines += ["", "clearly worse:" if worst else "clearly worse: none"]
    lines += [
        f"  {name}: {', '.join(described(label, before[name], after[name]) for label in flagged[name])}"
        for name in worst
    ]
    if unsure := [name for name in shared if reasons[name]]:
        lines.append(f"not judged: {', '.join(unsure)}")
    return "\n".join(lines), WORSE if worst else UNJUDGED if unsure else 0
