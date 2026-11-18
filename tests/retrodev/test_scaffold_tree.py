"""`new` on a copy of the real repository: the generated code passes the repository's own checks.

The one slow retrodev test (a few seconds), so it runs only with RD_SCAFFOLD_FULL set: `python tools/check.py
scaffold` (part of `check.py full` and `retrodev check --full`, added by `retrodev check` when a branch changes the
scaffolds or the files they edit; CI's page job runs it). It copies what a commit of this tree would hold into a short temp
folder (a fresh git repository on a work branch, so nothing of this checkout or its .git changes), borrows the
installed tools (.dev/py and tools/npm/node_modules, linked), runs `new feature rdtree`, `new rpc`, `new tool`,
`new event`, `new listener`, `new page rdtree`, `new tab rdtree extra` and `new slot rdtree extraActions`, then, side by side, `tools/check.py lint bundle`, the unit tests that judge structure and lock step (layout,
docs, boundaries, lock step, the registration snapshot, and the generated tests) and the page tests the new names
reach (the registry, the nav). With RD_SCAFFOLD_FULL=nested the full `tools/check.py lint bundle unit page` runs
there instead (it nests the whole unit suite, with tests/repo/test_placeholders.py's gate off for that run only:
the stubs are unfilled). Skipped when node, the npm tools or the pinned ruff are not set up
here (check.py scaffold then says so). A second test runs `new rpc history trial_ping` with its own checks: it
completes (tests/repo/test_placeholders.py skips its gate there) and the placeholder gate still fails afterwards.

Run alone: RD_SCAFFOLD_FULL=1 python -m unittest tests.retrodev.test_scaffold_tree
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.retrodev.fixture import parallel

load_tests = parallel

ROOT = Path(__file__).resolve().parents[2]
NESTED = "RD_SCAFFOLD_NESTED"
BORROWED = (".dev/py", "tools/npm/node_modules")  # linked; .dev itself stays real (the bundle writes temps there)
# Names no real feature, RPC, tool or page will take (the repository's own scaffolds must not collide with them).
STEPS = [
    ["feature", "rdtree", "--purpose", "A probe feature made by retrodev new"],
    ["rpc", "rdtree", "rdtree_ping"],
    ["tool", "rdtree", "rdtree_ping", "--step", 'Pinging "it"', "Pinged the probe's twin"],
    ["event", "rdtree", "pinged", "--payload", "count"],
    ["listener", "rdtree", "library.build_reported"],
    ["page", "rdtree"],
    ["tab", "rdtree", "extra"],
    ["slot", "rdtree", "extraActions", "--doc", "Buttons after the lede. Props: { ctx }"],
]
PAGE_TESTS = ["tests/page/registry.test.mjs", "tests/page/page-setup.test.mjs"]
STRUCTURE = [
    "tests.repo.test_layout",
    "tests.repo.test_docs",
    "tests.repo.test_boundaries",
    "tests.repo.test_lockstep",
    "tests.repo.test_registration_snapshot",
    "tests.backend.rdtree.test_rdtree",
    "tests.backend.rdtree.test_rpc_rdtree_ping",
    "tests.backend.rdtree.test_tool_rdtree_ping",
    "tests.backend.rdtree.test_event_pinged",
    "tests.backend.rdtree.test_listener_on_library_build_reported",
]


def run(command: list[str], cwd: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL)


RETRODEV = [sys.executable, str(ROOT / "tools" / "retrodev")]


def copy_tree(source: Path, target: Path, env: dict) -> None:
    listing = run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], source, env).stdout
    names = [name for name in listing.split("\0") if name and (source / name).is_file()]
    file_list = target.parent / "files.txt"
    file_list.write_text("\0".join(names))
    subprocess.run(
        ["tar", "--null", "-T", str(file_list), "-cf", str(target.parent / "tree.tar")], cwd=source, check=True
    )
    target.mkdir()
    subprocess.run(["tar", "-xf", str(target.parent / "tree.tar")], cwd=target, check=True)


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
        base = Path(tempfile.mkdtemp(prefix="rd-new-", dir=short if short and Path(short).is_dir() else None))
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
            self.assertEqual(run(["git", *command], tree, env).returncode, 0, command)
        (tree / ".git" / "info" / "exclude").write_text("/.dev\n/tools/npm/node_modules\n")
        return base, tree, env

    def test_new_writes_code_that_passes_lint_bundle_page_and_the_structure_tests(self):
        _, tree, env = self.make_tree()
        for step in STEPS:  # several in a row: the generated files are rebuilt once, after the last
            last = step is STEPS[-1]
            done = run([*RETRODEV, "new", *step, "--no-check", *([] if last else ["--no-build"])], tree, env)
            self.assertEqual(done.returncode, 0, f"new {' '.join(step)}:\n{done.stdout}{done.stderr}")
        commands = judges(os.environ.get("RD_SCAFFOLD_FULL", ""), env)
        running = [
            subprocess.Popen(c, cwd=tree, env=e, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for c, e in commands
        ]
        for (command, _), process in zip(commands, running, strict=True):
            output = process.communicate()[0]
            self.assertEqual(process.returncode, 0, f"{' '.join(command[1:])}:\n{output}")
        self.assertEqual(run(["git", "diff", "--quiet", "HEAD", "--", "engine"], tree, env).returncode, 0)

    def test_new_with_its_checks_completes_and_the_placeholder_gate_still_fails_afterwards(self):
        base, tree, env = self.make_tree()
        done = run([*RETRODEV, "new", "rpc", "history", "trial_ping"], tree, env)  # with its checks, unit among them
        self.assertEqual(done.returncode, 0, f"new rpc history trial_ping:\n{done.stdout}{done.stderr}")
        self.assertIn("next: ", done.stdout)
        kept = [path.read_text() for path in (base / "state").rglob("*.json")]
        self.assertFalse(any('"unit"' in text for text in kept), "new's own run must not keep a unit pass")
        gate = run([sys.executable, "-m", "unittest", "tests.repo.test_placeholders"], tree, env)
        self.assertNotEqual(gate.returncode, 0, f"the unfilled stub must fail an ordinary run:\n{gate.stderr}")
        self.assertIn("Describe what it does, its params and its result here.", gate.stderr)


if __name__ == "__main__":
    unittest.main()
