"""`new` on a copy of the real repository: the generated code passes the repository's own checks.

The one slow retrodev test (a few seconds), so it runs only with RD_SCAFFOLD_FULL set: `python tools/check.py
scaffold` (part of `check.py full` and `retrodev check --full`, added by `retrodev check` when a branch changes the
scaffolds or the files they edit; CI's page job runs it). It copies what a commit of this tree would hold into a short temp
folder (a fresh git repository on a work branch, so nothing of this checkout or its .git changes), borrows the
installed tools (.dev/py and tools/npm/node_modules, linked), runs `new feature rdtree`, `new rpc` (four times: plain,
--module, --game, --game with --module: their generated tests register a game with make_library_game), `new tool` (twice: once in its own module; twice more in history, --module first, then a plain one,
which goes in its own module too; once in library, a --project tool; once in rdtree, a --project tool importing
backend/hermes/tool_args.py),
`new event`, `new listener`, `new page rdtree`, `new tab rdtree extra` and `new slot rdtree extraActions`, then, side by side, `tools/check.py lint bundle`, the unit tests that judge structure and lock step (layout,
docs, boundaries, lock step, the registration snapshot, and the generated tests) and the page tests the new names
reach (the registry, the nav). With RD_SCAFFOLD_FULL=nested the full `tools/check.py lint bundle unit page` runs
there instead (it nests the whole unit suite, with tests/repo/test_placeholders.py's gate off for that run only:
the stubs are unfilled), and it is the guard against tests that pin the real tree's content: it first runs the copy's
unit suite as it is (a failure skips the test with "the tree fails unit (fix unit first)", which check.py scaffold
reports as such), notes every real feature README's RPCs/Tools/Listens lines (hand_edits.py), then runs real_steps(copy) after STEPS, each kind once more on a real feature or page as a
contributor's branch would (chosen from what the copy declares), before the full suites; a second guard run does
the same on a copy where setup has tabs, history listens to library.game_presented and history's README names an RPC
module beside rpcs.py already (made only where the copy lacks them: grown_steps). CI's page job runs it in this mode. Skipped when node, the npm tools or the pinned ruff are not set up
here (check.py scaffold then says so). Two more run `new rpc history trial_ping` and `new listener setup library.game_presented` with their own
checks: each completes (tests/repo/test_placeholders.py skips its gate there) and the placeholder gate still fails afterwards.
Two more run `new page rdtabs` (its Page imported under another name; then imported on several lines), then `new tab rdtabs first --from-page` and `new
tab rdtabs second` with their own checks (the page suite among them), then `tools/check.py lint bundle` (the tab
imports the Page's exported name as #pages/..., never ../). One more moves an exported Page that index.js defines
(`new tab rdinline first --from-page`) while another page imports it through #pages/rdinline/index.js: it bundles;
so do inline Pages moved with block comments and into an import with a trailing comma (scaffold_moves.py). One
more runs `new rpc` in history with RPCs named host, logger, dict and isinstance (host inline and --module, in two
rounds) and their generated tests pass: the handler's fixed name _answer shadows nothing it uses.

Run alone: RD_SCAFFOLD_FULL=1 python -m unittest tests.retrodev.test_scaffold_tree
"""

from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from retrodev.scaffold_imports import binding
from retrodev.scaffold_page import own_page

from tests.retrodev.fixture import parallel
from tests.retrodev.hand_edits import note_feature_readmes
from tests.retrodev.scaffold_moves import moved_pages_bundle
from tests.retrodev.tree_copy import copy_base, copy_tree, git_ok, run

load_tests = parallel

