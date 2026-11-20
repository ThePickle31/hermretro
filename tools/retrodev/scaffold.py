"""`new`: add a feature, page, tab, tool, RPC, event, listener or slot in the repository's shape, in one command.

    new feature <name> [--purpose TEXT]        backend/<name>/ (front door, README), its tests, the registry lines
    new rpc <feature> <name> | <feature>.<name> [--module M] [--game]  an @rpc stub (its handler in
                                               backend/<feature>/<M>.py with --module; a `game` param that answers
                                               NO_GAME with --game), its test, its CONTRACT section, the generated names
    new tool <feature> <name> [--step R D] [--module M] [--[no-]project]   a Tool stub (in backend/<feature>/<M>.py with its own
                                               TOOLS with --module, or when tools.py is over 400 lines), its test,
                                               plugin.yaml, the page's step words, CONTRACT
    new event <feature> <name> [--payload P] [--when W]   the front door's EVENTS entry and its CONTRACT row
    new listener <feature> <event>             an @on stub in the feature's listeners.py, its test, the docs
    new page <id> [--label L]                  page/pages/<id>/ (descriptor, component, README), the registry line
    new tab <page> <id> [--label L] [--from-page]   page/pages/<page>/<id>/index.js, listed in the page's tabs
                                               (--from-page: a tabless page's own Page becomes this tab)
    new slot <page> <name> [--doc TEXT]        a slot the page declares for others to fill
    new contribution <page> <slot> <Component> a component of <page> filling another page's declared slot

Each writes code, its test, the docs and the one registry line from the templates in templates/<kind>/ ({key}
replaced; {{ and }} are literal braces), prints every file it created or changed, rebuilds the generated files
when the change needs it (policy.toml [generated] regenerate), runs the checks those files feed (not the install
scan: `check` runs it before ship; the page kinds run only lint, bundle and page, `check` runs unit) and prints the next step. --dry-run lists the files, prints the unified diff of each and writes nothing;
--no-check skips the checks, --no-build the rebuild (for several `new` in a row: the last one rebuilds). It
refuses a name that exists or breaks the naming rules, and writes only on a work branch (never dev or main; a
--dry-run, which writes nothing, runs anywhere).
"""

from __future__ import annotations

import ast
import difflib
import keyword
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import checks, repo, state
from .output import Failure, cmd

TEMPLATES = Path(__file__).resolve().with_name("templates")
SNAKE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
KEBAB = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
CAMEL = re.compile(r"^[a-z][a-zA-Z0-9]{0,39}$")
KEY = re.compile(r"\{(\w+)\}")


def words(name: str) -> list[str]:
    return [part for part in re.split(r"[_\-]", name) if part]


def pascal(name: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in words(name))


def const(name: str) -> str:
    return "_".join(part.upper() for part in words(name))


def label(name: str) -> str:
    text = " ".join(words(name))
    return text[:1].upper() + text[1:]


def camel(name: str) -> str:
    parts = words(name)
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:]) if parts else name


def check_name(name: str, rule: re.Pattern, what: str, example: str) -> str:
    if not rule.match(name or "") or keyword.iskeyword(name) or name.endswith(("_", "-")):
        raise Failure(
            f"'{name}' is not a usable {what} name: it becomes a folder, a Python or JavaScript name and a doc entry",
            f"use {'lowercase letters, digits and underscores' if rule is SNAKE else 'lowercase letters, digits and dashes' if rule is KEBAB else 'a camelCase word'}, e.g. {example}",
        )
    return name


def one_line(text: str, what: str) -> str:
    if "\n" in text or "|" in text or not text.strip():
        raise Failure(
            f"the {what} must be one line without '|' (it goes into a table row)", f"pass --{what} 'one line'"
        )
    return text.strip()


def js_label(text: str | None, fallback: str, what: str = "label") -> str:
    """A page or tab label or a slot's doc, once it is safe inside a quoted JavaScript string and a // comment: no
    quote, backslash, line terminator (U+2028 and U+2029 included) or other unprintable character (the templates
    and descriptor edits interpolate it)."""
    text = one_line(text or fallback, what)
    if any(char in "'\\" or not char.isprintable() for char in text):
        raise Failure(
            f"the {what} {text!r} goes into a quoted JavaScript string: no quotes, backslashes or line breaks; "
            "nothing was written",
            f"pass --{what} 'plain words' (letters, digits, spaces and punctuation other than ' and \\)",
        )
    return text


