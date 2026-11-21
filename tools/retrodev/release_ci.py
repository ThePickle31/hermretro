"""Optional upgrade evidence from the repository's own CI, never a substitute for the required CI gate."""

from __future__ import annotations

import json
import re

from . import github, release_notes, repo

WORKFLOW = ".github/workflows/ci.yml"
UPGRADE_JOBS = ("Hermes validation and a clean install", "Update from the newest release")
UPGRADE_STEP = "python tools/ci/clean_install_check.py --update-from"
SHA = r"[0-9a-f]{40}"
STAMP = r"\d{4}-\d{2}-\d{2}T[\d:.]+Z "
RESULT = re.compile(rf"^{STAMP}upgrade evidence: (v\d+\.\d+\.\d+) ({SHA}) -> ({SHA})\s*$", re.M)
RUNTIME = re.compile(rf"^{STAMP}Hermes at ({SHA})\s*$", re.M)


def document(ctx, path: str) -> dict:
    code, out, _err = github.gh(ctx, ["api", path], check=False)
    try:
        value = json.loads(out) if not code else None
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def rows(data: dict, key: str) -> list[dict]:
    value = data.get(key)
    if not isinstance(value, list) or data.get("total_count") != len(value):
        return []
    return value if all(isinstance(row, dict) for row in value) else []


def succeeded(row: dict) -> bool:
    return row.get("status") == "completed" and row.get("conclusion") == "success"


def evidence(ctx, sha: str, tag: str | None, baseline: str | None) -> dict | None:
    """An exact candidate and immutable published baseline, proved in the latest attempt of a dev push."""
    slug = release_notes.slug(ctx)
    if ctx.base != "dev" or not slug or not tag or not baseline or baseline == sha:
        return None
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag) or any(not re.fullmatch(SHA, s) for s in (baseline, sha)):
        return None
    if not repo.is_ancestor(ctx.top, baseline, sha):
        return None
    root = f"repos/{slug}"
    published = document(ctx, f"{root}/releases/tags/{tag}")
    if not (
        published.get("tag_name") == tag
        and published.get("draft") is False
        and published.get("prerelease") is False
        and published.get("published_at")
        and published.get("immutable") is True
    ):
        return None
    listing = document(ctx, f"{root}/actions/workflows/ci.yml/runs?branch=dev&event=push&head_sha={sha}")
    runs = rows(listing, "workflow_runs")
    if len(runs) != 1:
        return None
    run = runs[0]
    if not (
        succeeded(run)
        and run.get("path") == WORKFLOW
        and run.get("event") == "push"
        and run.get("head_branch") == "dev"
        and run.get("head_sha") == sha
        and all(
            isinstance(run.get(key), dict) and str(run[key].get("full_name", "")).lower() == slug.lower()
            for key in ("repository", "head_repository")
        )
    ):
        return None
    run_id, attempt = run.get("id"), run.get("run_attempt")
    if not all(type(n) is int and n > 0 for n in (run_id, attempt)):
        return None
    jobs = rows(document(ctx, f"{root}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100"), "jobs")
    upgrades = [job for job in jobs if job.get("name") in UPGRADE_JOBS]
    if len(upgrades) != 1:
        return None
    job = upgrades[0]
    if not (
        succeeded(job)
        and job.get("head_sha") == sha
        and job.get("run_id") == run_id
        and job.get("run_attempt") == attempt
        and type(job.get("id")) is int
        and job["id"] > 0
    ):
        return None
    steps = job.get("steps")
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
        return None
    matching = [step for step in steps if step.get("name") == UPGRADE_STEP]
    if len(matching) != 1 or not succeeded(matching[0]):
        return None
    # gh refuses logs containing ANSI sequences unless allowed; never print raw logs to the terminal.
    code, log, _err = github.gh(
        ctx, ["api", "--allow-escape-sequences", f"{root}/actions/jobs/{job['id']}/logs"], check=False
    )
    runtimes = RUNTIME.findall(log)
    if code or RESULT.findall(log) != [(tag, baseline, sha)] or len(runtimes) != 1:
        return None
    return {"run": run_id, "attempt": attempt, "job": job["id"], "baseline": baseline, "hermes": runtimes[0]}
