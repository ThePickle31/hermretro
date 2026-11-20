"""The gates: rules a step must pass before retrodev does it. Each says what it protects and how to pass it.

A gate returns a Gate; ``enforce`` prints every gate (so an agent fixes all of them in one go) and raises one
Failure for the ones that did not pass, with the strictest exit code among them (3 when the owner must act).
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass

from . import checks, repo, state
from .output import FAILED, OWNER, Failure


@dataclass
class Gate:
    name: str
    ok: bool
    message: str = ""
    fix: str = ""
    code: int = FAILED


def passed(name: str, message: str = "") -> Gate:
    return Gate(name, True, message)


def enforce(ctx, gates: list[Gate], what: str) -> None:
    ctx.out.set(gates=[asdict(gate) for gate in gates])
    for gate in gates:
        ctx.out.say(f"  {'ok' if gate.ok else 'NO':>2}  {gate.name}" + (f": {gate.message}" if gate.message else ""))
        if not gate.ok:
            ctx.out.say(f"      FIX: {gate.fix}")
    failed = [gate for gate in gates if not gate.ok]
    if failed:
        raise Failure(
            f"{what} refused: {len(failed)} gate(s) did not pass ({', '.join(gate.name for gate in failed)})",
            failed[0].fix if len(failed) == 1 else "fix each gate above (each has its FIX line), then run it again",
            code=max(gate.code for gate in failed),
        )


BRANCH = re.compile(r"^([a-z]+)/([a-z0-9][a-z0-9._-]*)$")


def parse_branch(name: str, kinds: list[str]) -> tuple[str, str]:
    """(kind, topic) from feat/<topic>, fix/<topic>, docs/<topic> or chore/<topic>."""
    match = BRANCH.match(name or "")
    if not match or match.group(1) not in kinds:
        raise Failure(
            f"'{name}' is not a branch name this repository uses (the kind tells reviewers and the release notes "
            "what the change is)",
            "use <kind>/<topic> with kind one of " + ", ".join(kinds) + ", e.g. feat/retrodev-core",
        )
    return match.group(1), match.group(2)


def plan_approved(ctx, topic: str) -> Gate:
    plan = state.load_plan(ctx.top, topic)
    if plan and plan.get("approved"):
        return passed("plan approved", f"{plan['approved']['at']}: \"{plan['approved']['words']}\"")
    if not plan:
        message, fix = (
            f"there is no plan '{topic}': the owner approves a plan before work starts (the working agreement)",
            f"python tools/retrodev plan new {topic}, write it, show it to the owner",
        )
    else:
        message, fix = (
            f"the plan '{topic}' is not approved yet (the owner says start before work begins)",
            f'when the owner says start: python tools/retrodev plan approve {topic} --words "<their exact words>"',
        )
    return Gate("plan approved", False, message, fix, OWNER)


def plan_for(ctx, branch: str, record: dict) -> str | None:
    """The plan a branch's work needs approved, or None when it may go without one (docs and chore only).

    A record from start or plan link names its plan (None: started with --no-plan); a branch made by hand, or
    one whose record only check wrote, follows its kind: feat and fix need the plan named by their topic.
    """
    return state.plan_named(record, branch, ctx.policy["branches"]["no_plan"])  # only docs and chore go without


def plan_gate(ctx, branch: str, record: dict) -> Gate:
    """Ship's form of the working agreement's step 3: the owner approved the plan this branch works under."""
    named = plan_for(ctx, branch, record)
    if named is None:
        return passed("plan approved", "a small docs or chore change: no plan needed")
    if not state.NAME.match(named):
        return Gate(
            "plan approved",
            False,
            f"'{branch}' names no plan (a feat or fix change needs one the owner approved)",
            "python tools/retrodev plan link <topic> (or work on a branch <kind>/<topic>)",
            OWNER,
        )
    return plan_approved(ctx, named)


def on_work_branch(ctx, branch: str | None) -> Gate:
    protected = ctx.policy["branches"]["protected"]
    if not branch:
        return Gate("on a work branch", False, "HEAD is detached", "git switch <your branch>")
    if branch in protected:
        return Gate(
            "on a work branch",
            False,
            f"'{branch}' takes changes only through pull requests from a work branch",
            "python tools/retrodev start <kind>/<topic> (a worktree on its own branch)",
        )
    return passed("on a work branch", branch)


def committed(ctx) -> Gate:
    changes = repo.dirty(ctx.top)
    if changes:
        listed = ", ".join(line[3:] for line in changes[:5]) + (" ..." if len(changes) > 5 else "")
        return Gate(
            "committed and clean",
            False,
            f"{len(changes)} uncommitted change(s) ({listed}); a pull request holds only commits",
            "git add -A && git commit -m '<what changed>' (or remove the stray files)",
        )
    return passed("committed and clean")


def checks_on_tree(ctx, record: dict, digest: str) -> Gate:
    """The pass recorded for exactly this tree covered every check the policy requires of this change now."""
    missing = sorted(set(checks.required(ctx)) - set(record.get("passed_checks") or []))
    if record.get("passed_tree") == digest and not missing:
        return passed("checks passed on this tree", f"at {record.get('passed_at')}")
    if not record.get("passed_tree"):
        reason = "no passing check run is recorded"
    elif record["passed_tree"] != digest:
        reason = "the tree changed since"
    else:
        reason = f"the recorded pass did not include {', '.join(missing)}, which the policy now requires"
    return Gate(
        "checks passed on this tree",
        False,
        f"{reason}; what is pushed must be what passed the checks",
        "python tools/retrodev check",
    )


TITLE_LIMIT = 100  # characters: GitHub's list views and the release notes cut longer titles


def title_problems(title: str) -> list[str]:
    """Each thing wrong with a pull request title, naming its length when that is the problem."""
    said = (title or "").strip()
    if not said:
        return ["the title is empty"]
    problems = ["the title has more than one line"] if "\n" in said else []
    if said.endswith("."):
        problems.append("the title ends with a period")
    if len(said) > TITLE_LIMIT:
        problems.append(f"the title is {len(said)} characters; the limit is {TITLE_LIMIT}")
    return problems


def title_fixes(title: str) -> list[str]:
    """What to do about each of title_problems(title), in its order."""
    said = (title or "").strip()
    if not said:
        return ["give one plain sentence saying what the change does"]
    fixes = ["put it on one line"] if "\n" in said else []
    if said.endswith("."):
        fixes.append("drop the trailing period")
    if len(said) > TITLE_LIMIT:
        fixes.append(f"shorten it to {TITLE_LIMIT} characters or fewer (yours is {len(said)})")
    return fixes


def title_gate(title: str, where: str = "--title") -> Gate:
    problems = title_problems(title)
    if problems:
        return Gate(
            "title",
            False,
            "; ".join(problems) + " (it becomes the commit and the release-note line)",
            f"{where}: " + ", and ".join(title_fixes(title)),
        )
    return passed("title", title)


COMMENT = re.compile(r"<!--.*?-->", re.S)
UNCHECKED = re.compile(r"^\s*[-*]\s*\[ \]")
AGENT = re.compile(r"\bagents?\b", re.I)
MADE = re.compile(r"\b(made|built|wrote|written|created|opened|by)\b", re.I)
ATTRIBUTION = re.compile(r"^\s*made by an agent\b", re.I)  # the line ship writes; it fills no section
SEPARATOR = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")  # ends the last section: what follows is in none


def names_agent(line: str) -> bool:
    """A line like 'Made by an agent (Hermes) for the owner.' (the template asks who made the change)."""
    return bool(AGENT.search(line) and MADE.search(line))


def section_lines(text: str) -> dict[str, list[str]]:
    """{'## heading': its lines of content}: template comments, blank lines, unticked boxes and the attribution
    ('Made by an agent ...') are no content; a separator line ends the section (the attribution goes after one)."""
    found: dict[str, list[str]] = {}
    current = None
    for line in COMMENT.sub("", text).splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            current = heading.group(1)
            found.setdefault(current, [])
        elif SEPARATOR.match(line):
            current = None
        elif current is not None and line.strip() and not UNCHECKED.match(line) and not ATTRIBUTION.match(line):
            found[current].append(line)
    return found


def body_problems(text: str, sections: list[str]) -> list[str]:
    """What a pull request body lacks: an empty or missing template section, or the line naming the agent."""
    text = COMMENT.sub("", text)
    found = section_lines(text)
    problems = [f"section '## {name}' is missing" for name in sections if name not in found]
    problems += [f"section '## {name}' is empty" for name in sections if name in found and not found[name]]
    if not any(names_agent(line) for line in text.splitlines()):
        problems.append("no line says an agent made the change (e.g. 'Made by an agent (Hermes) for the owner.')")
    return problems


def body_gate(text: str | None, sections: list[str]) -> Gate:
    if text is None:
        return Gate(
            "body", False, "the body file does not exist", "--body <file> (fill in .github/pull_request_template.md)"
        )
    problems = body_problems(text, sections)
    if problems:
        return Gate(
            "body",
            False,
            "; ".join(problems) + " (the owner reads every section before approving)",
            "fill in every section of .github/pull_request_template.md in the body file",
        )
    return passed("body", "every section filled in")


def made_by(ctx, env=None) -> str:
    """The attribution: the agent (RETRODEV_AGENT, else Hermes) and the GitHub account (no GitHub remote: 'the
    owner'). The agent is always named, so the line agrees with agent_hint and the body gate takes it as written."""
    url = repo.git(["remote", "get-url", ctx.remote], ctx.top, check=False).strip()
    found = re.search(r"github\.com[:/]([^/]+)/", url)
    agent = (os.environ if env is None else env).get("RETRODEV_AGENT") or "Hermes"
    return f"Made by an agent ({agent}) for {'@' + found.group(1) if found else 'the owner'}."


GENERIC = ("Made by an agent (Hermes)", "Made by an agent for the owner")  # made_by's default; an older body's


def agent_hint(text: str | None, env=None) -> str:
    """While the body's Made by line names the default agent (or none, in a body an older retrodev wrote), or the
    body is still to be written without RETRODEV_AGENT: how to name the real one."""
    if (os.environ if env is None else env).get("RETRODEV_AGENT"):
        return ""
    if text is not None and not any(line in text for line in GENERIC):
        return ""
    said = "no agent" if text is not None and GENERIC[0] not in text else "no agent but Hermes"
    return (
        f"; its Made by line names {said}: name your agent and model there "
        "(RETRODEV_AGENT='<agent, model>' names it in a body start or ship writes)"
    )