def render(kind: str, file: str, **values: str) -> str:
    """A template with each {key} of ``values`` replaced; other {...} stay, then {{ and }} become braces."""
    text = (TEMPLATES / kind / file).read_text(encoding="utf-8")
    text = KEY.sub(lambda match: str(values[match.group(1)]) if match.group(1) in values else match.group(0), text)
    return text.replace("{{", "{").replace("}}", "}")


def parses(rel: str, text: str) -> str:
    """``text``, once it is known to be valid Python when ``rel`` is a Python file: a plan never holds broken code
    (it is built whole in memory and written only after every file of it was made)."""
    if rel.endswith(".py"):
        try:
            ast.parse(text, rel)
        except SyntaxError as error:
            raise Failure(
                f"new would write invalid Python to {rel} (line {error.lineno}: {error.msg}); nothing was written",
                "change the words that broke it, or make the change by hand",
            ) from None
    return text


@dataclass
class Plan:
    """The files one `new` creates or changes, applied together (or only listed, on a dry run)."""

    top: Path
    created: dict[str, str] = field(default_factory=dict)
    changed: dict[str, str] = field(default_factory=dict)
    regenerate: bool = False
    stdlib_only: tuple[str, ...] = ()  # policy.toml [new]: features new adds no rpc, tool or event to
    notes: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    done: list[str] = field(default_factory=list)  # edits new made that a reader might take for steps left
    dry_run: bool = False
    skip_checks: list[str] = field(default_factory=list)  # affected checks not to run now (a note says why)
    only_checks: tuple[str, ...] = ()  # when set, the affected checks new may run (the page kinds: PAGE_CHECKS)

    def exists(self, rel: str) -> bool:
        return rel in self.created or (self.top / rel).exists()

    def read(self, rel: str) -> str:
        if rel in self.created:
            return self.created[rel]
        if rel in self.changed:
            return self.changed[rel]
        path = self.top / rel
        if not path.is_file():
            raise Failure(f"{rel} is missing; the change needs it", f"restore it (git checkout -- {rel})")
        return path.read_text(encoding="utf-8")

    def create(self, rel: str, text: str) -> None:
        if self.exists(rel):
            raise Failure(f"{rel} exists already; new never overwrites a file", "pick another name, or edit it by hand")
        self.created[rel] = parses(rel, text)

    def ensure(self, rel: str, text: str) -> None:
        if not self.exists(rel):
            self.created[rel] = parses(rel, text)

    def edit(self, rel: str, change) -> None:
        before = self.read(rel)
        after = parses(rel, change(before))
        if after == before:
            return
        if rel in self.created:
            self.created[rel] = after
        else:
            self.changed[rel] = after

    def paths(self) -> list[str]:
        return sorted({*self.created, *self.changed})

    def diff(self) -> str:
        """The unified diff of every file the plan creates or changes, from its in-memory edits."""
        parts = []
        for rel in self.paths():
            before = "" if rel in self.created else (self.top / rel).read_text(encoding="utf-8")
            after = self.created.get(rel, self.changed.get(rel, ""))
            old = "/dev/null" if rel in self.created else f"a/{rel}"
            lines = difflib.unified_diff(
                before.splitlines(keepends=True), after.splitlines(keepends=True), old, f"b/{rel}"
            )
            parts.append(
                "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in lines)
            )
        return "".join(parts)


def insert_after(text: str, anchor: re.Pattern, line: str, where: str, last: bool = True) -> str:
    """``line`` after the last (or first) line matching ``anchor``."""
    lines = text.split("\n")
    hits = [index for index, current in enumerate(lines) if anchor.search(current)]
    if not hits:
        raise Failure(f"{where}: found no line to add after ({anchor.pattern})", f"add this line by hand: {line}")
    at = hits[-1] if last else hits[0]
    return "\n".join(lines[: at + 1] + [line] + lines[at + 1 :])


def insert_before(text: str, anchor: re.Pattern, block: str, where: str) -> str:
    lines = text.split("\n")
    for index, current in enumerate(lines):
        if anchor.search(current):
            return "\n".join(lines[:index] + block.split("\n") + lines[index:])
    raise Failure(f"{where}: found no line to add before ({anchor.pattern})", "add it by hand:\n" + block)


