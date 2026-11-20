"""Friction the eighth round of fresh-agent trials found in `new`: rpc --game's next steps gave a page query without
the game (its key, its params, where it runs, callStudio or callStudioOnly) and its help no rule for `game` versus
`id`; a tool's test called Tool.handler, which pyright sees as Optional; a listener took only **_payload; a slot's
README line ran on after its doc and its next steps named neither tests/page file it changes; page named none of
the places that list the pages; tool --project worked only in library. Each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_eight_new
"""

import argparse
import ast
import re
import shutil
import tomllib
import unittest
from typing import Any

from retrodev import cli, scaffold_rpc

from tests.retrodev.fixture import git, parallel, write
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase

load_tests = parallel
EVENT = "library.build_reported"


def joined(out) -> str:
    return " ".join(out["next"])


def help_of(*path: str) -> str:
    """The --help text of a subcommand (``new rpc``), formatted without printing it."""
    found = cli.parser()
    for name in path:
        found = next(a for a in found._actions if isinstance(a, argparse._SubParsersAction)).choices[name]
    return " ".join(found.format_help().split())


class Rpc(ScaffoldCase):
    def test_the_module_suggestion_reads_the_one_size_rule(self):  # follow-up of #60: one source for the size
        warn = tomllib.loads((ROOT / "tools/layout.toml").read_text())["size"]["warn"]
        self.assertEqual(scaffold_rpc.big_rpcs(), warn - scaffold_rpc.MODULE_MARGIN)
        self.assertIn(f"over {warn - scaffold_rpc.MODULE_MARGIN} lines", help_of("new", "rpc"))
        size = len(self.read("backend/history/rpcs.py").splitlines())
        for threshold, noted in ((size - 1, True), (size, False)):  # the tree's own layout.toml decides
            layout = self.read("tools/layout.toml")
            write(self.tree, "tools/layout.toml", re.sub(r"(?m)^warn = \d+", f"warn = {threshold + 50}", layout))
            git(self.tree, "add", "-A")
            git(self.tree, "commit", "-q", "-m", f"warn at {threshold + 50}")
            out = self.new("rpc", "history", f"rdprobe_sized{threshold}", "--dry-run", as_json=False)
            self.assertEqual("note: backend/history/rpcs.py has" in out, noted, threshold)

    def test_game_s_next_steps_key_and_call_with_the_game_where_the_game_is(self):
        steps = joined(self.new("rpc", "history", "rdprobe_card", "--game"))
        self.assertIn("run the query in the component that has the game", steps)
        self.assertIn("queryKey: [ID, 'rdprobe_card', viaProfile, game.id]", steps)
        self.assertIn("callStudio(RPC_RDPROBE_CARD, { game: game.id })", steps)
        self.assertIn("callStudioOnly for one that reads or binds a profile's Build conversations", steps)
        backend = (ROOT / "page/app/backend.js").read_text()  # the rule's source says the same
        self.assertIn(
            "RPCs that read or bind a profile's conversations (build, builds, build_restore, asset*)", backend
        )
        self.assertNotIn("game.id", joined(self.new("rpc", "history", "rdprobe_plain")))

    def test_game_s_help_states_the_game_or_id_rule_and_follows_builds(self):
        help_text = help_of("new", "rpc")
        self.assertIn("the rule: a game's library id is `game`", help_text)
        self.assertIn("the older player, captures, game_thumb and capture_image keep `id`", help_text)
        rows = {
            row.split("|")[1].strip(" `"): row.split("|")[2]
            for row in (ROOT / "docs/dev/CONTRACT.md").read_text().splitlines()
            if row.startswith("| `")
        }
        self.assertIn("{ game }", rows["builds"])  # what --game follows
        self.assertIn("{ id }", rows["captures"])  # what the rule names as the older form


class Tool(ScaffoldCase):
    def test_the_tool_test_calls_the_handler_function_itself(self):
        self.new("tool", "history", "rdprobe_peek")
        test = self.read("tests/backend/history/test_tool_rdprobe_peek.py")
        self.assertIn("from backend.history.tools import rdprobe_peek_handler", test)
        self.assertIn("rdprobe_peek_handler({})", test)
        self.assertNotIn(".handler(", test)
        self.new("tool", "history", "rdprobe_more", "--module", "rdprobe_more_tools")
        test = self.read("tests/backend/history/test_tool_rdprobe_more.py")
        self.assertIn("from backend.history.rdprobe_more_tools import rdprobe_more_handler", test)
        self.assertIn("rdprobe_more_handler", self.read("backend/history/rdprobe_more_tools.py"))

    def test_project_outside_library_is_refused_without_the_shared_helpers(self):
        out = self.new("tool", "history", "rdprobe_proj", "--project", code=1)
        self.assertIn("backend/hermes/tool_args.py", out["error"]["message"])
        self.assertIn("python tools/retrodev sync", out["error"]["fix"])
        self.assertEqual(git(self.tree, "status", "--porcelain"), "")

    def test_project_outside_library_imports_the_shared_helpers(self):
        write(self.tree, "backend/hermes/tool_args.py", (ROOT / "backend/hermes/tool_args.py").read_text())  # #60's
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "The shared helpers")
        out = self.new("tool", "history", "rdprobe_proj", "--project")
        source = self.read("backend/history/tools.py")
        self.assertIn("from ..hermes.tool_args import tool_error, tool_project", source)
        self.assertIn('tool_project("chromatic_rdprobe_proj", args, kwargs)', source)
        self.assertIn("a tool about the selected game: host.library_game_for([root])", joined(out))
        self.assertNotIn("--project", joined(self.new("tool", "history", "rdprobe_flat")))


