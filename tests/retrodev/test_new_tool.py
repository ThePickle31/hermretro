"""The trial rounds' regressions for this area (RoundEightNew, RoundEighteen, RoundElevenNew, RoundFive, RoundFour, RoundFourteen, RoundNineNew, RoundSevenNew, RoundSeventeen, RoundSixteen, RoundThree, RoundTwentyOne), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_new_tool
"""

import re
import shutil
from tests.retrodev.fixture import git, parallel, write
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase
import inspect
from tests import support
from tests.retrodev.test_scaffold import count_words, test_lockstep

load_tests = parallel


def joined(out) -> str:
    return " ".join(out["next"])


def steps(out) -> list[str]:
    return [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]


def agent_row(text: str, feature: str) -> str:
    rows = text.split("## The agent half", 1)[1].splitlines()
    return next(line for line in rows if line.startswith(f"| `backend/{feature}/` |"))


def line_with(text: str, start: str) -> str:
    return next(line for line in text.splitlines() if line.lstrip().startswith(start))


README = """# {Label}

**Shows:** the page.

**Tabs:** none.

**Slots:** declares none, contributes none.

**Tests:** `tests/page/page-{page}.test.mjs`.

## Adding a tab here

Make a folder `page/pages/{page}/<tab>/`{taken} with an `index.js` exporting `{{ id, label, Page }}`.
"""


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def last_feature_row(text: str) -> str:
    """The last `backend/` row of "The agent half"'s feature table (the one starting '| Feature | Declares |')."""
    lines = text.split("## The agent half", 1)[1].split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith("| Feature | Declares |"))
    end = next(i for i in range(start, len(lines)) if not lines[i].strip())
    return [line for line in lines[start:end] if line.startswith("| `backend/")][-1]


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


class ToolImportSorted(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def test_the_sibling_import_goes_where_isort_puts_it(self):
        self.real("backend/setup/*.py", "backend/setup/README.md")
        self.new("tool", "setup", "probe", "--module", "probe_tools", "--step", "Probing", "Probed")
        imports = [line for line in self.read("backend/setup/tools.py").splitlines() if line.startswith("from .")]
        self.assertEqual(imports[-2:], ["from . import probe_tools", "from . import provision"])


class ToolAndRpc(ScaffoldCase):
    def test_a_project_tool_names_the_library_game_helper_with_its_real_signature(self):
        for name in ("__init__.py", "tool_args.py"):
            write(self.tree, f"backend/library/{name}", (ROOT / f"backend/library/{name}").read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "tool_args")
        steps = joined(self.new("tool", "library", "rdprobe_picked"))
        self.assertIn(
            "a test that needs a library game: `game, root = make_library_game(self.home, name)` from tests.support",
            steps,
        )
        parameters = inspect.signature(support.make_library_game).parameters.values()
        positional = [p.name for p in parameters if p.kind is not inspect.Parameter.KEYWORD_ONLY]
        self.assertEqual(positional, ["home", "name"])  # the call above; its switches are keyword-only, defaulted
        self.assertTrue(all(p.default is not p.empty for p in parameters if p.kind is p.KEYWORD_ONLY))
        self.assertIn("self.home = isolated_home(self)", self.read("tests/backend/library/test_tool_rdprobe_picked.py"))


class New(ScaffoldCase):
    def ran(self, *argv) -> list[str]:
        self.clear_log()
        code, out = self.run_cli("new", *argv, cwd=self.tree)
        self.assertEqual(code, 0, out)
        return [name for entry in self.check_log() for name in entry["names"]]

    def test_the_page_kinds_run_lint_bundle_and_page_and_the_backend_kinds_unit(self):
        self.assertEqual(sorted(self.ran("page", "rdprobe-notes")), ["bundle", "lint", "page"])
        self.assertNotIn("unit", self.ran("tab", "rdprobe-notes", "extra"))
        self.assertNotIn("unit", self.ran("slot", "rdprobe-notes", "more", "--doc", "More. Props: { ctx }"))
        self.assertIn("unit", self.ran("rpc", "history", "rdprobe_ping"))


class NewRoundFour(ScaffoldCase):
    def row(self, feature: str) -> str:
        return agent_row(self.read("docs/dev/ARCHITECTURE.md"), feature)

    def alias(self, clause: str, page_field: str) -> None:
        """The rdprobe-notes page's index.js importing its Page through ``clause``, committed."""
        door = "page/pages/rdprobe-notes/index.js"
        text = self.read(door).replace("{ RdprobeNotesPage }", clause).replace("Page: RdprobeNotesPage", page_field)
        write(self.tree, door, text)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Alias")

    def test_rpc_tool_and_event_name_themselves_in_the_agent_half_row(self):
        self.new("feature", "rdprobe")
        self.new("rpc", "rdprobe", "rdprobe_ping")
        self.assertEqual(self.row("rdprobe"), "| `backend/rdprobe/` | RPC `rdprobe_ping` | nothing; no events |")
        self.new("rpc", "rdprobe", "rdprobe_pong")
        self.new("tool", "rdprobe", "rdprobe_go")
        self.new("event", "rdprobe", "moved", "--payload", "game")
        self.assertEqual(
            self.row("rdprobe"),
            "| `backend/rdprobe/` | RPCs `rdprobe_ping`, `rdprobe_pong`; tool `chromatic_rdprobe_go` | "
            "nothing; `rdprobe.moved` |",
        )

    def test_an_existing_row_gets_the_tool_after_its_rpcs_and_the_event_after_its_events(self):
        before = self.row("history")
        self.new("tool", "history", "rdprobe_hist")
        self.new("event", "history", "rdprobe_pruned", "--payload", "game")
        after = self.row("history")
        declares, events = after.strip("| ").split(" | ")[1:3]
        self.assertRegex(declares, r"; tools? (`chromatic_\w+`, )*`chromatic_rdprobe_hist`")  # after any it has
        self.assertTrue(declares.startswith(before.split(" | ")[1].split("; ")[0]), after)  # its RPCs stay first
        emitted = events.split("; listens to ")[0]  # whatever history listens to (a branch may add a listener) follows
        self.assertTrue(emitted.endswith(", `history.rdprobe_pruned`"), events)

    def test_a_library_project_tool_s_next_steps_name_project_files_and_the_title(self):
        for name in ("__init__.py", "tool_args.py"):
            write(self.tree, f"backend/library/{name}", (ROOT / f"backend/library/{name}").read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "tool_args")
        steps = self.new("tool", "library", "rdprobe_open")["next"]
        self.assertIn(
            'project files: backend/library/README.md "Project files"; title: games.project_title(root)', steps
        )


class Scaffolds(ScaffoldCase):
    def real(self, *names: str) -> None:
        for name in names:
            (self.tree / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, self.tree / name)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def files(self, files: dict) -> None:
        for name, text in files.items():
            write(self.tree, name, text)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "Known files")

    def readmes(self) -> None:
        taken = " (`install` and `onboarding` are taken: pick another id)"
        self.real("page/pages/setup/index.js")
        self.files(
            {
                "page/pages/build/README.md": README.format(Label="Build", page="build", taken=""),
                "page/pages/setup/README.md": README.format(Label="Setup", page="setup", taken=taken),
            }
        )

    def test_new_tool_quotes_the_contract_placeholder_with_its_line(self):
        out = self.new("tool", "history", "rdfourteen")
        contract = self.read("docs/dev/CONTRACT.md").split("\n")
        first = out["next"][0]
        found = re.search(
            r"in docs/dev/CONTRACT\.md:(\d+) replace 'say what it does and when the agent calls it' "
            r"after `chromatic_rdfourteen`",
            first,
        )
        self.assertTrue(found, first)
        self.assertIn("say what it does and when the agent calls it", contract[int(found.group(1)) - 1])