def section(text: str, heading: str) -> tuple[int, int]:
    """(start, end) character offsets of a Markdown section's body, up to the next heading of its level or above."""
    match = re.search(rf"^{re.escape(heading)}\n", text, re.M)
    if not match:
        raise Failure(f"no '{heading}' section", f"restore the '{heading}' heading")
    if heading.startswith("["):  # a TOML table runs to the next table
        after = re.search(r"^\[", text[match.end() :], re.M)
    else:
        level = len(heading) - len(heading.lstrip("#"))
        after = re.search(rf"^#{{1,{level}}} ", text[match.end() :], re.M)
    return match.end(), match.end() + after.start() if after else len(text)


def in_section(text: str, heading: str, change) -> str:
    start, end = section(text, heading)
    return text[:start] + change(text[start:end]) + text[end:]


def readme_item(text: str, label_text: str, item: str, only_none: bool = False) -> str:
    """Add ``item`` to a README line such as '- RPCs: none.' or '**Tabs:** none.' (its first sentence: 'none'
    becomes the item, else it is appended). Unchanged when there is no such line, or (``only_none``) when the
    sentence already lists something: the caller then reminds the author."""
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if not line.lstrip("-* ").startswith(label_text):
            continue
        head, sep, rest = line.partition(label_text)
        end = re.search(r"\.(?=\s|$)", rest)
        segment, tail = (rest[: end.start()], rest[end.start() :]) if end else (rest, "")
        if re.search(r"\bnone\b", segment):
            segment = re.sub(r"\bnone\b", lambda _match: item, segment, count=1)
        elif only_none:
            return text
        else:
            segment = segment.rstrip() + ", " + item
        lines[index] = head + sep + segment + tail
        return "\n".join(lines)
    return text


def guard(ctx) -> str:
    branch = repo.branch(ctx.top)
    policy = ctx.policy["branches"]
    if not branch or branch in policy["protected"]:  # any work branch: ship and land take any name (a takeover's)
        raise Failure(
            f"new writes code only on a work branch, and this checkout is on {branch or 'a detached HEAD'}",
            "python tools/retrodev start feat/<topic> (a worktree on its own branch), then run new there (--dry-run "
            "lists the files from here)",
        )
    return branch


def affected(ctx, paths: list[str]) -> list[str]:
    """The fast checks whose inputs these files are, without the install scan (check runs it before ship)."""
    inputs = ctx.policy["checks"]["inputs"]
    return [
        name
        for name in ctx.policy["checks"]["fast"]
        if name != "scan" and any(repo.matches(p, inputs[name]) for p in paths)
    ]


def shown(command: list[str]) -> str:
    return cmd(*["python" if word == sys.executable else word for word in command])


# The page kinds touch no Python the unit tests import (page/, tests/page/registry.test.mjs, the generated bundle):
# their own checks are these, and `check` runs unit before ship. The backend kinds keep unit.
PAGE_CHECKS = ("lint", "bundle", "page")
SCAFFOLD_CHECK = "RETRODEV_SCAFFOLD_CHECK"  # tests/repo/test_placeholders.py skips its gate while it is set


def validate(ctx, names: list[str]) -> None:
    """The checks right after writing the stubs: without the placeholder gate (the stubs are not filled in yet), so
    their results are not kept as passes (the branch's own record is put back: `check` runs the gate before ship)."""
    branch = repo.branch(ctx.top)
    kept = state.load_branch(ctx.top, branch)
    try:  # the gate's switch goes only to the checks' processes: os.environ is shared by every thread
        checks.run(ctx, names, env={SCAFFOLD_CHECK: "1"})
    finally:
        state.save_branch(ctx.top, kept)


