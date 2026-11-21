"""The trial rounds' regressions for this area (RoundEighteen, RoundElevenNew, RoundFifteen, RoundFive, RoundNineNew, RoundSevenNew, RoundSeventeen, RoundSixNew, RoundTenNew, RoundTwo), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_new_event
"""

from retrodev import scaffold_backend, scaffold_payload
from tests.retrodev.fixture import git, parallel, write
from tests.retrodev.fixture import retrodev_docs
from tests.retrodev.test_scaffold import ScaffoldCase
import ast
from retrodev import scaffold_source
from tests.retrodev.test_scaffold import ROOT
from retrodev import scaffold
import argparse
from retrodev import cli
import shutil

load_tests = parallel

PAYLOAD = "game=<library id, str>, root=<the real project folder, pathlib.Path>, count=<how many, int>"


def events_table(contract: str) -> list[list[str]]:
    body = contract.split("## Events between backend features", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in body.splitlines() if line.startswith("| `")]
    return [[cell.strip() for cell in row.strip().strip("|").split(" | ")] for row in rows]


TESTS = "## Tests\n\n"


def steps(out) -> list[str]:
    return [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]


LINE_LENGTH = 120

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


def event_help() -> str:
    """`new event --help`, as argparse prints it (format_help is what print_help writes; read from the parser itself
    so no test swaps sys.stdout, which every thread of the pool writes to). An uncached parser of its own: cli.parser()
    is cached and shared by every test."""
    parser = event_parser(cli.parser.__wrapped__())
    parser.color = False  # as print_help into a stream that is not a terminal
    return parser.format_help()


def event_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    for name in ("new", "event"):
        parser = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction)).choices[name]
    return parser


DISPATCHER = "backend/system/events.py"


