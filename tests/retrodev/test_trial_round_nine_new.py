"""Friction the ninth round of fresh-agent trials found in `new`: rpc's next steps gave two rules for a page's
query and none for an RPC reading the plugin data folder, nor the shell fixture or CONTRACT's page RPC table;
event left `key=<...>` placeholders unnamed; a tool's test pinned the stub's answer silently; --dry-run refused dev;
a tab on the Emulator page said nothing of the player under it; filling a slot had no command. Each test failed
before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_nine_new
"""

import json
import re
from pathlib import Path

from retrodev import scaffold_rpc

from tests.retrodev import test_scaffold_tree as tree_test
from tests.retrodev.fixture import git, parallel, retrodev_docs, write
from tests.retrodev.test_scaffold import ROOT, ScaffoldCase

load_tests = parallel
SHELLS = "a page that reads a new shell field adds it to its fixture in tests/page/shells.mjs (pageShell())"


def joined(out) -> str:
    return " ".join(out["next"])


class Rpc(ScaffoldCase):
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
        self.assertEqual(scaffold_rpc.STUDIO_ONLY, ("history", "assets"))
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


class Event(ScaffoldCase):
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

    def test_the_reference_example_says_what_each_key_holds(self):
        self.assertIn("`--payload 'game=<id>'", retrodev_docs("REFERENCE.md"))


class Tool(ScaffoldCase):
    def test_the_test_says_it_pins_the_stub_s_answer(self):
        out = self.new("tool", "history", "rdprobe_peek")
        self.assertIn("pins the stub's answer: change it with the real answer", joined(out))
        test = self.read("tests/backend/history/test_tool_rdprobe_peek.py")
        self.assertIn("# Pins the stub's answer: change it with the real answer", test)
        project = (ROOT / "tools/retrodev/templates/tool/test_tool_project.py.tmpl").read_text()
        self.assertIn("# Pins the stub's answer", project)


class DryRunAnywhere(ScaffoldCase):
    def test_a_dry_run_on_dev_lists_the_files_and_writes_nothing(self):
        git(self.tree, "switch", "-q", "-c", "master")  # a protected branch, holding the real files new reads
        state = Path(git(self.main, "rev-parse", "--git-common-dir").strip())
        state = (state if state.is_absolute() else self.main / state) / "retrodev"
        before = sorted((p.relative_to(state), p.read_bytes()) for p in state.rglob("*") if p.is_file())
        self.assertTrue(before, f"the branch record is in {state}")
        status = git(self.tree, "status", "--porcelain")
        done, out = self.run_cli("new", "feature", "rdprobe", "--dry-run", cwd=self.tree, as_json=True)
        self.assertEqual(done, 0, out)
        self.assertIn("backend/rdprobe/__init__.py", out["created"])
        self.assertEqual(git(self.tree, "status", "--porcelain"), status)
        after = sorted((p.relative_to(state), p.read_bytes()) for p in state.rglob("*") if p.is_file())
        self.assertEqual(after, before, "the state is untouched too")
        done, out = self.run_cli("new", "feature", "rdprobe", cwd=self.tree)
        self.assertEqual(done, 1, out)
        self.assertIn("only on a work branch", out)


class Tab(ScaffoldCase):
    def test_a_page_with_a_player_under_it_says_it_stays_under_every_tab(self):
        self.new("page", "rdprobe-play")
        door = self.tree / "page/pages/rdprobe-play/index.js"
        text = door.read_text().replace("  Page: RdprobePlayPage\n", "  Page: RdprobePlayPage,\n  pad: 'flush',\n")
        write(self.tree, "page/pages/rdprobe-play/index.js", text)
        git(self.tree, "add", "-A")
        git(self.tree, "commit", "-qm", "pad")
        steps = joined(self.new("tab", "rdprobe-play", "extra"))
        self.assertIn("the shell's player and BelowPlayer stay under every tab", steps)
        self.new("page", "rdprobe-flat")
        self.assertNotIn("BelowPlayer", joined(self.new("tab", "rdprobe-flat", "extra")))
        shell = (ROOT / "page/app/studio-page.js").read_text()  # body, then the stage, then BelowPlayer
        order = [shell.index("...body,"), shell.index("              stage,"), shell.index("currentPage.BelowPlayer ?")]
        self.assertEqual(order, sorted(order))


