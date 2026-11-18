"""A tiny hermretro-shaped repository with a bare origin, made once and copied per test, and a fake gh.

The copy holds stand-ins for tools/check.py (prints check.py's result rows, logs each run and its environment to
<test folder>/checks.log, fails the checks listed in <test folder>/fail-checks), the clean install script and the
bundle generator. Git runs with a throwaway global config and identity, so nothing of the developer's setup
(signing, hooks, default branch) leaks in, and the real home is never read or written.

Speed: every test has its own folders and passes its own working folder, output stream and gh to retrodev, so
`parallel()` runs a module's tests on threads (git and Python subprocesses dominate), with the one environment
they share set once around them. Run alone (python -m unittest tests.retrodev.test_x.Case.test_y), a test sets
that environment itself.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import tomllib
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

import retrodev
from retrodev import cli, state

POLICY = Path(retrodev.__file__).with_name("policy.toml")

# The stand-ins find their test's folder (the one holding origin.git) above the checkout they run in.
FIND_BASE = """from pathlib import Path
base = next(p for p in Path.cwd().resolve().parents if (p / "origin.git").is_dir())
"""
FAKE_CHECK = (
    "import json, os, sys\n"
    + FIND_BASE
    + '''names = sys.argv[1:]
with open(base / "checks.log", "a") as handle:
    handle.write(json.dumps({"names": names, "tmpdir": os.environ.get("TMPDIR"),
                             "deps": os.environ.get("HERMRETRO_DEPS_ROOT")}) + "\\n")
failing = (base / "fail-checks").read_text().split() if (base / "fail-checks").is_file() else []
code = 0
for name in names:
    if name in failing:
        print(f"{'FAILED':>7}  {name:<10} {0.2:5.1f} s  it broke")
        print("         FIX: fix " + name)
        code = 1
    else:
        print(f"{'ok':>7}  {name:<10} {0.1:5.1f} s  fine")
sys.exit(code)
'''
)
# Like the real one, it installs the committed HEAD: it logs which commit that was.
FAKE_INSTALL = (
    "import json, subprocess, sys\n"
    + FIND_BASE
    + '''head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
with open(base / "checks.log", "a") as handle:
    handle.write(json.dumps({"script": sys.argv[1:], "head": head}) + "\\n")
print("clean install ok")
'''
)
# Builds desktop/plugin.js from page/*.js, as bundle.mjs builds the real bundle from page/.
FAKE_GENERATOR = '''from pathlib import Path
parts = [path.read_text() for path in sorted(Path("page").glob("*.js"))]
Path("desktop/plugin.js").write_text("// built\\n" + "".join(parts))
'''
LAYOUT = """[root]
"plugin.yaml" = "manifest"
[folders.backend]
purpose = "backend"
areas.hermes = "hermes"
areas.library = "library"
[folders.page]
purpose = "page"
[folders.desktop]
purpose = "bundle"
[folders.docs]
purpose = "docs"
[folders.tools]
purpose = "tools"
"""
FILES = {
    "plugin.yaml": "version: 0.0.1\n",
    ".gitignore": "notes/\n__pycache__/\nnode_modules/\n",
    ".gitattributes": "desktop/plugin.js -merge\n",
    "page/a.js": "export const a = 1\n",
    "desktop/plugin.js": "// built\nexport const a = 1\n",
    "backend/library/core.py": "VALUE = 1\n",
    "backend/hermes/glue.py": "GLUE = 1\n",
    "docs/guide.md": "# Guide\n",
    "tools/check.py": FAKE_CHECK,
    "tools/ci/clean_install_check.py": FAKE_INSTALL,
    "tools/gen.py": FAKE_GENERATOR,
    "tools/layout.toml": LAYOUT,
}
GOOD_BODY = """## Why
Because.

## What changed
Things.

## How verified
- [x] Linux
python tools/retrodev check: all passed

## Risk and rollback
Low; revert the commit.

## Not done
Nothing.

