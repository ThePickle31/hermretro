"""The release notes, written by release publish (gh release create --notes-file) instead of GitHub's list.

Every pull request since the previous stable tag is one line (its squash commit's subject: a plain sentence) in one
of three groups, decided by its branch kind and the files it changed:

    New                         feat/ branches
    Fixes and improvements      any other change to what users run (USER_PATHS)
    Behind the scenes           only development files (tools, tests, docs/dev, CI): folded away

Version pull requests (chore/release-X.Y.Z, "Release X.Y.Z", "Version X.Y.Z for the next release") are left out.
Then how to update, what was tested (CI's systems, the update check from the previous release), and the
real-machine checklist (docs/dev/RELEASE-CHECKLIST.md): needed only when setup, the broker or the host code changed
(CHECKLIST_PATHS), and whether it ran (release run/publish --checklist "<result>" records it).
"""

from __future__ import annotations

import json
import re

from . import github, repo

USER_PATHS = (
    "backend/",
    "page/",
    "player/",
    "desktop/",
    "engine/",
    "skills/",
    "profile/",
    "__init__.py",
    "plugin.yaml",
    "README.md",
)
CHECKLIST_PATHS = ("backend/setup/", "backend/broker/", "backend/system/host.py")
VERSION_PR = re.compile(r"^(Release \d+\.\d+\.\d+|Version \d+\.\d+\.\d+ for the next release)\b")
NUMBER = re.compile(r"\s*\(#(\d+)\)\s*$")
CHECKLIST_DOC = "docs/dev/RELEASE-CHECKLIST.md"


def commits(ctx, since: str, sha: str) -> list[dict]:
    """The squash commits on the base branch after ``since`` up to ``sha``, oldest first: sha, subject, number, files."""
    out = repo.git(["log", "--first-parent", "--reverse", "--format=%H%x00%s", f"{since}..{sha}"], ctx.top)
    found = []
    for line in out.splitlines():
        commit, _sep, subject = line.partition("\x00")
        files = repo.git(["diff-tree", "--no-commit-id", "--name-only", "-r", "--no-renames", commit], ctx.top)
        match = NUMBER.search(subject)
        found.append(
            {
                "sha": commit,
                "subject": NUMBER.sub("", subject).strip(),
                "number": int(match.group(1)) if match else None,
                "files": files.split(),
            }
        )
    return found


def branches(ctx) -> dict[str, str]:
    """Merge commit -> head branch of the merged pull requests (one gh call); empty when GitHub cannot say."""
    args = [
        "pr",
        "list",
        "--base",
        ctx.base,
        "--state",
        "merged",
        "--limit",
        "300",
        "--json",
        "headRefName,mergeCommit",
    ]
    code, out, _err = github.gh(ctx, args, check=False)
    try:
        found = json.loads(out) if code == 0 else []
    except json.JSONDecodeError:
        found = []
    return {
        str(pr["mergeCommit"]["oid"]): str(pr.get("headRefName") or "")
        for pr in found
        if isinstance(pr.get("mergeCommit"), dict) and pr["mergeCommit"].get("oid")
    }


TRIALS = re.compile(r"^(?P<what>.*?): fixes from the (?P<nth>\w+) round of fresh-agent trials$")


def folder_notes(name: str) -> bool:
    """A folder's README under the code (developer notes), never the root README, a skill or the profile's files."""
    return name.endswith("/README.md")


def runs_for_users(name: str) -> bool:
    """A file users run or see: under USER_PATHS (skills and the studio profile's Markdown included), folder READMEs
    aside."""
    return not folder_notes(name) and (name.startswith(USER_PATHS) or name in USER_PATHS)


def checklist_line(result: str | None, touched: list[str]) -> str:
    """The notes' real-machine checklist line: the owner's result, else whether it was needed."""
    if result and result.strip():
        return f"Real-machine checklist ({CHECKLIST_DOC}): {result.strip()}"
    if touched:
        shown = ", ".join(f"`{name}`" for name in touched[:4]) + (" and more" if len(touched) > 4 else "")
        return (
            f"Real-machine checklist ({CHECKLIST_DOC}): not run, though this release changes setup, the broker or the "
            f"host code ({shown}); tell us if setup or the broker misbehaves."
        )
    return f"Real-machine checklist ({CHECKLIST_DOC}): not needed, as nothing in setup, the broker or the host code changed."


LINE = re.compile(r"^Real-machine checklist \([^)]*\):[^\n]*$", re.M)


