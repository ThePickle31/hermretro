"""The trial rounds' regressions for this area (RoundEightNew, RoundEighteen, RoundElevenNew, RoundFive, RoundFour, RoundFourteen, RoundNineNew, RoundNineteen, RoundSevenNew, RoundSeventeen, RoundSixteen, RoundTenNew, RoundThree, RoundTwenty, RoundTwo), filed beside the code they test.

Run alone: python -m unittest tests.retrodev.test_new_rpc
"""

import argparse
import ast
import re
import shutil
import tomllib
from retrodev import cli, scaffold_rpc
from tests.retrodev.fixture import git, parallel, write
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase
from tests.retrodev.fixture import retrodev_docs
from retrodev import scaffold
from retrodev import scaffold_readme
import logging
from types import SimpleNamespace

load_tests = parallel


def joined(out) -> str:
    return " ".join(out["next"])


def help_of(*path: str) -> str:
    """The --help text of a subcommand (``new rpc``), formatted without printing it."""
    found = cli.parser()
    for name in path:
        found = next(a for a in found._actions if isinstance(a, argparse._SubParsersAction)).choices[name]
    return " ".join(found.format_help().split())


def steps(out) -> list[str]:
    return [line.removeprefix("next: ") for line in out.splitlines() if line.startswith("next: ")]


def agent_row(text: str, feature: str) -> str:
    rows = text.split("## The agent half", 1)[1].splitlines()
    return next(line for line in rows if line.startswith(f"| `backend/{feature}/` |"))


SETUP_RPCS = '''"""The Setup page's RPCs: status, doctor, activity, studio_profile, install and remove_tools. Declared with
@rpc; registered in this order (backend/hermes/declare.py)."""

from __future__ import annotations

from ..hermes import host
from ..hermes.declare import rpc

logger = host.logger
''' + "".join(
    f'\n\n@rpc("{name}")\ndef rpc_{name}(ctx):\n    return lambda params, **_kwargs: {{"ok": True}}\n'
    for name in ("status", "doctor", "activity", "studio_profile", "install", "remove_tools")
)

README = """# {Label}

**Shows:** the page.

**Tabs:** none.

**Slots:** declares none, contributes none.

**Tests:** `tests/page/page-{page}.test.mjs`.

## Adding a tab here

Make a folder `page/pages/{page}/<tab>/`{taken} with an `index.js` exporting `{{ id, label, Page }}`.
"""

SHELLS = "a page that reads a new shell field adds it to its fixture in tests/page/shells.mjs (pageShell())"

PAGES = "docs/dev/STUDIO-PAGES.md"

PAGES_TEXT = (
    "# Pages\n\n## Pages (one control)\n\n### Home\n\n- hero\n\n## Rdbuild: one game\n\n### Binding\n\n### Page\n\n"
    "- chat\n\n## Adding to the page\n\n### A tab\n\nTesting a tab:\n\n```js\nawait runScenario(async () => {})\n```\n\n"
    "### An event\n"
)


class RpcRoundEightNew(ScaffoldCase):
    def test_the_module_suggestion_reads_the_one_size_rule(self):  # follow-up of #60: one source for the size
        warn = tomllib.loads((ROOT / "tools/layout.toml").read_text())["size"]["warn"]
        self.assertEqual(scaffold_rpc.big_rpcs(), warn - scaffold_rpc.MODULE_MARGIN)
        self.assertIn(f"over {warn - scaffold_rpc.MODULE_MARGIN} lines", help_of("new", "rpc"))

        def noted(threshold: int) -> str:  # the tree's own layout.toml decides
            layout = self.read("tools/layout.toml")
            write(self.tree, "tools/layout.toml", re.sub(r"(?m)^warn = \d+", f"warn = {threshold + 50}", layout))
            git(self.tree, "add", "-A")
            git(self.tree, "commit", "-q", "-m", f"warn at {threshold + 50}")
            return self.new("rpc", "history", "rdprobe_sized", "--dry-run", as_json=False)

        out = noted(0)  # round 20: the size rpcs.py would have with the RPC in decides, not its size now
        size = int(re.search(r"note: backend/history/rpcs.py would have (\d+) lines", out).group(1))
        self.assertGreater(size, len(self.read("backend/history/rpcs.py").splitlines()))
        self.assertIn("note: backend/history/rpcs.py would have", noted(size - 1))
        self.assertNotIn("note: backend/history/rpcs.py", noted(size))

    def test_game_s_next_steps_key_and_call_with_the_game_where_the_game_is(self):
        steps = joined(self.new("rpc", "history", "rdprobe_card", "--game"))
        self.assertIn("run the query in the component that has the game", steps)
        self.assertIn("queryKey: [ID, 'rdprobe_card', game.id]", steps)  # round nine: one rule, as captures has it
        self.assertIn("callStudioOnly(RPC_RDPROBE_CARD, { game: game.id })", steps)  # history: its data folder
        self.assertIn(
            "callStudioOnly (page/app/backend.js; the hermretro profile only) if the handler reads or binds a "
            "profile's Build conversations",
            steps,
        )
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


