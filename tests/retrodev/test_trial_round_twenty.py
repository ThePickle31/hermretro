"""Friction the twentieth round of fresh-agent trials found in `new` (a text dry run hid the next steps, the rpcs.py
size note ignored the RPC being added, generic tool step words, the listener's logging import, the event and
listener arguments, generated test docstrings), the PR body's unchanged citations, takeover's runner and plan
advice, and the README's no-plan entry and split recipe; each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_twenty
"""

import argparse
import re
import shlex
import shutil
import unittest
from pathlib import Path

import retrodev
from retrodev import body_names, cli, scaffold_preview, scaffold_rpc
from retrodev.scaffold_listener import host_name

from tests.retrodev.fixture import RepoCase, git, parallel, retrodev_docs, write
from tests.retrodev.test_scaffold import ScaffoldCase

load_tests = parallel
ROOT = Path(retrodev.__file__).resolve().parents[2]
NEW_COMMAND = re.compile(r"(?:python tools/retrodev |(?<=\| ))new [a-z]+")


def described(kind: str) -> str:
    """`new <kind> --help`'s description, from the real parser."""

    def sub(parser: argparse.ArgumentParser) -> dict:
        return next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction)).choices

    return sub(sub(cli.parser())["new"])[kind].description


class Previews(ScaffoldCase):
    def test_a_text_dry_run_shows_the_next_steps_as_a_preview_and_writes_nothing(self):
        text = self.new("feature", "rdprobe_tw", "--dry-run", as_json=False)
        lines = text.splitlines()
        self.assertIn(scaffold_preview.HEAD, lines)
        self.assertIn(
            "would next: python tools/retrodev new rpc rdprobe_tw <name> --dry-run | new tool rdprobe_tw <name> "
            "--dry-run | new event rdprobe_tw <name> --dry-run",
            lines,
        )
        self.assertFalse([line for line in lines if line.startswith(("next: ", "then: "))], text)  # nothing to run
        self.assertEqual(lines[-1], "dry run: nothing was written")
        self.assertEqual(git(self.tree, "status", "--porcelain"), "")
        data = self.new("feature", "rdprobe_tw", "--dry-run")  # JSON: the same previewed steps
        self.assertEqual(
            ["would next: " + step for step in data["next"]], [x for x in lines if x.startswith("would next: ")]
        )
        real = self.new("feature", "rdprobe_tw")  # the real run's steps run as printed
        self.assertNotIn("--dry-run", " ".join(real["next"]))
        self.assertIn("python tools/retrodev new rpc rdprobe_tw <name> | new tool", " ".join(real["next"]))

    def test_every_new_command_a_preview_prints_keeps_dry_run(self):
        shutil.copyfile(ROOT / "backend/library/__init__.py", self.tree / "backend/library/__init__.py")
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "Library front door")
        runs = (
            ["feature", "rdprobe_tw"],
            ["page", "rdprobe-tw"],
            ["event", "history", "rdprobe_moved"],
            ["tab", "home", "rdprobe-extra"],  # home has no tabs: the --from-page step
        )
        said = []
        for argv in runs:
            steps = self.new(*argv, "--dry-run")["next"]
            for step in steps:
                for match in NEW_COMMAND.finditer(step):
                    rest = re.split(r"[|;()`]", step[match.end() :], maxsplit=1)[0]
                    self.assertTrue(rest.rstrip().endswith("--dry-run"), (argv, step))
            said.append(" ".join(steps))
        self.assertIn("`python tools/retrodev new listener <feature> history.rdprobe_moved --dry-run` writes", said[2])
        self.assertIn("`python tools/retrodev new tab home main --from-page --dry-run` makes its current", said[3])
        self.assertIn("python tools/retrodev new tab rdprobe-tw <tab> --dry-run | new slot", said[1])
        self.assertEqual(git(self.tree, "status", "--porcelain"), "")

    def test_previewed_leaves_prose_and_an_existing_dry_run_alone(self):
        step = "python tools/retrodev new tab x <tab> --dry-run | new slot x <name>"
        self.assertEqual(scaffold_preview.previewed(step), step + " --dry-run")
        self.assertEqual(scaffold_preview.previewed("new put it after the others"), "new put it after the others")

    def test_a_page_id_cannot_replace_the_dry_run_flag_in_the_first_tab_command(self):
        page = "probe--dry-run"
        self.new("page", page)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "A tabless probe page")
        output = self.new("tab", page, "extra", "--dry-run")
        assert isinstance(output, dict)
        argv = shlex.split(output["next"][0].split("`")[1])
        self.assertEqual(argv, ["python", "tools/retrodev", "new", "tab", page, "main", "--from-page", "--dry-run"])
        text = self.new(*argv[3:], as_json=False)
        self.assertIn("dry run: nothing was written", text)
        self.assertEqual(git(self.tree, "status", "--porcelain"), "")


