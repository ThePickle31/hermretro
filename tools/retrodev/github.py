"""Every GitHub call retrodev makes goes through gh(), with a runner tests replace (they never reach GitHub).

A runner is ``runner(args, cwd) -> (returncode, stdout, stderr)`` where args start after "gh".
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from . import repo
from .output import Failure


def real_runner(args: list[str], cwd: Path | str) -> tuple[int, str, str]:
    if not shutil.which("gh"):
        return 127, "", "gh is not installed"
    return repo.run(["gh", *args], cwd, timeout=120)


def gh(ctx, args: list[str], check: bool = True) -> tuple[int, str, str]:
    """Run gh through the context's runner (the real one unless a test set another)."""
    runner = ctx.gh_runner or real_runner
    code, out, err = runner(list(args), ctx.top or ctx.cwd)
    if check and code:
        raise Failure(
            f"gh {' '.join(args[:3])} failed: {(err or out).strip()[:400]}",
            "python tools/retrodev doctor (checks gh is installed and logged in), then run the command again",
        )
    return code, out, err


def login(ctx) -> str | None:
    """The account gh is logged in as, or None."""
    code, out, _err = gh(ctx, ["api", "user", "--jq", ".login"], check=False)
    return out.strip() or None if code == 0 else None


def open_pr(ctx, branch: str) -> dict | None:
    """The open pull request from ``branch``, or None."""
    _code, out, _err = gh(
        ctx, ["pr", "list", "--head", branch, "--state", "open", "--json", "number,url,headRefOid,isDraft,baseRefName"]
    )
    found = json.loads(out or "[]")
    return found[0] if found else None


def branch_pr(ctx, branch: str) -> dict | None:
    """The pull request from ``branch`` that counts (merged, else open; newest first), or None. Raises when gh
    cannot tell, so a caller never mistakes an unanswered question for 'there is none'."""
    code, out, err = gh(
        ctx, ["pr", "list", "--head", branch, "--state", "all", "--json", "number,state,mergeCommit"], check=False
    )
    try:
        found = json.loads(out or "[]") if code == 0 else None
    except json.JSONDecodeError:
        found = None
    if found is None:
        raise Failure(
            f"gh pr list --head {branch} failed: {(err or out).strip()[:300]}", "python tools/retrodev doctor"
        )
    found = sorted(found, key=lambda pr: -int(pr.get("number") or 0))
    for wanted in ("MERGED", "OPEN"):
        for pr in found:
            if pr.get("state") == wanted:
                return pr
    return None


def pr_state(ctx, number: int) -> str | None:
    """MERGED, CLOSED or OPEN, or None when gh cannot tell."""
    code, out, _err = gh(ctx, ["pr", "view", str(number), "--json", "state", "--jq", ".state"], check=False)
    return out.strip() or None if code == 0 else None


def pr_number(url: str) -> int | None:
    match = re.search(r"/pull/(\d+)", url or "")
    return int(match.group(1)) if match else None


def create_args(base: str, branch: str, title: str, body_file: str, labels: list[str]) -> list[str]:
    args = ["pr", "create", "--draft", "--base", base, "--head", branch, "--title", title, "--body-file", body_file]
    for label in labels:
        args += ["--label", label]
    return args


def edit_args(number: int, title: str, body_file: str) -> list[str]:
    return ["pr", "edit", str(number), "--title", title, "--body-file", body_file]


def checks(ctx, number: int) -> list[dict] | None:
    """CI jobs of a pull request: [{name, state, bucket, link}] (bucket: pass, fail, pending, skipping, cancel)."""
    code, out, _err = gh(ctx, ["pr", "checks", str(number), "--json", "name,state,bucket,link"], check=False)
    # gh prints the JSON and exits 1 when a check failed, 8 while some are pending; anything else is an error.
    if code not in (0, 1, 8) or not out.strip():
        return None
    try:
        jobs = json.loads(out)
    except json.JSONDecodeError:
        return None
    return jobs if isinstance(jobs, list) else None


def ci_summary(jobs: list[dict] | None) -> str:
    """One word for a list of CI jobs: none, unknown, pending, failing or passing."""
    if jobs is None:
        return "unknown"
    if not jobs:
        return "none"
    buckets = {job.get("bucket") for job in jobs}
    if "fail" in buckets or "cancel" in buckets:
        return "failing"
    if "pending" in buckets:
        return "pending"
    return "passing"
