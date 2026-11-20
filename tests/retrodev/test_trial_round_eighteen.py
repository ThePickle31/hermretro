"""Friction the eighteenth round of fresh-agent trials found: `new event`'s test lacked isolated_home and sampled every
key as a string, and its CONTRACT row differed from its neighbours; `new event|listener|rpc` left the feature README's
Tests line behind; `new rpc` put a feature's RPC far from its others and assumed a read query; `new listener --dry-run`
refused an event a plan had not added yet; `new tool` put its sibling import out of order; sync's moved-block hint, the
body warning on a synced takeover, `start`'s silence about empty body sections, and the unit row's layout summary.
Each test failed before its fix.

Run alone: python -m unittest tests.retrodev.test_trial_round_eighteen
"""

import importlib.util
import io
import re
import unittest
from pathlib import Path

from retrodev import body_names, config, output, scaffold_backend, scaffold_payload, scaffold_rpc

from tests.retrodev.fixture import GOOD_BODY, RepoCase, git, parallel, write
from tests.retrodev.test_trial_round_seventeen import RealFiles

load_tests = parallel
ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = "game=<library id, str>, root=<the real project folder, pathlib.Path>, count=<how many, int>"


def events_table(contract: str) -> list[list[str]]:
    body = contract.split("## Events between backend features", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in body.splitlines() if line.startswith("| `")]
    return [[cell.strip() for cell in row.strip().strip("|").split(" | ")] for row in rows]


class EventTest(RealFiles):
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
        from retrodev import scaffold

        self.assertEqual(
            scaffold.TOKEN.sub(lambda m: m.group(0)[0] if m.group(1) is None else "X", "{{a}} {b}"), "{a} X"
        )
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


class EventContractRow(RealFiles):
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


TESTS = "## Tests\n\n"


class ReadmeTestsLine(RealFiles):
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


class RpcBesideItsFeature(RealFiles):
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


class RpcActionStep(RealFiles):
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


class ListenerDryRun(RealFiles):
    def test_a_dry_run_lists_the_files_for_an_event_not_declared_yet_and_the_real_run_refuses(self):
        self.real("backend/assets/*.py", "backend/assets/README.md")
        out = self.new("listener", "assets", "history.rdprobe_later", "--dry-run", as_json=False)
        self.assertIn("would create  tests/backend/assets/test_listener_on_history_rdprobe_later.py", out)
        self.assertIn("would change  backend/assets/listeners.py", out)
        self.assertIn(
            "note: no front door declares history.rdprobe_later yet: the real run refuses until it exists", out
        )
        refused = self.new("listener", "assets", "history.rdprobe_later", code=1)
        self.assertIn("no front door declares the event 'history.rdprobe_later'", refused["error"]["message"])


class ToolImportSorted(RealFiles):
    def test_the_sibling_import_goes_where_isort_puts_it(self):
        self.real("backend/setup/*.py", "backend/setup/README.md")
        self.new("tool", "setup", "probe", "--module", "probe_tools", "--step", "Probing", "Probed")
        imports = [line for line in self.read("backend/setup/tools.py").splitlines() if line.startswith("from .")]
        self.assertEqual(imports[-2:], ["from . import probe_tools", "from . import provision"])


class Docs(unittest.TestCase):
    def test_the_readme_and_reference_say_it(self):
        readme = (ROOT / "tools/retrodev/README.md").read_text()
        quick = readme.split("## Quick path", 1)[1].split("\n5. ", 1)[0]
        self.assertIn("an RPC about one game takes `--game`", quick)
        split = readme.split("### Split a long module", 1)[1].split("\n## ", 1)[0]
        self.assertIn("`from .<new> import X as X`", split)
        self.assertIn("`tests/retrodev` (trial tests read file text)", split)
        self.assertIn("400-line warning", split)
        self.assertLess(readme.index("### Rename or move a module"), readme.index("### Split a long module"))
        reference = (ROOT / "tools/retrodev/REFERENCE.md").read_text()
        check = reference.split("### `check [names", 1)[1].split("\n### ", 1)[0]
        self.assertIn("`check <names>` counts toward that gate too", check)
        sync = reference.split("### `sync`", 1)[1].split("\n### ", 1)[0]
        self.assertIn(
            "first check whether\ndev's version there already does what your lines did; if it does, add only a test",
            sync,
        )


