"""Prepare one review round's folder: a throwaway export of the PR head and the reviewer's reading material.

    <reviews root>/<pr>/round<N>/src/      `git archive <sha>` extracted (no .git, so no history and no remote)
    <reviews root>/<pr>/round<N>/review/   brief.md (filled in), commits.txt, stat.txt, diff.patch,
                                           commit-<sha>.patch per commit, and in rounds 2-3
                                           round<K>-findings-and-answers.txt and round<K>-fixes.patch

The reviews root defaults to <git common dir>/retrodev/reviews, which is outside every worktree's files.
Generated files and lockfiles are left out of every patch: they are megabytes of noise.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from string import Template

BRIEF = Path(__file__).resolve().parent / "brief.md"
EXCLUDED = (
    "desktop/plugin.js",
    "player/frame-shim.js",
    "page/app/rpc-names.js",
    "tools/npm/package-lock.json",
    "tests/repo/registration.json",
)
MAX_ROUNDS = 3
# The brief's two free sections, replaced whole by a short override (a focused or smoke-test round).
BODY_START, BODY_END = "WHAT YOU ARE REVIEWING", "OUTPUT:"


class InputsError(RuntimeError):
    """The round folder cannot be prepared (a bad commit, a root inside a worktree)."""


@dataclass
class RoundInputs:
    pr: int
    round: int
    sha: str
    base: str
    dir: Path
    src: Path
    review: Path
    brief: Path
    commits: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pr": self.pr,
            "round": self.round,
            "sha": self.sha,
            "base": self.base,
            "dir": str(self.dir),
            "brief": str(self.brief),
            "commits": self.commits,
            "files": self.files,
        }


def git_bytes(repo: Path | str, *args: str) -> bytes:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if proc.returncode:
        raise InputsError(f"git {' '.join(args)} failed: {proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout


def git(repo: Path | str, *args: str) -> str:
    return git_bytes(repo, *args).decode(errors="replace")


def common_dir(repo: Path | str) -> Path:
    """The repository's shared git folder (the main checkout's .git, whichever worktree ``repo`` is)."""
    return Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").strip())


def main_checkout(repo: Path | str) -> Path | None:
    """The main checkout's folder, or None for a bare repository."""
    common = common_dir(repo)
    return common.parent if common.name == ".git" else None


def reviews_root(repo: Path | str, root: Path | str | None = None) -> Path:
    return Path(root) if root else common_dir(repo) / "retrodev" / "reviews"


def worktrees(repo: Path | str) -> list[Path]:
    out = git(repo, "worktree", "list", "--porcelain")
    return [Path(line[len("worktree ") :]) for line in out.splitlines() if line.startswith("worktree ")]


def pathspec() -> list[str]:
    return ["--", ".", *(f":(exclude){name}" for name in EXCLUDED)]


def resolve(repo: Path | str, rev: str) -> str:
    return git(repo, "rev-parse", "--verify", f"{rev}^{{commit}}").strip()


def _inside(path: Path, folder: Path) -> bool:
    try:
        path.resolve().relative_to(folder.resolve())
    except ValueError:
        return False
    return True


def export(repo: Path | str, sha: str, dest: Path) -> None:
    """Extract ``git archive <sha>`` into ``dest`` (recreated empty): files only, no .git."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    data = git_bytes(repo, "archive", "--format=tar", sha)
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dest, filter="data")
        else:  # Python 3.11 before 3.11.4: git archive's own output, no absolute or parent paths
            tar.extractall(dest)


def commit_notes(commits: list[str], mechanical=(), moves=()) -> str:
    """The brief's lines on how closely to read each commit."""
    short = [line.split(" ", 1)[0] for line in commits]

    def pick(prefixes) -> list[str]:
        return [c for c in short if any(c.startswith(p[:7]) or p.startswith(c) for p in prefixes)]

    mech, moved = pick(mechanical), pick(moves)
    logic = [c for c in short if c not in mech and c not in moved]
    lines = []
    if mech:
        lines.append(f"- Commits {', '.join(mech)} are mechanical (a formatter pass or generated output): skip them.")
    if moved:
        lines.append(
            f"- Commits {', '.join(moved)} are moves: look for anything the move broke (a path, import, CI filter,"
            " cache key, doc or FIX line pointing at an old location; a `Path(__file__).parents[n]` now wrong)."
        )
    if logic:
        lines.append(
            f"- Commits {', '.join(logic)} contain real logic: review them most closely, and read the surrounding"
            " code in REV/src (callers, imports, tests, docs) to judge them."
        )
    return "\n".join(lines)


