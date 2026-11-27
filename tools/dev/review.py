"""python tools/dev review VERB --pass N: the bookkeeping of a pull request's review (tools/review/README.md). The
reviewers and the author do the reading; this pins what they read, writes their briefs, starts the author's answers
and puts the outcome in the pull request.

  prepare   the pass's tier and briefs, in notes/reviews/<branch>/<pass>/, pinned to the pushed head in a detached
            checkout beside the worktree for the reviewers to read (the worktree stays free)
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
import review_tier as tier

CAP = 3
BASE = "origin/dev"
KINDS = {  # a review: its template, findings and answers files
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

    def pushed_head(self) -> str:
        if git(self.root, "status", "--porcelain").strip():
            raise ReviewError("the worktree has uncommitted changes\nFIX: commit them, push, then run this again")
        head = git(self.root, "rev-parse", "HEAD").strip()
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
            found.append(record)
            n += 1
        return found

    # -- prepare -------------------------------------------------------------------------------------------------
    def prepare(self, n: int, over_cap: bool = False) -> str:
        if n > CAP and not over_cap:
            raise ReviewError(f"a review stops after pass {CAP}\nFIX: --over-cap, only when the owner asked for it")
        if n > 1 and self.load(n - 1, "record.json") is None:
            raise ReviewError(f"pass {n - 1} is not recorded\nFIX: python tools/dev review record --pass {n - 1}")
        if self.load(n, "pass.json") is not None:
            raise ReviewError(f"pass {n} is prepared already, its reviewers may be reading it\nFIX: take it first")
        decisions = self.folder / "decisions.md"
        if not decisions.is_file():
            raise ReviewError(f"{decisions} is missing\nFIX: write what the owner approved there first")
        head = self.pushed_head()
        if n == 1:
            changed = self.changed(f"{BASE}...{head}")
            judged = tier.judge(changed)
            scope, diff, security = "the whole change", f"git diff {BASE}...{head}", judged.tier == tier.SENSITIVE
        else:
            first = self.load(1, "pass.json")
            last = self.load(n - 1, "pass.json")
            judged = tier.Judged(first["tier"], tuple(first["reasons"]))
            if last["head"] == head:
                raise ReviewError(f"pass {n - 1} reviewed {head[:10]} already\nFIX: commit and push what changes first")
            changed = self.changed(f"{last['head']}..{head}")
            needs = tier.later(changed)
            if needs == tier.NOTHING:
                raise ReviewError(f"what changed since pass {n - 1} is documentation alone: it needs no pass")
            scope = (
                f"the tests changed since pass {n - 1}, alone"
                if needs == tier.TESTS
                else f"what changed since pass {n - 1}, and how it fits the rest of the change"
            )
            diff = f"git diff {last['head']}..{head}"
            security = judged.tier == tier.SENSITIVE and (
                any(tier.sensitive(file.path) for file in changed) or self.security_fixed(n - 1)
            )
        if judged.tier == tier.LIGHT:
            return "Tier light: Markdown and tests alone, so no review. Its Review section says `Tier light · not reviewed`."
        folder = self.pass_folder(n)
        folder.mkdir(parents=True, exist_ok=True)
        checkout = self.checkout(n)
        git(self.root, "worktree", "add", "--detach", str(checkout), head)
        kinds = ["code", "security"] if security else ["code"]
        values = {
            "branch": self.branch,
            "head": head,
            "checkout": str(checkout),
            "scope": scope,
            "diff": diff,
            "purpose": self.purpose(),
            "decisions": str(decisions),
            "rules": str(checkout / "tools" / "review" / "rules.md"),
            "reading": self.reading(checkout, [file.path for file in changed]),
            "earlier": self.earlier(n),
        }
        written = []
        for kind in kinds:
            template, brief, found, _answers = KINDS[kind]
            text = (checkout / "tools" / "review" / template).read_text(encoding="utf-8")
            brief_path = folder / brief
            brief_path.write_text(fill(text, {**values, "findings": str(folder / found)}), encoding="utf-8")
            written.append(brief_path)
        reasons = {"tier": judged.tier, "reasons": list(judged.reasons)}
        (folder / "pass.json").write_text(
            json.dumps({"pass": n, "head": head, "scope": scope, "kinds": kinds, **reasons}, indent=2) + "\n",
            encoding="utf-8",
        )
        why = f" ({'; '.join(judged.reasons)})" if judged.reasons else ""
        lines = [f"Pass {n}, tier {judged.tier}{why}, pinned to {head[:10]} in {checkout}."]
        lines += [f"  {path}" for path in written]
        lines.append(
            "Start each brief's reviewer with delegate_task, its model as hermretro-dev-maintain's table says."
        )
        return "\n".join(lines)

    def security_fixed(self, n: int) -> bool:
        record = self.load(n, "record.json") or {}
        return any(
            o["security"] and o["label"] == "Important" and o["answer"] == "fixed" for o in record.get("outcomes", [])
        )

    def purpose(self) -> str:
        view = json.loads(gh(self.root, "pr", "view", self.branch, "--json", "title,body"))
        parts = [view["title"]] + [
            section for name in ("Summary", "Why") if (section := pr_section(view["body"], name))
        ]
        return "\n>\n".join("> " + part.replace("\n", "\n> ") for part in parts)

    def reading(self, checkout: Path, paths: list[str]) -> str:
        lines = [f"- {checkout / 'AGENTS.md'}: how code here is written, and the rules that protect users."]
        for prefixes, page in READING:
            if any(path.startswith(prefixes) for path in paths) and (checkout / page).is_file():
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
            _template, _brief, found, answers = KINDS[kind]
            if not (folder / found).is_file():
                raise ReviewError(f"{folder / found} is missing\nFIX: wait for that reviewer's answer")
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
        if "security" in prepared["kinds"] and not security_model:
            raise ReviewError("this pass had a security review\nFIX: --security-model <the model that ran it>")
        folder, outcomes = self.pass_folder(n), []
        for kind in prepared["kinds"]:
            _template, _brief, found, answers = KINDS[kind]
            if not (folder / answers).is_file():
                raise ReviewError(f"{folder / answers} is missing\nFIX: python tools/dev review take --pass {n}")
            parsed, _dropped = findings.parse((folder / found).read_text(encoding="utf-8"))
            for done in findings.answers(parsed, (folder / answers).read_text(encoding="utf-8")):
                outcomes.append(
                    {
                        "label": done.finding.label,
                        "what": done.finding.what,
                        "answer": done.answer,
                        "reason": done.reason,
                        "security": kind == "security",
                    }
                )
        recorded_head = self.pushed_head()
        record = {"pass": n, "head": prepared["head"], "recorded_head": recorded_head, "model": model,
                  "security_model": security_model, "outcomes": outcomes}  # fmt: skip
        (folder / "record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        self.write_review_section(prepared["tier"])
        if any(o["label"] == "Important" and o["answer"] == "fixed" for o in outcomes):
            if n >= CAP:
                return (
                    f"Pass {n} recorded. An Important was fixed, but a review stops after pass {CAP}: tell the owner."
                )
            return (
                f"Pass {n} recorded. An Important was fixed: pass {n + 1} reads what changed (prepare --pass {n + 1})."
            )
        return f"Pass {n} recorded. No Important was fixed: no other pass, unless commits come after this."

    def write_review_section(self, tier_name: str) -> None:
        body = json.loads(gh(self.root, "pr", "view", self.branch, "--json", "body"))["body"]
        new = replace_section(body, "Review", review_text(tier_name, self.recorded()))
        path = self.folder / "pr-body.md"
        path.write_text(new, encoding="utf-8")
        gh(self.root, "pr", "edit", self.branch, "--body-file", str(path))

    # -- status --------------------------------------------------------------------------------------------------
    def status(self) -> str:
        records = self.recorded()
        head = git(self.root, "rev-parse", "HEAD").strip()
        if not records:
            first = self.load(1, "pass.json")
            if first:
                return f"Tier {first['tier']}. Pass 1 is prepared: take it once its reviewers answered."
            judged = tier.judge(self.changed(f"{BASE}...{head}"))
            return f"Tier {judged.tier}. No pass yet: prepare --pass 1 once the pull request is open and pushed."
        last = records[-1]
        tier_name = self.load(1, "pass.json")["tier"]
        lines = [f"Tier {tier_name}. {len(records)} pass(es) recorded."]
        needs = tier.later(self.changed(f"{last['recorded_head']}..{head}")) if last["recorded_head"] != head else None
        fixed = any(o["label"] == "Important" and o["answer"] == "fixed" for o in last["outcomes"])
        if fixed or needs in (tier.PASS, tier.TESTS):
            n = last["pass"] + 1
            lines.append(f"Next: pass {n}" if n <= CAP else f"Next: nothing; a pass {n} only when the owner asks")
        else:
            lines.append("Next: nothing; the review is done")
        return "\n".join(lines)


def fill(template: str, values: dict) -> str:
    """template with each {{key}} replaced, from the template alone so a value's own text stays as it is."""

    def value(match: re.Match) -> str:
        if match.group(1) not in values:
            raise ReviewError(f"the template names {{{{{match.group(1)}}}}}, which prepare doesn't fill")
        return str(values[match.group(1)])

    return re.sub(r"\{\{(\w+)\}\}", value, template)


