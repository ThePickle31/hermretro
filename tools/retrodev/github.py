"""Every GitHub call retrodev makes goes through gh(), with a runner tests replace (they never reach GitHub).

A runner is ``runner(args, cwd) -> (returncode, stdout, stderr)`` where args start after "gh".
"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from . import repo
from .output import Failure, cmd


def real_runner(args: list[str], cwd: Path | str) -> tuple[int, str, str]:
    if not shutil.which("gh"):
        return 127, "", "gh is not installed"
    return repo.run(["gh", *args], cwd, timeout=120)


# GitHub's passing failures: a 5xx from its API or a dropped connection. Worth a retry, never a FIX.
TRANSIENT = re.compile(
    r"HTTP 5\d\d|\b50[234]\b|bad gateway|service unavailable|gateway time-?out|server error|connection reset|"
    r"connection refused|i/o timeout|TLS handshake|unexpected EOF|temporary failure in name resolution",
    re.I,
)
RETRY_DELAYS = (2.0, 6.0)  # two retries: about 8 s at most before the failure is reported


def read_only(args: list[str]) -> bool:
    """A gh call that changes nothing, so running it twice is safe: views, lists, checks and GET api calls."""
    if not args:
        return False
    if args[0] == "api":
        writes = {"-f", "-F", "--field", "--raw-field", "--input"}
        method = next((args[i + 1] for i, a in enumerate(args[:-1]) if a in ("-X", "--method")), "GET")
        return method.upper() == "GET" and not writes.intersection(args)
    return len(args) > 1 and (args[0], args[1]) in {
        ("pr", "view"),
        ("pr", "list"),
        ("pr", "checks"),
        ("pr", "diff"),
        ("run", "list"),
        ("run", "view"),
        ("release", "view"),
        ("release", "list"),
        ("repo", "view"),
        ("auth", "status"),
    }


def transient(text: str) -> bool:
    return bool(TRANSIENT.search(text or ""))


def gh(ctx, args: list[str], check: bool = True) -> tuple[int, str, str]:
    """Run gh through the context's runner (the real one unless a test set another). A read-only call that fails
    the way a busy GitHub fails (a 5xx, a dropped connection) is retried twice before its failure counts."""
    runner = ctx.gh_runner or real_runner
    sleep = (getattr(ctx, "fakes", None) or {}).get("sleep", time.sleep)
    code, out, err = runner(list(args), ctx.top or ctx.cwd)
    for delay in RETRY_DELAYS if read_only(args) else ():
        if not code or not transient(err or out):
            break
        ctx.out.say(
            f"note: gh {' '.join(args[:2])} failed on GitHub's side ({(err or out).strip()[:80]}); again in {delay:g} s"
        )
        sleep(delay)
        code, out, err = runner(list(args), ctx.top or ctx.cwd)
    if check and code:
        raise failed(args, err or out)
    return code, out, err


def failed(args: list[str], text: str) -> Failure:
    return Failure(
        f"{cmd('gh', *args[:3])} failed: {text.strip()[:400]}",
        "python tools/retrodev doctor (checks gh is installed and logged in), then run the command again",
    )


# What gh says when the repository's remotes name no GitHub repository (a sandbox, a local or another host).
NO_GITHUB = re.compile(
    r"none of the git remotes|no git remotes found|known GitHub host|could not determine base repo", re.I
)
NO_GITHUB_NOTE = "note: no GitHub remote; the open pull request lookup was skipped"


def no_github(ctx, err: str) -> bool:
    """True when gh failed because no remote is on GitHub; says the note once per command instead of gh's error."""
    if not NO_GITHUB.search(err or ""):
        return False
    if not ctx.out.data.get("no_github_remote"):
        ctx.out.say(NO_GITHUB_NOTE)
        ctx.out.set(no_github_remote=True)
    return True


class NoGitHub(Failure):
    """gh cannot answer: no remote of this repository is on GitHub."""


def login(ctx) -> str | None:
    """The account gh is logged in as, or None."""
    code, out, _err = gh(ctx, ["api", "user", "--jq", ".login"], check=False)
    return out.strip() or None if code == 0 else None


def open_pr(ctx, branch: str) -> dict | None:
    """The open pull request from ``branch``, or None."""
    code, out, err = gh(
        ctx,
        ["pr", "list", "--head", branch, "--state", "open", "--json", "number,url,headRefOid,isDraft,baseRefName"],
        check=False,
    )
    if code and no_github(ctx, err or out):
        raise NoGitHub(
            f"no remote of this repository is on GitHub ({repo.git(['remote'], ctx.top, check=False).strip() or 'none'})",
            f"git remote set-url {ctx.remote} <the GitHub repository's address> (a pull request lives on GitHub)",
        )
    if code:
        raise failed(["pr", "list", "--head"], err or out)
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


def create_or_find(ctx, args: list[str], branch: str) -> str:
    """Run ``gh pr create``; when it fails, GitHub may have opened the pull request before failing (a 502 after the
    write), so the open pull request from ``branch`` counts. gh's output (its address), else raises."""
    code, out, err = gh(ctx, args, check=False)
    if not code:
        return out
    opened = open_pr(ctx, branch)
    if not opened:
        raise failed(args, err or out)
    ctx.out.say(f"note: gh pr create failed ({(err or out).strip()[:120]}), but GitHub had opened it")
    return opened.get("url") or ""


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
    code, out, err = gh(ctx, ["pr", "checks", str(number), "--json", "name,state,bucket,link"], check=False)
    # gh prints the JSON and exits 1 when a check failed, 8 while some are pending; anything else is an error.
    if code and not out.strip() and no_github(ctx, err):
        return None
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
