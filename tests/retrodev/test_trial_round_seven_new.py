"""Friction the seventh round of fresh-agent trials found in `new`: rpc --module left the README's RPCs line
without its module, an event's emitter took **payload and its test emitted example=1, a listener's test called it
with example=1 and its next steps said nothing of what to test, of path-only payloads or of the emitter's mocked
tests, a tool's name was missing from CONTRACT's list of plugin-owned tools, a taken tab id was refused without
saying what holds it, and rpc gave no hint where a page's query goes and no --game shape. Each test failed before
its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_seven_new
"""

import ast
import re
import unittest

from tests.retrodev.fixture import git, parallel, write
from tests.retrodev.hand_edits import line_of
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase

load_tests = parallel


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


class Rpc(ScaffoldCase):
    def test_module_names_its_module_on_the_readme_rpcs_line(self):
        before = line_of(self.read("backend/history/README.md"), "- RPCs")
        self.new("rpc", "history", "rdprobe_pong", "--module", "rdprobe_pong_rpcs")
        after = line_of(self.read("backend/history/README.md"), "- RPCs")
        self.assertTrue(after.startswith("- RPCs (`rpcs.py`, `rdprobe_pong_rpcs.py`): "), after)
        self.assertEqual(
            after.split("): ", 1)[1].split("`rdprobe_pong`")[0], before.split("): ", 1)[1].split(".")[0] + ", "
        )

    def test_next_steps_say_where_a_page_s_query_goes(self):
        steps = self.new("rpc", "history", "rdprobe_recent")["next"]
        self.assertIn(
            "in a page: put the useQuery in the page's own Page component (e.g. Games in page/pages/games/games-page.js) "
            "and pass the result down as a prop; extend tests/page/page-<page>.test.mjs",
            steps,
        )
        self.assertIn("export function Games(", (ROOT / "page/pages/games/games-page.js").read_text())

    def test_game_takes_a_game_answers_no_game_and_its_test_registers_one(self):
        self.new("feature", "rdprobe_g")
        write(self.tree, "backend/rdprobe_g/rpcs.py", '"""RPCs."""\n\nfrom ..hermes.declare import rpc\n')
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Probe without host")
        out = self.new("rpc", "rdprobe_g", "rdprobe_info", "--game")
        source = self.read("backend/rdprobe_g/rpcs.py")
        self.assertIn("from ..hermes import host", source)  # the guard needs it: added where it was missing
        self.assertIn("root = host._game_root(game)", source)
        self.assertIn('"code": "NO_GAME"', source)
        test = self.read("tests/backend/rdprobe_g/test_rpc_rdprobe_info.py")
        tree = ast.parse(test)
        top = [ast.unparse(node) for node in tree.body if isinstance(node, ast.ImportFrom)]
        self.assertFalse([line for line in top if "make_library_game" in line], "imported inside the test only")
        self.assertIn("from tests.support import make_library_game", test)
        self.assertIn('make_library_game(self.home, "Probe")', test)
        self.assertIn("### `rdprobe_info` — params `{ game }`", self.read("docs/dev/CONTRACT.md"))
        self.assertTrue(any("make_library_game(home, name)" in step for step in out["next"]), out["next"])
        self.new("rpc", "rdprobe_g", "rdprobe_more", "--game", "--module", "rdprobe_more_rpcs")
        self.assertIn("host._game_root(game)", self.read("backend/rdprobe_g/rdprobe_more_rpcs.py"))


