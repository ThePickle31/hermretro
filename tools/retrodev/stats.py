"""`stats`: how the working agreement is going, from retrodev's records and git. Read-only.

    stats [--json]

- pull requests landed through retrodev (review records with a merge) against those merged into the base branch
  (git subjects ending in "(#N)");
- per landed pull request: review rounds, findings per round and how many were answered, and whether reviews
  were skipped;
- the average time from ship to merge (ship records the first push of each pull request) and from the owner's
  approval to merge;
- check times from the branch records (each check's runs that were not cached, and the fast checks' wall time);
- friction: rows of the main checkout's notes/friction.md, and how many are still open.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from . import repo, state

STAMP = "%Y-%m-%dT%H:%M:%S%z"


def _time(text: str | None) -> datetime | None:
    try:
        return datetime.strptime(text, STAMP) if text else None
    except ValueError:
        return None


def _hours(older: str | None, newer: str | None) -> float | None:
    start, end = _time(older), _time(newer)
    return round((end - start).total_seconds() / 3600, 2) if start and end else None


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def review_records(root: Path) -> list[dict]:
    folder = root / "reviews"
    found = []
    for path in sorted(folder.glob("*.json"), key=lambda p: int(p.stem) if p.stem.isdigit() else 0):
        if not path.stem.isdigit():
            continue
        try:
            found.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return found


def pull_request(record: dict) -> dict:
    rounds = [entry for entry in record.get("rounds", []) if not entry.get("void")]
    findings = [len((entry.get("result") or {}).get("findings") or []) for entry in rounds]
    answered = sum(len(entry.get("answers") or {}) for entry in rounds)
    merged = (record.get("merged") or {}).get("at")
    shipped = (record.get("shipped") or {}).get("at")
    approved = (record.get("approval") or {}).get("at")
    return {
        "pr": record.get("pr"),
        "subject": (record.get("merged") or {}).get("subject"),
        "merged": merged,
        "rounds": len(rounds),
        "findings": findings,
        "answered": answered,
        "reviews_skipped": (record.get("skipped") or {}).get("reason"),
        "ship_to_merge_hours": _hours(shipped, merged),
        "approval_to_merge_hours": _hours(approved, merged),
    }


def merged_in_git(ctx) -> list[int]:
    ref = ctx.remote_base if repo.head(ctx.top, ctx.remote_base) else "HEAD"
    subjects = repo.git(["log", "--format=%s", ref], ctx.top, check=False)
    return [int(match.group(1)) for line in subjects.splitlines() if (match := re.search(r"\(#(\d+)\)$", line))]


def check_times(root: Path) -> dict:
    per_check: dict[str, list[float]] = {}
    walls = []
    for record in _branch_records(root):
        for name, entry in (record.get("checks") or {}).items():
            if entry.get("state") == "ok" and isinstance(entry.get("seconds"), (int, float)):
                per_check.setdefault(name, []).append(float(entry["seconds"]))
        wall = (record.get("last_run") or {}).get("fast_wall")
        if isinstance(wall, (int, float)):
            walls.append(float(wall))
    return {
        "per_check": {
            name: {"runs": len(values), "mean_seconds": _mean(values)} for name, values in sorted(per_check.items())
        },
        "fast_wall_mean_seconds": _mean(walls),
        "branches": len(walls),
    }


def _branch_records(root: Path) -> list[dict]:
    folder = root / "branches"
    found = []
    for path in sorted(folder.rglob("*.json")) if folder.is_dir() else []:
        try:
            found.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return found


def friction(main: Path) -> dict | None:
    path = main / "notes" / "friction.md"
    if not path.is_file():
        return None
    rows = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("| ") and not line.startswith(("| When", "|---")) and not set(line) <= set("|- ")
    ]
    return {"rows": len(rows), "open": sum("(open)" in row for row in rows), "file": str(path)}


def run(ctx) -> int:
    root = state.root(ctx.top)
    prs = [pull_request(record) for record in review_records(root)]
    landed = [pr for pr in prs if pr["merged"]]
    in_git = merged_in_git(ctx)
    found = {
        "landed_with_retrodev": len(landed),
        "merged_into_base": len(in_git),
        "pull_requests": landed,
        "open_or_unmerged_records": [pr["pr"] for pr in prs if not pr["merged"]],
        "mean_rounds": _mean([float(pr["rounds"]) for pr in landed]),
        "mean_findings": _mean([float(sum(pr["findings"])) for pr in landed]),
        "mean_ship_to_merge_hours": _mean([h for pr in landed if (h := pr["ship_to_merge_hours"]) is not None]),
        "mean_approval_to_merge_hours": _mean([h for pr in landed if (h := pr["approval_to_merge_hours"]) is not None]),
        "checks": check_times(root),
        "friction": friction(ctx.main()),
    }
    ctx.out.set(**found)
    say = ctx.out.say
    say(f"pull requests: {len(landed)} landed with retrodev; {len(in_git)} merged into {ctx.base} in all")
    for pr in landed:
        rounds = ", ".join(str(n) for n in pr["findings"]) or "none"
        extra = f"; reviews skipped: {pr['reviews_skipped']}" if pr["reviews_skipped"] else ""
        timing = f"; ship->merge {pr['ship_to_merge_hours']} h" if pr["ship_to_merge_hours"] is not None else ""
        say(
            f"  #{pr['pr']}: {pr['rounds']} rounds, findings per round: {rounds}, answered {pr['answered']}{extra}{timing}"
        )
    say(f"mean review rounds {found['mean_rounds']}, findings {found['mean_findings']} per landed pull request")
    ship = found["mean_ship_to_merge_hours"]
    say(
        "ship to merge: "
        + (f"{ship} h on average" if ship is not None else "not recorded yet (ship records it from now on)")
        + f"; approval to merge: {found['mean_approval_to_merge_hours']} h on average"
    )
    times = found["checks"]
    rows = ", ".join(f"{name} {row['mean_seconds']} s" for name, row in times["per_check"].items()) or "none recorded"
    say(f"check times (mean of passes, {times['branches']} branch records): {rows}")
    say(f"fast checks wall time: {times['fast_wall_mean_seconds']} s on average")
    if found["friction"]:
        say(f"friction: {found['friction']['rows']} rows in notes/friction.md, {found['friction']['open']} open")
    else:
        say("friction: no notes/friction.md in the main checkout")
    return 0