class ToolRoundNineNew(ScaffoldCase):
    def test_the_test_says_it_pins_the_stub_s_answer(self):
        out = self.new("tool", "history", "rdprobe_peek")
        self.assertIn("pins the stub's answer: change it with the real answer", joined(out))
        test = self.read("tests/backend/history/test_tool_rdprobe_peek.py")
        self.assertIn("# Pins the stub's answer: change it with the real answer", test)
        self.new("feature", "rdprobe_lib")
        write(self.tree, "backend/rdprobe_lib/tool_args.py", (ROOT / "backend/library/tool_args.py").read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "A feature with tool_args")
        self.new("tool", "rdprobe_lib", "rdprobe_project_peek")  # tool_args: a project tool by default
        project = self.read("tests/backend/rdprobe_lib/test_tool_rdprobe_project_peek.py")
        self.assertIn("# Pins the stub's answer", project)


class ToolRoundSevenNew(ScaffoldCase):
    def test_the_contract_sentence_names_the_new_tool_last(self):
        contract = flat(self.read("docs/dev/CONTRACT.md"))
        total = int(re.search(r"(\d+) in total", contract).group(1))
        sentence = contract[contract.index("tools, plus") : contract.index(f"{total} in total")]
        self.new("tool", "history", "rdprobe_snap")
        self.new("tool", "history", "rdprobe_shot")
        raw = self.read("docs/dev/CONTRACT.md")
        after = flat(raw)
        said = "say what it does and when the agent calls it"
        self.assertIn(f"and `chromatic_rdprobe_shot` (`backend/history/tools.py`: {said}). {total + 2} in total", after)
        names = re.findall(r"`(chromatic_\w+)`", sentence)
        listed = after[after.index("tools, plus") : after.index(f"{total + 2} in total")]
        self.assertEqual(
            re.findall(r"`(chromatic_\w+)`", listed), [*names, "chromatic_rdprobe_snap", "chromatic_rdprobe_shot"]
        )

    def test_the_lockstep_check_counts_each_new_tool_once(self):  # review 1, follow-up: no bullet after the sentence
        self.new("tool", "history", "rdprobe_snap")
        self.new("tool", "history", "rdprobe_shot")
        raw = self.read("docs/dev/CONTRACT.md")
        self.assertNotIn("- `chromatic_rdprobe_", raw)
        word, listed = test_lockstep.contract_tool_list(raw)
        self.assertEqual(count_words.count_value(word), len(listed), listed)
        self.assertEqual(len(listed), len(set(listed)), listed)