class Listener(ScaffoldCase):
    def test_the_listener_takes_the_event_s_payload_keys_keyword_only(self):
        shutil.copyfile(ROOT / "backend/library/__init__.py", self.tree / "backend/library/__init__.py")
        self.new("feature", "rdprobe_ears")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Probe feature")
        self.new("listener", "rdprobe_ears", EVENT)
        source = self.read("backend/rdprobe_ears/listeners.py")
        self.assertIn("def on_library_build_reported(*, game, assets, **_payload) -> None:", source)
        scope = {"on": lambda _name: lambda function: function}
        exec(compile(source.replace("from ..system.events import on", ""), "listeners.py", "exec"), scope)
        listener = scope["on_library_build_reported"]
        self.assertIsNone(listener(game="g", assets=[], later="a key added later"))
        with self.assertRaises(TypeError):
            listener(game="g")  # a key the event carries is missing: it fails where it is called
        ast.parse(self.read("tests/backend/rdprobe_ears/test_listener_on_library_build_reported.py"))

    def test_a_payload_key_named_like_the_catch_all_keeps_the_listener_valid(self):  # review 1, 0
        self.new("event", "history", "rdprobe_caught", "--payload", "_payload, _rest, game")
        emits = self.read("backend/history/emits.py")  # the emitter's own names (emit) never meet these keys
        heard = []
        scope: dict[str, Any] = {"emit": lambda name, **kw: heard.append((name, kw))}
        exec(compile(emits.replace("from ..system.events import emit", ""), "emits.py", "exec"), scope)
        scope["rdprobe_caught"](_payload=1, _rest=2, game="g")
        self.assertEqual(heard, [("history.rdprobe_caught", {"_payload": 1, "_rest": 2, "game": "g"})])
        self.new("feature", "rdprobe_ears")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Probe event and feature")
        self.new("listener", "rdprobe_ears", "history.rdprobe_caught")
        source = self.read("backend/rdprobe_ears/listeners.py")
        self.assertIn("def on_history_rdprobe_caught(*, _payload, _rest, game, **_rest2) -> None:", source)
        scope: dict[str, Any] = {"on": lambda _name: lambda function: function}
        exec(compile(source.replace("from ..system.events import on", ""), "listeners.py", "exec"), scope)
        listener = scope["on_history_rdprobe_caught"]
        self.assertIsNone(listener(_payload=1, _rest=2, game="g", later="a key added later"))
        ast.parse(self.read("tests/backend/rdprobe_ears/test_listener_on_history_rdprobe_caught.py"))


class Slot(ScaffoldCase):
    def test_the_readme_line_ends_the_doc_before_contributes(self):
        self.new("page", "rdprobe-shelf")
        out = self.new("slot", "rdprobe-shelf", "more", "--doc", "Buttons after the lede. Props: { ctx }")
        line = next(r for r in self.read("page/pages/rdprobe-shelf/README.md").splitlines() if "**Slots:**" in r)
        self.assertEqual(
            line, "**Slots:** declares `rdprobe-shelf.more` (buttons after the lede. Props: { ctx }). Contributes none."
        )
        steps = joined(out)
        self.assertIn("add a HOSTS recipe for 'rdprobe-shelf.more' in tests/page/slots.test.mjs", steps)
        self.assertIn("a contribution changes the `filled` assertion in tests/page/registry.test.mjs", steps)
        self.assertIn("'Events and slots today' line of docs/dev/STUDIO-PAGES.md", steps)
        self.assertIn("const filled =", (ROOT / "tests/page/registry.test.mjs").read_text())
        self.assertIn("HOSTS", (ROOT / "tests/page/slots.test.mjs").read_text())


class Page(ScaffoldCase):
    def test_the_next_steps_name_every_place_that_lists_the_pages(self):
        steps = joined(self.new("page", "rdprobe-board"))
        self.assertIn("README.md 'What works today'", steps)
        self.assertIn("docs/dev/CONTRACT.md 'Studio pages (desktop) and their RPCs'", steps)
        self.assertIn("the Pages table of docs/dev/STUDIO-PAGES.md", steps)
        self.assertIn("## What works today", (ROOT / "README.md").read_text())
        self.assertIn("## Studio pages", (ROOT / "docs/dev/CONTRACT.md").read_text())
        self.assertIn("## Pages", (ROOT / "docs/dev/STUDIO-PAGES.md").read_text())


if __name__ == "__main__":
    unittest.main()
