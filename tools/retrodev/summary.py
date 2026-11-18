"""Step 8: the skeleton of the note to the owner once a pull request landed, from the records and git.

    summary <pr> [--json]

Added / Changed / Fixed / Removed, seeded from the squash commit's files (a pull request not merged yet: its head
against the base branch), grouped by the map's areas (tools/layout.toml); the review rounds (findings per round and
how many were answered); the CI result; and what the owner must do (restart the Hermes gateway, reload the app).
The agent adds the prose. Read-only: it asks GitHub and git, and changes nothing.
"""

from __future__ import annotations

import tomllib

from . import github, report, repo, reviews
from .output import Failure


def file_changes(ctx, older: str, newer: str) -> dict[str, list[str]]:
    """{added, changed, removed, moved} between two commits (a move lists 'old -> new')."""
    out = repo.git(["diff", "--name-status", "-M", older, newer], ctx.top)
    found: dict[str, list[str]] = {"added": [], "changed": [], "removed": [], "moved": []}
    for line in out.splitlines():
        parts = line.split("\t")
        kind = parts[0][:1]
        if kind == "A":
            found["added"].append(parts[1])
        elif kind == "D":
            found["removed"].append(parts[1])
        elif kind == "R" and len(parts) == 3:
            found["moved"].append(f"{parts[1]} -> {parts[2]}")
        elif len(parts) > 1:
            found["changed"].append(parts[-1])
    return found


def commits_known(ctx, *shas: str) -> bool:
    return all(sha and repo.ok(["cat-file", "-e", f"{sha}^{{commit}}"], ctx.top) for sha in shas)


def collect(ctx, number: int) -> dict:
    info = reviews.pr_view(
        ctx, number, "number,title,state,url,headRefName,headRefOid,baseRefName,mergeCommit,mergedAt"
    )
    merge = (info.get("mergeCommit") or {}).get("oid")
    if info.get("state") == "MERGED" and merge:
        newer, older, source = merge, f"{merge}^", f"the squash commit {merge[:9]}"
        known = commits_known(ctx, merge)
    else:
        newer = info.get("headRefOid") or ""
        known = commits_known(ctx, newer)
        older = repo.git(["merge-base", ctx.remote_base, newer], ctx.top, check=False).strip() if known else ""
        source = f"the head {newer[:9]} against {ctx.remote_base} (not merged yet)"
    if not known or not older:
        raise Failure(
            f"the commit of #{number} ({(merge or newer)[:9]}) is not in this checkout",
            f"git fetch {ctx.remote}, then python tools/retrodev summary {number} again",
        )
    changes = file_changes(ctx, older, newer)
    layout_path = ctx.top / "tools" / "layout.toml"
    layout = tomllib.loads(layout_path.read_text(encoding="utf-8")) if layout_path.is_file() else {}
    moved_to = [name.split(" -> ")[1] for name in changes["moved"]]
    every = changes["added"] + changes["changed"] + changes["removed"] + moved_to
    rec = reviews.load(ctx, number)
    jobs = github.checks(ctx, number)
    return {
        "pr": number,
        "title": info.get("title"),
        "url": info.get("url"),
        "state": info.get("state"),
        "merged_at": info.get("mergedAt"),
        "commit": newer,
        "source": source,
        "added": report.grouped(changes["added"], layout),
        "changed": report.grouped(changes["changed"], layout),
        "moved": changes["moved"],
        "removed": report.grouped(changes["removed"], layout),
        "fixed": [
            {"round": row["round"], **item}
            for row in reviews.rounds(rec)
            for item in row["items"]
            if item.get("answer")
        ],
        "reviews": {
            "rounds": reviews.rounds(rec),
            "skipped": rec.get("skipped"),
            "line": reviews.describe(rec),
            "approval": rec.get("approval"),
        },
        "ci": {"summary": github.ci_summary(jobs), "jobs": jobs or []},
        "owner": report.restarts(ctx, every),
    }


def short(text, limit: int = 200) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def run(ctx, number: int) -> int:
    data = collect(ctx, number)
    ctx.out.set(**data)
    say = ctx.out.say
    state = "merged " + str(data["merged_at"] or "") if data["state"] == "MERGED" else str(data["state"]).lower()
    say(f"#{number} {data['title']} ({state}; {data['url']})")
    say(f"files from {data['source']}")

    def groups(title: str, found: dict[str, list[str]]) -> None:
        say(f"\n{title}")
        for area, names in found.items():
            say(f"  {area}: " + ", ".join(names[:8]) + (f" and {len(names) - 8} more" if len(names) > 8 else ""))
        if not found:
            say("  (none)")

    groups("Added", data["added"])
    groups("Changed", data["changed"])
    if data["moved"]:
        say("  moved: " + ", ".join(data["moved"][:8]) + (" ..." if len(data["moved"]) > 8 else ""))
    say("\nFixed (review findings and their answers)")
    for item in data["fixed"]:
        where = f"{item.get('file')}:{item.get('line')}"
        say(f"  round {item['round']} [{item.get('severity')}] {where}: {short(item.get('problem'))}")
        say(f"    answer: {short(item['answer'])}")
    if not data["fixed"]:
        say("  (none)")
    groups("Removed", data["removed"])
    say(f"\nReviews: {data['reviews']['line']}")
    for row in data["reviews"]["rounds"]:
        say(
            f"  round {row['round']} on {str(row['sha'])[:9]}: {row['findings']} finding(s), {row['answered']} answered"
        )
    approval = data["reviews"]["approval"]
    if approval:
        say(f"Approved by the owner {approval['at']}: \"{approval['words']}\"")
    say(f"CI: {data['ci']['summary']} ({len(data['ci']['jobs'])} job(s))")
    say("\nThe owner:")
    for what, names in data["owner"].items():
        say(f"  {report.RESTART_TEXT[what]}: {', '.join(names[:4])}" + (" ..." if len(names) > 4 else ""))
    if not data["owner"]:
        say("  nothing to restart or reload")
    return 0