def pr_section(body: str, name: str) -> str:
    match = re.search(rf"(?ms)^## {re.escape(name)}\n(.*?)(?=^## |\Z)", body)
    return match.group(1).strip() if match else ""


def replace_section(body: str, name: str, text: str) -> str:
    pattern = rf"(?ms)^## {re.escape(name)}\n.*?(?=^## |\Z)"
    section = f"## {name}\n{text}\n"
    if re.search(pattern, body):
        return (
            re.sub(pattern, lambda _m: section + ("\n" if not section.endswith("\n\n") else ""), body, count=1).rstrip()
            + "\n"
        )
    return body.rstrip() + "\n\n" + section


def review_text(tier_name: str, records: list[dict]) -> str:
    """The pull request's Review section: a line per pass, the answers that left something, and what is left."""
    passes = []
    for record in records:
        models = record["model"] + (f" + {record['security_model']}" if record.get("security_model") else "")
        tally: dict[str, int] = {}
        for o in record["outcomes"]:
            key = f"{o['label']} {o['answer']}"
            tally[key] = tally.get(key, 0) + 1
        said = ", ".join(f"{count} {key}" for key, count in tally.items()) or "no findings"
        passes.append(f"pass {record['pass']} ({models}): {said}")
    lines = [f"Tier {tier_name} · " + " · ".join(passes) + "."]
    kept = [
        (r["pass"], o)
        for r in records
        for o in r["outcomes"]
        if o["answer"] in ("wrong", "intentional", "declined", "kept")
    ]
    left = [(r["pass"], o) for r in records for o in r["outcomes"] if o["answer"] == "noted"]
    if kept:
        lines += ["", "Answered without a change:"] + [
            f"- Pass {n}, {o['label']} {o['answer']}: {o['what']} — {o['reason']}" for n, o in kept
        ]
    if left:
        lines += ["", "Left for after the merge:"] + [f"- {o['label']}: {o['what']}" for _n, o in left]
    return "\n".join(lines)