class SyncedTakeoverBody(RepoCase):
    def warning(self, tree, what: str) -> str:
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        return body_names.warning(ctx, GOOD_BODY.replace("Things.", what)) or ""

    def test_no_warning_for_what_dev_moved_once_synced_and_still_one_without_a_sync(self):
        self.on_dev("tools/old_helpers.py", "def rdprobe_helper():\n    return 1\n", "A helper")
        git(self.main, "fetch", "-q", "origin")
        synced, plain = self.worktree("fix/taken"), self.worktree("fix/plain")
        for tree in (synced, plain):
            self.commit(tree, "tools/kept.py", "VALUE = 1\n")
        other = self.base / "other"
        git(other, "rm", "-q", "tools/old_helpers.py")
        write(other, "tools/new_helpers.py", "def rdprobe_renamed():\n    return 1\n")
        git(other, "add", "-A")
        git(other, "commit", "-q", "-m", "Dev moves the helper")
        git(other, "push", "-q", "origin", "dev")
        git(synced, "fetch", "-q", "origin")
        git(synced, "merge", "-q", "--no-edit", "origin/dev")
        said = "- Explained why `tools/old_helpers.py`'s `rdprobe_helper` went away."
        self.assertEqual(self.warning(synced, said), "")
        git(plain, "fetch", "-q", "origin")
        away = self.warning(plain, said)
        self.assertIn("`tools/old_helpers.py`", away)  # its tree still has the helper itself


class StartNamesEmptySections(RepoCase):
    def test_start_prints_the_sections_left_empty_and_copies_the_plan_s_risk(self):
        self.new_plan("risky")
        self.run_cli("plan", "approve", "risky", "--words", "start")
        code, out = self.run_cli("start", "feat/risky", "--no-setup")
        self.assertEqual(code, 0, out)
        self.assertIn("(still empty: How verified, Risk and rollback)", out)
        from retrodev import plan

        path = self.new_plan("careful")
        text = path.read_text().replace(
            "## Not in scope", "## Risk and rollback\nRevert the commit.\n\n## Not in scope"
        )
        path.write_text(text)
        self.run_cli("plan", "approve", "careful", "--words", "start")
        code, out = self.run_cli("start", "feat/careful", "--no-setup")
        self.assertEqual(code, 0, out)
        self.assertIn("(still empty: How verified)", out)
        body = (self.main / "notes" / "pr" / "careful.md").read_text()
        self.assertRegex(
            body,
            r"## Risk and rollback\n(?:<!--.*?-->\n)*Revert the commit\.",
        )
        self.assertIn("## Risk and rollback\n<!--", plan.TEMPLATE)
        self.run_cli("plan", "new", "bare")
        code, out = self.run_cli("plan", "approve", "bare", "--words", "start", as_json=True)
        self.assertEqual(code, 1, out)
        self.assertIn("'## Risk and rollback'", out["error"]["message"])


class LayoutSummary(unittest.TestCase):
    def test_the_branch_s_own_big_files_are_named_first(self):
        spec = importlib.util.spec_from_file_location("unit_home_round_eighteen", ROOT / "tools/py/unit_home.py")
        unit_home = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(unit_home)
        lines = [f"layout warning: backend/f{n}.py has 450 lines (over 400)" for n in range(9)]
        note = unit_home.layout_note(lines, ["backend/f8.py", "docs/x.md"])
        self.assertTrue(re.search(r"over the size warning: backend/f8\.py, backend/f0\.py", note), note)
        self.assertIn("and 3 more", note)


if __name__ == "__main__":
    unittest.main()