class RpcSize(ScaffoldCase):
    def padded(self, lines: int) -> None:
        source = (ROOT / "backend/history/rpcs.py").read_text()  # whatever the real file holds: padded to `lines`
        pad = lines - len(source.splitlines())
        self.assertGreater(pad, 0)
        write(self.tree, "backend/history/rpcs.py", source + "# padding\n" * pad)
        git(self.tree, "commit", "-qam", f"rpcs.py at {lines} lines")

    def size_said(self, text: str) -> int | None:
        found = re.search(r"backend/history/rpcs\.py (?:would have|has) (\d+) lines with this RPC", text)
        return int(found.group(1)) if found else None

    def test_the_note_counts_the_rpc_being_added_one_line_either_side_of_the_limit(self):
        limit = scaffold_rpc.big_rpcs(self.read("tools/layout.toml"))
        self.padded(limit + 20)
        added = self.size_said(self.new("rpc", "history", "rdprobe_size", "--dry-run", as_json=False)) - limit - 20
        self.assertGreater(added, 0)
        git(self.tree, "reset", "-q", "--hard", "HEAD~1")
        self.padded(limit - added)  # with the RPC in: exactly the limit, no note
        text = self.new("rpc", "history", "rdprobe_size", "--dry-run", as_json=False)
        self.assertIsNone(self.size_said(text), text)
        git(self.tree, "reset", "-q", "--hard", "HEAD~1")
        self.padded(limit - added + 1)  # one line over once it is in: the note, though rpcs.py is under it now
        self.assertLessEqual(len(self.read("backend/history/rpcs.py").splitlines()), limit)
        text = self.new("rpc", "history", "rdprobe_size", "--dry-run", as_json=False)
        self.assertEqual(self.size_said(text), limit + 1, text)
        self.assertIn(
            f"over {limit} (where new suggests --module, before the layout test warns): python tools/retrodev new rpc "
            "history rdprobe_size --module rdprobe_size_rpcs --dry-run previews it in its own module",
            text,
        )
        text = self.new("rpc", "history", "rdprobe_size", as_json=False)  # advice only: the real run writes it
        self.assertEqual(self.size_said(text), limit + 1, text)
        self.assertIn("give the next one its own module (python tools/retrodev new rpc history <name> --module", text)
        self.assertEqual(len(self.read("backend/history/rpcs.py").splitlines()), limit + 1)

    def test_the_projected_size_preview_keeps_game_mode_and_exposes_its_note_in_json(self):
        self.padded(scaffold_rpc.big_rpcs(self.read("tools/layout.toml")))
        out = self.new("rpc", "history", "rdprobe_size_game", "--game", "--dry-run")
        assert isinstance(out, dict)
        self.assertIn("--module rdprobe_size_game_rpcs --game --dry-run", " ".join(out["notes"]))


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


class BodyCitations(unittest.TestCase):
    def test_a_path_the_body_calls_unchanged_is_cited_not_claimed(self):
        cases = {
            "The guide `docs/dev/TESTING.md` is unchanged.": [],
            "Left `docs/dev/TESTING.md` untouched; fixed `tools/retrodev/sync.py`.": ["tools/retrodev/sync.py"],
            "No change to `docs/dev/TESTING.md`.": [],
            "`docs/a.md`, `docs/b.md` and `docs/c.md` are unchanged.": [],
            "Fixed `tools/a.py`, `docs/b.md` unchanged.": ["tools/a.py"],  # only the name the words follow
            "Fixed `tools/a.py` so the API stays unchanged.": ["tools/a.py"],  # not next to it
            "Changed `tools/a.py`.": ["tools/a.py"],
        }
        for sentence, claimed in cases.items():
            self.assertEqual(body_names.claimed(sentence), claimed, sentence)


class TakeoverAdvice(RepoCase):
    def pushed(self, retrodev_too: bool) -> None:
        mate = self.base / "mate"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(mate))
        git(mate, "switch", "-q", "-c", "feat/mate")
        self.commit(mate, "backend/library/core.py", "VALUE = 2\n")
        git(mate, "push", "-q", "origin", "feat/mate")
        if retrodev_too:
            self.on_dev("tools/retrodev/newer.py", "NEWER = 1\n")

    def test_the_plan_step_says_what_a_takeover_plan_holds_and_the_runner_step_how_long_it_lasts(self):
        self.pushed(retrodev_too=True)
        code, out = self.run_cli("takeover", "feat/mate")
        self.assertEqual(code, 0, out)
        steps = [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]
        plan = next(step for step in steps if " plan new mate " in step)
        self.assertIn("git log --oneline --no-merges origin/dev..HEAD", plan)
        self.assertIn("what is left for you, and that you took the branch over", plan)
        sync = next(step for step in steps if step.startswith(f"python {self.main}/tools/retrodev sync"))
        self.assertIn("every retrodev step until sync is done: then the worktree's own copy is current", sync)


class Readme(unittest.TestCase):
    def test_the_quick_path_names_the_no_plan_entry_and_the_split_recipe_where_to_patch(self):
        step = next(line for line in (ROOT / "tools/retrodev/README.md").read_text().splitlines() if line[:3] == "3. ")
        readme = retrodev_docs("README.md")
        self.assertIn("`docs/` and `chore/` may skip steps 1-2: `start <kind>/<topic> --no-plan`", step)
        self.assertIn('the moved code imports: `mock.patch.object(<new module>, "dep")`, not the old module', readme)


if __name__ == "__main__":
    unittest.main()
