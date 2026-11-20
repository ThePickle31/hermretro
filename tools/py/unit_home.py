"""check.py unit's empty home and empty temp folder: the environment it runs the suite in, and, only when the suite
wrote into that home or left something in that temp folder, which test modules did it.

The suite runs once in an empty home folder. Anything found there afterwards was written by a test that was not given
a temp folder. Finding which one costs a rerun, so it happens only after a leak: each test module runs again on its own,
in a fresh empty home, and the modules that write there are named. The usual cause is a test that calls a real
emitter (a tool or RPC that emits an event): the event reaches every feature's listeners.py, which writes where the
real home is unless the test called isolated_home(self). The temp folder (TMPDIR, which the suite's tempfile.tempdir
comes from) must be empty again after the run: a tempfile.mkdtemp() without a cleanup leaves its folder behind on
every run, and thousands of them once filled a machine's /run/user temp space.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

LOCATE_BUDGET_S = 120  # stop looking after this; the leak itself is already reported


def unit_env(home: str, bytecode: str, tmp: str | None = None, source: dict | None = None) -> dict[str, str]:
    """No HERMRETRO_* folders (nor RD_SCAFFOLD_* modes) from the developer's shell, HOME and HERMES_HOME (Hermes's plugin data folder,
    host._data_dir(), lands there too) in the empty home, TMPDIR in the empty temp folder ``tmp``, and an empty
    bytecode folder (-B alone still reads stale .pyc)."""
    # RD_SCAFFOLD_* belong to check.py scaffold's own run: in the suite they would run the slow scaffold module
    # (nested, minutes) inside unit, and turn the tests of check.py scaffold itself to that mode.
    dropped = ("HERMRETRO_", "RD_SCAFFOLD_")
    source = os.environ if source is None else source  # tests pass their own: os.environ is shared by the pool
    env = {k: v for k, v in source.items() if not k.startswith(dropped) and k != "GB_STUDIO_SETUP_ROOT"}
    env.update(HOME=home, HERMES_HOME=str(Path(home) / ".hermes"))
    if tmp:
        env.update(TMPDIR=tmp)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=bytecode)
    return env


def written(home: str | Path) -> list[str]:
    return sorted(str(path.relative_to(home)) for path in Path(home).rglob("*"))


def left(tmp: str | Path) -> list[str]:
    """What the suite left directly in its temp folder (each a test's own temp file or folder), as full paths."""
    return sorted(str(path) for path in Path(tmp).iterdir())


def test_modules(root: Path) -> list[str]:
    """Every unit test module under tests/, dotted, as discovery finds them (test_*.py)."""
    return sorted(
        ".".join(path.relative_to(root).with_suffix("").parts) for path in (root / "tests").rglob("test_*.py")
    )


def leaking_modules(root: Path, temp_base: str, run: Callable) -> list[str]:
    """The test modules that write into an empty home, or leave something in an empty temp folder, when each runs
    alone (within LOCATE_BUDGET_S). ``run(cmd, env)`` runs one command from the repository root (check.py's run; tests
    pass a fake)."""
    found = []
    started = time.monotonic()
    for module in test_modules(root):
        if time.monotonic() - started > LOCATE_BUDGET_S:
            found.append("(stopped looking after the time budget)")
            break
        with (
            tempfile.TemporaryDirectory(prefix="hermretro-home-", dir=temp_base) as home,
            tempfile.TemporaryDirectory(prefix="hermretro-tmp-", dir=temp_base) as tmp,
            tempfile.TemporaryDirectory(prefix="hermretro-pyc-") as bytecode,
        ):
            run([sys.executable, "-B", "-m", "unittest", module], unit_env(home, bytecode, tmp))
            if written(home) or left(tmp):
                found.append(f"{module} ({', '.join((written(home) + [Path(p).name for p in left(tmp)])[:3])})")
    return found


def leaks(home: str, tmp: str, root: Path, temp_base: str, run: Callable) -> str:
    """After the suite ran with ``unit_env(home, bytecode, tmp)``: "" when it left nothing, else the failure message
    naming what was left and, after a rerun module by module, which test modules left it."""
    in_home, in_tmp = written(home), left(tmp)
    if not in_home and not in_tmp:
        return ""
    modules = leaking_modules(root, temp_base, run)
    if in_home:
        return leak_message(in_home, modules)
    return tmp_message(in_tmp, modules)


def leak_message(leaked: list[str], modules: list[str]) -> str:
    who = (
        "\nwritten by: " + "; ".join(modules)
        if modules
        else "\n(no single module writes there on its own: look for a test that changes HOME or HERMES_HOME)"
    )
    return (
        "the tests wrote into the home folder: " + ", ".join(leaked[:8]) + who + "\nFIX: give those tests a temp "
        "folder: isolated_home(self) from tests/support.py in setUp (moves HERMRETRO_HOME and the plugin data folder; "
        "a test that calls a real emitter reaches every feature's listeners.py and needs it), or throwaway_deps for "
        "downloads"
    )


def tmp_message(leftover: list[str], modules: list[str]) -> str:
    who = "\nleft by: " + "; ".join(modules) if modules else "\n(no single module leaves them on its own)"
    return (
        "the tests left files in the temp folder: " + ", ".join(leftover[:8]) + who + "\nFIX: clean up with "
        "addCleanup / TemporaryDirectory: self.addCleanup(shutil.rmtree, folder, ignore_errors=True) right after "
        "tempfile.mkdtemp(), or tempfile.TemporaryDirectory() with its cleanup (NamedTemporaryFile(delete=False) needs "
        "an addCleanup that unlinks it)"
    )


def layout_note(lines: list[str], changed: list[str] | None = None) -> str:
    """The unit row's note on tests/repo/test_layout.py's warnings (it prints them without failing): how many, the
    files over the size warning (tools/layout.toml [size]) by name, those the branch changed (``changed``) first,
    and the command that lists them all."""
    warnings = [line.split("layout warning: ", 1)[1] for line in lines if "layout warning: " in line]
    if not warnings:
        return ""
    big = [w.split(" has ")[0] for w in warnings if " has " in w and " lines " in w]
    mine = set(changed or ())
    big = [name for name in big if name in mine] + [name for name in big if name not in mine]
    shown = ", ".join(big[:6]) + (f" and {len(big) - 6} more" if len(big) > 6 else "")
    over = f"; over the size warning: {shown}" if big else ""
    return f"; {len(warnings)} layout warnings{over} (all: python -m unittest tests.repo.test_layout)"


def branch_files(run) -> list[str]:
    """The files the branch changed since it left origin/dev, committed or not (none outside a git checkout or
    without that ref): layout_note names the over-size ones among them first."""
    found = run(["git", "diff", "--name-only", "--merge-base", "origin/dev"])
    return found.stdout.split() if found.returncode == 0 else []
