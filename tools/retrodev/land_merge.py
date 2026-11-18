"""land's last step: recheck the pull request, merge it, then the steps after the merge, which resume.

The review record keeps a landing record: {head, branch, pulled, gc}, saved after the merge and after each step.
`land` on a merged pull request whose landing record has steps left does them (pull the main checkout when it is
on the base branch and clean; gc that branch only) and never merges again.
"""

from __future__ import annotations

from . import gc, github, land_gates, repo, reviews, state
from .output import Failure, cmd

RECHECK = "state,baseRefName,headRefOid"


def progress(ctx, record: dict, step: str, **facts) -> None:
    """Remember the landing's last step in the branch record (status shows it; a rerun resumes from the records)."""
    record["land"] = {"step": step, "at": state.now(), **facts}
    state.save_branch(ctx.top, record)


def merge(ctx, info: dict, sha: str, record: dict, jobs: list[dict]) -> int:
    number, branch = info["number"], info["headRefName"]
    main = ctx.at(ctx.main())
    land_gates.recheck(ctx, number, sha, reviews.pr_view(ctx, number, RECHECK))
    subject = f"{info['title']} (#{number})"
    args = ["pr", "merge", str(number), "--squash", "--delete-branch", "--match-head-commit", sha, "--subject", subject]
    ctx.out.say(f"merging #{number} at {sha[:9]}: gh {' '.join(args[:7])} ...")
    code, out, err = github.gh(main, args, check=False)
    if code and github.pr_state(main, number) != "MERGED":
        raise Failure(
            f"gh pr merge {number} failed: {(err or out).strip()[:300]}",
            f"gh pr view {number} (a head that moved is refused by --match-head-commit: land again)",
        )
    if code:
        ctx.out.say(f"merged (gh also said: {(err or out).strip()[:200]})")
    rec = reviews.load(ctx, number)
    rec["merged"] = {"at": state.now(), "head": sha, "subject": subject, "ci": [j.get("name") for j in jobs]}
    rec["landing"] = {"head": sha, "branch": branch, "pulled": False, "gc": False}
    reviews.save(ctx, rec)
    progress(ctx, record, "merged", head=sha)
    ctx.out.say(f"merged #{number} into {ctx.base} (squash)")
    return finish(ctx, number, rec)


def unfinished(rec: dict) -> bool:
    landing = rec.get("landing")
    return bool(landing) and not (landing.get("pulled") and landing.get("gc"))


def finish(ctx, number: int, rec: dict) -> int:
    """The steps after the merge that are not done yet; each is recorded when done."""
    landing = rec["landing"]
    tops = ctx.main()
    if not landing.get("pulled"):
        if repo.branch(tops) == ctx.base and not repo.dirty(tops):
            try:
                repo.git(["pull", "--ff-only", "--quiet", ctx.remote, ctx.base], tops)
            except repo.GitError as error:
                raise Failure(
                    f"#{number} is merged, but updating the main checkout {tops} failed: {error.message}",
                    f"let {ctx.base} there fast-forward ({cmd('git', '-C', tops, 'status')}; no commits of its own), then "
                    f"python tools/retrodev land {number} (it finishes the steps after the merge, never merges again)",
                )
            landing["pulled"] = True
            reviews.save(ctx, rec)
            ctx.out.say(f"updated the main checkout {tops} ({ctx.base} at {(repo.head(tops) or '')[:9]})")
        else:
            ctx.out.say(
                f"left the main checkout {tops} alone (not on {ctx.base}, or uncommitted changes): once it is, "
                f"python tools/retrodev land {number} pulls it"
            )
    if not landing.get("gc"):
        gc.run(ctx.at(tops), only=landing["branch"])
        landing["gc"] = True
        reviews.save(ctx, rec)
    move = (
        cmd("cd", ctx.out.data["cd"]) + " && " if ctx.out.data.get("cd") else ""
    )  # gc removed the folder it started in
    ctx.out.say(f"next: {move}python tools/retrodev summary {number} (the step-8 note for the owner)")
    ctx.out.set(merged=True, head=landing["head"], action="merged", landing=landing)
    return 0