Made by an agent (Hermes) for the owner.
"""


def git(cwd: Path, *args: str, check: bool = True) -> str:
    done = subprocess.run(["git", *args], cwd=str(cwd), text=True, capture_output=True)
    if check and done.returncode:
        raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
    return done.stdout


def write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def policy_text() -> str:
    """The real policy, with the setup and generators swapped for the stand-ins (no npm, node or network)."""
    text = POLICY.read_text()
    policy = tomllib.loads(text)
    setup = repr(policy["setup"]["commands"])  # only to be sure the sections exist
    assert setup
    start, end = text.index("[setup]"), text.index("[checks]")
    text = text[:start] + '[setup]\ncommands = [["{python}", "-c", "print(\'set up\')"]]\n\n' + text[end:]
    start = text.index("regenerate = [")
    end = text.index("]\n\n", text.index("--write")) + 3
    return text[:start] + 'regenerate = [["{python}", "tools/gen.py"]]\n\n' + text[end:]


class Template:
    """Built once per test run: a bare origin with dev, and a main checkout on dev."""

    path: Path | None = None
    _keep: tempfile.TemporaryDirectory | None = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> Path:
        with cls._lock:
            return cls._build()

    @classmethod
    def _build(cls) -> Path:
        if cls.path is None:
            cls._keep = tempfile.TemporaryDirectory(prefix="retrodev-template-")
            base = Path(cls._keep.name)
            with mock.patch.dict(os.environ, git_env(base)):
                git(base, "init", "-q", "--bare", "-b", "dev", "origin.git")
                main = base / "hermretro"
                main.mkdir()
                git(main, "init", "-q", "-b", "dev")
                for name, text in FILES.items():
                    write(main, name, text)
                write(main, "tools/retrodev/policy.toml", policy_text())
                git(main, "add", "-A")
                git(main, "commit", "-q", "-m", "Start")
                git(main, "remote", "add", "origin", str(base / "origin.git"))
                git(main, "push", "-q", "origin", "dev")
                git(main, "fetch", "-q", "origin")
            cls.path = base
        return cls.path


def git_env(base: Path) -> dict:
    config = base / "gitconfig"
    if not config.exists():
        # No template: new repositories get no sample hooks, so each test's copy is small.
        config.write_text("[init]\n\tdefaultBranch = dev\n\ttemplateDir =\n[advice]\n\tdetachedHead = false\n")
    return {
        "GIT_CONFIG_GLOBAL": str(config),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "You",
        "GIT_AUTHOR_EMAIL": "you@example.com",
        "GIT_COMMITTER_NAME": "You",
        "GIT_COMMITTER_EMAIL": "you@example.com",
    }


def shared_env() -> dict:
    """The environment every test runs in: git isolated, no retrodev settings, a toolchain override to drop."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("RETRODEV_")}
    env.update(git_env(Template.get()), HERMRETRO_DEPS_ROOT="/nonexistent-deps")
    return env


class _Recorded(unittest.TestResult):
    """Keeps every call a test makes on its result, to replay them on the real one in order."""

    def __init__(self):
        super().__init__()
        self.calls: list[tuple[str, tuple]] = []

    def __getattribute__(self, name):
        attr = super().__getattribute__(name)
        if name in REPLAYED:
            calls = super().__getattribute__("calls")

            def record(*args):
                calls.append((name, args))
                return attr(*args)

            return record
        return attr


REPLAYED = {
    "startTest",
    "stopTest",
    "addSuccess",
    "addError",
    "addFailure",
    "addSkip",
    "addExpectedFailure",
    "addUnexpectedSuccess",
    "addSubTest",
    "addDuration",
}
_SHARED = {"on": False}


class ParallelSuite(unittest.BaseTestSuite):
    def run(self, result, debug=False):
        tests = list(_flatten(self))
        if not tests:
            return result

        def one(test):
            recorded = _Recorded()
            test(recorded)
            return recorded.calls

        with mock.patch.dict(os.environ, shared_env(), clear=True):
            _SHARED["on"] = True
            try:
                with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 2, len(tests))) as pool:
                    outcomes = list(pool.map(one, tests))
            finally:
                _SHARED["on"] = False
        for calls in outcomes:
            for name, args in calls:
                method = getattr(result, name, None)
                if method is not None:
                    method(*args)
        return result


