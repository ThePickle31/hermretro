"""`new` on a copy of the real repository: the generated code passes the repository's own checks.

The one slow-ish retrodev test (about 10 s): it copies what a commit of this tree would hold into a short temp
folder (a fresh git repository on a work branch, so nothing of this checkout or its .git changes), borrows the
installed tools (.dev/py and tools/npm/node_modules, linked), runs `new feature rdprobe`, `new rpc`, `new tool`,
`new event`, `new page rdprobe`, `new tab rdprobe extra` and `new slot rdprobe extraActions`, then, side by side, `tools/check.py lint bundle`, the unit tests that judge structure and lock step (layout,
docs, boundaries, lock step, the registration snapshot, and the generated tests) and the page tests the new names
reach (the registry, the nav). The full `tools/check.py lint bundle unit page` runs there instead with
RD_SCAFFOLD_FULL=1 (it nests the whole unit suite, so it is not the default). Skipped when node, the npm
tools or the pinned ruff are not set up here (CI's unit jobs: the page job runs the page side).

Run alone: python -m unittest tests.retrodev.test_scaffold_tree
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
    ["feature", "rdprobe", "--purpose", "A probe feature made by retrodev new"],
    ["rpc", "rdprobe", "rdprobe_ping"],
    ["tool", "rdprobe", "rdprobe_ping"],
    ["event", "rdprobe", "pinged", "--payload", "count"],
    ["page", "rdprobe"],
    ["tab", "rdprobe", "extra"],
    ["slot", "rdprobe", "extraActions", "--doc", "Buttons after the lede. Props: { ctx }"],
]
PAGE_TESTS = ["tests/page/registry.test.mjs", "tests/page/page-setup.test.mjs"]
STRUCTURE = [
    "tests.repo.test_layout",
    "tests.repo.test_docs",
    "tests.repo.test_boundaries",
    "tests.repo.test_lockstep",
    "tests.repo.test_registration_snapshot",
    "tests.backend.rdprobe.test_rdprobe",
    "tests.backend.rdprobe.test_rpc_rdprobe_ping",
    "tests.backend.rdprobe.test_tool_rdprobe_ping",
    "tests.backend.rdprobe.test_event_pinged",
]


def run(command: list[str], cwd: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, stdin=subprocess.DEVNULL)


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


@unittest.skipIf(os.environ.get(NESTED), "inside its own throwaway run")
class GeneratedCodePassesTheRealChecks(unittest.TestCase):
    def test_new_writes_code_that_passes_lint_bundle_page_and_the_structure_tests(self):
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
        retrodev = [sys.executable, str(ROOT / "tools" / "retrodev")]
        for step in STEPS:  # several in a row: the generated files are rebuilt once, after the last
            last = step is STEPS[-1]
            done = run([*retrodev, "new", *step, "--no-check", *([] if last else ["--no-build"])], tree, env)
            self.assertEqual(done.returncode, 0, f"new {' '.join(step)}:\n{done.stdout}{done.stderr}")
        if os.environ.get("RD_SCAFFOLD_FULL"):
            commands = [[sys.executable, "tools/check.py", "lint", "bundle", "unit", "page"]]
        else:  # the same judges, faster: the page tests the new names reach, and the structure tests, side by side
            commands = [
                [sys.executable, "tools/check.py", "lint", "bundle"],
                [sys.executable, "-m", "unittest", *STRUCTURE],
                ["node", "--test", *PAGE_TESTS],
            ]
        running = [
            subprocess.Popen(c, cwd=tree, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for c in commands
        ]
        for command, process in zip(commands, running, strict=True):
            output = process.communicate()[0]
            self.assertEqual(process.returncode, 0, f"{' '.join(command[1:])}:\n{output}")
        self.assertEqual(run(["git", "diff", "--quiet", "HEAD", "--", "engine"], tree, env).returncode, 0)


if __name__ == "__main__":
    unittest.main()
