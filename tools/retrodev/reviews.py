"""Review and landing facts shared by approve, answer, land, summary, status, report and doctor.

Review records live in <state root>/reviews/<pr>.json (review/records.py), with a readable copy in the main
checkout's notes/reviews/pr<N>.md. The owner's approval of a pull request is kept, with its number, in its branch
record and its review record, which outlives the branch (gc drops a branch's record once it merged); land reads it
from the review record, so it belongs to that pull request only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import repo, state
from .github import gh
from .output import Failure
from .review import records

PR_FIELDS = "number,title,state,isDraft,baseRefName,headRefName,headRefOid,url,body"


def root(ctx) -> Path:
    return state.root(ctx.top) / "reviews"


def notes(ctx) -> Path:
    return ctx.main() / "notes" / "reviews"


def load(ctx, pr: int) -> dict:
    return records.load(root(ctx), pr)


def save(ctx, record: dict) -> dict:
    records.save(root(ctx), record, notes(ctx))
    return record


def settings(ctx) -> dict:
    """The reviewer's settings: the personal profile (no default: without it reviews are skipped) and the policy's
    provider, model and reasoning (each may be overridden personally with config set)."""
    return {
        "profile": ctx.get("review_profile") or None,
        "provider": ctx.get("review_provider"),
        "model": ctx.get("review_model"),
        "reasoning": ctx.get("review_reasoning"),
    }


def pr_view(ctx, number: int, fields: str = PR_FIELDS) -> dict:
    _code, out, _err = gh(ctx, ["pr", "view", str(number), "--json", fields])
    try:
        found = json.loads(out)
    except json.JSONDecodeError:
        raise Failure(f"gh pr view {number} printed no JSON: {out.strip()[:200]}", f"gh pr view {number}")
    if not isinstance(found, dict):
        raise Failure(f"gh pr view {number} printed {type(found).__name__}, not an object", f"gh pr view {number}")
    return found


def branch_record(ctx, branch: str) -> dict:
    """The branch's record, or a new one (a branch shipped by hand has none yet)."""
    if state.branch_path(ctx.top, branch).is_file():
        return state.load_branch(ctx.top, branch)
    return {"branch": branch, "checks": {}}


def record_pr(record: dict, number: int, url: str | None, head: str | None, title: str | None, **more) -> dict:
    """Record the branch's pull request. An approval of another pull request (a replacement from the same branch)
    no longer counts: it moves to record['approvals'] (the history). Pushes to the same pull request keep it."""
    current = record.get("pr") or {}
    approval = record.get("approval")
    if approval and approval.get("pr", current.get("number")) != number:
        record.setdefault("approvals", []).append(record.pop("approval"))
    if current.get("number") != number:
        current = {"number": number}
    found = {"url": url, "head": head, "title": title, **more}
    record["pr"] = current | {key: value for key, value in found.items() if value is not None}
    return record


def findings(entry: dict) -> list[dict]:
    return (entry.get("result") or {}).get("findings") or []


def unanswered(record: dict) -> list[tuple[int, int, dict]]:
    """(round, index, finding) for every finding of a valid round that has no answer yet."""
    found = []
    for entry in records.valid_rounds(record):
        answers = entry.get("answers") or {}
        found += [(entry["round"], n, f) for n, f in enumerate(findings(entry)) if str(n) not in answers]
    return found


def finding_line(index: int, finding: dict) -> str:
    where = f"{finding.get('file')}:{finding.get('line')}"
    return f"{index}. [{finding.get('severity')}] {where}: {finding.get('problem')}\n     fix: {finding.get('fix')}"


def rounds(record: dict) -> list[dict]:
    """Each valid round: {round, sha, verdict, findings, answered, items}; void attempts are counted apart."""
    rows = []
    for entry in records.valid_rounds(record):
        items = findings(entry)
        answers = entry.get("answers") or {}
        rows.append(
            {
                "round": entry["round"],
                "sha": entry.get("sha"),
                "verdict": entry["result"]["verdict"],
                "findings": len(items),
                "answered": sum(str(n) in answers for n in range(len(items))),
                "items": [dict(f, answer=answers.get(str(n))) for n, f in enumerate(items)],
            }
        )
    return rows


def describe(record: dict) -> str:
    """One line: the review rounds so far, or why reviews were skipped."""
    if record.get("skipped"):
        return f"skipped ({record['skipped']['reason']})"
    rows = rounds(record)
    void = sum(1 for entry in record.get("rounds", []) if entry.get("void"))
    if not rows:
        return "none yet" + (f" ({void} void attempt(s))" if void else "")
    parts = [
        f"round {row['round']} {row['verdict']}"
        + (f" ({row['findings']} finding(s), {row['answered']} answered)" if row["findings"] else "")
        for row in rows
    ]
    carried = [
        entry
        for entry in record.get("carried") or []
        # only a carry in effect: not one a later review of that very head replaced
        if entry.get("head") == record.get("head")
        and records.reviewed_as(record, entry["head"]) == entry.get("reviewed")
    ]
    for entry in carried[-1:]:
        lines = entry.get("resolution_lines") or 0
        parts.append(
            f"merge resolution, not reviewed: {lines} lines"
            if lines
            else "dev merged in after the review (no resolution)"
        )
    return "; ".join(parts) + (f"; {void} void attempt(s)" if void else "")


def mechanical(ctx, tree: Path, base: str, sha: str) -> list[str]:
    """Commits of the pull request whose subject marks them mechanical (policy.toml [land] mechanical)."""
    patterns = ctx.policy.get("land", {}).get("mechanical", [])
    point = repo.git(["merge-base", base, sha], tree, check=False).strip()
    if not point or not patterns:
        return []
    log = repo.git(["log", "--no-merges", "--format=%H %s", f"{point}..{sha}"], tree)
    return [
        line.split(" ", 1)[0]
        for line in log.splitlines()
        if " " in line and repo.matches(line.split(" ", 1)[1], patterns)
    ]


COMMENT = re.compile(r"<!--.*?-->", re.S)


def section(text: str, name: str) -> str:
    """The text under '## <name>' in a Markdown document (comments removed), or ''."""
    text = COMMENT.sub("", text or "")
    match = re.search(rf"^##\s+{re.escape(name)}\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    return " ".join(match.group(1).split()) if match else ""


def goal(ctx, plan_topic: str | None, body: str) -> str:
    """The reviewer's 'Goal': the approved plan's Goal section, else the pull request's Why."""
    if plan_topic and state.NAME.match(plan_topic):
        path = ctx.main() / "notes" / "plans" / f"{plan_topic}.md"
        if path.is_file():
            found = section(path.read_text(encoding="utf-8"), "Goal")
            if found:
                return found
    return section(body, "Why") or "(no plan goal recorded; judge the change by its title and diff)"
