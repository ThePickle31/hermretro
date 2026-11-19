"""No feature README offers a `retrodev new` that `new` refuses there.

Every `python tools/retrodev new <kind> <feature> ...` that a feature README (backend/<feature>/README.md) offers,
with a concrete kind and feature, is planned with the scaffold functions `new` itself runs (tools/retrodev/
scaffold_backend.py, scaffold_listener.py): its placeholders become a fresh name (for a listener, an event that
feature does not hear yet), and any refusal (a stdlib-only feature in policy.toml [new], a TOOLS factory, a front
door without EVENTS, ...) fails this test. Planning writes nothing: scaffold.Plan keeps the files in memory, as on
`new --dry-run`. Generic lines (`new <kind> <feature> ...`, `new rpc|tool|event <that feature>`) name no single
command and are not planned.
"""

import re
import shlex
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from retrodev import scaffold, scaffold_backend, scaffold_listener  # noqa: E402 - tools/ goes on sys.path first
from retrodev.output import Failure  # noqa: E402 - tools/ goes on sys.path first

OFFERED = re.compile(r"python tools/retrodev new ([a-z]+) ([a-z_]+)(?=[\s`])([^`\n]*)")
PROBE = "readme_probe"  # a name no feature uses


def offered(text: str) -> list[tuple[str, str, str]]:
    return [match.groups() for match in OFFERED.finditer(text)]


def stdlib_only() -> tuple[str, ...]:
    policy = tomllib.loads((ROOT / "tools" / "retrodev" / "policy.toml").read_text(encoding="utf-8"))
    return tuple(policy.get("new", {}).get("stdlib_only", ()))


def unheard_event(plan: scaffold.Plan, feature: str) -> str:
    listeners = ROOT / "backend" / feature / "listeners.py"
    heard = listeners.read_text(encoding="utf-8") if listeners.is_file() else ""
    free = [
        event
        for event in sorted(scaffold_listener.declared_events(plan))
        if not event.startswith(f"{feature}.") and f'@on("{event}")' not in heard
    ]
    return free[0] if free else ""


def refusal(kind: str, feature: str, rest: str) -> str:
    """'' when `new <kind> <feature> <rest>` would be accepted on this tree, else why it is refused."""
    plan = scaffold.Plan(ROOT, stdlib_only=stdlib_only())
    words = shlex.split(re.sub(r"<[^>]*>(?:\.<[^>]*>)?", PROBE, rest))
    name = words[0] if words and not words[0].startswith("--") else PROBE
    options = {word: words[at + 1 : at + 3] for at, word in enumerate(words) if word in ("--step", "--payload")}
    try:
        if kind == "rpc":
            scaffold_backend.rpc_(plan, feature, name)
        elif kind == "tool":
            scaffold_backend.tool(plan, feature, name, options.get("--step"))
        elif kind == "event":
            scaffold_backend.event(plan, feature, name, (options.get("--payload") or [None])[0])
        elif kind == "listener":
            name = unheard_event(plan, feature) if name == PROBE else name
            if name:  # with every declared event heard already, there is nothing left to offer a listener for
                scaffold_listener.listener(plan, feature, name)
        else:
            return f"'{kind}' is not a backend kind this test plans (rpc, tool, event, listener)"
    except Failure as refused:
        return refused.message
    return ""


class ReadmeScaffoldTests(unittest.TestCase):
    def test_every_offered_scaffold_is_one_new_accepts(self):
        refused = []
        for readme in sorted(ROOT.glob("backend/*/README.md")):
            for kind, feature, rest in offered(readme.read_text(encoding="utf-8")):
                why = refusal(kind, feature, rest)
                if why:
                    refused.append(f"{readme.relative_to(ROOT)}: new {kind} {feature}{rest}: {why}")
        self.assertEqual(
            refused,
            [],
            "\nthese READMEs offer a `retrodev new` that new refuses there:\n  "
            + "\n  ".join(refused)
            + "\nFIX: offer the path that works instead (the owning feature's new, or the edit by hand and where)",
        )

    def test_the_planner_tells_a_refused_scaffold_from_an_accepted_one(self):
        self.assertTrue(refusal("tool", stdlib_only()[0], '<name> --step "<while it runs>" "<once done>"'))
        self.assertTrue(refusal("rpc", "no_such_feature", "<name>"))
        self.assertTrue(refusal("tool", "hermes", '<name> --step "<while it runs>" "<once done>"'))  # TOOLS() factory
        self.assertTrue(refusal("event", "hermes", '<name> --payload "..."'))  # no EVENTS dict in its front door
        self.assertEqual(refusal("rpc", "library", "<name>"), "")
        self.assertEqual(refusal("listener", "history", "<feature>.<event>"), "")

    def test_offered_reads_only_concrete_commands(self):
        text = "`python tools/retrodev new <kind> library <name>` or `python tools/retrodev new rpc|tool|event <x> ...`"
        self.assertEqual(offered(text), [])
        self.assertEqual(offered("`python tools/retrodev new rpc library <name>`"), [("rpc", "library", " <name>")])


if __name__ == "__main__":
    unittest.main()