def with_result(body: str, result: str) -> str:
    """``body`` (a draft's notes, perhaps edited) with its checklist line replaced by the owner's result, or the
    line added; everything else kept as it is."""
    new = checklist_line(result, [])
    return LINE.sub(lambda _m: new, body, count=1) if LINE.search(body) else body.rstrip() + f"\n\n{new}\n"


def group(entry: dict, branch: str) -> str | None:
    """new, fixes or behind; None for a version pull request."""
    if branch.startswith("chore/release-") or VERSION_PR.match(entry["subject"]):
        return None
    if branch.startswith("feat/"):
        return "new"
    if any(runs_for_users(name) for name in entry["files"]):
        return "fixes"
    return "behind"


def checklist_files(entries: list[dict]) -> list[str]:
    files = sorted({name for entry in entries for name in entry["files"]})
    return [name for name in files if name.startswith(CHECKLIST_PATHS) and not folder_notes(name)]


def slug(ctx) -> str | None:
    url = repo.git(["remote", "get-url", ctx.remote], ctx.top, check=False).strip()
    match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return match.group(1) if match else None


def fold(entries: list[dict], where: str | None) -> list[str]:
    """One line per change; the fresh-agent trial rounds of one kind in one line ("... from N rounds of ...")."""
    lines, rounds = [], {}
    for entry in entries:
        match = TRIALS.match(entry["subject"])
        if match:
            if match["what"] not in rounds:
                rounds[match["what"]] = []
                lines.append(match["what"])  # its place: where the first round was
            rounds[match["what"]].append(entry)
        else:
            lines.append(entry)
    shown = []
    for item in lines:
        if isinstance(item, dict):
            shown.append(line(item, where))
            continue
        same = rounds[item]
        if len(same) == 1:
            shown.append(line(same[0], where))
            continue
        refs = ", ".join(ref(entry, where) for entry in same if entry["number"])
        shown.append(f"- {item}: fixes from {len(same)} rounds of fresh-agent trials ({refs})")
    return shown


def ref(entry: dict, where: str | None) -> str:
    number = entry["number"]
    return f"[#{number}](https://github.com/{where}/pull/{number})" if where else f"#{number}"


def line(entry: dict, where: str | None) -> str:
    if entry["number"] and where:
        return f"- {entry['subject']} ([#{entry['number']}](https://github.com/{where}/pull/{entry['number']}))"
    return f"- {entry['subject']}" + (f" (#{entry['number']})" if entry["number"] else "")


def write(ctx, version: str, sha: str, previous: str | None, checklist: str | None, rc: bool = False) -> str:
    """The notes of release ``version`` at ``sha``, from the previous stable tag (or the whole history)."""
    since = f"refs/tags/v{previous}" if previous else repo.git(["rev-list", "--max-parents=0", sha], ctx.top).split()[0]
    entries = commits(ctx, since, sha)
    heads = branches(ctx)
    where = slug(ctx)
    sorted_: dict[str, list[dict]] = {"new": [], "fixes": [], "behind": []}
    for entry in entries:
        kind = group(entry, heads.get(entry["sha"], ""))
        if kind:
            sorted_[kind].append(entry)
    groups = {kind: fold(items, where) for kind, items in sorted_.items()}
    parts = []
    if rc:
        parts.append(f"A release candidate for {version.split('-rc.')[0]}: for trying out before the release.\n")
    if groups["new"]:
        parts.append("## New\n\n" + "\n".join(groups["new"]) + "\n")
    if groups["fixes"]:
        parts.append("## Fixes and improvements\n\n" + "\n".join(groups["fixes"]) + "\n")
    if not groups["new"] and not groups["fixes"]:
        parts.append("## Changes\n\nNothing that changes what you see; the work below is behind the scenes.\n")
    parts.append(
        "## Updating\n\n"
        "`hermes plugins update hermretro` in the profile you installed it into (or Capabilities > Plugins), then quit "
        "and reopen Hermes. Your games and library are kept.\n"
    )
    tested = "CI on Linux, Apple Silicon and Intel macOS, including the real engine"
    if previous:
        tested += f", and the update from v{previous} (a library game, a New Game chat and a running broker kept)"
    machine = checklist_line(checklist, checklist_files(entries))
    parts.append(f"## Tested\n\n{tested}.\n\n{machine}\n")
    if groups["behind"]:
        count = len(sorted_["behind"])
        parts.append(
            f"<details><summary>Behind the scenes ({count} change{'s' if count != 1 else ''} to tests, tools and "
            "docs)</summary>\n\n" + "\n".join(groups["behind"]) + "\n\n</details>\n"
        )
    if previous and where:
        parts.append(f"**Full changelog**: https://github.com/{where}/compare/v{previous}...v{version}\n")
    return "\n".join(parts)