class Contribution(ScaffoldCase):
    def host(self) -> None:
        self.new("page", "rdprobe-host")
        self.new("slot", "rdprobe-host", "extra", "--doc", "Buttons at the end. Props: { ctx }")

    def test_it_writes_the_stub_contributes_the_readme_and_the_filled_assertion(self):
        self.host()
        self.new("page", "rdprobe-giver")  # a page of its own: a real page may contribute already (the guard's)
        out = self.new("contribution", "rdprobe-giver", "rdprobe-host.extra", "RdprobeButton")
        folder = "page/pages/rdprobe-giver"
        self.assertEqual(out["created"], [f"{folder}/rdprobe-button.js"])
        self.assertIn("export function RdprobeButton(props) {", self.read(f"{folder}/rdprobe-button.js"))
        door = self.read(f"{folder}/index.js")
        self.assertIn("import { RdprobeButton } from './rdprobe-button.js'", door)
        self.assertIn("'rdprobe-host.extra': [RdprobeButton]", door)
        self.assertIn("contributes `RdprobeButton` to `rdprobe-host.extra`", self.read(f"{folder}/README.md"))
        registry = self.read("tests/page/registry.test.mjs")
        self.assertIn(f"const {{ RdprobeButton }} = await import('../../{folder}/rdprobe-button.js')", registry)
        self.assertRegex(registry, r"const expected = \{[^\n]*'rdprobe-host\.extra': \[RdprobeButton\]")
        steps = joined(out)
        for place in ("'Events and slots today'", "HOSTS"):
            self.assertIn(place, steps)
        # the host's Slots line is written, not left as a step (round 14)
        host = " ".join(self.read("page/pages/rdprobe-host/README.md").split())
        self.assertIn("Rdprobe giver fills it with `RdprobeButton`.", host)

    def test_a_second_contribution_joins_the_list_in_pages_order(self):
        self.host()
        self.new("contribution", "rdprobe-host", "rdprobe-host.extra", "RdprobeLater")  # the last page
        self.new("contribution", "build", "rdprobe-host.extra", "RdprobeFirst")  # the first page
        registry = self.read("tests/page/registry.test.mjs")
        self.assertIn("'rdprobe-host.extra': [RdprobeFirst, RdprobeLater]", registry)
        self.new("contribution", "build", "rdprobe-host.extra", "RdprobeSecond")
        self.assertIn("'rdprobe-host.extra': [RdprobeFirst, RdprobeSecond]", self.read("page/pages/build/index.js"))

    def test_an_undeclared_slot_is_refused_naming_the_declared_ones(self):
        self.host()
        before = git(self.tree, "status", "--porcelain")
        out = self.new("contribution", "build", "nowhere.slot", "RdprobeX", code=1)
        self.assertIn("rdprobe-host.extra", out["error"]["fix"])
        self.assertEqual(git(self.tree, "status", "--porcelain"), before)

    def test_the_guard_and_the_fast_scaffold_check_run_it(self):
        self.assertIn("contribution", [step[0] for step in tree_test.STEPS])
        real = [step for step in tree_test.REAL_STEPS if step[0] == "contribution"]
        self.assertEqual(len(real), 1, tree_test.REAL_STEPS)
        self.assertEqual(real[0][1], "build")
        declared = re.findall(
            r"'([a-z-]+\.\w+)':", (ROOT / f"page/pages/{real[0][2].split('.')[0]}/index.js").read_text()
        )
        self.assertIn(real[0][2], declared, "a slot the real tree declares")
        self.assertIn('"tests/retrodev/scaffold_steps.py"', (ROOT / "tools/retrodev/policy.toml").read_text())
        self.assertTrue(json.dumps(real))
