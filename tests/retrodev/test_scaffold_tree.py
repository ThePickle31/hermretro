"""`new` on a copy of the real repository: the generated code passes the repository's own checks.

The slow tests run only with RD_SCAFFOLD_FULL set (`python tools/check.py scaffold`). Each uses a short-lived Git
copy and borrows the installed tools (.dev/py and tools/npm/node_modules). The primary guard prepares a copy
where Setup already has tabs, History already listens to library.game_presented and its README lists another RPC
module. It makes only the missing pieces, fills their placeholders and commits that starting point. It then runs
STEPS for every `new` kind, followed by lint, bundle, selected structure and generated tests, and the page tests
those scaffolds affect.

CI sets RD_SCAFFOLD_FULL=nested. The same guard scaffolds against real features and pages as well as the probes,
and runs the full lint, bundle, unit and page suites in that one copy. This catches tests tied to the current tree's
shape. The placeholder gate is off for the full unit run on unfilled stubs, not on the branch the guard is testing.

The separate check-wiring test adds a listener without checks, then runs `new rpc` with its own checks in the same
copy. It proves unrelated lint errors are diagnosed correctly, no unit pass is cached, and the normal placeholder
gate rejects both stubs afterwards. Other focused tests cover page conversions, shadowing names, linting just the
named files, and the scaffold trigger rules. A baseline page failure is reported as inherited, whereas a failure
introduced by scaffolding fails the check (`scaffold_inherited.py`).

Run alone: RD_SCAFFOLD_FULL=1 python -m unittest tests.retrodev.test_scaffold_tree
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path


from tests.retrodev.fixture import parallel
from tests.retrodev.hand_edits import note_feature_readmes
from tests.retrodev.scaffold_inherited import INNER, inherited_page_failure_skips_the_whole_check
from tests.retrodev.scaffold_moves import moved_pages_bundle
from tests.retrodev.tree_copy import NO_MAINTENANCE, copy_base, copy_tree, git_ok, run

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
    ["contribution", "rdtree", "rdtree.extraActions", "RdtreeExtra"],  # fills it: the registry's filled assertion
    ["contribution", "rdtree", "rdtree.extraActions", "Text"],  # a name the registry test binds: an alias there
]
STEPS += [["tool", "rdtree", "rdtree_proj", "--project"]]  # outside library: imports backend/hermes/tool_args.py
# The guard's steps on REAL features and pages (nested mode): scaffold_steps.py chooses them from the copy.
from tests.retrodev.scaffold_steps import (  # noqa: E402, F401 - other tests read them from here too
    REAL_LISTENERS,
    REAL_PAGES,
    declared_events,
    grown_steps,
    listens,
    page_steps,
    real_steps,
)


FILLED = (  # the placeholders a tab and a listener write (tests/repo/test_placeholders.py), filled in
    ("describe what this tab shows.", "a probe tab."),
    ("say what this listener does", "keeps a note"),
    ("(say what it does)", "(keeps a note)"),
    ("Describe what it does, its params and its result here.", "Answers ok."),
)
REAL_STEPS = real_steps(ROOT)  # this tree's, for the fast checks; the guard computes them again on its copy
UNIT_FIRST = "the tree fails unit (fix unit first)"  # tools/check.py scaffold reports this skip as such
PAGE_FIRST = "the tree fails page (fix page first)"  # likewise, when the copy's page suite fails before new runs
BASE = "RD_SCAFFOLD_BASE"  # suites tools/check.py scaffold found passing on this tree: not run again here
FIRST = {}  # mode: why every slow test skips ("" when the copy passes), found once per process (first_failure)
FIRST_LOCK = threading.Lock()
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
TRIGGERED = (  # {check: why} for the copy's branch, by the copy's own retrodev and policy
    "import io, json, sys; sys.path.insert(0, 'tools'); from retrodev import checks_triggers, config, output; "
    "print(json.dumps(checks_triggers.triggered(config.Context.make('.', output.Out(stream=io.StringIO())))))"
)


def triggered(tree: Path, env: dict) -> dict:
    done = run([sys.executable, "-c", TRIGGERED], tree, env)
    assert not done.returncode, done.stdout + done.stderr
    return json.loads(done.stdout)


def judges(mode: str, env: dict) -> list[tuple[list[str], dict]]:
    """The checks run on the scaffolded copy, each with its environment. The stubs there are left unfilled, so
    the nested mode's full unit suite runs with the placeholder gate off (RETRODEV_SCAFFOLD_CHECK, for that
    subprocess only); the fast mode's unit tests do not include the gate."""
    if mode == "nested":
        # as tools/retrodev/scaffold_checks.py sets for new's own checks
        gate_off = {**env, "RETRODEV_SCAFFOLD_CHECK": "1"}
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
        """A copy of this tree (copy()), once the module's setup found the tree passing what it must (first)."""
        self.first()
        return self.copy()

    def first(self, mode: str | None = None, known: str | None = None, cache: dict = FIRST) -> None:
        """The module's setup, once per process on whichever slow test comes first (the tests run on threads, so not
        setUpModule): the copy's page suite (nested: and unit) as it is, before any new runs, except the suites
        check.py scaffold found passing (``known``, RD_SCAFFOLD_BASE). A failure skips every slow test ("fix page
        first"): new's own checks and the judges would all fail on it, and it says nothing of new. A failure only
        new (or a test's own preparation) brings still fails its test."""
        mode = os.environ.get("RD_SCAFFOLD_FULL", "") if mode is None else mode
        known = os.environ.get(BASE, "") if known is None else known
        with FIRST_LOCK:
            if mode not in cache:
                suites = ["unit", "page"] if mode == "nested" else ["page"]
                cache[mode] = self.first_failure([name for name in suites if name not in known.split(",")])
        if cache[mode]:
            self.skipTest(cache[mode])

    def first_failure(self, suites: list[str]) -> str:
        if not suites:
            return ""
        _, tree, env = self.copy()
        for name in suites:
            done = self.suite([sys.executable, "tools/check.py", name], tree, env)
            if done.returncode:
                said = (done.stdout + (done.stderr or ""))[-2000:]
                return f"{UNIT_FIRST if name == 'unit' else PAGE_FIRST}:\n{said}"
        return ""

    def copy(self) -> tuple[Path, Path, dict]:
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
        env = {key: value for key, value in os.environ.items() if not key.startswith(("RETRODEV_", "GIT_DIR", BASE))}
        env |= {
            NESTED: "1",
            "RD_SCAFFOLD_FULL": "",
            "RETRODEV_STATE_DIR": str(base / "state"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            **NO_MAINTENANCE,  # git commit's detached maintenance would still write in .git as the copy is removed
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

    def assert_engine_clean(self, tree: Path, env: dict) -> None:
        done = run(["git", "status", "--porcelain=v1", "--untracked-files=all", "--", "engine"], tree, env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, "", "scaffolding must not change engine/:\n" + done.stdout)

    def grow(self, tree: Path, env: dict) -> None:
        """Model a branch where contributors have already added Setup tabs, an RPC module and a History listener."""
        for step in grown_steps(tree):
            done = run([*RETRODEV, "new", *step, "--no-check", "--no-build"], tree, env)
            self.assertEqual(done.returncode, 0, f"new {' '.join(step)}:\n{done.stdout}{done.stderr}")
        listing = run(["git", "ls-files", "-z", "-m", "-o", "--exclude-standard"], tree, env)
        self.assertEqual(listing.returncode, 0, listing.stderr)
        for path in (tree / name for name in listing.stdout.split("\0") if name):
            text = path.read_text()
            for stub, said in FILLED:
                text = text.replace(stub, said)
            path.write_text(text)
        # Check before committing so a scaffold cannot bake an engine edit into the fixture's baseline.
        self.assert_engine_clean(tree, env)
        for command in (["add", "-A"], ["commit", "-q", "--allow-empty", "-m", "Grown"]):
            git_ok(self, tree, env, command)
        steps = real_steps(tree)
        self.assertNotIn("--from-page", [word for step in steps if step[1] == "setup" for word in step])
        self.assertNotIn(["listener", "history", "library.game_presented"], steps)
        self.assertEqual(grown_steps(tree), [], "the grown copy has everything grown_steps makes")

    def test_new_writes_code_that_passes_the_repository_checks(self):
        _, tree, env = self.make_tree()
        mode = os.environ.get("RD_SCAFFOLD_FULL", "")
        self.grow(tree, env)
        if mode == "nested":
            # Hand edits a branch makes: pins of those lines fail here.
            self.assertTrue(note_feature_readmes(tree))
        steps = STEPS + (real_steps(tree) if mode == "nested" else [])
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
        self.assert_engine_clean(tree, env)

    def suite(self, command: list[str], tree: Path, env: dict) -> subprocess.CompletedProcess:
        return run(command, tree, env)

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

    def test_the_files_new_writes_never_add_the_nested_scaffold_run(self):  # review 2, 0 (#75)
        """The real plans on a copy, each committed on a branch off its start: the whole changed-file set of `new
        tool`, then with `new rpc`, then with every other kind (the registration snapshot and the page registry test
        among them) never adds scaffold nested; a hand edit to tests/repo/test_docs.py after them still does."""
        _, tree, env = self.copy()
        git_ok(self, tree, env, ["update-ref", "refs/remotes/origin/dev", "HEAD"])
        rest = [
            ["feature", "rdtrig", "--purpose", "A probe feature made by retrodev new"],
            ["event", "rdtrig", "pinged", "--payload", "count", "--when", "the probe was pinged"],
            ["listener", "rdtrig", "library.build_reported"],
            ["page", "rdtrig"],
            ["tab", "rdtrig", "extra"],
            ["slot", "rdtrig", "extraActions", "--doc", "Buttons after the lede. Props: { ctx }"],
            ["contribution", "rdtrig", "rdtrig.extraActions", "RdtrigExtra"],
        ]
        rounds = [[["tool", "history", "rdtrig_tool"]], [["rpc", "history", "rdtrig_rpc"]], rest]
        for steps in rounds:
            for step in steps:  # the generated files rebuilt once a round, as a branch's last `new` does
                build = [] if step is steps[-1] else ["--no-build"]
                done = run([*RETRODEV, "new", *step, "--no-check", *build], tree, env)
                self.assertEqual(done.returncode, 0, f"new {' '.join(step)}:\n{done.stdout}{done.stderr}")
            for command in (["add", "-A"], ["commit", "-q", "-m", steps[0][0]]):
                git_ok(self, tree, env, command)
            self.assertNotIn("run nested", triggered(tree, env).get("scaffold", ""), steps[0])
        changed = run(["git", "diff", "--name-only", "origin/dev"], tree, env).stdout.split()
        self.assertIn("tests/repo/registration.json", changed)  # what the trigger matched before the fix
        docs = tree / "tests/repo/test_docs.py"
        docs.write_text(docs.read_text() + "\nHAND_EDIT = 1  # code: a comment alone adds nothing (round 16)\n")
        self.assertIn("changed tests/repo/test_docs.py; run nested", triggered(tree, env).get("scaffold", ""))

    def test_moved_pages_with_comments_and_trailing_commas_bundle(self):  # review 2, 2 and 3
        moved_pages_bundle(self, RETRODEV)

    @unittest.skipIf(os.environ.get(INNER), "inside the scaffold check this test runs")
    def test_an_inherited_page_failure_skips_the_whole_check_and_one_new_brings_fails(self):  # review round 2, 0
        inherited_page_failure_skips_the_whole_check(self, "skipped: " + PAGE_FIRST, (NESTED, BASE))

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

    def test_new_runs_checks_without_caching_or_failing_on_unfilled_stubs(self):
        base, tree, env = self.make_tree()
        root = tree / "__init__.py"
        root.write_text(root.read_text() + "\n\ndef _rdlint_probe():\n    return rdlint_undefined_name\n")
        for command in (["add", "-A"], ["commit", "-q", "-m", "An unrelated lint error"]):
            git_ok(self, tree, env, command)

        listener = run(
            [*RETRODEV, "--json", "new", "listener", "setup", "library.game_presented", "--no-check"], tree, env
        )
        self.assertEqual(listener.returncode, 0, listener.stdout + listener.stderr)
        edits = json.loads(listener.stdout)
        files = [path for path in edits["created"] + edits["changed"] if path.endswith(".py")]
        self.assertTrue(files, edits)
        linted = run([sys.executable, "tools/check.py", "lint-files", *files], tree, env)
        self.assertEqual(linted.returncode, 0, linted.stdout + linted.stderr)

        done = run([*RETRODEV, "new", "rpc", "history", "trial_ping"], tree, env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("unit", line(done.stdout, "checks: ").split(), done.stdout)
        self.assertIn("pre-existing on this tree (not from new)", done.stdout)
        self.assertIn("next: ", done.stdout)
        kept = [path.read_text() for path in (base / "state").rglob("*.json")]
        self.assertFalse(any('"unit"' in text for text in kept), "new's own run must not keep a unit pass")

        gate = run([sys.executable, "-m", "unittest", "tests.repo.test_placeholders"], tree, env)
        self.assertNotEqual(gate.returncode, 0, f"the unfilled stubs must fail an ordinary run:\n{gate.stderr}")
        for text in (
            "Describe what it does, its params and its result here.",
            "say what this listener does",
            "(say what it does)",
        ):
            self.assertIn(text, gate.stderr)

    def test_lint_files_lints_only_the_named_files_and_fails_without_ruff(self):  # review 2, 0 (round twelve)
        _, tree, env = self.make_tree()
        (tree / "backend/history/rdlint_other.py").write_text("import os\n")  # not named: not linted
        (tree / "backend/history/rdlint_mine.py").write_text('"""Mine."""\n')
        (tree / "page/pages/build/rdlint.js").write_text("export const a = 1\n")
        mine = ["backend/history/rdlint_mine.py", "page/pages/build/rdlint.js", "docs/dev/CONTRACT.md"]
        lint = [sys.executable, "tools/check.py", "lint-files"]
        done = run([*lint, *mine], tree, env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("(1 Python, 1 page;", done.stdout)
        done = run([*lint, "backend/history/rdlint_other.py"], tree, env)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("rdlint_other.py", done.stdout)
        (tree / "page/pages/build/rdlint.js").write_text("export const a = rdlintUndefined\n")
        done = run([*lint, "page/pages/build/rdlint.js"], tree, env)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("the page lint fails on new's own files", done.stdout)
        (tree / ".dev/py").unlink()  # the borrowed ruff gone
        done = run([*lint, *mine], tree, env)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("ruff is missing", done.stdout)
        self.assertIn("python tools/py/setup.py", done.stdout)


if __name__ == "__main__":
    unittest.main()
