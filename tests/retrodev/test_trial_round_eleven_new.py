"""Friction the eleventh round of fresh-agent trials found in `new`: event put the separating comma inside the
previous EVENTS value's parentheses (a parenthesised implicit concatenation became a one-element tuple) and wrote
the new entry as one long line; its CONTRACT row listed bare keys; contribution --dry-run refused a slot a plan
declares first, and listed an edit it made as a next step; slot's README line nested parentheses; listener listed
every emitting-feature test that mocks host helpers, emitting or not; tool and rpc --game lacked a step each. Each
test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_eleven_new
"""

import ast
import inspect

from retrodev import scaffold_source

from tests import support
from tests.retrodev.fixture import git, parallel, retrodev_docs, write
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase

load_tests = parallel
LINE_LENGTH = 120  # tools/py/ruff.toml

# A front door shaped like backend/library/__init__.py: each EVENTS value a parenthesised implicit concatenation.
DOOR = '''"""The games library (a probe of its front door's shape)."""

__all__ = []

EVENTS = {
    "library.build_reported": (
        "chromatic_build_report accepted a build card; game=<library id, str; None without a project>, "
        "assets=[the absolute image paths it shows, list of str]"
    ),
    "library.game_presented": (
        "chromatic_present_game showed a game beside the chat; game=<library id, str>, root=<the project folder, str>"
    ),
}
'''
WHEN = (
    "chromatic_present_game showed a game beside the chat and the player loaded it in the emulator tab, ready to play"
)


def joined(out) -> str:
    return " ".join(out["next"])


def events_of(text: str) -> dict:
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "EVENTS":
            return ast.literal_eval(node.value)
    raise AssertionError("no EVENTS")


class Event(ScaffoldCase):
    def library_door(self) -> None:
        write(self.tree, "backend/library/__init__.py", DOOR)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "library door")

    def test_a_parenthesised_previous_value_stays_a_string_and_the_entry_wraps(self):
        self.library_door()
        payload = "game=<library id, str>, root=<the project folder, str>"
        self.new("event", "library", "rdprobe_loaded", "--payload", payload, "--when", WHEN)
        self.new("event", "library", "rdprobe_again", "--payload", "game=<library id, str>", "--when", WHEN)
        door = self.read("backend/library/__init__.py")
        events = events_of(door)
        for name, value in events.items():
            self.assertIsInstance(value, str, f"{name} became {type(value).__name__}:\n{door}")
        self.assertEqual(
            list(events),
            ["library.build_reported", "library.game_presented", "library.rdprobe_loaded", "library.rdprobe_again"],
        )
        self.assertTrue(events["library.rdprobe_loaded"].endswith(payload), events["library.rdprobe_loaded"])
        long = [line for line in door.splitlines() if len(line) > LINE_LENGTH]
        self.assertEqual(long, [], door)
        self.assertIn('    "library.rdprobe_loaded": (\n        "', door)  # wrapped as the file wraps its own

    def test_the_comma_goes_after_a_closing_parenthesis_in_tools_too(self):
        text = "TOOLS = (\n    a,\n    (b)\n)\n"
        done = scaffold_source.append_entry(text, "tools.py", "    c,")
        self.assertEqual(len(ast.parse(done).body[0].value.elts), 3, done)  # not (b,) as one element
        self.assertIn("    (b),\n    c,\n", done)

    def test_the_contract_row_says_what_each_key_holds(self):
        self.library_door()
        payload = "game=<library id, str>, root=<the project folder, str>, count"
        self.new("event", "library", "rdprobe_counted", "--payload", payload, "--when", "it counted")
        row = next(line for line in self.read("docs/dev/CONTRACT.md").splitlines() if "library.rdprobe_counted" in line)
        self.assertEqual(
            row,
            "| `library.rdprobe_counted` | `game` (library id, str), `root` (the project folder, str), `count` (<...>) "
            "| it counted | — |",
        )
        self.assertIn("`` `key` (what it holds) `` per `--payload` part", retrodev_docs("REFERENCE.md"))