class ToolSelectedGame(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def test_one_line_says_tool_project_first_and_library_game_for_only_for_the_id(self):
        self.real("backend/features.py", "backend/library/*.py", "backend/library/README.md")
        steps = self.new("tool", "library", "rdprobe_pick", "--project")["next"]
        about = [step for step in steps if "library_game_for" in step]
        self.assertEqual(len(about), 1, about)
        self.assertIn(
            "the selected game is this chat's project (or the `project` argument): tool_project, as the stub does; "
            "call host.library_game_for([root]) -> (game id, root) or None (from ..hermes import host) only when you "
            "need the game's library id or entry (e.g. the id player.list_captures(root, game_id) takes)",
            about[0],
        )
        self.assertIn("def list_captures(root: Path, identifier: str)", (ROOT / "backend/player/server.py").read_text())


class NewSteps(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def test_new_tool_says_tool_project_first_and_the_game_card(self):
        self.real("backend/features.py", "backend/library/*.py", "backend/library/README.md")
        said = " ".join(self.new("tool", "library", "rdprobe_card", "--project")["next"])
        self.assertIn(
            "the selected game is this chat's project (or the `project` argument): tool_project, as the stub does; "
            "call host.library_game_for([root])",
            said,
        )
        self.assertIn(
            "game_card.public(root) (None without a game.json); game_card.status(root, strict=True) for what is "
            "missing",
            said,
        )
        card = (ROOT / "backend/library/game_card.py").read_text()
        self.assertIn("def public(root: Path) -> dict | None:", card)
        self.assertIn("*, strict: bool = False", card)
        self.assertIn("def library_game_for(", (ROOT / "backend/hermes/host.py").read_text())


class NewRoundThree(ScaffoldCase):
    def test_a_feature_s_agent_half_row_goes_in_the_feature_table(self):
        path = self.tree / "docs/dev/ARCHITECTURE.md"
        text = path.read_text()
        other = "\n| Module | Why |\n|---|---|\n| `backend/hermes/contracts.py` | pinned contracts |\n"
        at = text.index("`__init__.register()` collects")
        path.write_text(text[:at] + other.lstrip("\n") + "\n" + text[at:])
        git(self.tree, "commit", "-qam", "Another table")
        last = last_feature_row(path.read_text())  # whatever row ends the table now (a branch may have added one)
        self.new("feature", "rdprobe")
        lines = path.read_text().splitlines()
        mine = lines.index("| `backend/rdprobe/` | nothing yet | nothing; no events |")
        self.assertEqual(lines[mine - 1], last)
        self.assertEqual(lines[mine + 1], "")
        self.assertEqual(lines.count("| `backend/rdprobe/` | nothing yet | nothing; no events |"), 1)

    def test_every_branch_says_check_then_commit_then_ship(self):
        """check runs only the fast checks, which pass on uncommitted files: no kind needs a commit first."""
        for step in (["feature", "rdprobe"], ["tab", "build", "rdprobe-extra"]):
            out = self.new(*step, as_json=False)
            self.assertEqual(
                line_with(out, "then:"), "then: python tools/retrodev check, commit, python tools/retrodev ship"
            )


class NewTool(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def test_the_game_card_step_says_to_pass_a_path_and_the_contract_step_names_the_lockstep_count(self):
        self.real("backend/features.py", "backend/library/*.py", "backend/library/README.md")
        said = " ".join(self.new("tool", "library", "rdprobe_card", "--project")["next"])
        self.assertIn(
            "game_card.status(root, strict=True) for what is missing (its missing and problems); both take a Path "
            "and tool_project gives root as a str, so pass them Path(root) (from pathlib import Path)",
            said,
        )
        # What the advice rests on, read from the real files rather than assumed.
        card = (ROOT / "backend/library/game_card.py").read_text()
        self.assertIn("def public(root: Path) -> dict | None:", card)
        self.assertRegex(card, r"def status\(root: Path,")
        args = (ROOT / "backend/hermes/tool_args.py").read_text()
        self.assertIn("def tool_project(tool: str, args: dict, kwargs: dict) -> tuple[str | None, str | None]:", args)
        self.assertIn(
            "(another tool named there goes without backticks: tests/repo/test_lockstep.py counts every backticked "
            "chromatic_* name in that sentence as a listed tool)",
            said,
        )
        self.assertIn(
            r're.findall(r"`(chromatic_\w+)`", sentence.group(2))', (ROOT / "tests/repo/test_lockstep.py").read_text()
        )