class EventTestRoundEighteen(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def test_the_event_test_isolates_the_home_and_samples_the_hinted_types(self):
        self.new("event", "history", "rdprobe", "--payload", PAYLOAD, "--when", "When a build was kept")
        test = self.read("tests/backend/history/test_event_rdprobe.py")
        self.assertIn("from tests.support import isolated_home  # noqa: E402", test)
        self.assertIn("    def setUp(self):\n", test)
        self.assertIn("        isolated_home(self)\n", test)
        self.assertIn('emits.rdprobe(game="probe", root=Path("/games/probe"), count=1)', test)
        self.assertIn('[{"game": "probe", "root": Path("/games/probe"), "count": 1}]', test)
        compile(test, "test_event_rdprobe.py", "exec")
        # the same samples new listener's test uses
        self.assertEqual(
            scaffold_payload.typed_sample(["root", "count"], PAYLOAD), 'root=Path("/games/probe"), count=1'
        )

    def test_a_dict_typed_last_key_renders_valid_python(self):  # review 1, 0
        self.new("event", "history", "rdprobe", "--payload", "data=<metadata, dict>")
        test = self.read("tests/backend/history/test_event_rdprobe.py")
        self.assertIn('[{"data": {}}]', test)
        compile(test, "test_event_rdprobe.py", "exec")

    def test_render_unescapes_the_template_but_never_a_value(self):  # review 1, 0
        text = scaffold.render(
            "event",
            "test_event.py.tmpl",
            **dict.fromkeys(
                scaffold.KEY.findall((scaffold.TEMPLATES / "event" / "test_event.py.tmpl").read_text(encoding="utf-8")),
                "{}}",
            ),
        )
        self.assertIn("{}}", text)

    def test_new_listener_then_finds_that_test_already_isolated(self):
        self.real("backend/assets/*.py", "backend/assets/README.md")
        self.new("event", "history", "rdprobe", "--payload", PAYLOAD)
        steps = " ".join(self.new("listener", "assets", "history.rdprobe")["next"])
        self.assertRegex(steps, r"already isolated: [^;]*tests/backend/history/test_event_rdprobe\.py::EventRdprobe")
        self.assertNotIn("give each isolated_home(self)", steps)


class EventContractRowRoundEighteen(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def test_the_row_backticks_a_code_type_and_lowers_the_when_cell_like_its_neighbours(self):
        real = events_table((ROOT / "docs/dev/CONTRACT.md").read_text())
        self.assertTrue(all(row[2][:1] == "`" or row[2][:1].islower() for row in real), real)
        self.assertTrue(any("`pathlib.Path`" in row[1] for row in real), real)  # the neighbour it copies
        self.new("event", "history", "rdprobe", "--payload", PAYLOAD, "--when", "When a build was kept")
        row = next(row for row in events_table(self.read("docs/dev/CONTRACT.md")) if row[0] == "`history.rdprobe`")
        self.assertEqual(
            row[1],
            "`game` (library id, str), `root` (the real project folder, `pathlib.Path`), `count` (how many, int)",
        )
        self.assertEqual(row[2], "a build was kept")
        self.assertIn('"When a build was kept; game=<library id, str>', self.read("backend/history/__init__.py"))

    def test_the_cell_helpers(self):
        self.assertEqual(scaffold_payload.code_type("folder, pathlib.Path"), "folder, `pathlib.Path`")
        self.assertEqual(scaffold_payload.code_type("names, list of str"), "names, list of str")
        self.assertEqual(scaffold_payload.code_type("`chromatic_x` ran"), "`chromatic_x` ran")
        self.assertEqual(
            scaffold_backend.when_cell("`chromatic_build_report` accepted"), "`chromatic_build_report` accepted"
        )
        self.assertEqual(scaffold_backend.when_cell("RPC finished"), "RPC finished")
        self.assertEqual(scaffold_backend.when_cell("A build was kept"), "a build was kept")


class ReadmeTestsLineRoundEighteen(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def readme_tests(self, feature: str) -> str:
        return self.read(f"backend/{feature}/README.md").split(TESTS, 1)[1].split("\n", 1)[0]

    def test_event_listener_and_rpc_add_their_test_where_the_line_names_files(self):
        self.real("backend/library/*.py", "backend/library/README.md")
        self.new("event", "history", "rdprobe", "--payload", "game")
        self.assertTrue(
            self.readme_tests("history").endswith(", `test_event_rdprobe.py` (the `history.rdprobe` event).")
        )
        self.new("listener", "history", "library.build_reported")
        listener = "`test_listener_on_library_build_reported.py` (the `library.build_reported` listener)."
        self.assertTrue(self.readme_tests("history").endswith(listener), self.readme_tests("history"))
        self.new("rpc", "history", "rdprobe_list")
        self.assertTrue(self.readme_tests("history").endswith(", `test_rpc_rdprobe_list.py` (the `rdprobe_list` RPC)."))
        self.assertIn("`test_event_build_kept.py` (the event)", self.readme_tests("history"))  # kept as it was
        self.new("rpc", "library", "rdprobe_info")  # a line naming only the folder stays as it is
        self.assertEqual(self.readme_tests("library"), "`tests/backend/library/`.")


class EventRoundElevenNew(ScaffoldCase):
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


class EventBrokerRoundFifteen(ScaffoldCase):
    def test_the_steps_say_the_broker_never_emits(self):
        said = " ".join(self.new("event", "history", "rdprobe_moved", "--payload", "game=<id>")["next"])
        self.assertIn(
            "the broker process never emits (backend/system/events.py): call it from Hermes-side code (an RPC, tool "
            "or hook) that sees it happen",
            said,
        )
        reference = retrodev_docs("REFERENCE.md")
        self.assertIn("--when 'Setup finished installing the toolchain'", reference)
        self.assertIn("### Changing an event's payload or name", reference)
        self.assertIn("`git mv tests/backend/<feature>/test_event_<old>.py", reference)


class NewRoundFive(ScaffoldCase):
    def ran(self, *argv) -> list[str]:
        self.clear_log()
        code, out = self.run_cli("new", *argv, cwd=self.tree)
        self.assertEqual(code, 0, out)
        return [name for entry in self.check_log() for name in entry["names"]]

    def test_an_event_s_payload_reads_as_the_existing_entries(self):
        self.new("event", "history", "rdprobe_pruned", "--payload", "game, root=<project>", "--when", "it pruned")
        door = self.read("backend/history/__init__.py")
        self.assertIn('"history.rdprobe_pruned": "it pruned; game=<...>, root=<project>",', door)
        self.assertNotIn("payload: ", door)
        self.assertIn("names in backticks", " ".join(event_help().split()))


class EventRoundNineNew(ScaffoldCase):
    def test_bare_payload_keys_are_named_as_placeholders_and_the_emitter_test_is_named(self):
        steps = joined(self.new("event", "history", "rdprobe_kept", "--payload", "game=<id>, root"))
        self.assertIn("replace the <...> placeholders in backend/history/__init__.py EVENTS (root=<...>)", steps)
        self.assertIn("grep -rln <the function that calls emits.rdprobe_kept> tests/backend/history", steps)
        steps = joined(self.new("event", "history", "rdprobe_said", "--payload", "game=<id>"))
        self.assertNotIn("placeholders", steps)

    def test_a_listener_names_the_placeholders_it_copied(self):
        self.new("event", "history", "rdprobe_bare", "--payload", "game, root")
        steps = joined(self.new("listener", "history", "history.rdprobe_bare"))
        self.assertIn("on_history_rdprobe_bare's docstring copies history.rdprobe_bare's EVENTS entry", steps)
        self.assertIn("game=<...>, root=<...>", steps)


class EventRoundSevenNew(ScaffoldCase):
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
            "| `history.rdprobe_edited` | `game` (id), `fields` ([the fields it changed]) | after `builds` answered |",
            self.read("docs/dev/CONTRACT.md"),
        )

    def test_a_payload_key_the_dispatcher_takes_itself_is_refused_with_nothing_written(self):  # review 2, 1
        self.assertIn("def emit(name: str, **payload)", (ROOT / DISPATCHER).read_text())
        before = git(self.tree, "rev-parse", "HEAD")
        for payload in ("name", "game=<id>, name=<new name>"):
            out = self.new("event", "history", "rdprobe_renamed", "--payload", payload, code=1)
            self.assertIn("reserved word(s) 'name' cannot be payload keys", out["error"]["message"])
            self.assertIn("game_name instead of name", out["error"]["fix"])
            self.assertEqual(git(self.tree, "status", "--porcelain"), "", payload)
            self.assertEqual(git(self.tree, "rev-parse", "HEAD"), before)
        # the reserved words are read from the tree's dispatcher: a parameter it gains is refused as well
        write(self.tree, DISPATCHER, "def emit(name: str, *, when=None, **payload) -> None:\n    pass\n")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "A dispatcher with another parameter")
        out = self.new("event", "history", "rdprobe_timed", "--payload", "when=<time>", code=1)
        self.assertIn("reserved word(s) 'name', 'when'", out["error"]["message"])
        self.assertEqual(git(self.tree, "status", "--porcelain"), "")

    def test_a_payload_without_keys_keeps_payload(self):
        self.new("event", "history", "rdprobe_any")
        self.assertIn("def rdprobe_any(**payload) -> None:", self.read("backend/history/emits.py"))
        self.assertIn("emits.rdprobe_any(example=1)", self.read("tests/backend/history/test_event_rdprobe_any.py"))


class LongEventDocstringRoundSeventeen(ScaffoldCase):
    def test_the_emits_docstring_wraps_at_120_columns(self):
        payload = "game=<the library id of the game whose build finished>, rom=<the built ROM's path>, ok=<bool>"
        self.new("event", "history", "rdprobe_build_finished_everywhere", "--payload", payload)
        emits = self.read("backend/history/emits.py")
        self.assertIn("Tell other features that history.rdprobe_build_finished_everywhere happened", emits)
        self.assertEqual([line for line in emits.splitlines() if len(line) > 120], [])
        compile(emits, "emits.py", "exec")


class EventRoundSixNew(ScaffoldCase):
    def test_a_repeated_payload_keeps_every_value(self):
        self.new(
            "event", "history", "rdprobe_three", "--payload", "game", "--payload", "root=<project>",
            "--payload", "count", "--when", "it counted",
        )  # fmt: skip
        door = self.read("backend/history/__init__.py")
        self.assertIn('"history.rdprobe_three": "it counted; game=<...>, root=<project>, count=<...>",', door)
        self.assertIn(
            "| `history.rdprobe_three` | `game` (<...>), `root` (project), `count` (<...>) | it counted |",
            self.read("docs/dev/CONTRACT.md"),
        )
        self.assertIn("(game, root=<project>, count)", self.read("backend/history/emits.py"))
        reference = retrodev_docs("REFERENCE.md")
        row = reference[reference.index("### `new event ") :].split("\n\n")[1]  # its section's paragraph
        self.assertIn("either way: comma-separated", row)
        self.assertIn("or repeated (`--payload 'game=<id>' --payload 'root=<project>'`)", row)


class EventRoundTenNew(ScaffoldCase):
    def test_the_next_steps_and_the_reference_say_how_to_change_a_payload_later(self):
        steps = joined(self.new("event", "history", "rdprobe_moved", "--payload", "game=<id>"))
        self.assertIn(  # round 12: the steps point to the reference's list, which names the callers and tests too
            "changing history.rdprobe_moved's payload later: tools/retrodev/REFERENCE.md \"Changing an event's "
            "payload or name\" lists every place (backend/history/emits.py's function rdprobe_moved, its callers: "
            "grep -rn 'rdprobe_moved(' backend/history; the EVENTS entry in backend/history/__init__.py, its "
            "docs/dev/CONTRACT.md row, tests/backend/history/test_event_rdprobe_moved.py",
            steps,
        )
        self.assertIn("### Changing an event's payload or name", retrodev_docs("REFERENCE.md"))


class NewKindsRoundTwoRoundTwo(ScaffoldCase):
    def test_an_event_says_when_lists_its_keys_and_sits_after_its_owner_s_rows(self):
        shutil.copyfile(ROOT / "backend/library/__init__.py", self.tree / "backend/library/__init__.py")
        payload = "game=<id> (None without a project, or a list), root=<project>"
        rows = [line for line in self.read("docs/dev/CONTRACT.md").splitlines() if line.startswith("| `")]
        owned = [i for i, line in enumerate(rows) if line.startswith("| `library.")]
        after = rows[owned[-1] + 1] if owned[-1] + 1 < len(rows) else None  # whatever follows library's rows now
        out = self.new("event", "library", "rdprobe_moved", "--payload", payload, "--when", "a game moved folders")
        door = self.read("backend/library/__init__.py")
        self.assertIn(f'"library.rdprobe_moved": "a game moved folders; {payload}"', door)  # keys say what they hold
        self.assertNotIn("    # emits.", door, "no hint comment inside EVENTS")
        rows = [line for line in self.read("docs/dev/CONTRACT.md").splitlines() if line.startswith("| `")]
        mine = "| `library.rdprobe_moved` | `game` (id; None without a project, or a list), `root` (project) | a game moved folders | — |"
        self.assertIn(mine, rows)
        before = rows[rows.index(mine) - 1]
        self.assertTrue(before.startswith("| `library."), before)
        following = rows[rows.index(mine) + 1] if rows.index(mine) + 1 < len(rows) else None
        self.assertEqual(following, after, "after the owner's last row only")
        self.assertIn('emit("library.rdprobe_moved", ...)', " ".join(out["next"]))
