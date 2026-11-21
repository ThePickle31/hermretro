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

from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, retrodev_docs, write
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
            ["tab", "build", "rdprobe-extra"],  # build has no tabs: the --from-page step
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
        self.assertIn("`python tools/retrodev new tab build main --from-page --dry-run` makes its current", said[3])
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


class AcceptanceInputs(RepoCase):
    """A branch that needs the real-engine run passed it, then changed only a retrodev test: acceptance reran (40 s)
    though nothing it runs reads tests/retrodev/. Every file it may read still takes its pass back."""

    def checked(self, tree, *, cached: bool, code: int = 0) -> dict:
        self.clear_log()
        got, data = self.run_cli("check", cwd=tree, as_json=True)
        self.assertEqual(got, code, data)
        ran = [name for entry in self.check_log() for name in entry.get("names", [])]
        self.assertEqual("acceptance" not in ran, cached, ran)
        row = next(row for row in data["checks"] if row["name"] == "acceptance")
        self.assertEqual(row["cached"], cached, row)
        return data

    def shipped(self, tree) -> list[str]:
        body = write(self.base, "body.md", GOOD_BODY)
        _code, data = self.run_cli(
            "ship", "--title", "Move the glue", "--body", str(body), "--dry-run", cwd=tree, as_json=True
        )
        return [gate["name"] for gate in data["gates"] if not gate["ok"]]

    def test_a_retrodev_test_edit_keeps_the_acceptance_pass_and_the_tree_may_ship(self):
        tree = self.worktree("chore/move")
        self.commit(tree, "backend/library/core.py", "VALUE = 2\n", "Change the core")
        self.assertTrue(self.checked(tree, cached=False)["tree_passed"])
        self.commit(tree, "tests/retrodev/test_probe.py", "PROBE = 1\n", "Add a retrodev test")
        data = self.checked(tree, cached=True)
        self.assertTrue(data["tree_passed"], data)
        self.assertEqual(
            self.check_log()[0]["names"], ["unit", "lint", "scan"], "the fast checks that read it still run"
        )
        self.assertEqual(self.shipped(tree), [], "the ship gate takes the tree whose pass reused acceptance")
        write(tree, "tests/retrodev/test_probe.py", "PROBE = 2\n")  # uncommitted: the other gates still hold
        self.assertIn("committed and clean", self.shipped(tree))
        git(tree, "commit", "-q", "-am", "Change the probe")
        self.fail_checks("unit")
        data = self.checked(tree, cached=True, code=1)
        self.assertFalse(data["tree_passed"], "a cached acceptance pass never outweighs a failure")
        self.assertIn("checks passed on this tree", self.shipped(tree))

    def test_every_file_the_real_engine_run_may_read_takes_its_pass_back(self):
        tree = self.worktree("chore/move")
        self.commit(tree, "backend/library/core.py", "VALUE = 2\n", "Change the core")
        self.checked(tree, cached=False)
        for name in (
            "backend/library/core.py",  # the backend, broker and player it runs
            "tests/acceptance/broker_acceptance.py",  # the suite itself
            "tests/support.py",  # shared test helpers
            "tests/retrodev.py",  # beside the folder, not in it
            "tools/ci/prepare_toolchain.py",  # the toolchain
            "tools/check.py",  # the runner
            "tools/retrodev/checks.py",  # what decides and runs it
            "tools/retrodev/policy.toml",  # its inputs and their exceptions
        ):
            with self.subTest(name):
                path = tree / name
                write(tree, name, (path.read_text() if path.is_file() else "") + "\n# changed\n")
                git(tree, "add", "-A")
                git(tree, "commit", "-q", "-m", f"Change {name}")
                self.checked(tree, cached=False)


class Readme(unittest.TestCase):
    def test_the_quick_path_names_the_no_plan_entry_and_the_split_recipe_where_to_patch(self):
        step = next(line for line in (ROOT / "tools/retrodev/README.md").read_text().splitlines() if line[:3] == "3. ")
        readme = retrodev_docs("README.md")
        self.assertIn("`docs/` and `chore/` may skip steps 1-2: `start <kind>/<topic> --no-plan`", step)
        self.assertIn('the moved code imports: `mock.patch.object(<new module>, "dep")`, not the old module', readme)


if __name__ == "__main__":
    unittest.main()
