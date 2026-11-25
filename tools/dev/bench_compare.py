"""`bench compare`: each game's report in a run beside the same game's in an earlier run, every measure's change,
and the games that got clearly worse.

The earlier run is the one named, else the newest run before it in the same folder that made every one of its games.
A game got clearly worse when it no longer ended normally, or, when both runs' chats ended normally, when a judged
measure rose by at least its floor and by more than its share of the earlier value (MEASURES); the other measures
move with how a game was made more than with how well, so they are shown only. Reads what `report` reads, read-only.
Standard library only; development only; Linux and macOS.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import bench
from bench import BenchError, Report


class Measure(NamedTuple):
    """One row of the comparison; ``floor`` None when it is shown but not judged."""

    label: str
    value: Callable[[Report], float]
    shown: Callable[[float], str]
    floor: float | None = None
    share: float = 0.0


def count(value: float) -> str:
    return str(int(value))


def dollars(value: float) -> str:
    return f"${value:.2f}"


MEASURES = (
    Measure("wall time", lambda r: r.wall, bench.minutes, floor=300, share=0.25),
    Measure("cost (estimated)", lambda r: r.cost, dollars, floor=2.0, share=0.25),
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


def run_games(folder: Path) -> list[str]:
    return list(bench.run_record(folder).get("games") or {})


def previous_run(run: Path) -> Path:
    """The newest run before ``run`` in its folder that made every one of its games."""
    wanted = set(run_games(run))
    earlier = sorted(f for f in run.parent.iterdir() if f.name < run.name and (f / "run.json").is_file())
    for folder in reversed(earlier):
        if wanted <= set(run_games(folder)):
            return folder
    raise BenchError(
        f"no run before {run.name} in {run.parent} made {', '.join(sorted(wanted))}: name one with --against FOLDER"
    )


def change(measure: Measure, before: float, after: float) -> str:
    delta = after - before
    if not delta:
        return ""
    share = f" ({delta / before:+.0%})" if before else ""
    return ("+" if delta > 0 else "-") + measure.shown(abs(delta)) + share


def worse(measure: Measure, before: float, after: float) -> bool:
    rise = after - before
    return measure.floor is not None and rise >= measure.floor and rise > before * measure.share


def judged(before: Report, after: Report) -> list[str]:
    """The rows that got clearly worse from ``before`` to ``after``: the ending alone when it did, the measures only
    when both chats ended normally."""
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


def game_table(name: str, columns: tuple[str, str], before: Report, after: Report, flagged: list[str]) -> list[str]:
    """One game's rows: each measure in the earlier run, in this one, its change, and `worse` where it got so."""
    cells = [[name, *columns, "change"]]
    for measure in MEASURES:
        old, new = measure.value(before), measure.value(after)
        mark = "  worse" if measure.label in flagged else ""
        cells.append([measure.label, measure.shown(old), measure.shown(new), change(measure, old, new) + mark])
    cells.append([ENDED, before.ended, after.ended, "worse" if ENDED in flagged else ""])
    widths = [max(len(row[column]) for row in cells) for column in range(len(cells[0]))]
    return ["  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip() for row in cells]


def named(folder: Path) -> str:
    commit = bench.run_record(folder).get("commit")
    return f"{folder.name} ({commit[:7]})" if commit else folder.name


def compare(profile_home: Path, run: Path, against: Path) -> tuple[str, bool]:
    """The comparison of the games both runs made, and whether any got clearly worse."""
    if run.resolve() == against.resolve():
        raise BenchError(f"{run} is compared with itself: name an earlier run with --against FOLDER")
    after, before = bench.reports(profile_home, run), bench.reports(profile_home, against)
    shared = [name for name in after if name in before]
    if not shared:
        raise BenchError(f"{run.name} and {against.name} made no game in common")
    lines = [f"run      {named(run)}", f"against  {named(against)}"]
    for side, games in (("only in run", after), ("only in against", before)):
        if alone := [name for name in games if name not in shared]:
            lines.append(f"{side}: {', '.join(alone)}")
    flagged = {name: judged(before[name], after[name]) for name in shared}
    for name in shared:
        lines += ["", *game_table(name, (against.name, run.name), before[name], after[name], flagged[name])]
        if {before[name].ended, after[name].ended} != {NORMAL}:
            lines.append("measures not judged: a chat did not end normally")
    worst = [name for name in shared if flagged[name]]
    lines += ["", "clearly worse:" if worst else "clearly worse: none"]
    lines += [
        f"  {name}: {', '.join(described(label, before[name], after[name]) for label in flagged[name])}"
        for name in worst
    ]
    return "\n".join(lines), bool(worst)