class RpcBesideItsFeatureRoundEighteen(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def test_a_history_rpc_gets_its_table_row_after_build_restore(self):
        mine = re.findall(r'@rpc\("(\w+)"\)', self.read("backend/history/rpcs.py"))  # a grown tree may hold more
        self.assertIn("build_restore", mine)
        out = self.new("rpc", "history", "rdprobe_list", "--game")
        contract = self.read("docs/dev/CONTRACT.md")
        lines = contract.splitlines()
        at = max(i for i, line in enumerate(lines) if any(line.startswith(f"| `{rpc}` |") for rpc in mine))
        self.assertEqual(
            lines[at + 1],
            "| `rdprobe_list` | `{ game }` | `{ ok, game }`, or `NO_GAME`: "
            "Describe what it does, its params and its result here. |",
        )
        self.assertNotIn("### `rdprobe_list`", contract)
        steps = " ".join(out["next"])
        self.assertIn(f"grep -n '`{mine[-1]}' docs/dev/CONTRACT.md", steps)
        self.assertNotIn("add its row to the RPC table", steps)

    def test_a_setup_rpc_follows_setup_s_last_section_and_others_keep_today_s_place(self):
        text = "## A\n\n### `one` — x\n\nOne.\n\n## Hardware\n\nH.\n\n### `two` — y\n\nTwo.\n\n## Other\n\nO.\n\n## Studio pages\n"
        placed = scaffold_rpc.contract_placed(text, ["one", "two"], "new", "### `new` — z\n\nNew.\n", False)
        self.assertIn("Two.\n\n### `new` — z\n\nNew.\n\n## Other", placed)
        alone = scaffold_rpc.contract_placed(text, ["zzz"], "new", "### `new` — z\n\nNew.\n", False)
        self.assertIn("O.\n\n### `new` — z\n\nNew.\n\n## Studio pages", alone)


class RpcActionStepRoundEighteen(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def test_the_steps_say_how_to_call_and_answer_a_one_off_action(self):
        harness = (ROOT / "tests/page/sdk-stub.mjs").read_text()
        self.assertIn("if (method in scenario.byMethod)", harness)
        self.assertIn(
            "scenario.byMethod['plugin.hermretro.build'] = params =>",
            (ROOT / "tests/page/page-build.test.mjs").read_text(),
        )
        self.assertIn("callStudioOnly(RPC_BUILD_RESTORE", (ROOT / "page/pages/build/build-page.js").read_text())
        steps = " ".join(self.new("rpc", "history", "rdprobe_undo")["next"])
        self.assertIn("for an action (a button that changes something, run once) instead of a read: no useQuery", steps)
        self.assertIn("`await callStudioOnly(RPC_RDPROBE_UNDO, { ... })` from the click handler", steps)
        self.assertIn("scenario.byMethod['plugin.hermretro.rdprobe_undo'] = params => ({ ok: true })", steps)


class ToolAndRpcRoundElevenNew(ScaffoldCase):
    def test_a_game_rpc_says_to_check_what_games_returns_first(self):
        steps = joined(self.new("rpc", "history", "rdprobe_rom", "--game"))
        self.assertIn(
            "check what the `games` RPC already returns about a game (rom, state, web, ...) before adding a per-game "
            "query",
            steps,
        )


class NewRoundFive(ScaffoldCase):
    def ran(self, *argv) -> list[str]:
        self.clear_log()
        code, out = self.run_cli("new", *argv, cwd=self.tree)
        self.assertEqual(code, 0, out)
        return [name for entry in self.check_log() for name in entry["names"]]

    def test_the_rpc_test_uses_isolated_home_and_the_next_steps_name_the_page_docs(self):
        out = self.new("rpc", "history", "rdprobe_ping")
        test = self.read("tests/backend/history/test_rpc_rdprobe_ping.py")
        self.assertIn("from tests.support import isolated_home", test)
        self.assertNotIn('HERMRETRO_HOME": home.name', test)
        self.assertIn(
            "if a page shows it, describe it in that page's README **Shows:** line and as a bullet in its `### <Page>` "
            "subsection under `## Pages` of docs/dev/STUDIO-PAGES.md (the table row stays short)",
            out["next"],
        )
        self.assertIn("calls `isolated_home(self)`", retrodev_docs())


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

    def test_rpc_next_steps_name_shell_via_profile(self):
        self.new("feature", "rdprobe")  # not history or assets, whose RPCs go through callStudioOnly (round nine)
        steps = " ".join(self.new("rpc", "rdprobe", "rdprobe_recent")["next"])
        self.assertIn("queryKey: [ID, 'rdprobe_recent', shell.viaProfile]", steps)


class ScaffoldsRoundFourteen(ScaffoldCase):
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

    def test_new_rpc_adds_its_name_to_the_docstring_s_rpc_list(self):
        self.real("backend/setup/__init__.py", "backend/setup/README.md")
        self.files({"backend/setup/rpcs.py": SETUP_RPCS})
        out = self.new("rpc", "setup", "rdfourteen_ping")
        doc = self.read("backend/setup/rpcs.py").split('"""')[1]
        self.assertIn("install, remove_tools and rdfourteen_ping.", " ".join(doc.split()))
        self.assertTrue(all(len(line) <= 120 for line in doc.split("\n")))
        self.assertIn("added `rdfourteen_ping` to the list of RPCs in backend/setup/rpcs.py's docstring", out["done"])

    def test_a_long_name_rewraps_the_docstring(self):
        said = scaffold_rpc.docstring_listed(SETUP_RPCS, "a_rather_long_rpc_name_for_wrapping")
        doc = said.split('"""')[1]
        self.assertIn("remove_tools and a_rather_long_rpc_name_for_wrapping.", " ".join(doc.split()))
        self.assertTrue(all(len(line) <= 117 for line in doc.split("\n")), doc)
        other = SETUP_RPCS.replace("status, doctor, activity, studio_profile, install and remove_tools", "the setup")
        self.assertIsNone(scaffold_rpc.docstring_listed(other, "x_y"))


class RpcRoundNineNew(ScaffoldCase):
    def test_game_runs_its_query_where_the_game_is_keyed_on_the_game_alone(self):
        steps = joined(self.new("rpc", "history", "rdprobe_card", "--game"))
        self.assertIn("useQuery({ queryKey: [ID, 'rdprobe_card', game.id], queryFn: () => callStudioOnly(", steps)
        self.assertNotIn("page's own Page component", steps, "one rule for --game: where the game is")
        self.assertIn(SHELLS, steps)
        bar = (ROOT / "page/pages/emulator/emulator-bar.js").read_text()  # the real per-game query it points to
        self.assertIn("queryKey: [ID, 'captures', game?.id ?? null]", bar)

    def test_history_and_assets_rpcs_go_through_call_studio_only_others_through_call_studio(self):
        steps = joined(self.new("rpc", "history", "rdprobe_list"))
        # round ten: what the handler reads decides, not the feature; history and assets stay the default
        self.assertIn(
            "if the handler reads or binds a profile's Build conversations or its plugin data folder "
            "(host._data_dir(): snapshots, asset versions); otherwise callStudio",
            steps,
        )
        self.assertIn("history and assets RPCs usually do: check what yours reads", steps)
        self.assertNotIn("reads that folder: use callStudioOnly", steps)
        self.assertIn(SHELLS, steps)
        self.new("feature", "rdprobe")
        steps = joined(self.new("rpc", "rdprobe", "rdprobe_count", "--game"))
        self.assertIn("callStudio(RPC_RDPROBE_COUNT, { game: game.id })", steps)
        self.assertIn("useQuery({ queryKey: [ID, 'rdprobe_count', game.id], queryFn: () => callStudio(", steps)
        self.assertNotIn("shell.viaProfile", steps, "a per-game key leaves viaProfile out, as captures and player do")
        studio = (ROOT / "page/app/studio-page.js").read_text()  # the real per-game callStudio query and games'
        self.assertIn("queryKey: [ID, 'player', game?.id ?? null, emu.reload]", studio)
        self.assertIn("queryKey: [ID, 'games', viaProfile]", studio)
        self.assertTrue(set(scaffold_rpc.STUDIO_ONLY), "the rule names the features it covers")
        for feature in scaffold_rpc.STUDIO_ONLY:  # each reads the plugin data folder, as the step says
            self.assertIn("host._data_dir()", (ROOT / f"backend/{feature}/rpcs.py").read_text(), feature)

    def test_the_next_steps_name_contract_s_page_rpc_table_and_what_it_lists(self):
        listed = scaffold_rpc.page_rpcs(self.read("docs/dev/CONTRACT.md"))
        self.assertIn("builds", listed)  # read from the tree, not pinned
        self.new("feature", "rdprobe", "--purpose", "A probe")  # no RPC in the table yet (history's get a row)
        steps = joined(self.new("rpc", "rdprobe", "rdprobe_table"))
        self.assertIn(f"'Studio pages (desktop) and their RPCs' (it lists {', '.join(listed)})", steps)
        self.assertEqual(scaffold_rpc.page_rpcs("## Studio pages (desktop) and their RPCs\nno table\n"), [])
        later = "## Studio pages (desktop) and their RPCs\n| `a` | x |\n\n## Other\n| `b` | y |\n"
        self.assertEqual(scaffold_rpc.page_rpcs(later), ["a"], "the next section's table is not the page table")


class RpcPageDocsRoundNineteen(ScaffoldCase):
    def page_step(self, *argv) -> str:
        steps = self.new("rpc", "history", *argv)["next"]
        return next(step for step in steps if step.startswith("if a page shows it"))

    def test_a_page_with_a_section_of_its_own_is_named_with_its_real_heading(self):
        self.commit(self.tree, PAGES, PAGES_TEXT, "A pages doc")
        step = self.page_step("rdprobe_ping")
        self.assertIn("as a bullet in its `### <Page>` subsection under `## Pages` of docs/dev/STUDIO-PAGES.md", step)
        self.assertIn("; Rdbuild's is its `### Page` subsection under `## Rdbuild: one game`", step)
        self.assertNotIn("Home's", step)

    def test_every_heading_named_for_the_real_doc_is_in_it(self):
        doc = (ROOT / PAGES).read_text()
        tops = re.findall(r"under `## ([^`]+)`", scaffold_readme.own_sections(doc))
        self.assertTrue(tops, "own_sections names at least one heading of the real doc")
        for top in tops:
            self.assertIn(f"\n## {top}\n", doc)
            self.assertIn("### Page", doc.split(f"\n## {top}\n")[1].split("\n## ")[0])

    def test_a_game_rpc_points_at_contract_s_game_object_and_its_card(self):
        steps = " ".join(self.new("rpc", "history", "rdprobe_rom", "--game")["next"])
        self.assertIn("docs/dev/CONTRACT.md 'The game object' lists each field, the game card's (`card`", steps)
        self.assertIn("\n## The game object\n", self.read("docs/dev/CONTRACT.md"))
        self.commit(self.tree, "docs/dev/CONTRACT.md", "# Contract\n", "No game object")
        steps = " ".join(self.new("rpc", "history", "rdprobe_web", "--game")["next"])
        self.assertNotIn("The game object", steps)
        self.assertIn("before adding a per-game query (its row in docs/dev/CONTRACT.md", steps)


class RpcRoundSevenNew(ScaffoldCase):
    def test_next_steps_say_where_a_page_s_query_goes(self):
        steps = self.new("rpc", "history", "rdprobe_recent")["next"]
        self.assertIn(
            "in the page's own Page component, or a hook it calls (as page/pages/setup/install/installer.js's "
            "useInstall does for the Setup page), and pass the result down as a prop",
            " ".join(steps),
        )
        self.assertIn("extend tests/page/page-<page>.test.mjs", " ".join(steps))
        self.assertIn("useQuery({", (ROOT / "page/pages/setup/install/installer.js").read_text())  # round 16

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

    def test_an_rpc_named_after_the_handler_s_imports_answers_in_every_variant(self):  # review 2, 2
        variants = [
            ("host", ["--game"], "rpcs"),
            ("logger", ["--game", "--module", "logger_rpcs"], "logger_rpcs"),
            ("dict", [], "rpcs"),
            ("isinstance", ["--module", "isinstance_rpcs"], "isinstance_rpcs"),
        ]
        for name, flags, _module in variants:
            self.new("rpc", "history", name, *flags)
        roots = {"g": "/games/g"}
        host = SimpleNamespace(_game_root=roots.get, logger=logging.getLogger("rdprobe"))
        for name, flags, module in variants:
            source = self.read(f"backend/history/{module}.py")
            self.assertIn("    def _answer(params, **_kwargs):", source)
            self.assertNotIn(f"    def {name}(", source)
            scope = {"rpc": lambda _name: lambda factory: factory, "host": host, "logger": host.logger}
            code = re.sub(r"^from \.\S* import .*$", "", source, flags=re.M)
            code = re.sub(r"^logger = host\.logger.*$", "", code, flags=re.M)
            exec(compile(code, f"{module}.py", "exec"), scope)
            answer = scope[f"rpc_{name}"](None)
            if "--game" in flags:
                self.assertEqual(answer({"game": "g"}), {"ok": True, "game": "g"}, name)
                self.assertEqual(answer({"game": "x"})["code"], "NO_GAME", name)
            else:
                self.assertEqual(answer({"echo": 1}), {"ok": True, "echo": 1}, name)


class ReservedScenarioKeysRoundSeventeen(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def test_new_rpc_refuses_ambient_a_null_key_the_harness_reads(self):
        self.real("tests/page/sdk-stub.mjs", "tests/page/harness.mjs", "backend/setup/*.py", "backend/setup/*.md")
        out = self.new("rpc", "setup", "ambient", "--dry-run", code=1)
        self.assertIn("reserves scenario.ambient", out["error"]["message"])
        from retrodev import scaffold_rpc

        reserved = scaffold_rpc.reserved_scenario(scaffold.Plan(self.tree))
        self.assertIn("ambient", reserved)
        self.assertFalse({"status", "doctor", "activity"} & reserved, reserved)

    def test_new_rpc_refuses_a_key_the_page_harness_keeps_on_scenario(self):
        self.real("tests/page/sdk-stub.mjs", "tests/page/harness.mjs", "backend/setup/*.py", "backend/setup/*.md")
        for name in ("storage", "calls", "queries"):
            with self.subTest(name=name):
                out = self.new("rpc", "setup", name, "--dry-run", code=1)
                self.assertIn(f"reserves scenario.{name}", out["error"]["message"])
                self.assertIn("pick another RPC name", out["error"]["fix"])
        self.assertIn("disk_usage", self.new("rpc", "setup", "storage", "--dry-run", code=1)["error"]["fix"])
        self.new("rpc", "setup", "disk_usage", "--dry-run")

    def test_query_answers_are_not_reserved(self):
        self.real("tests/page/sdk-stub.mjs", "tests/page/harness.mjs")
        from retrodev import scaffold_rpc

        plan = scaffold.Plan(self.tree)
        reserved = scaffold_rpc.reserved_scenario(plan)
        self.assertTrue({"storage", "calls", "queries", "queryData", "byMethod", "revealed", "lastParams"} <= reserved)
        self.assertFalse({"status", "doctor", "activity", "games", "player"} & reserved, reserved)


class NewStepsRoundSixteen(ScaffoldCase):
    def real(self, *patterns: str) -> None:
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                write(self.tree, str(path.relative_to(ROOT)), path.read_text())
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-q", "-m", "More real files")

    def test_new_rpc_names_a_real_use_query_and_scenario_queries(self):
        said = " ".join(self.new("rpc", "history", "rdprobe_recent")["next"])
        self.assertIn("page/pages/setup/install/installer.js's useInstall", said)
        self.assertNotIn("games-page.js", said)
        self.assertIn("scenario.queries.some(q => q.key === 'rdprobe_recent')", said)
        self.assertIn("useQuery({", (ROOT / "page/pages/setup/install/installer.js").read_text())
        stub = (ROOT / "tests/page/sdk-stub.mjs").read_text()
        self.assertIn("const key = options.queryKey[1]", stub)
        self.assertIn("scenario.queries.push({ key,", stub)
        self.assertIn("takes `--module <name>_rpcs`", retrodev_docs("README.md"))


class RpcRoundTenNew(ScaffoldCase):
    def test_what_the_handler_reads_decides_the_call(self):
        self.new("feature", "rdprobe")
        steps = joined(self.new("rpc", "rdprobe", "rdprobe_peek"))
        self.assertIn(
            "if the handler reads or binds a profile's Build conversations or its plugin data folder "
            "(host._data_dir(): snapshots, asset versions); otherwise callStudio",
            steps,
        )
        self.assertIn("what the handler reads decides, not the feature", steps)
        self.assertNotIn("usually do", steps, "the default for history and assets only")
        self.assertIn("callStudioOnly", retrodev_docs("REFERENCE.md"))
        self.assertIn("chosen by what the handler reads, not by the feature", retrodev_docs("REFERENCE.md"))


class NewRoundThree(ScaffoldCase):
    def test_rpc_next_steps_say_when_to_set_the_scenario_and_what_each_call_resolves_to(self):
        steps = " ".join(self.new("rpc", "history", "rdprobe_recent")["next"])
        self.assertIn("set before the page renders", steps)
        self.assertNotIn("enabled", steps)  # round nine: a page's query, as a page writes it (no enabled)
        self.assertIn("callStudio and callStudioOnly resolve to the RPC's answer itself", steps)
        self.assertIn("callBackend resolves to { data }", steps)
        backend = (ROOT / "page/app/backend.js").read_text()  # what the hint claims, in the real page
        self.assertIn("return { data: await host.requestProfile(", backend)
        studio = backend[backend.index("export async function callStudio(") :].split("\n}")[0]
        self.assertNotIn("data:", studio)


class RpcSizeRoundTwenty(ScaffoldCase):
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


class NewKindsRoundTwoRoundTwo(ScaffoldCase):
    def test_rpc_next_steps_show_the_page_query_and_the_test_answer(self):
        out = self.new("rpc", "history", "rdprobe_recent")
        steps = " ".join(out["next"])
        self.assertIn(
            "useQuery({ queryKey: [ID, 'rdprobe_recent'], queryFn: () => callStudioOnly(RPC_RDPROBE_RECENT) })",
            steps,
        )
        self.assertIn("scenario.rdprobe_recent = answered(", steps)
        studio = (ROOT / "page/app/studio-page.js").read_text()  # the names the snippet uses are the real ones
        self.assertIn("queryKey: [ID, 'games', viaProfile]", studio)
        self.assertIn("export async function callStudio(", (ROOT / "page/app/backend.js").read_text())
        self.assertIn("export const ID = ", (ROOT / "page/app/ids.js").read_text())
        self.assertIn("const answered = ", (ROOT / "tests/page/harness.mjs").read_text())
        self.assertIn("const key = options.queryKey[1]", (ROOT / "tests/page/sdk-stub.mjs").read_text())
