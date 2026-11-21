"""The trial rounds' regressions for this area (RoundElevenNew, RoundFive, RoundNineteen, RoundSevenNew, RoundSeventeen, RoundSixNew, RoundThree, RoundTwelveNew, RoundTwo), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_new_listener_steps
"""

from tests.retrodev.fixture import git, parallel, retrodev_docs, write
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase
from retrodev.scaffold import Plan
from retrodev.scaffold_listener import payload_of
from tests.retrodev.hand_edits import line_of
import shutil
from tests.repo.test_placeholders import PLACEHOLDERS

load_tests = parallel

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


def joined(out) -> str:
    return " ".join(out["next"])


MOCK = "from unittest import mock\nmock.patch.object(hermes_host, '_chat_project', f)\n"


def steps(out) -> list[str]:
    return [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]


STANDARD = "  # noqa: E402 - the repository root goes on sys.path first"

EMITTING = '''"""Tests that emit library.rdprobe_typed (a probe)."""

import unittest

from backend.system import events
from tests.support import isolated_home


class Isolated(unittest.TestCase):
    def setUp(self):
        isolated_home(self)

    def test_emits(self):
        events.emit("library.rdprobe_typed", count=1)


class InheritsIsolation(Isolated):
    def test_emits_too(self):
        events.emit("library.rdprobe_typed", count=2)


class Bare(unittest.TestCase):
    def test_emits(self):
        events.emit("library.rdprobe_typed", count=3)


class Unrelated(unittest.TestCase):
    def test_other(self):
        self.assertTrue(True)
'''

LISTENERS = "backend/history/listeners.py"

DOOR_RoundTwelveNew = '''"""The games library (a probe of its front door's shape)."""

__all__ = []

EVENTS = {
    "library.rdprobe_typed": (
        "a probe happened, described at length so that the copied description runs well past one line of the "
        "listener's docstring; count=<how many, int>, title=<the game's title, str>, root=<the project folder, "
        "pathlib.Path>, fresh=<whether it is new, bool>, other=<id>"
    ),
    "library.rdprobe_wide": (
        "a wide one; the_first_rather_long_key_name=<a, str>, the_second_rather_long_key_name=<b, str>, "
        "the_third_rather_long_key_name=<c, str>"
    ),
}
'''


class ListenerRoundElevenNew(ScaffoldCase):
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


class NewRoundFive(ScaffoldCase):
    def ran(self, *argv) -> list[str]:
        self.clear_log()
        code, out = self.run_cli("new", *argv, cwd=self.tree)
        self.assertEqual(code, 0, out)
        return [name for entry in self.check_log() for name in entry["names"]]

    def test_a_listener_joins_entries_that_say_what_each_does_as_an_entry_of_its_own(self):
        self.new("feature", "rdprobe_ears")  # a probe feature: what history listens to is the real tree's business
        readme = self.read("backend/rdprobe_ears/README.md")
        readme = readme.replace("Listens to: none.", "Listens to: `library.build_reported` — keeps a note.")
        write(self.tree, "backend/rdprobe_ears/README.md", readme)
        write(self.tree, "backend/library/__init__.py", (ROOT / "backend/library/__init__.py").read_text())
        out = self.new("listener", "rdprobe_ears", "library.game_presented")
        line = next(row for row in self.read("backend/rdprobe_ears/README.md").splitlines() if "Listens to" in row)
        self.assertTrue(
            line.endswith(
                "`library.build_reported` — keeps a note; `library.game_presented` — say what this listener does."
            ),
            line,
        )
        steps = " ".join(out["next"])
        self.assertIn("'say what this listener does' in backend/rdprobe_ears/README.md's 'Listens to' entry", steps)
        source = self.read("backend/rdprobe_ears/listeners.py")
        self.assertIn("A listener runs synchronously", source)  # round 15: host.logger is a next step, not prose
        self.assertIn("to log, add `from ..hermes import host` to its imports first", steps)
        said = " ".join(source.split())
        self.assertIn(
            "in the process and thread that emits the event, on the Hermes side (the gateway, the plugin host", said
        )
        self.assertIn("never in the broker; state kept at module level is that process's own", said)
        self.assertNotIn("only in the gateway", said)
        self.assertNotIn("only in the gateway", retrodev_docs())


