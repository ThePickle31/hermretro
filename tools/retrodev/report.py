"""Step 5's factual half: what the pull request is, from the record and git, so the agent writes only the prose.

    report [--json]

The pull request, its commits, the files changed grouped by the map's areas (tools/layout.toml), the checks with
their times (ran or cached), CI per job, whether the owner must restart the Hermes gateway or reload the app once
it lands, the owner's approval and the review rounds.
"""

from __future__ import annotations

import tomllib

from . import github, repo, reviews, state


def area_of(name: str, layout: dict) -> str:
    parts = name.split("/")
    if len(parts) == 1:
        return "root files"
    folder = layout.get("folders", {}).get(parts[0])
    if folder is None:
        return f"{parts[0]}/ (not in the map)"
    if len(parts) > 2 and parts[1] in folder.get("areas", {}):
        return f"{parts[0]}/{parts[1]}/"
    return f"{parts[0]}/"


def grouped(files: list[str], layout: dict) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for name in files:
        groups.setdefault(area_of(name, layout), []).append(name)
    return dict(sorted(groups.items()))


def restarts(ctx, files: list[str]) -> dict[str, list[str]]:
    """{gateway|app: files that need it} (policy.toml [restart])."""
    found = {}
    for what, patterns in ctx.policy["restart"].items():
        hits = [name for name in files if repo.matches(name, patterns)]
        if hits:
            found[what] = hits
    return found


RESTART_TEXT = {
    "gateway": "the owner restarts the Hermes gateway after it lands (the running gateway holds the old backend)",
    "app": "the owner reloads Hermes Desktop after it lands (the page bundle changed)",
}


def collect(ctx) -> dict:
    branch = repo.branch(ctx.top)
    record = state.load_branch(ctx.top, branch) if branch else {}
    base = ctx.remote_base
    layout_path = ctx.top / "tools" / "layout.toml"
    layout = tomllib.loads(layout_path.read_text(encoding="utf-8")) if layout_path.is_file() else {}
    files = repo.changed_files(ctx.top, base) or []
    point = repo.merge_base(ctx.top, base)
    log = repo.git(["log", "--format=%h %s", f"{point}..HEAD"], ctx.top).splitlines() if point else []
    pr = record.get("pr")
    jobs = github.checks(ctx, pr["number"]) if pr else None
    tree = repo.tree_digest(ctx.top)
    return {
        "branch": branch,
        "pr": pr,
        "head": repo.head(ctx.top),
        "pushed": record.get("pushed"),
        "commits": log,
        "files": grouped(files, layout),
        "checks": (record.get("last_run") or {}).get("rows", []),
        "checks_on_this_tree": record.get("passed_tree") == tree,
        "ci": {"summary": github.ci_summary(jobs) if pr else "no pull request", "jobs": jobs or []},
        "restart": restarts(ctx, files),
        "approval": record.get("approval"),
        "review": reviews.describe(reviews.load(ctx, pr["number"])) if pr else None,
        "review_rounds": reviews.rounds(reviews.load(ctx, pr["number"])) if pr else [],
    }


def run(ctx) -> int:
    data = collect(ctx)
    ctx.out.set(**data)
    say = ctx.out.say
    pr = data["pr"]
    say(f"Pull request: #{pr['number']} {pr['url']}" if pr else "Pull request: none yet (python tools/retrodev ship)")
    say(
        f"Branch: {data['branch']} at {(data['head'] or '')[:9]}"
        + ("" if not pr or data["pushed"] == data["head"] else " (not pushed yet: ship again)")
    )
    say(f"\nCommits ({len(data['commits'])}):")
    for line in data["commits"]:
        say(f"  {line}")
    say(f"\nFiles changed ({sum(map(len, data['files'].values()))}):")
    for area, names in data["files"].items():
        say(f"  {area}: " + ", ".join(names))
    say("\nChecks" + (" (passed on this tree)" if data["checks_on_this_tree"] else " (NOT passed on this tree)") + ":")
    for row in data["checks"]:
        say(f"  {row['state']:>7}  {row['name']:<13} " + ("cached" if row["cached"] else f"{row['seconds']:.1f} s"))
    say(f"\nCI: {data['ci']['summary']}")
    for job in data["ci"]["jobs"]:
        say(f"  {job.get('bucket', '?'):>8}  {job.get('name')}")
    say("\nAfter it lands:")
    for what, names in data["restart"].items():
        say(f"  {RESTART_TEXT[what]}: {', '.join(names[:4])}" + (" ..." if len(names) > 4 else ""))
    if not data["restart"]:
        say("  nothing to restart or reload")
    say(f"\nReview rounds: {data['review'] or 'none yet'}")
    approval = data["approval"]
    say("Owner's approval: " + (f"{approval['at']}: \"{approval['words']}\"" if approval else "not yet"))
    return 0