ROOT = Path(__file__).resolve().parents[2]
NESTED = "RD_SCAFFOLD_NESTED"
BORROWED = (".dev/py", "tools/npm/node_modules")  # linked; .dev itself stays real (the bundle writes temps there)
# Names no real feature, RPC, tool or page will take (the repository's own scaffolds must not collide with them).
STEPS = [
    ["feature", "rdtree", "--purpose", "A probe feature made by retrodev new"],
    ["rpc", "rdtree", "rdtree_ping"],
    ["rpc", "rdtree", "rdtree_pong", "--module", "rdtree_pong_rpcs"],  # its handler in its own module
    # about one library game: its generated test registers one with tests.support.make_library_game (review 1, 0)
    ["rpc", "rdtree", "rdtree_info", "--game"],
    ["rpc", "rdtree", "rdtree_card", "--game", "--module", "rdtree_card_rpcs"],
    ["tool", "rdtree", "rdtree_ping", "--step", 'Pinging "it"', "Pinged the probe's twin"],
    ["tool", "rdtree", "rdtree_more", "--module", "rdtree_more_tools"],  # its own module, taken in by tools.py
    # history has no tools.py: --module first makes an aggregator one, and a plain tool after it gets its own module
    ["tool", "history", "rdtree_hist_first", "--module", "rdtree_hist_tools"],
    ["tool", "history", "rdtree_hist_second"],
    [
        "tool",
        "library",
        "rdtree_lib",
    ],  # library has tool_args.py: a --project tool, in its own module (tools.py is big)
    ["event", "rdtree", "pinged", "--payload", "count", "--when", "the probe was pinged"],
    ["listener", "rdtree", "library.build_reported"],
    ["page", "rdtree"],
    ["tab", "rdtree", "extra"],
    ["slot", "rdtree", "extraActions", "--doc", "Buttons after the lede. Props: { ctx }"],
]
STEPS += [["tool", "rdtree", "rdtree_proj", "--project"]]  # outside library: imports backend/hermes/tool_args.py
# The guard (nested mode only, after STEPS on the same copy): each kind once more on a REAL feature or page, as a
# contributor's branch does, so a test that pins the real tree's current content (Home's slots, history without a
# listener, a page without tabs) fails here, in CI, instead of in that contributor's branch. feature, page and a
# library tool are in STEPS already. The steps follow what the copy holds (real_steps), so a branch that gives
# setup or prompts tabs, or history a listener, still passes: the tabless-page conversions have their own probe
# fixtures (tab_from_page below, tests/retrodev/test_trial_round_five.py).
REAL_PAGES = ("setup", "prompts")
REAL_LISTENERS = ("history", "assets", "library", "setup", "hermes")  # the first that can take one more


def declared_events(tree: Path) -> dict[str, str]:
    """{event: owning feature} from every front door's EVENTS dict literal."""
    found = {}
    for door in sorted(tree.glob("backend/*/__init__.py")):
        for node in ast.parse(door.read_text()).body:
            target = node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else None
            target = node.target if isinstance(node, ast.AnnAssign) else target
            if getattr(target, "id", "") == "EVENTS" and isinstance(getattr(node, "value", None), ast.Dict):
                for key in node.value.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        found[key.value] = door.parent.name
    return found


def listens(tree: Path, feature: str, event: str) -> bool:
    source = tree / "backend" / feature / "listeners.py"
    text = source.read_text() if source.is_file() else ""
    func = "on_" + event.replace(".", "_")
    return f'@on("{event}")' in text or re.search(rf"^(?:async\s+)?def {func}\b|^{func}\s*=", text, re.M) is not None


def page_steps(tree: Path, page: str, prefix: str) -> list[list[str]]:
    """Two tabs on a real page: the first --from-page when the page has no tabs and imports its Page by name from a
    file of its own (as setup does), else a plain one (a page with tabs, or one that defines its Page in index.js)."""
    text = (tree / "page" / "pages" / page / "index.js").read_text()
    tabless, component = own_page(text)
    kind, _exported, module = binding(text, component) if component else (None, None, None)
    convert = tabless and kind == "named" and (module or "").startswith("./")
    return [["tab", page, f"{prefix}-first", *(["--from-page"] if convert else [])], ["tab", page, f"{prefix}-second"]]


def real_steps(tree: Path) -> list[list[str]]:
    """The guard's steps, chosen from the copy's current declarations (before STEPS run): an event name history does
    not declare, a (feature, event) pair no listener takes yet, the tab kind each real page can take."""
    declared = declared_events(tree)
    pruned = next(f"rdreal_pruned{n or ''}" for n in range(100) if f"history.rdreal_pruned{n or ''}" not in declared)
    pairs = [(f, e) for f in REAL_LISTENERS for e, owner in declared.items() if owner != f and not listens(tree, f, e)]
    feature, event = pairs[0] if pairs else ("library", f"history.{pruned}")  # the new event: nobody hears it yet
    steps = [
        ["rpc", "library", "rdreal_ping"],
        ["rpc", "library", "rdreal_info", "--game"],  # its generated test runs make_library_game on the real tree
        ["event", "history", pruned, "--payload", "game", "--when", "the probe pruned a snapshot"],
        ["listener", feature, event],
    ]
    for page in REAL_PAGES:
        steps += page_steps(tree, page, f"rdreal-{page}")
    return steps + [["slot", "home", "rdrealSlot", "--doc", "After the hero. Props: { ctx }"]]


