"""One review round, end to end: probe, prepare, snapshot, run, parse, audit, record.

    result = run_round(repo, pr, sha, settings, title=..., goal=...)
    result["status"]: "skipped" | "reviewed" | "invalid" | "void" | "limit"

A void audit (a write, a path outside the round folder, a change to the PR's worktree or remote branch) discards the reply and
runs the round once more from a fresh export; a second void stops with 'needs-owner'.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from retrodev.review import audit as audit_mod
from retrodev.review import inputs, records, runner


def landing_probe(settings: dict, run: runner.Runner | None = None) -> dict:
    """Probe the reviewer once per landing; reuse the answer for each round of it."""
    return runner.probe(settings, run)


def run_round(
    repo: Path | str,
    pr: int,
    sha: str,
    settings: dict,
    *,
    title: str = "",
    goal: str = "",
    base: str = "origin/dev",
    mechanical=(),
    moves=(),
    probe: dict | None = None,
    run: runner.Runner | None = None,
    ls_remote: Callable[[Path, str | None], str] | None = None,
    root: Path | str | None = None,
    notes: Path | str | None = None,
    brief_override: str | None = None,
    env=None,
    db: Path | None = None,
    branch: str | None = None,
) -> dict:
    """Run the next round of ``pr`` at ``sha``. Returns {status, action, round, result, audit, record, probe,
    attempts, inputs}; ``action`` is records.next_action as if CI were green (the caller checks CI).
    ``repo`` is the pull request's worktree; its files and HEAD, ``branch`` on origin (default: its checked-out
    branch) and the round's src/ export must be unchanged afterwards (audit.snapshot)."""
    repo = Path(repo)
    sha = inputs.resolve(repo, sha)
    root = inputs.reviews_root(repo, root)
    notes = Path(notes) if notes else records.notes_dir(repo)
    settings = runner.settings_with_defaults(settings)
    branch = branch or audit_mod.branch_of(repo)

    def finish(status: str, record: dict, **extra) -> dict:
        return {
            "status": status,
            "action": records.next_action(record, True, head=sha),
            "record": str(records.record_path(root, pr)),
            "probe": probe,
            **{"round": None, "result": None, "audit": None, "attempts": [], "inputs": None, **extra},
        }

    if probe is None:
        probe = runner.probe(settings, run)
    if not probe.get("available"):
        if settings["profile"]:
            records.add_probe(root, pr, probe, notes)
        record = records.mark_skipped(root, pr, probe.get("reason", "reviewer unavailable"), notes)
        return finish("skipped", record)

    record = records.load(root, pr)
    round_no = records.next_round(record)
    if round_no > records.MAX_ROUNDS:
        return finish("limit", record)
    earlier, last_reviewed = records.earlier_inputs(record)
    attempts = []
    for attempt in (1, 2):
        prepared = inputs.prepare(
            repo,
            pr,
            sha,
            round_no=round_no,
            title=title,
            goal=goal,
            base=base,
            mechanical=mechanical,
            moves=moves,
            earlier=earlier,
            last_reviewed=last_reviewed,
            root=root,
            brief_override=brief_override,
        )
        started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        before = audit_mod.snapshot(repo, prepared.src, branch, ls_remote)
        out = root / str(pr) / f"round{round_no}{'' if attempt == 1 else f'-attempt{attempt}'}.out"
        reply = runner.run_review(settings, prepared.brief, prepared.dir, out, run)
        after = audit_mod.snapshot(repo, prepared.src, branch, ls_remote)
        checked = audit_mod.audit(
            profile=settings["profile"],
            session_ids=reply["session_ids"],
            round_dir=prepared.dir,
            before=before,
            after=after,
            db=db,
            env=env,
            unaudited=sum(1 for a in reply["attempts"] if not a.get("session_id")),
        )
        entry = {
            "round": round_no,
            "started": started,
            "attempt": attempt,
            "sha": prepared.sha,
            "inputs": prepared.to_dict(),
            "output": reply["output"],
            "session_ids": reply["session_ids"],
            "result": reply["result"] if checked["ok"] else None,
            "discarded_result": None if checked["ok"] else reply["result"],
            "errors": reply["errors"],
            "audit": checked,
            "void": not checked["ok"],
            "seconds": reply["seconds"],
            "runs": reply["attempts"],
        }
        attempts.append({"attempt": attempt, "audit": checked, "seconds": reply["seconds"], "errors": reply["errors"]})
        if checked["ok"]:
            status = "reviewed" if reply["result"] is not None else "invalid"
            if status == "invalid":
                entry["stopped"] = "the reviewer gave no valid review JSON, even when asked again: needs the owner"
            record = records.add_round(root, pr, entry, notes)
            return finish(
                status,
                record,
                round=round_no,
                result=reply["result"],
                audit=checked,
                attempts=attempts,
                inputs=prepared.to_dict(),
            )
        if attempt == 2:
            entry["stopped"] = "the reviewer broke the read-only rules twice: needs the owner"
        record = records.add_round(root, pr, entry, notes)
    return finish("void", record, round=round_no, audit=checked, attempts=attempts, inputs=prepared.to_dict())