def round_section(round_no: int, earlier: dict[int, str], fixes: dict[int, str], total: int = MAX_ROUNDS) -> str:
    """``total``: the rounds this pull request gets (records.depth); the fixes of the last one are not reviewed."""
    last = " (the last)" if round_no >= total and (round_no > 1 or total == 1) else ""
    parts = [f"THIS IS ROUND {round_no} of {total}{last}."]
    if round_no == 1 and total == 1:
        parts.append(
            "The fixes for its findings merge without another review unless a finding is high severity: report"
            " every problem now and give each its true severity."
        )
    for k in sorted(earlier, reverse=True):
        part = f"Round {k}'s findings with the author's answers: REV/review/round{k}-findings-and-answers.txt"
        if k in fixes:
            part += f"; the commits that fixed them: REV/review/round{k}-fixes.patch"
        parts.append(part + ".")
    return "\n  ".join(parts)


def fill_brief(
    *,
    pr: int,
    title: str,
    goal: str,
    rev: Path,
    sha: str,
    commits: list[str],
    section: str,
    notes: str,
    override: str | None = None,
    template: str | None = None,
) -> str:
    text = template if template is not None else BRIEF.read_text(encoding="utf-8")
    if override is not None:
        start, end = text.index(BODY_START), text.index(BODY_END)
        text = text[:start] + override.strip() + "\n\n" + text[end:]
    return Template(text).safe_substitute(
        pr=pr,
        title=title,
        goal=goal,
        rev=str(rev),
        sha=sha,
        commit_count=len(commits),
        round_section=section,
        commit_notes=notes,
    )


def prepare(
    repo: Path | str,
    pr: int,
    sha: str,
    *,
    round_no: int = 1,
    title: str = "",
    goal: str = "",
    base: str = "origin/dev",
    mechanical=(),
    moves=(),
    earlier: dict[int, str] | None = None,
    last_reviewed: str | None = None,
    root: Path | str | None = None,
    brief_override: str | None = None,
    total: int = MAX_ROUNDS,
) -> RoundInputs:
    """Build <root>/<pr>/round<N>/ afresh for ``sha``.

    ``earlier`` maps each earlier round number to its findings-and-answers text; ``last_reviewed`` is the head the
    previous round saw, so the fix commits since then go into round<N-1>-fixes.patch. The PR's commits and diff
    run from the merge base of ``base`` and ``sha`` (so a PR already squash-merged still shows its own diff)."""
    repo = Path(repo)
    sha = resolve(repo, sha)
    root = reviews_root(repo, root)
    # A round folder in a worktree's files would show up in its git status (and void the audit); git's own folder
    # (the default, <git-common-dir>/retrodev/reviews) never does.
    git_dir = common_dir(repo)
    for tree in worktrees(repo):
        if _inside(root, tree) and not _inside(root, git_dir):
            raise InputsError(f"the reviews folder {root} is inside the worktree {tree}; pick one outside")
    merge_base = git(repo, "merge-base", resolve(repo, base), sha).strip()
    rdir = root / str(pr) / f"round{round_no}"
    if rdir.exists():
        shutil.rmtree(rdir)
    src, review = rdir / "src", rdir / "review"
    review.mkdir(parents=True)
    export(repo, sha, src)

    spec = pathspec()
    log = git(repo, "log", "--no-merges", "--reverse", "--format=%h %s", f"{merge_base}..{sha}").splitlines()
    commits = [line for line in log if line.strip()]
    write = {"commits.txt": "\n".join(commits) + "\n"}
    write["stat.txt"] = git(repo, "diff", "--stat=150", "-M", merge_base, sha, *spec)
    write["diff.patch"] = git(repo, "diff", "-M30%", "-w", merge_base, sha, *spec)
    for line in commits:
        short = line.split(" ", 1)[0]
        write[f"commit-{short}.patch"] = git(repo, "show", "-M30%", "-w", "--format=fuller", short, *spec)
    earlier = dict(earlier or {})
    fixes: dict[int, str] = {}
    for k, text in earlier.items():
        write[f"round{k}-findings-and-answers.txt"] = text.rstrip() + "\n"
    if round_no > 1 and last_reviewed and earlier:
        last = resolve(repo, last_reviewed)
        k = max(earlier)
        ancestor = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", last, sha]).returncode == 0
        if ancestor and last != sha:
            fixes[k] = git(repo, "log", "-p", "--reverse", "-M30%", "-w", "--format=fuller", f"{last}..{sha}", *spec)
        elif last != sha:  # history rewritten: the whole range since the old head is not meaningful
            fixes[k] = git(repo, "diff", "-M30%", "-w", last, sha, *spec)
        if k in fixes:
            write[f"round{k}-fixes.patch"] = fixes[k]

    brief = review / "brief.md"
    write["brief.md"] = fill_brief(
        pr=pr,
        title=title,
        goal=goal,
        rev=rdir,
        sha=sha,
        commits=commits,
        section=round_section(round_no, earlier, fixes, total),
        notes=commit_notes(commits, mechanical, moves),
        override=brief_override,
    )
    for name, text in write.items():
        (review / name).write_text(text, encoding="utf-8")
    return RoundInputs(
        pr=pr,
        round=round_no,
        sha=sha,
        base=merge_base,
        dir=rdir,
        src=src,
        review=review,
        brief=brief,
        commits=commits,
        files=sorted(write),
    )
