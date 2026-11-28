"""python tools/dev review VERB --pass N: the bookkeeping of a pull request's review (tools/review/README.md). The
reviewers and the author do the reading; this pins what they read, writes their briefs, starts the author's answers
and puts the outcome in the pull request.

  prepare   the pass's tier and briefs, in notes/reviews/<branch>/<pass>/, pinned to the pushed head in a detached
            checkout beside the worktree for the reviewers to read (the worktree stays free); for a light change,
            the Review section saying it is not reviewed
  take      once the reviewers wrote their findings: removes that checkout and starts answers.md
  record    refuses an unanswered finding, writes the pass's outcome into the pull request's Review section, and
            says whether another pass runs
  status    the tier, the passes so far, and what is next

Standard library only, with git and gh."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import review_findings as findings
import review_pr
import review_tier as tier

CAP = 3
BASE = "origin/dev"
KINDS = {  # a review: its template, its brief, findings and answers files
    "code": ("brief.md", "brief.md", "findings.md", "answers.md"),
    "security": ("security.md", "security-brief.md", "security-findings.md", "security-answers.md"),
}
# What a reviewer reads besides AGENTS.md and the rules, by the paths the change touches.
READING = (
    (
        ("backend/", "__init__.py", "plugin.yaml"),
        ".agents/skills/hermretro-dev-architecture/references/architecture.md",
    ),
    (("page/", "player/"), ".agents/skills/hermretro-dev-page/SKILL.md"),
    (("tests/", "tools/ci/", ".github/"), ".agents/skills/hermretro-dev-testing/references/testing.md"),
    (("engine/",), "engine/README.md"),
)


class ReviewError(Exception):
    """A step that cannot run as asked; the message says what to do."""


def git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if done.returncode:
        raise ReviewError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout


def gh(root: Path, *args: str) -> str:
    try:
        done = subprocess.run(["gh", *args], cwd=root, capture_output=True, text=True)
    except FileNotFoundError:
        raise ReviewError("gh is not installed\nFIX: install the GitHub CLI and sign in (gh auth login)") from None
    if done.returncode:
        raise ReviewError(
            f"gh {' '.join(args)}: {done.stderr.strip()}\nFIX: open the pull request first (gh pr create)"
        )
    return done.stdout


def fixed(outcome: dict) -> bool:
    """Whether an answer changed the code."""
    return outcome["answer"] in ("fixed", "changed")


class Review:
    """One branch's review, from the worktree at root."""

    def __init__(self, root: Path):
        self.root = Path(git(root, "rev-parse", "--show-toplevel").strip())
        self.branch = git(self.root, "branch", "--show-current").strip()
        if not self.branch:
            raise ReviewError("not on a branch\nFIX: review from the change's worktree")
        self.slug = self.branch.replace("/", "-")
        self.folder = self.root / "notes" / "reviews" / self.slug

    def pass_folder(self, n: int) -> Path:
        return self.folder / str(n)

    def checkout(self, n: int) -> Path:
        return self.root.parent / f".review-{self.slug}-{n}"

    def load(self, n: int, name: str) -> dict | None:
        path = self.pass_folder(n) / name
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def changed(self, revisions: str) -> list[tier.Changed]:
        return tier.numstat(git(self.root, "diff", "--numstat", "--no-renames", "-z", revisions))

    def judged(self, head: str) -> tier.Judged:
        return tier.judge(self.changed(f"{BASE}...{head}"))

    def head(self) -> str:
        return git(self.root, "rev-parse", "HEAD").strip()

    def pushed_head(self) -> str:
        if git(self.root, "status", "--porcelain").strip():
            raise ReviewError("the worktree has uncommitted changes\nFIX: commit them, push, then run this again")
        head = self.head()
        try:
            upstream = git(self.root, "rev-parse", "@{u}").strip()
        except ReviewError:
            upstream = ""
        if upstream != head:
            raise ReviewError("HEAD is not pushed\nFIX: git push, then run this again")
        return head

    def recorded(self) -> list[dict]:
        found, n = [], 1
        while (record := self.load(n, "record.json")) is not None:
            found.append({"tier": (self.load(n, "pass.json") or {}).get("tier"), **record})
            n += 1
        return found

    def due(self, head: str) -> tuple[int, str] | None:
        """The pass that is due at head, and what it reads (tier.PASS or tier.TESTS), or None when none is: after a
        fixed Important, or commits no answer accounts for, past what needs no pass (tools/review/README.md)."""
        records = self.recorded()
        if not records:
            return 1, tier.PASS
        last = records[-1]
        if last["head"] == head:
            return None
        needs = tier.later(self.changed(f"{last['head']}..{head}"))
        if needs == tier.NOTHING:
            return None
        if any(o["label"] == "Important" and fixed(o) for o in last["outcomes"]):
            return last["pass"] + 1, needs
        # Commits before the record answer its findings in the files the findings that changed the code name, and
        # nowhere else; commits after it answer none.
        answered = {o["what"].split(":", 1)[0] for o in last["outcomes"] if fixed(o)}
        before = last["recorded_head"]
        unaccounted = (
            [f for f in self.changed(f"{last['head']}..{before}") if f.path not in answered]
            if before != last["head"]
            else []
        )
        unaccounted += self.changed(f"{before}..{head}") if before != head else []
        if unaccounted and tier.later(unaccounted) != tier.NOTHING:
            return last["pass"] + 1, needs
        return None

    # -- prepare -------------------------------------------------------------------------------------------------
    def prepare(self, n: int, over_cap: bool = False) -> str:
        if n < 1 or n > CAP + 1:
            raise ReviewError(f"a pass is numbered 1 to {CAP}, or {CAP + 1} when the owner asked for it")
        if n > CAP and not over_cap:
            raise ReviewError(f"a review stops after pass {CAP}\nFIX: --over-cap, only when the owner asked for it")
        if self.load(n, "pass.json") is not None:
            raise ReviewError(f"pass {n} is prepared already, its reviewers may be reading it\nFIX: take it first")
        decisions = self.folder / "decisions.md"
        if not decisions.is_file():
            raise ReviewError(f"{decisions} is missing\nFIX: write what the owner approved there first")
        head = self.pushed_head()
        judged = self.judged(head)
        if n == 1 and judged.tier == tier.LIGHT:
            self.write_review_section([])
            return "Tier light: Markdown and tests alone, so no review. The Review section says so."
        due = self.due(head)
        if due is None:
            raise ReviewError(f"no pass is due: {self.status()}")
        if due[0] != n:
            raise ReviewError(f"the pass due is {due[0]}, not {n}\nFIX: prepare --pass {due[0]}")
        if n == 1:
            scope, diff, kinds = "the whole change", f"git diff {BASE}...{head}", ["code"]
            paths = [file.path for file in self.changed(f"{BASE}...{head}")]
            if judged.tier == tier.SENSITIVE:
                kinds.append("security")
        else:
            last = self.load(n - 1, "record.json")
            delta = self.changed(f"{last['head']}..{head}")
            paths = [file.path for file in delta]
            if due[1] == tier.TESTS:
                scope = f"the tests changed since pass {n - 1}, alone"
                diff = f"git diff {last['head']}..{head} -- tests/"
                paths = [path for path in paths if tier.is_test(path)]
            else:
                scope = f"what changed since pass {n - 1}, and how it fits the rest of the change"
                diff = f"git diff {last['head']}..{head}"
            security = any(tier.sensitive(path) for path in paths) or any(
                o["security"] and fixed(o) for o in last["outcomes"]
            )
            kinds = ["code", "security"] if security else ["code"]
        # Everything that can fail before the reviewers' checkout is made: the purpose and the templates.
        purpose = self.purpose()
        templates = {kind: git(self.root, "show", f"{head}:tools/review/{KINDS[kind][0]}") for kind in kinds}
        checkout, folder = self.checkout(n), self.pass_folder(n)
        values = {
            "branch": self.branch,
            "head": head,
            "checkout": str(checkout),
            "scope": scope,
            "diff": diff,
            "purpose": purpose,
            "decisions": str(decisions),
            "rules": str(checkout / "tools" / "review" / "rules.md"),
            "reading": self.reading(checkout, head, paths),
            "earlier": self.earlier(n),
        }
        briefs = {kind: fill(templates[kind], {**values, "findings": str(folder / KINDS[kind][2])}) for kind in kinds}
        git(self.root, "worktree", "add", "--detach", str(checkout), head)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            for kind, text in briefs.items():
                (folder / KINDS[kind][1]).write_text(text, encoding="utf-8")
            state = {
                "pass": n,
                "head": head,
                "scope": scope,
                "kinds": kinds,
                "tier": judged.tier,
                "reasons": list(judged.reasons),
            }
            (folder / "pass.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        except BaseException:
            git(self.root, "worktree", "remove", "--force", str(checkout))
            raise
        why = f" ({'; '.join(judged.reasons)})" if judged.reasons else ""
        lines = [f"Pass {n}, tier {judged.tier}{why}, pinned to {head[:10]} in {checkout}."]
        lines += [f"  {folder / KINDS[kind][1]}" for kind in kinds]
        lines.append(
            "Start each brief's reviewer with delegate_task, its model as hermretro-dev-maintain's table says."
        )
        return "\n".join(lines)

    def purpose(self) -> str:
        view = json.loads(gh(self.root, "pr", "view", self.branch, "--json", "title,body"))
        parts = [view["title"]] + [
            text for name in ("Summary", "Why") if (text := review_pr.section(view["body"], name))
        ]
        return "\n>\n".join("> " + part.replace("\n", "\n> ") for part in parts)

    def reading(self, checkout: Path, head: str, paths: list[str]) -> str:
        lines = [f"- {checkout / 'AGENTS.md'}: how code here is written, and the rules that protect users."]
        for prefixes, page in READING:
            if any(path.startswith(prefixes) for path in paths) and git(self.root, "ls-tree", head, page).strip():
                lines.append(f"- {checkout / page}: how the parts this change touches are built.")
        return "\n".join(lines)

    def earlier(self, n: int) -> str:
        if n == 1:
            return ""
        folders = ", ".join(str(self.pass_folder(k)) for k in range(1, n))
        return f"\nEarlier passes' findings and the answers to them are in {folders}: don't raise again what they settled.\n"

    # -- take ----------------------------------------------------------------------------------------------------
    def take(self, n: int) -> str:
        prepared = self.load(n, "pass.json")
        if prepared is None:
            raise ReviewError(f"pass {n} is not prepared\nFIX: python tools/dev review prepare --pass {n}")
        folder, lines = self.pass_folder(n), []
        for kind in prepared["kinds"]:
            if not (folder / KINDS[kind][2]).is_file():
                raise ReviewError(f"{folder / KINDS[kind][2]} is missing\nFIX: wait for that reviewer's answer")
        for kind in prepared["kinds"]:
            _template, _brief, found, answers = KINDS[kind]
            parsed, dropped = findings.parse((folder / found).read_text(encoding="utf-8"))
            if not (folder / answers).exists():
                (folder / answers).write_text(findings.skeleton(parsed), encoding="utf-8")
            counts = ", ".join(f"{sum(f.label == label for f in parsed)} {label}" for label in findings.ANSWERS)
            lines.append(f"{kind}: {counts}" + (f" ({dropped} Nits past {findings.NITS} dropped)" if dropped else ""))
            lines.append(f"  answer them in {folder / answers}")
        if self.checkout(n).exists():
            git(self.root, "worktree", "remove", "--force", str(self.checkout(n)))
        return "\n".join(lines)

    # -- record --------------------------------------------------------------------------------------------------
    def record(self, n: int, model: str, security_model: str | None = None) -> str:
        prepared = self.load(n, "pass.json")
        if prepared is None:
            raise ReviewError(f"pass {n} is not prepared\nFIX: python tools/dev review prepare --pass {n}")
        if self.load(n, "record.json") is not None:
            raise ReviewError(f"pass {n} is recorded already")
        if "security" in prepared["kinds"] and not security_model:
            raise ReviewError("this pass had a security review\nFIX: --security-model <the model that ran it>")
        folder, outcomes = self.pass_folder(n), []
        for kind in prepared["kinds"]:
            _template, _brief, found, answers = KINDS[kind]
            if not (folder / answers).is_file():
                raise ReviewError(f"{folder / answers} is missing\nFIX: python tools/dev review take --pass {n}")
            parsed, _dropped = findings.parse((folder / found).read_text(encoding="utf-8"))
            for done in findings.answers(parsed, (folder / answers).read_text(encoding="utf-8")):
                outcomes.append({"label": done.finding.label, "what": done.finding.what, "answer": done.answer,
                                 "reason": done.reason, "security": kind == "security"})  # fmt: skip
        # A first attempt whose publishing failed keeps the head it recorded: what came after it is still unanswered.
        pending = folder / "record.pending.json"
        recorded_head = json.loads(pending.read_text())["recorded_head"] if pending.is_file() else self.pushed_head()
        record = {"pass": n, "tier": prepared["tier"], "head": prepared["head"], "recorded_head": recorded_head,
                  "model": model, "security_model": security_model, "outcomes": outcomes}  # fmt: skip
        pending.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        self.write_review_section([*self.recorded(), record])
        pending.replace(folder / "record.json")
        return f"Pass {n} recorded. {self.next_step(self.due(self.head()))}"

    @staticmethod
    def next_step(due: tuple[int, str] | None) -> str:
        if due is None:
            return "No other pass is due."
        if due[0] == CAP + 1:
            return (
                f"Another pass is due, but a review stops after pass {CAP}: a pass {CAP + 1} only when the owner asks."
            )
        if due[0] > CAP + 1:
            return f"Another pass is due, past pass {CAP + 1}: the review is over, tell the owner."
        return f"Pass {due[0]} is due: prepare --pass {due[0]}."

    def write_review_section(self, records: list[dict]) -> None:
        body = json.loads(gh(self.root, "pr", "view", self.branch, "--json", "body"))["body"]
        path = self.folder / "pr-body.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(review_pr.replace_section(body, "Review", review_pr.review_text(records)), encoding="utf-8")
        gh(self.root, "pr", "edit", self.branch, "--body-file", str(path))

    # -- status --------------------------------------------------------------------------------------------------
    def status(self) -> str:
        head, records = self.head(), self.recorded()
        latest = next((p for n in range(CAP + 1, 0, -1) if (p := self.load(n, "pass.json"))), None)
        tier_name = latest["tier"] if latest else self.judged(head).tier
        if tier_name == tier.LIGHT and not records:
            return "Tier light: no review. prepare --pass 1 writes `Tier light · not reviewed` into the Review section."
        prepared = [
            p for n in range(1, CAP + 2) if (p := self.load(n, "pass.json")) and not self.load(n, "record.json")
        ]
        if prepared:
            return f"Tier {tier_name}. Pass {prepared[0]['pass']} is prepared: take it once its reviewers answered."
        return f"Tier {tier_name}. {len(records)} pass(es) recorded. {self.next_step(self.due(head))}"


def fill(template: str, values: dict) -> str:
    """template with each {{key}} replaced, from the template alone so a value's own text stays as it is."""

    def value(match: re.Match) -> str:
        if match.group(1) not in values:
            raise ReviewError(f"the template names {{{{{match.group(1)}}}}}, which prepare doesn't fill")
        return str(values[match.group(1)])

    return re.sub(r"\{\{(\w+)\}\}", value, template)
