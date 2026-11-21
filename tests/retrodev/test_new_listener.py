"""The trial rounds' regressions for this area (RoundEightNew, RoundEighteen, RoundFifteen, RoundTwentyOne), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_new_listener
"""

import ast
import re
import shutil
from typing import Any
from tests.retrodev.fixture import git, parallel, write
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase
from tests.repo.test_placeholders import left_in

load_tests = parallel

EVENT = "library.build_reported"


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


class ListenerDryRun(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def test_a_dry_run_lists_the_files_for_an_event_not_declared_yet_and_the_real_run_refuses(self):
        self.real("backend/assets/*.py", "backend/assets/README.md")
        out = self.new("listener", "assets", "history.rdprobe_later", "--dry-run", as_json=False)
        self.assertIn("would create  tests/backend/assets/test_listener_on_history_rdprobe_later.py", out)
        self.assertIn("would change  backend/assets/listeners.py", out)
        self.assertIn(
            "note: no front door declares history.rdprobe_later yet: the real run refuses until it exists", out
        )
        self.assertIn("python tools/retrodev new event history rdprobe_later --dry-run", out)
        refused = self.new("listener", "assets", "history.rdprobe_later", code=1)
        self.assertIn("no front door declares the event 'history.rdprobe_later'", refused["error"]["message"])


class ListenerStub(ScaffoldCase):
    def test_the_placeholder_has_a_line_of_its_own_and_host_logger_is_a_step(self):
        write(self.tree, "backend/library/__init__.py", (ROOT / "backend/library/__init__.py").read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "library")
        out = self.new("listener", "history", "library.build_reported")
        source = self.read("backend/history/listeners.py")
        lines = source.splitlines()
        self.assertIn("    say what this listener does.", lines)
        self.assertEqual([line for line in lines if left_in(line)], ["    say what this listener does."])
        self.assertNotIn("host.logger", source)
        self.assertTrue(all(len(line) <= 120 for line in lines))
        self.assertIn("to log, add `from ..hermes import host` to its imports first", " ".join(out["next"]))


class ListenerRoundTwentyOne(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    DOC = "chromatic_rdprobe_tool kept a note; note=<the note's text, str>, at=<when, float>"

    def test_the_docstring_and_first_step_keep_the_description_and_the_payload_apart_as_written(self):
        self.real("backend/history/*.py", "backend/history/README.md")
        self.new("event", "history", "rdprobe_noted")
        door = self.read("backend/history/__init__.py")
        door, count = re.subn(r'("history\.rdprobe_noted":\s*\(?\s*)"[^"]*"', rf'\1"{self.DOC}"', door)
        self.assertEqual(count, 1, door)
        write(self.tree, "backend/history/__init__.py", door)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "The probe event's entry")
        out = self.new("listener", "history", "history.rdprobe_noted")
        source = self.read("backend/history/listeners.py")
        func = next(
            node
            for node in ast.parse(source).body
            if isinstance(node, ast.FunctionDef) and node.name == "on_history_rdprobe_noted"
        )
        doc = ast.get_docstring(func) or ""
        flat = " ".join(doc.split())
        self.assertIn(
            "When history.rdprobe_noted happens, backend/history does this (a listener that raises is logged): "
            "say what this listener does.",
            flat,
        )
        self.assertIn("The event: chromatic_rdprobe_tool kept a note.", flat, "its case stays as written")
        self.assertIn("Its payload: note=<the note's text, str>, at=<when, float>.", flat)
        self.assertNotIn("(chromatic_rdprobe_tool kept a note;", flat)
        self.assertTrue(all(len(row) <= 120 for row in source.splitlines()), source)
        self.assertIn("    say what this listener does.\n", source, "the placeholder stays a line of its own")
        self.assertIn(
            'on_history_rdprobe_noted; the event: "chromatic_rdprobe_tool kept a note"; its payload: '
            "note=<the note's text, str>, at=<when, float>); to log, ",
            out["next"][0],
        )