def apply(ctx, plan: Plan, what: str, dry_run: bool, run_checks: bool, build: bool = True) -> int:
    out = ctx.out
    verb = "would " if dry_run else ""
    for rel in sorted(plan.created):
        out.say(f"{verb}create  {rel}")
    for rel in sorted(plan.changed):
        out.say(f"{verb}change  {rel}")
    regenerate = [ctx.command(words) for words in ctx.policy["generated"]["regenerate"]] if plan.regenerate else []
    if regenerate and not build:
        plan.next_steps.insert(0, "rebuild the generated files: " + "; ".join(shown(c) for c in regenerate))
        regenerate = []
    for command in regenerate:
        out.say(f"{verb}run     {shown(command)}")
    for note in plan.notes:
        out.say("note: " + note)
    out.set(what=what, created=sorted(plan.created), changed=sorted(plan.changed), dry_run=dry_run)
    out.set(regenerate=[shown(command) for command in regenerate], next=plan.next_steps, done=plan.done)
    if dry_run:
        diff = plan.diff()
        out.set(diff=diff)
        out.say(diff.rstrip("\n"))
        out.say("dry run: nothing was written")
        return 0
    for rel, text in {**plan.created, **plan.changed}.items():
        path = ctx.top / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    python = [rel for rel in plan.paths() if rel.endswith(".py")]
    ruff = ctx.top / ".dev" / "py" / "bin" / "ruff"
    if python and ruff.is_file():  # the one formatting (tools/check.py fix does the same); without ruff, as written
        repo.run([str(ruff), "format", "--config", "tools/py/ruff.toml", "-q", *python], ctx.top, timeout=120)
    for command in regenerate:
        code, stdout, stderr = repo.run(command, ctx.top, timeout=300)
        if code:
            raise Failure(
                f"{shown(command)} failed after the files were written: {(stderr or stdout).strip()[-400:]}",
                f"fix what it names, then run {shown(command)} again (the new files stay; git status lists them)",
            )
    names = [name for name in affected(ctx, plan.paths()) if name not in plan.skip_checks] if run_checks else []
    names = [name for name in names if name in plan.only_checks] if plan.only_checks else names
    if names:
        out.say("checks: " + " ".join(names))
        validate(ctx, names)
    for item in plan.done:
        out.say("done: " + item)
    for step in plan.next_steps:
        out.say("next: " + step)
    out.say("then: " + then(ctx, plan.paths()))
    return 0


def then(ctx, paths: list[str]) -> str:
    """The steps after new's own: a branch the clean install covers commits first (it installs the committed tree,
    so check refuses uncommitted changes then). Decided over the whole branch, as check decides it (its changes
    since it left the base, plus this scaffold's files), not over the latest scaffold alone."""
    branch = set(repo.changed_files(ctx.top, ctx.remote_base) or []) | set(paths)
    if any(repo.matches(path, ctx.policy["checks"]["triggers"].get("clean_install", [])) for path in branch):
        return (
            "commit (git add -A && git commit; the clean install that check adds installs the committed tree), "
            "then python tools/retrodev check, then python tools/retrodev ship"
        )
    return "python tools/retrodev check, commit, python tools/retrodev ship"


def run(ctx, args) -> int:
    from . import (  # the kinds; they import this module
        scaffold_backend,
        scaffold_contribution,
        scaffold_listener,
        scaffold_page,
        scaffold_tool,
    )

    if not args.dry_run:  # a dry run writes nothing, so a planner may list the files from dev or main
        guard(ctx)
    plan = Plan(ctx.top, stdlib_only=tuple(ctx.policy.get("new", {}).get("stdlib_only", ())), dry_run=args.dry_run)
    kind = args.kind
    if kind == "feature":
        what = scaffold_backend.feature(plan, args.name, args.purpose)
    elif kind == "rpc":
        target, name = args.target, args.name
        if name is None:
            target, dot, name = target.partition(".")
            if not dot or not name:
                raise Failure(
                    f"new rpc needs a feature and a name, as two words or <feature>.<name>; got '{args.target}'",
                    "python tools/retrodev new rpc library recent (or: new rpc library.recent)",
                )
        what = scaffold_backend.rpc_(plan, target, name, args.module, bool(getattr(args, "game", False)))
    elif kind == "listener":
        what = scaffold_listener.listener(plan, args.target, args.name)
    elif kind == "tool":
        what = scaffold_tool.tool(plan, args.target, args.name, args.step, args.module, args.project)
    elif kind == "event":
        what = scaffold_backend.event(plan, args.target, args.name, args.payload, args.when)
    elif kind == "page":
        what = scaffold_page.page(plan, args.name, args.label)
    elif kind == "tab":
        what = scaffold_page.tab(plan, args.target, args.name, args.label, getattr(args, "from_page", False))
    elif kind == "contribution":
        what = scaffold_contribution.contribution(plan, args.target, args.name, args.component)
    else:
        what = scaffold_page.slot(plan, args.target, args.name, args.doc)
    if kind in ("page", "tab", "slot", "contribution"):
        plan.only_checks = PAGE_CHECKS
    return apply(ctx, plan, what, args.dry_run, not args.no_check, not getattr(args, "no_build", False))
