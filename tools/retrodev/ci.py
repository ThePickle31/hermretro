"""Wait for CI on a pull request's exact head: green, failing (with the jobs and how to read them) or still running.

Every job must pass or be skipped (neutral counts as passed), except those in policy.toml [land] ignore_jobs; the
[land] required_jobs (the "All checks pass" aggregate) must be there, so a head whose jobs have not started yet is
still waiting, never green. The head is checked on every poll: a push while waiting stops land (run it again).
"""

from __future__ import annotations

import re
import time

from . import github, reviews
from .output import FAILED, WAITING, Failure

PASSED = {"pass", "skipping", "neutral"}
FAILING = {"fail", "cancel"}


def from_rollup(rollup: list[dict] | None) -> list[dict]:
    """gh pr view's statusCheckRollup as gh pr checks' rows (used when gh pr checks gives nothing)."""
    jobs = []
    for item in rollup or []:
        name = item.get("name") or item.get("context") or "?"
        status, conclusion = (
            (item.get("status") or "").upper(),
            (item.get("conclusion") or item.get("state") or "").upper(),
        )
        if status and status != "COMPLETED":
            bucket = "pending"
        elif conclusion in ("SUCCESS",):
            bucket = "pass"
        elif conclusion in ("SKIPPED", "NEUTRAL"):
            bucket = "skipping"
        elif conclusion in ("PENDING", "EXPECTED", "QUEUED", "IN_PROGRESS", ""):
            bucket = "pending"
        elif conclusion == "CANCELLED":
            bucket = "cancel"
        else:
            bucket = "fail"
        jobs.append(
            {
                "name": name,
                "bucket": bucket,
                "state": conclusion,
                "link": item.get("detailsUrl") or item.get("targetUrl"),
            }
        )
    return jobs


def classify(jobs: list[dict], required: list[str], ignore: list[str]) -> tuple[str, list[dict], list[str]]:
    """(green | failing | pending, the failing jobs, what is still awaited)."""
    watched = [job for job in jobs if job.get("name") not in ignore]
    failing = [job for job in watched if job.get("bucket") in FAILING]
    if failing:
        return "failing", failing, []
    waiting = [job["name"] for job in watched if job.get("bucket") not in PASSED]
    names = {job.get("name") for job in watched}
    waiting += [f"{name} (not reported yet)" for name in required if name not in names]
    if not watched:
        waiting.append("any job (none reported yet)")
    return ("pending", [], waiting) if waiting else ("green", [], [])


def run_id(link: str | None) -> str | None:
    match = re.search(r"/actions/runs/(\d+)", link or "")
    return match.group(1) if match else None


def wait(ctx, number: int, sha: str, timeout: float, poll: float | None = None) -> list[dict]:
    """Poll until CI on ``sha`` is green (returns its jobs); failing raises 1, still running after ``timeout`` 2."""
    land = ctx.policy.get("land", {})
    required, ignore = land.get("required_jobs", []), land.get("ignore_jobs", [])
    poll = float(poll if poll is not None else land.get("ci_poll", 20))
    sleep, clock = ctx.fakes.get("sleep", time.sleep), ctx.fakes.get("clock", time.monotonic)
    started, last = clock(), None
    while True:
        view = reviews.pr_view(ctx, number, "headRefOid,statusCheckRollup")
        if view.get("headRefOid") != sha:
            raise Failure(
                f"the head of #{number} moved from {sha[:9]} to {str(view.get('headRefOid'))[:9]} while waiting for "
                "CI (a push): CI and the reviews must pass on what is merged",
                f"python tools/retrodev land {number} (it reviews and waits for the new head)",
            )
        jobs = github.checks(ctx, number)
        if jobs is None:
            jobs = from_rollup(view.get("statusCheckRollup"))
        verdict, failing, waiting = classify(jobs, required, ignore)
        if verdict == "green":
            ctx.out.say(f"CI green on {sha[:9]} ({len(jobs)} job(s))")
            return jobs
        if verdict == "failing":
            for job in failing:
                ctx.out.say(f"  FAILED  {job.get('name')}  {job.get('link') or ''}")
            runs = sorted({rid for rid in (run_id(job.get("link")) for job in failing) if rid})
            reads = "; ".join(f"gh run view {rid} --log-failed" for rid in runs) or f"gh pr checks {number}"
            raise Failure(
                f"CI failed on {sha[:9]}: {', '.join(job.get('name', '?') for job in failing)}",
                f"read the failure ({reads}), fix it, python tools/retrodev check, commit, ship, then land {number} "
                "again",
                code=FAILED,
                data={"action": "fix CI", "failing": failing, "runs": runs},
            )
        waited = clock() - started
        if waited >= timeout:
            raise Failure(
                f"CI is still running on {sha[:9]} after {int(waited)} s: {', '.join(waiting[:6])}",
                f"python tools/retrodev land {number} again later (it resumes: nothing is reviewed twice)",
                code=WAITING,
                data={"action": "wait-ci", "waiting": waiting},
            )
        if waiting != last:
            ctx.out.say(f"CI: waiting for {', '.join(waiting[:6])}" + (" ..." if len(waiting) > 6 else ""))
            last = waiting
        sleep(min(poll, max(timeout - waited, 0.0)))
