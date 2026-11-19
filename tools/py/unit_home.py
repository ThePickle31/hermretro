"""check.py unit's empty home: the environment it runs the suite in, and, only when the suite wrote into that home,
which test modules did it.

The suite runs once in an empty home folder. Anything found there afterwards was written by a test that was not given
a temp folder. Finding which one costs a rerun, so it happens only after a leak: each test module runs again on its own,
in a fresh empty home, and the modules that write there are named. The usual cause is a test that calls a real
emitter (a tool or RPC that emits an event): the event reaches every feature's listeners.py, which writes where the
real home is unless the test called isolated_home(self).
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

LOCATE_BUDGET_S = 120  # stop looking after this; the leak itself is already reported


def unit_env(home: str, bytecode: str) -> dict[str, str]:
    """No HERMRETRO_* folders from the developer's shell, HOME and HERMES_HOME (Hermes's plugin data folder,
    host._data_dir(), lands there too) in the empty home, and an empty bytecode folder (-B alone still reads stale
    .pyc)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("HERMRETRO_") and k != "GB_STUDIO_SETUP_ROOT"}
    env.update(HOME=home, HERMES_HOME=str(Path(home) / ".hermes"))
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=bytecode)
    return env


def written(home: str | Path) -> list[str]:
    return sorted(str(path.relative_to(home)) for path in Path(home).rglob("*"))


def test_modules(root: Path) -> list[str]:
    """Every unit test module under tests/, dotted, as discovery finds them (test_*.py)."""
    return sorted(
        ".".join(path.relative_to(root).with_suffix("").parts) for path in (root / "tests").rglob("test_*.py")
    )


def leaking_modules(root: Path, temp_base: str, run: Callable) -> list[str]:
    """The test modules that write into an empty home when each runs alone (within LOCATE_BUDGET_S). ``run(cmd, env)``
    runs one command from the repository root (check.py's run; tests pass a fake)."""
    found = []
    started = time.monotonic()
    for module in test_modules(root):
        if time.monotonic() - started > LOCATE_BUDGET_S:
            found.append("(stopped looking after the time budget)")
            break
        with (
            tempfile.TemporaryDirectory(prefix="hermretro-home-", dir=temp_base) as home,
            tempfile.TemporaryDirectory(prefix="hermretro-pyc-") as bytecode,
        ):
            run([sys.executable, "-B", "-m", "unittest", module], unit_env(home, bytecode))
            if written(home):
                found.append(f"{module} ({', '.join(written(home)[:3])})")
    return found


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