def _flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite | unittest.BaseTestSuite):
            yield from _flatten(item)
        else:
            yield item


def parallel(loader, tests, pattern):
    """A module's load_tests: its tests on threads (each RepoCase is independent)."""
    return ParallelSuite(list(_flatten(tests)))


class FakeGH:
    """Answers gh calls from a table of (argument prefix -> (code, stdout, stderr)); records every call."""

    def __init__(self, answers: dict | None = None):
        self.answers = {("api", "user"): (0, "you\n", ""), ("pr", "list"): (0, "[]", "")}
        self.answers.update(answers or {})
        self.calls: list[list[str]] = []
        self.effects: dict = {}  # argument prefix -> callable(args), run before answering (a merge that merges)

    def __call__(self, args, cwd):
        self.calls.append(list(args))
        for prefix, effect in self.effects.items():
            if tuple(args[: len(prefix)]) == prefix:
                effect(list(args))
        for prefix, answer in sorted(self.answers.items(), key=lambda item: -len(item[0])):
            if tuple(args[: len(prefix)]) == prefix:
                return answer
        return 1, "", f"no fake answer for gh {' '.join(args)}"

    def called(self, *prefix: str) -> list[list[str]]:
        return [call for call in self.calls if tuple(call[: len(prefix)]) == prefix]


class RepoCase(unittest.TestCase):
    """Each test gets its own copy of the template (main checkout, origin, worktree root beside them)."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="retrodev-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        if not _SHARED["on"]:  # run alone, not through parallel(): set the shared environment here
            patch = mock.patch.dict(os.environ, shared_env(), clear=True)
            patch.start()
            self.addCleanup(patch.stop)
        shutil.copytree(Template.get(), self.base, dirs_exist_ok=True, symlinks=True)
        self.main = self.base / "hermretro"
        self.origin = self.base / "origin.git"
        git(self.main, "remote", "set-url", "origin", str(self.origin))
        self.gh = FakeGH()
        self.fakes: dict = {}  # passed to retrodev as Context.fakes (the reviewer's runner, its database, sleep)

    def fail_checks(self, *names: str) -> None:
        """Make the stand-in check.py fail these checks (none: pass them all again)."""
        (self.base / "fail-checks").write_text(" ".join(names))

    def run_cli(self, *argv: str, cwd: Path | None = None, as_json: bool = False):
        """(exit code, output text or parsed JSON)."""
        stream = io.StringIO()
        args = (["--json"] if as_json else []) + list(argv)
        code = cli.main(args, cwd=cwd or self.main, gh_runner=self.gh, stream=stream, fakes=self.fakes)
        text = stream.getvalue()
        return code, (json.loads(text) if as_json else text)

    def check_log(self) -> list[dict]:
        path = self.base / "checks.log"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.is_file() else []

    def clear_log(self) -> None:
        (self.base / "checks.log").unlink(missing_ok=True)

    def worktree(self, name: str = "docs/tidy") -> Path:
        """A worktree as `start` makes it (start itself is tested in test_plan_start), in one git call."""
        kind, topic = name.split("/")
        path = self.base / "hermretro-wt" / topic
        git(self.main, "worktree", "add", "-q", "--no-track", "-b", name, str(path), "origin/dev")
        record = {"branch": name, "kind": kind, "topic": topic, "plan": None, "worktree": str(path), "checks": {}}
        state.save_branch(self.main, record)
        return path

    def commit(self, cwd: Path, name: str, text: str, message: str = "Change") -> None:
        write(cwd, name, text)
        git(cwd, "add", "-A")
        git(cwd, "commit", "-q", "-m", message)

    def on_dev(self, name: str, text: str, message: str = "Dev moves") -> None:
        """A commit lands on origin/dev from elsewhere (a clone of the origin)."""
        other = self.base / "other"
        if not other.exists():
            git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(other))
        git(other, "pull", "-q", "origin", "dev")
        self.commit(other, name, text, message)
        git(other, "push", "-q", "origin", "dev")


PYTHON = sys.executable