def grown_steps(tree: Path) -> list[list[str]]:
    """What makes the copy a grown tree (setup with tabs, history listening to library.game_presented, history's
    README naming an RPC module beside rpcs.py), only where it lacks that already: a branch that added any of them
    keeps it, and nothing is made twice."""
    tabless, _component = own_page((tree / "page/pages/setup/index.js").read_text())
    steps = page_steps(tree, "setup", "rdgrown") if tabless else []
    rpcs = next(
        (row for row in (tree / "backend/history/README.md").read_text().splitlines() if row.startswith("- RPCs")), ""
    )
    if not re.match(r"- RPCs \(`rpcs\.py`, `", rpcs):  # review 1, 2: a test pinning the module list fails here
        steps.append(["rpc", "history", "rdgrown_pong", "--module", "rdgrown_pong_rpcs"])
    event = "library.game_presented"
    heard = listens(tree, "history", event) or event not in declared_events(tree)
    return steps + ([] if heard else [["listener", "history", event]])


FILLED = (  # the placeholders a tab and a listener write (tests/repo/test_placeholders.py), filled in
    ("describe what this tab shows.", "a probe tab."),
    ("say what this listener does", "keeps a note"),
    ("(say what it does)", "(keeps a note)"),
    ("Describe what it does, its params and its result here.", "Answers ok."),
)
REAL_STEPS = real_steps(ROOT)  # this tree's, for the fast checks; the guard computes them again on its copy
UNIT_FIRST = "the tree fails unit (fix unit first)"  # tools/check.py scaffold reports this skip as such
PAGE_TESTS = ["tests/page/registry.test.mjs", "tests/page/page-setup.test.mjs", "tests/page/slots.test.mjs"]
STRUCTURE = [
    "tests.repo.test_layout",
    "tests.repo.test_readmes",
    "tests.repo.test_noqa",
    "tests.repo.test_docs",
    "tests.repo.test_boundaries",
    "tests.repo.test_lockstep",
    "tests.repo.test_registration_snapshot",
    "tests.backend.rdtree.test_rdtree",
    "tests.backend.rdtree.test_rpc_rdtree_ping",
    "tests.backend.rdtree.test_rpc_rdtree_pong",
    "tests.backend.rdtree.test_rpc_rdtree_info",
    "tests.backend.rdtree.test_rpc_rdtree_card",
    "tests.backend.rdtree.test_tool_rdtree_ping",
    "tests.backend.rdtree.test_tool_rdtree_more",
    "tests.backend.history.test_tool_rdtree_hist_first",
    "tests.backend.history.test_tool_rdtree_hist_second",
    "tests.backend.library.test_tool_rdtree_lib",
    "tests.backend.rdtree.test_event_pinged",
    "tests.backend.rdtree.test_listener_on_library_build_reported",
    "tests.backend.rdtree.test_tool_rdtree_proj",
]


def line(text: str, start: str) -> str:
    return next((row[len(start) :] for row in text.splitlines() if row.startswith(start)), "")


RETRODEV = [sys.executable, str(ROOT / "tools" / "retrodev")]


def judges(mode: str, env: dict) -> list[tuple[list[str], dict]]:
    """The checks run on the scaffolded copy, each with its environment. The stubs there are left unfilled, so
    the nested mode's full unit suite runs with the placeholder gate off (RETRODEV_SCAFFOLD_CHECK, for that
    subprocess only); the fast mode's unit tests do not include the gate."""
    if mode == "nested":
        gate_off = {**env, "RETRODEV_SCAFFOLD_CHECK": "1"}  # as tools/retrodev/scaffold.py sets for its own checks
        return [([sys.executable, "tools/check.py", "lint", "bundle", "unit", "page"], gate_off)]
    # the same judges, faster: the page tests the new names reach, and the structure tests, side by side
    return [
        ([sys.executable, "tools/check.py", "lint", "bundle"], env),
        ([sys.executable, "-m", "unittest", *STRUCTURE], env),
        (["node", "--test", *PAGE_TESTS], env),
    ]