class Contribution(ScaffoldCase):
    def host(self, declared: bool) -> None:
        self.new("page", "rdprobe-host")
        if declared:
            self.new("slot", "rdprobe-host", "extra", "--doc", "Buttons at the end. Props: { ctx }")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "probe host")

    def test_a_dry_run_previews_a_slot_not_declared_yet_and_the_real_run_refuses(self):
        self.host(declared=False)
        out = self.new("contribution", "home", "rdprobe-host.extra", "RdprobeItem", "--dry-run", as_json=False)
        self.assertIn("note: slot not declared yet: run new slot rdprobe-host extra first", out)
        self.assertIn("dry run: nothing was written", out)
        out = self.new("contribution", "home", "rdprobe-host.extra", "RdprobeItem", code=1)
        self.assertIn("no page declares the slot 'rdprobe-host.extra'", out["error"]["message"])
        self.assertIn("with `--dry-run` only, a slot of an existing host page", retrodev_docs("REFERENCE.md"))

    def test_the_registry_edit_it_made_is_done_not_next(self):
        self.host(declared=True)
        out = self.new("contribution", "home", "rdprobe-host.extra", "RdprobeItem")
        self.assertTrue(any("added RdprobeItem to the `filled` assertion" in line for line in out["done"]), out)
        self.assertFalse([step for step in out["next"] if "added RdprobeItem" in step], out["next"])
        text = self.new("contribution", "home", "rdprobe-host.extra", "RdprobeOther", as_json=False)
        self.assertIn("done: tests/page/registry.test.mjs: added RdprobeOther", text)


class Slot(ScaffoldCase):
    def test_the_readme_line_reads_as_the_emulator_page_s(self):
        self.new("page", "rdprobe-shelf")
        self.new("slot", "rdprobe-shelf", "more", "--doc", "Buttons after the lede (one per page). Props: { ctx }")
        line = next(r for r in self.read("page/pages/rdprobe-shelf/README.md").splitlines() if "**Slots:**" in r)
        self.assertEqual(
            line,
            "**Slots:** declares `rdprobe-shelf.more`: buttons after the lede (one per page). Props: `{ ctx }`. "
            "Contributes none.",
        )
        emulator = (ROOT / "page/pages/emulator/README.md").read_text()
        self.assertIn("**Slots:** declares `emulator.barActions`: ", emulator)


MOCK = "from unittest import mock\nmock.patch.object(hermes_host, '_chat_project', f)\n"


class Listener(ScaffoldCase):
    def test_only_tests_that_emit_the_event_are_listed(self):
        self.new("event", "history", "rdprobe_moved", "--payload", "game=<id>", "--when", "a probe moved")
        write(
            self.tree,
            "backend/history/mover.py",
            "from .emits import rdprobe_moved\n\n\ndef relocate(game):\n    rdprobe_moved(game=game)\n",
        )
        write(self.tree, "tests/backend/history/test_rdmover.py", MOCK + "mover.relocate('g')\n")
        write(self.tree, "tests/backend/history/test_rdemits.py", MOCK + "emits.rdprobe_moved(game='g')\n")
        write(self.tree, "tests/backend/history/test_rdother.py", MOCK + "snapshots.keep('g')\n")
        self.new("feature", "rdprobe_ears")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "probe event, its caller and tests")
        steps = self.new("listener", "rdprobe_ears", "history.rdprobe_moved")["next"]
        mocked = next(s for s in steps if "mock backend.hermes.host helpers" in s)
        self.assertIn("tests/backend/history/test_rdmover.py (_chat_project)", mocked)
        self.assertIn("tests/backend/history/test_rdemits.py (_chat_project)", mocked)
        self.assertNotIn("test_rdother.py", mocked)
        self.assertIn("these tests emit history.rdprobe_moved", mocked)


class ToolAndRpc(ScaffoldCase):
    def test_a_project_tool_names_the_library_game_helper_with_its_real_signature(self):
        for name in ("__init__.py", "tool_args.py"):
            write(self.tree, f"backend/library/{name}", (ROOT / f"backend/library/{name}").read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "tool_args")
        steps = joined(self.new("tool", "library", "rdprobe_picked"))
        self.assertIn(
            "a test for the selected game: `game, root = make_library_game(self.home, name)` from tests.support", steps
        )
        self.assertEqual(list(inspect.signature(support.make_library_game).parameters), ["home", "name"])
        self.assertIn("self.home = isolated_home(self)", self.read("tests/backend/library/test_tool_rdprobe_picked.py"))

    def test_a_game_rpc_says_to_check_what_games_returns_first(self):
        steps = joined(self.new("rpc", "history", "rdprobe_rom", "--game"))
        self.assertIn(
            "check what the `games` RPC already returns about a game (rom, state, web, ...) before adding a per-game "
            "query",
            steps,
        )