class Event(ScaffoldCase):
    def test_the_emitter_takes_the_payload_keys_and_its_test_emits_them(self):
        payload = "game=<id>, fields=[the fields it changed]"
        self.new("event", "history", "rdprobe_edited", "--payload", payload, "--when", "after `builds` answered")
        emits = self.read("backend/history/emits.py")
        self.assertIn("def rdprobe_edited(*, game, fields) -> None:", emits)
        self.assertIn('emit("history.rdprobe_edited", game=game, fields=fields)', emits)
        heard = []
        code = compile(emits.replace("from ..system.events import emit", ""), "emits.py", "exec")
        scope = {"emit": lambda name, **kw: heard.append((name, kw))}
        exec(code, scope)  # the generated emitter, with a stand-in emit
        scope["rdprobe_edited"](game="g", fields=["x"])
        self.assertEqual(heard, [("history.rdprobe_edited", {"game": "g", "fields": ["x"]})])
        with self.assertRaises(TypeError):
            scope["rdprobe_edited"](game="g")  # a missing key fails where it is called
        test = self.read("tests/backend/history/test_event_rdprobe_edited.py")
        self.assertIn('emits.rdprobe_edited(game="sample game", fields="sample fields")', test)
        self.assertIn('self.assertEqual(heard, [{"game": "sample game", "fields": "sample fields"}])', test)
        door = self.read("backend/history/__init__.py")
        self.assertIn(
            '"history.rdprobe_edited": "after builds answered; game=<id>, fields=[the fields it changed]"', door
        )
        self.assertIn(
            "| `history.rdprobe_edited` | `game`, `fields` | after `builds` answered |",
            self.read("docs/dev/CONTRACT.md"),
        )

    def test_a_payload_without_keys_keeps_payload(self):
        self.new("event", "history", "rdprobe_any")
        self.assertIn("def rdprobe_any(**payload) -> None:", self.read("backend/history/emits.py"))
        self.assertIn("emits.rdprobe_any(example=1)", self.read("tests/backend/history/test_event_rdprobe_any.py"))


class Listener(ScaffoldCase):
    def test_the_test_calls_it_with_the_declared_keys_and_the_next_steps_say_what_to_test(self):
        self.new("event", "history", "rdprobe_moved", "--payload", "path, root", "--when", "a probe moved")
        write(
            self.tree,
            "tests/backend/history/test_probe_mocks.py",
            "mock.patch.object(hermes_host, '_chat_project', f)\n",
        )
        self.new("feature", "rdprobe_ears")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Probe event and feature")
        steps = self.new("listener", "rdprobe_ears", "history.rdprobe_moved")["next"]
        test = self.read("tests/backend/rdprobe_ears/test_listener_on_history_rdprobe_moved.py")
        self.assertIn('listeners.on_history_rdprobe_moved(path="sample path", root="sample root")', test)
        self.assertTrue(any(s.startswith("test what the listener does, not only that it runs") for s in steps), steps)
        self.assertIn(
            "find the library game with host.library_game_for([path]); in tests register one with "
            "tests.support.make_library_game(home, name) -> (game_id, root)",
            steps,
        )
        mocked = next(s for s in steps if "mock backend.hermes.host helpers" in s)
        self.assertIn("tests/backend/history/test_probe_mocks.py (_chat_project)", mocked)


class Tool(ScaffoldCase):
    def test_the_contract_sentence_names_the_new_tool_last(self):
        contract = flat(self.read("docs/dev/CONTRACT.md"))
        total = int(re.search(r"(\d+) in total", contract).group(1))
        sentence = contract[contract.index("tools, plus") : contract.index(f"{total} in total")]
        self.new("tool", "history", "rdprobe_snap")
        after = flat(self.read("docs/dev/CONTRACT.md"))
        self.assertIn(f"and `chromatic_rdprobe_snap`. {total + 1} in total", after)
        names = re.findall(r"`(chromatic_\w+)`", sentence)
        listed = after[after.index("tools, plus") : after.index(f"{total + 1} in total")]
        self.assertEqual(re.findall(r"`(chromatic_\w+)`", listed), [*names, "chromatic_rdprobe_snap"])


class Tab(ScaffoldCase):
    def test_a_taken_id_says_what_the_folder_is_and_how_to_keep_the_label(self):
        write(self.tree, "page/pages/home/rdprobe-x/index.js", "// The probe's own background.\nexport const X = 1\n")
        write(self.tree, "page/pages/home/rdprobe-y/notes.txt", "x\n")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Folders")
        out = self.new("tab", "home", "rdprobe-x", "--label", "Probe", code=1)
        self.assertIn("page/pages/home/rdprobe-x exists: The probe's own background.", out["error"]["message"])
        self.assertIn("python tools/retrodev new tab home rdprobe-x-tab --label Probe", out["error"]["fix"])
        out = self.new("tab", "home", "rdprobe-y", code=1)
        self.assertIn("page/pages/home/rdprobe-y exists: an existing folder", out["error"]["message"])
        self.assertIn("--label 'Rdprobe y'", out["error"]["fix"])


if __name__ == "__main__":
    unittest.main()