class NestedModeSkipsOnlyThePlaceholderGate(unittest.TestCase):
    """Fast, always run: RD_SCAFFOLD_FULL=nested runs the whole unit suite (the placeholder gate among it) on
    unfilled stubs, so only that subprocess gets RETRODEV_SCAFFOLD_CHECK; the fast mode and the caller's own
    environment (which the later placeholder-gate run uses) keep the gate on."""

    def test_nested_mode_turns_the_gate_off_for_its_own_run_only(self):
        env = {"PATH": "/bin"}
        [(command, nested_env)] = judges("nested", env)
        self.assertIn("unit", command)
        self.assertEqual(nested_env.get("RETRODEV_SCAFFOLD_CHECK"), "1")
        self.assertNotIn("RETRODEV_SCAFFOLD_CHECK", env, "the caller's environment keeps the gate on")

    def test_the_fast_mode_keeps_the_gate_on(self):
        for command, fast_env in judges("1", {"PATH": "/bin"}):
            self.assertNotIn("RETRODEV_SCAFFOLD_CHECK", fast_env, command)


@unittest.skipIf(os.environ.get(NESTED), "inside its own throwaway run")
@unittest.skipUnless(os.environ.get("RD_SCAFFOLD_FULL"), "slow: python tools/check.py scaffold runs it")
class GeneratedCodePassesTheRealChecks(unittest.TestCase):
    def make_tree(self) -> tuple[Path, Path, dict]:
        """A copy of this tree in a fresh git repository on a work branch, its tools borrowed: (base, tree, env)."""
        if not shutil.which("node") or not shutil.which("tar"):
            self.skipTest("node and tar are needed")
        if not all((ROOT / path).exists() for path in BORROWED):
            self.skipTest("set up first: npm ci --prefix tools/npm --ignore-scripts; python tools/py/setup.py")
        short = os.environ.get("XDG_RUNTIME_DIR") if len(os.environ.get("XDG_RUNTIME_DIR", "x" * 50)) < 40 else None
        chosen, note = copy_base(short if short and Path(short).is_dir() else None)
        if note:
            print(note, file=sys.stderr)
        base = Path(tempfile.mkdtemp(prefix="rd-new-", dir=chosen))
        if not os.environ.get("RD_SCAFFOLD_KEEP"):
            self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        else:
            print(f"keeping {base}", file=sys.stderr)
        env = {key: value for key, value in os.environ.items() if not key.startswith(("RETRODEV_", "GIT_DIR"))}
        env |= {
            NESTED: "1",
            "RD_SCAFFOLD_FULL": "",
            "RETRODEV_STATE_DIR": str(base / "state"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
        tree = base / "tree"
        copy_tree(ROOT, tree, env)
        for path in BORROWED:
            (tree / path).parent.mkdir(parents=True, exist_ok=True)
            (tree / path).symlink_to(ROOT / path)
        for command in (["init", "-q", "-b", "feat/demo"], ["add", "-A"], ["commit", "-q", "-m", "Start"]):
            git_ok(self, tree, env, command)
        (tree / ".git" / "info" / "exclude").write_text("/.dev\n/tools/npm/node_modules\n")
        return base, tree, env

    def test_new_writes_code_that_passes_lint_bundle_page_and_the_structure_tests(self):
        self.guard()

    def test_the_guard_passes_where_setup_has_tabs_and_history_listens_to_game_presented(self):  # review 1, 0
        def grown(tree: Path, env: dict) -> None:  # a contributor's branch: setup's Page is a tab, history listens
            for step in grown_steps(tree):  # only what the copy lacks (review 2, 0)
                done = run([*RETRODEV, "new", *step, "--no-check"], tree, env)
                self.assertEqual(done.returncode, 0, f"new {' '.join(step)}:\n{done.stdout}{done.stderr}")
            changed = run(["git", "ls-files", "-m", "-o", "--exclude-standard"], tree, env).stdout.split()
            for path in (tree / name for name in changed):  # filled in, as the contributor would: unit then passes
                text = path.read_text()
                for stub, said in FILLED:
                    text = text.replace(stub, said)
                path.write_text(text)
            built = run(["node", "tools/bundle/bundle.mjs"], tree, env)  # the filled-in tab is in the bundle
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            for command in (["add", "-A"], ["commit", "-q", "--allow-empty", "-m", "Grown"]):
                git_ok(self, tree, env, command)
            steps = real_steps(tree)
            self.assertNotIn("--from-page", [word for step in steps if step[1] == "setup" for word in step])
            self.assertNotIn(["listener", "history", "library.game_presented"], steps)
            self.assertEqual(grown_steps(tree), [], "the grown copy has everything grown_steps makes")

        if (
            os.environ.get("RD_SCAFFOLD_FULL", "") != "nested"
        ):  # the guard's real steps run only nested: here, the choice
            _, tree, env = self.make_tree()
            grown(tree, env)
            return
        self.guard(grown)

    def guard(self, prepare=None) -> None:
        _, tree, env = self.make_tree()
        if prepare:
            prepare(tree, env)
        mode = os.environ.get("RD_SCAFFOLD_FULL", "")
        steps = STEPS + (real_steps(tree) if mode == "nested" else [])
        if mode == "nested":  # the full suites judge the copy: a tree that fails them already says nothing of new
            base = run([sys.executable, "tools/check.py", "unit"], tree, env)
            if base.returncode and prepare:  # the grown copy is this test's own: it must pass unit
                self.fail(f"the grown copy fails unit:\n{base.stdout[-6000:]}")
            if base.returncode:
                self.skipTest(f"{UNIT_FIRST}:\n{base.stdout[-2000:]}")
            self.assertTrue(note_feature_readmes(tree))  # hand edits a branch makes: pins of those lines fail here
        for step in steps:  # several in a row: the generated files are rebuilt once, after the last
            last = step is steps[-1]
            done = run([*RETRODEV, "new", *step, "--no-check", *([] if last else ["--no-build"])], tree, env)
            self.assertEqual(done.returncode, 0, f"new {' '.join(step)}:\n{done.stdout}{done.stderr}")
        commands = judges(mode, env)
        running = [
            subprocess.Popen(c, cwd=tree, env=e, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for c, e in commands
        ]
        for (command, _), process in zip(commands, running, strict=True):
            output = process.communicate()[0]
            self.assertEqual(process.returncode, 0, f"{' '.join(command[1:])}:\n{output}")
        git_ok(self, tree, env, ["diff", "--quiet", "HEAD", "--", "engine"])

    def test_rpcs_named_after_what_their_handler_uses_pass_their_generated_tests(self):  # review 2, 2
        """RPCs named host, logger or a builtin, in every variant (host both inline and --module, so in two rounds:
        RPC names are global), on their own copy: the handler's fixed name _answer shadows none of them."""
        _, tree, env = self.make_tree()
        rounds = [
            [["host", "--game"], ["logger", "--game", "--module", "rdshadow_logger_rpcs"], ["dict"]],
            [
                ["host", "--game", "--module", "rdshadow_host_rpcs"],
                ["logger"],
                ["isinstance", "--module", "rdshadow_isinstance_rpcs"],
            ],
        ]
        for steps in rounds:
            for step in steps:
                done = run([*RETRODEV, "new", "rpc", "history", *step, "--no-check"], tree, env)
                self.assertEqual(done.returncode, 0, f"new rpc {' '.join(step)}:\n{done.stdout}{done.stderr}")
            tests = [f"tests.backend.history.test_rpc_{step[0]}" for step in steps]
            judged = run([sys.executable, "-m", "unittest", *tests], tree, env)
            self.assertEqual(judged.returncode, 0, judged.stdout + judged.stderr)
            self.assertIn("OK", judged.stderr)
            linted = run([sys.executable, "tools/check.py", "lint"], tree, env)
            self.assertEqual(linted.returncode, 0, linted.stdout + linted.stderr)
            for command in (["reset", "-q", "--hard"], ["clean", "-qfd"]):  # the next round starts from the copy
                git_ok(self, tree, env, command)

    def test_moved_pages_with_comments_and_trailing_commas_bundle(self):  # review 2, 2 and 3
        moved_pages_bundle(self, RETRODEV)

    def test_tab_from_page_passes_its_own_checks_lint_and_bundle(self):
        self.tab_from_page("{ RdtabsPage as TabsPanel }", "TabsPanel")  # aliased: the tab imports the exported name

    def test_tab_from_page_with_a_multiline_import_passes_its_own_checks_lint_and_bundle(self):  # review round 2, 1
        self.tab_from_page("{\n  RdtabsPage\n}", "RdtabsPage")

    def test_an_exported_inline_page_moved_by_from_page_still_bundles_for_its_consumer(self):  # review 1, 2
        _, tree, env = self.make_tree()
        for page in ("rdinline", "rdconsumer"):
            done = run([*RETRODEV, "new", "page", page, "--no-check", "--no-build"], tree, env)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        folder = tree / "page/pages/rdinline"
        door = folder / "index.js"
        own = (folder / "rdinline-page.js").read_text().split("\n", 1)[1]  # its imports and exported function
        (folder / "rdinline-page.js").unlink()
        text = door.read_text().replace("import { RdinlinePage } from './rdinline-page.js'\n", own.rstrip() + "\n")
        door.write_text(text)  # the Page defined (and exported) in index.js itself
        consumer = tree / "page/pages/rdconsumer/rdconsumer-page.js"
        consumer.write_text(
            "// The Rdconsumer page: it shows Rdinline's exported Page through that page's front door.\n"
            "import { jsx } from '#sdk'\nimport { RdinlinePage } from '#pages/rdinline/index.js'\n\n"
            "export function RdconsumerPage() {\n  return jsx(RdinlinePage, {})\n}\n"
        )
        for command in (["add", "-A"], ["commit", "-q", "-m", "Inline"]):
            git_ok(self, tree, env, command)
        done = run([*RETRODEV, "new", "tab", "rdinline", "first", "--from-page", "--no-check"], tree, env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("export { RdinlinePage } from './rdinline-page.js'", door.read_text())
        judged = run([sys.executable, "tools/check.py", "lint", "bundle"], tree, env)
        self.assertEqual(judged.returncode, 0, judged.stdout + judged.stderr)

    def tab_from_page(self, clause: str, local: str) -> None:
        _, tree, env = self.make_tree()
        done = run([*RETRODEV, "new", "page", "rdtabs", "--no-check", "--no-build"], tree, env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        door = tree / "page/pages/rdtabs/index.js"
        text = door.read_text().replace("{ RdtabsPage }", clause)
        door.write_text(text.replace("Page: RdtabsPage", f"Page: {local}"))
        for step in (["tab", "rdtabs", "first", "--from-page"], ["tab", "rdtabs", "second"]):  # with their checks
            done = run([*RETRODEV, "new", *step], tree, env)
            self.assertEqual(done.returncode, 0, f"new {' '.join(step)}:\n{done.stdout}{done.stderr}")
            self.assertIn("page", line(done.stdout, "checks: ").split(), done.stdout)
        judged = run([sys.executable, "tools/check.py", "lint", "bundle"], tree, env)
        self.assertEqual(judged.returncode, 0, judged.stdout + judged.stderr)

    def new_then_gate(self, step: list[str], placeholders: list[str]) -> None:
        """`new <step>` with its own checks completes (the gate is skipped there and keeps no unit pass), then an
        ordinary run of the placeholder gate fails on the unfilled stubs, naming each placeholder."""
        base, tree, env = self.make_tree()
        done = run([*RETRODEV, "new", *step], tree, env)  # with its checks, unit among them
        self.assertEqual(done.returncode, 0, f"new {' '.join(step)}:\n{done.stdout}{done.stderr}")
        self.assertIn("next: ", done.stdout)
        kept = [path.read_text() for path in (base / "state").rglob("*.json")]
        self.assertFalse(any('"unit"' in text for text in kept), "new's own run must not keep a unit pass")
        gate = run([sys.executable, "-m", "unittest", "tests.repo.test_placeholders"], tree, env)
        self.assertNotEqual(gate.returncode, 0, f"the unfilled stub must fail an ordinary run:\n{gate.stderr}")
        for text in placeholders:
            self.assertIn(text, gate.stderr)

    def test_new_with_its_checks_completes_and_the_placeholder_gate_still_fails_afterwards(self):
        self.new_then_gate(["rpc", "history", "trial_ping"], ["Describe what it does, its params and its result here."])

    def test_new_listener_with_its_checks_completes_and_the_placeholder_gate_still_fails_afterwards(self):
        self.new_then_gate(
            ["listener", "setup", "library.game_presented"], ["say what this listener does", "(say what it does)"]
        )


if __name__ == "__main__":
    unittest.main()