class ListenerPreviewRoundNineteen(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def test_the_log_hint_takes_the_listener_s_own_level(self):
        said = " ".join(self.new("listener", "history", "history.build_kept")["next"])
        self.assertNotIn('logger, "INFO")', said)
        self.assertIn('"<LEVEL>"):`, the level the listener logs at ("INFO" for host.logger.info', said)


class ListenerRoundSevenNew(ScaffoldCase):
    def test_the_test_calls_it_with_the_declared_keys_and_the_next_steps_say_what_to_test(self):
        self.new("event", "history", "rdprobe_moved", "--payload", "path, root", "--when", "a probe moved")
        write(
            self.tree,
            "tests/backend/history/test_probe_mocks.py",
            "mock.patch.object(hermes_host, '_chat_project', f)\nemits.rdprobe_moved(path='p', root='r')\n",
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
        mocked = next(s for s in steps if "mock backend.hermes.host helpers" in s)  # it emits the event
        self.assertIn("tests/backend/history/test_probe_mocks.py (_chat_project)", mocked)

    def test_the_payload_keys_are_each_entry_s_leading_name_not_the_names_in_its_description(self):  # review 1, 1
        row = line_of((ROOT / "docs/dev/CONTRACT.md").read_text(), "| `library.build_reported` |")
        self.assertIn("`null`", row)  # inside game's description: not a key
        self.assertEqual(payload_of(Plan(ROOT), "library.build_reported", ""), ["game", "assets"])
        self.new("feature", "rdprobe_ears")
        write(self.tree, "backend/library/__init__.py", (ROOT / "backend/library/__init__.py").read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Probe feature and the library's front door")
        self.new("listener", "rdprobe_ears", "library.build_reported")
        test = self.read("tests/backend/rdprobe_ears/test_listener_on_library_build_reported.py")
        self.assertIn('listeners.on_library_build_reported(game="probe", assets=["probe"])', test)  # typed: round 12
        self.assertNotIn("null", test)


class ListenerLogsRoundSeventeen(ScaffoldCase):
    def test_the_listener_steps_say_how_to_assert_a_log(self):
        said = " ".join(self.new("listener", "history", "history.build_kept")["next"])
        self.assertIn('with self.assertLogs(listeners.host.logger, "<LEVEL>"):`, the level the listener logs at', said)
        self.assertIn("from ..hermes import host", said)
        self.assertIn("logger = logging.getLogger(__name__)", (ROOT / "backend/hermes/host.py").read_text())


class ListenerRoundSixNew(ScaffoldCase):
    def setUp(self):
        super().setUp()
        self.new("feature", "rdprobe_ears")
        write(self.tree, "backend/library/__init__.py", (ROOT / "backend/library/__init__.py").read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "Probe feature")

    def listens(self) -> str:
        return next(row for row in self.read("backend/rdprobe_ears/README.md").splitlines() if "Listens to" in row)

    def test_none_becomes_an_entry_naming_the_file_that_the_placeholder_gate_catches(self):
        out = self.new("listener", "rdprobe_ears", "library.game_presented")
        line = self.listens()
        self.assertTrue(
            line.endswith("Listens to (`listeners.py`): `library.game_presented` — say what this listener does."), line
        )
        self.assertTrue(any(text in line for text in PLACEHOLDERS), line)
        steps = " ".join(out["next"])
        self.assertIn(
            "if other code reads what the listener keeps, export the reader in backend/rdprobe_ears/__init__.py "
            "__all__ and name it on the README Front door line",
            steps,
        )
        self.assertIn("goes in a file under backend.system.paths.hermretro_home(), written atomically", steps)
        said = " ".join(self.read("backend/rdprobe_ears/listeners.py").split())
        self.assertIn(
            "state other processes must read goes in a file under backend.system.paths.hermretro_home(),", said
        )

    def test_a_plain_listed_event_gets_the_new_one_as_an_entry_of_its_own(self):
        readme = self.read("backend/rdprobe_ears/README.md")
        write(
            self.tree,
            "backend/rdprobe_ears/README.md",
            readme.replace("Listens to: none.", "Listens to: `library.build_reported`."),
        )
        git(self.tree, "commit", "-qam", "Listed by hand")
        self.new("listener", "rdprobe_ears", "library.game_presented")
        self.assertTrue(
            self.listens().endswith(
                "Listens to (`listeners.py`): `library.build_reported`; `library.game_presented` — say what this "
                "listener does."
            ),
            self.listens(),
        )


class NewRoundThree(ScaffoldCase):
    def test_listener_next_steps_name_the_placeholders_and_the_emitter_s_tests(self):
        shutil.copyfile(ROOT / "backend/library/__init__.py", self.tree / "backend/library/__init__.py")
        self.new("feature", "rdprobe_ears")
        steps = " ".join(self.new("listener", "rdprobe_ears", "library.build_reported")["next"])
        self.assertIn("'rdprobe_ears (say what it does)'", steps)
        self.assertIn("'say what this listener does'", steps)
        self.assertIn("grep -rn 'emit(\"library.build_reported\"' backend tests", steps)
        self.assertIn("isolated_home(self)", steps)


class ListenerRoundTwelveNew(ScaffoldCase):
    def setUp(self):
        super().setUp()
        write(self.tree, "backend/library/__init__.py", DOOR_RoundTwelveNew)
        write(self.tree, "tests/backend/library/test_rdprobe_emits.py", EMITTING)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Probe events")

    def with_ruff(self) -> None:
        ruff = ROOT / ".dev" / "py"
        if not (ruff / "bin" / "ruff").is_file():
            self.skipTest("the pinned ruff is not set up here (python tools/py/setup.py)")
        (self.tree / ".dev").mkdir(exist_ok=True)
        (self.tree / ".dev" / "py").symlink_to(ruff)
        write(self.tree, "tools/py/ruff.toml", (ROOT / "tools/py/ruff.toml").read_text())

    def test_the_dry_run_diff_is_the_ruff_formatted_text_the_write_produces(self):
        self.with_ruff()
        diff = self.new("listener", "history", "library.rdprobe_wide", "--dry-run")["diff"]
        part = diff[diff.index(f"+++ b/{LISTENERS}") :].split("\n--- ", 1)[0]
        shown = "".join(line[1:] + "\n" for line in part.splitlines()[2:] if line.startswith("+"))
        self.new("listener", "history", "library.rdprobe_wide")
        written = self.read(LISTENERS)
        self.assertIn("def on_library_rdprobe_wide(\n", written, "ruff wrapped the long signature")
        self.assertEqual(shown, written)

    def test_the_next_steps_say_which_emitting_tests_are_already_isolated(self):
        steps = joined(self.new("listener", "history", "library.rdprobe_typed"))
        test = "tests/backend/library/test_rdprobe_emits.py"
        self.assertIn(
            f"give each isolated_home(self) (tests/support.py) in setUp, so it never touches the real home: "
            f"{test}::Bare; already isolated: {test}::Isolated, {test}::InheritsIsolation",
            steps,
        )
        self.assertNotIn("Unrelated", steps)

    def test_the_docstring_wraps_within_120_characters_and_keeps_the_placeholder_whole(self):
        self.new("listener", "history", "library.rdprobe_typed")
        text = self.read(LISTENERS)
        long = [line for line in text.splitlines() if len(line) > LINE_LENGTH]
        self.assertEqual(long, [])
        self.assertIn("say what this listener does", text)
        self.assertIn("pathlib.Path>, fresh=<whether it is new, bool>", " ".join(text.split()))

    def test_the_test_s_sample_values_follow_the_type_hints(self):
        self.new("listener", "history", "library.rdprobe_typed")
        test = self.read("tests/backend/history/test_listener_on_library_rdprobe_typed.py")
        self.assertIn(
            'on_library_rdprobe_typed(count=1, title="probe", root=Path("/games/probe"), fresh=True, '
            'other="sample other")',
            test,
        )
        self.assertIn("from pathlib import Path", test)

    def test_the_next_steps_point_to_changing_an_event_s_payload(self):
        steps = joined(self.new("listener", "history", "library.rdprobe_typed"))
        self.assertIn(
            "when library.rdprobe_typed's payload changes: tools/retrodev/REFERENCE.md \"Changing an event's "
            'payload or name" lists every place, this listener among them',
            steps,
        )
        event = joined(self.new("event", "history", "rdprobe_moved", "--payload", "game=<id, str>"))
        self.assertIn("tools/retrodev/REFERENCE.md \"Changing an event's payload or name\" lists every place", event)
        self.assertIn("grep -rln 'history.rdprobe_moved' tests/backend/history", event)
        reference = retrodev_docs("REFERENCE.md")
        for place in (
            "its function in `backend/<feature>/emits.py`",
            "every caller of that function, which passes the keys (`grep -rn '<name>(' backend/<feature>`)",
            "its `EVENTS` entry in `backend/<feature>/__init__.py`",
            "its row in `docs/dev/CONTRACT.md`",
            "`tests/backend/<feature>/test_event_<name>.py`",
            "the emitter's own tests that assert the payload (`grep -rln '<feature>.<name>' tests/backend/<feature>`)",
        ):
            self.assertIn(place, reference)


class NewKindsRoundTwoRoundTwo(ScaffoldCase):
    def test_the_listener_test_uses_isolated_home_when_tests_support_has_it(self):
        shutil.copyfile(ROOT / "backend/library/__init__.py", self.tree / "backend/library/__init__.py")
        self.new("feature", "rdprobe_ears")
        self.new("listener", "rdprobe_ears", "library.build_reported")
        test = self.read("tests/backend/rdprobe_ears/test_listener_on_library_build_reported.py")
        self.assertIn('mock.patch.object(host, "_data_dir", lambda: data)', test)
        self.assertIn('"HERMRETRO_HOME": home.name', test)
        self.assertNotIn("TODO", test)
        write(self.tree, "tests/support.py", "def isolated_home(test):\n    pass\n")
        self.new("listener", "rdprobe_ears", "library.game_presented")
        test = self.read("tests/backend/rdprobe_ears/test_listener_on_library_game_presented.py")
        self.assertIn("from tests.support import isolated_home" + STANDARD, test)
        self.assertIn("        isolated_home(self)\n", test)
