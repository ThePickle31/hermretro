"""The trial rounds' regressions for this area (RoundTwenty, RoundTwo), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_new_guides
"""

import argparse
import shlex
import shutil
from pathlib import Path
import retrodev
from retrodev import cli
from retrodev.scaffold_listener import host_name
from tests.retrodev.fixture import git, parallel, write
from tests.retrodev.test_scaffold import ScaffoldCase
import importlib.util

load_tests = parallel

ROOT = Path(retrodev.__file__).resolve().parents[2]


def described(kind: str) -> str:
    """`new <kind> --help`'s description, from the real parser."""

    def sub(parser: argparse.ArgumentParser) -> dict:
        return next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction)).choices

    return sub(sub(cli.parser())["new"])[kind].description


STANDARD = "  # noqa: E402 - the repository root goes on sys.path first"


class Guidance(ScaffoldCase):
    def test_generic_tool_step_words_say_they_are_generic_and_chosen_words_do_not(self):
        steps = " ".join(self.new("tool", "history", "rdprobe_words")["next"])
        self.assertIn("'Running rdprobe words' / 'Ran rdprobe words'", steps)
        self.assertIn("generic words new made from the tool's name, so write what the user should read", steps)
        steps = " ".join(self.new("tool", "history", "rdprobe_said", "--step", "Probing it", "Probed it")["next"])
        self.assertNotIn("generic words", steps)

    def test_the_listener_logging_step_names_the_import_only_when_it_is_missing(self):
        shutil.copyfile(ROOT / "backend/library/__init__.py", self.tree / "backend/library/__init__.py")
        steps = " ".join(self.new("listener", "history", "library.build_reported")["next"])
        self.assertIn("to log, add `from ..hermes import host` to its imports first, then use host.logger", steps)
        self.assertIn("listeners.host.logger", steps)
        self.assertIn("once listeners.py imports host as the first step says", steps)
        source = self.read("backend/history/listeners.py")
        self.assertNotIn("import host", source)  # the template imports only `on`: no unused import
        lines = source.split("\n")  # follow the step: the import goes with the others, and is then recognised
        at = max(i for i, line in enumerate(lines) if line.startswith("from "))
        write(
            self.tree,
            "backend/history/listeners.py",
            "\n".join([*lines[: at + 1], "from ..hermes import host", *lines[at + 1 :]]),
        )
        self.assertEqual(host_name(self.read("backend/history/listeners.py")), ("host", ""))
        steps = " ".join(self.new("listener", "history", "library.game_presented")["next"])
        self.assertIn("to log, use host.logger (e.g. host.logger.info(...))", steps)
        self.assertNotIn("to its imports first", steps)
        self.assertEqual(host_name("from . import x as host\n")[0], "hermes_host")  # `host` taken: another name
        self.assertIn("from ..hermes import host as hermes_host", host_name("host = None\n")[1])

    def test_logging_advice_avoids_rebound_imports_payload_keys_and_taken_aliases(self):
        text = "from ..hermes import host\nhost = None\nhermes_host = None\n"
        name, step = host_name(text, ("hermes_host2",))
        self.assertEqual(name, "hermes_host3")
        self.assertIn("from ..hermes import host as hermes_host3", step)
        self.assertEqual(host_name("from ..hermes import host\n", ("host",))[0], "hermes_host")

    def test_the_event_and_listener_help_examples_run_as_written(self):
        shutil.copyfile(ROOT / "backend/library/__init__.py", self.tree / "backend/library/__init__.py")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "Library front door")
        for kind in ("event", "listener"):
            example = described(kind).split("e.g. ", 1)[1]
            argv = shlex.split(example)
            self.assertEqual(argv[:2], ["new", kind], example)
            self.new(*argv[1:], "--dry-run")  # exit 0: the example is a real call

    def test_generated_tests_put_their_run_alone_line_on_its_own(self):
        shutil.copyfile(ROOT / "backend/library/__init__.py", self.tree / "backend/library/__init__.py")
        for argv in (
            ["rpc", "history", "rdprobe_alone"],
            ["tool", "history", "rdprobe_alone"],
            ["event", "history", "rdprobe_alone"],
            ["listener", "history", "library.build_reported"],
        ):
            self.new(*argv)
        for path in sorted((self.tree / "tests/backend/history").glob("test_*rdprobe_alone*.py")) + sorted(
            (self.tree / "tests/backend/history").glob("test_listener_*.py")
        ):
            first, blank, alone = path.read_text().split("\n")[:3]
            self.assertNotIn("Run alone", first, path.name)
            self.assertEqual((blank, alone.split(": ")[0]), ("", "Run alone"), path.name)


class NewKinds(ScaffoldCase):
    def test_every_generated_test_gives_its_noqa_reason_and_imports_tests_support_as_a_package(self):
        shutil.copyfile(ROOT / "backend/library/__init__.py", self.tree / "backend/library/__init__.py")
        write(self.tree, "tests/support.py", "def isolated_home(test):\n    pass\n")
        for step in (
            ["feature", "rdprobe_all"],
            ["rpc", "rdprobe_all", "rdprobe_all_ping"],
            ["tool", "rdprobe_all", "rdprobe_all_ping"],
            ["event", "rdprobe_all", "pinged"],
            ["listener", "rdprobe_all", "library.build_reported"],
        ):
            self.new(*step)
        tests = sorted((self.tree / "tests/backend/rdprobe_all").glob("test_*.py"))
        self.assertEqual(len(tests), 5, tests)
        for path in tests:
            for line in path.read_text().splitlines():
                if "noqa: E402" in line:
                    self.assertTrue(line.endswith(STANDARD), f"{path.name}: {line}")
                if "sys.path.insert" in line:
                    self.assertEqual(line, "sys.path.insert(0, str(Path(__file__).resolve().parents[3]))", path.name)
                if "support" in line and "import" in line:
                    self.assertTrue(line.startswith("from tests.support import "), f"{path.name}: {line}")
        spec = importlib.util.spec_from_file_location("check_py_round_two", ROOT / "tools" / "check.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        test = ["/usr/bin/python3", "-m", "unittest", "-v", "tests.retrodev.test_scaffold_tree"]
        for mode in ("1", "nested"):
            self.assertEqual(
                module.scaffold_fix(test, mode),
                f"RD_SCAFFOLD_FULL={mode} RD_SCAFFOLD_KEEP=1 python -B -m unittest -v tests.retrodev.test_scaffold_tree",
            )
