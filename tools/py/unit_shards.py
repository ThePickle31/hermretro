"""check.py unit's processes: the suite split into shards that run at the same time.

One `unittest` process ran every test module one after another, so most of a machine's cores waited. Now every
test module goes to one of a few shards, each its own process with its own empty home and temp folder. A module
never runs in two shards, so a module that patches process-wide state is as alone in its shard as it was in the
single process.

Shards are filled largest first by each module's recorded time (TIMES: the per-test durations of the last local
run, summed per module; written only from a real run), or by its file size where no time is recorded (a fresh
checkout, CI). Standard library only.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sys
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import unit_home

TIMES = ".dev/unit-times.json"  # git-ignored, per checkout
MAX_SHARDS = 4
DURATION = re.compile(r"^(\d+(?:\.\d+)?)s\s+\S+ \((tests\.[\w.]+)\)$")  # unittest --durations: "0.5s  test (id)"


def shard_count(cpus: int | None) -> int:
    """How many processes: one per core, at least one, at most four."""
    return max(1, min(MAX_SHARDS, cpus or 2))


def deal(weights: dict[str, float], count: int) -> list[list[str]]:
    """The modules dealt into ``count`` shards, heaviest first onto the lightest shard; empty shards dropped."""
    shards: list[tuple[float, list[str]]] = [(0.0, []) for _ in range(count)]
    for module in sorted(weights, key=lambda name: (-weights[name], name)):
        lightest = min(range(count), key=lambda i: shards[i][0])
        total, members = shards[lightest]
        shards[lightest] = (total + weights[module], [*members, module])
    return [sorted(members) for _, members in shards if members]


def weights(root: Path, modules: list[str], times: dict[str, float]) -> dict[str, float]:
    """Each module's recorded seconds, or its size scaled by the recorded modules' seconds per byte."""
    size = {name: (root / (name.replace(".", "/") + ".py")).stat().st_size for name in modules}
    known = [name for name in modules if name in times]
    rate = sum(times[n] for n in known) / max(1, sum(size[n] for n in known)) if known else 1e-4
    return {name: times[name] if name in times else size[name] * rate for name in modules}


def groups(root: Path, modules: list[str], *, times: dict[str, float], cpus: int | None) -> list[list[str]]:
    """The test modules of each process."""
    return deal(weights(root, modules, times), shard_count(cpus)) if modules else []


def without_durations(stderr: str) -> str:
    """The output without unittest's "Slowest test durations" rows, which come after the tracebacks."""
    hidden = ("Slowest test durations", "(durations < ")
    return "\n".join(
        line for line in stderr.splitlines() if not DURATION.match(line.strip()) and not line.startswith(hidden)
    )


def module_times(stderr: str) -> dict[str, float]:
    """Seconds per test module from `--durations 0` output (tests under a millisecond are not listed)."""
    found: dict[str, float] = {}
    for line in stderr.splitlines():
        if match := DURATION.match(line.strip()):
            module = match.group(2).rsplit(".", 2)[0]
            found[module] = found.get(module, 0.0) + float(match.group(1))
    return found


def slowest(stderr: str, count: int = 3) -> list[tuple[float, str]]:
    """The slowest tests across every shard's `--durations` lines, as (seconds, test name)."""
    found = []
    for line in stderr.splitlines():
        if match := DURATION.match(line.strip()):
            found.append((float(match.group(1)), match.group(2).rsplit(".", 1)[-1]))
    return sorted(found, reverse=True)[:count]


def load(path: Path) -> dict[str, float]:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return {str(k): float(v) for k, v in data.items() if isinstance(v, int | float)} if isinstance(data, dict) else {}


def save(path: Path, times: dict[str, float]) -> None:
    """Keep the times for the next run's dealing; a checkout that cannot be written to just deals by size."""
    if not times:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + f".{os.getpid()}")
        temp.write_text(json.dumps(dict(sorted(times.items())), indent=0) + "\n")
        temp.replace(path)
    except OSError:
        pass


def run_suite(root: Path, run: Callable, temp_base: str) -> tuple[str, str]:
    """Every shard at once, each in its own empty home, TMPDIR and bytecode folder: (check.py's unit row, "") or
    ("", the failure with its FIX line). ``run(cmd, env=...)`` runs a command from the repository root."""
    times = root / TIMES
    shards = groups(root, unit_home.test_modules(root), times=load(times), cpus=os.cpu_count())
    durations = ["--durations", "0"] if sys.version_info >= (3, 12) else []
    started = time.monotonic()
    with contextlib.ExitStack() as stack:
        kinds = (("home", temp_base), ("tmp", temp_base), ("pyc", None))
        folders = [
            [stack.enter_context(tempfile.TemporaryDirectory(prefix=f"hermretro-{k}-", dir=d)) for k, d in kinds]
            for _ in shards
        ]

        def one(index: int):
            home, tmp, bytecode = folders[index]
            env = unit_home.unit_env(home, bytecode, tmp)
            return run([sys.executable, "-B", "-m", "unittest", *shards[index], *durations], env=env)

        with ThreadPoolExecutor(max_workers=max(1, len(shards))) as pool:
            results = list(pool.map(one, range(len(shards))))
        wall = time.monotonic() - started
        if failed := [result for result in results if result.returncode]:
            said = "\n".join(
                "\n".join(without_durations(result.stderr).strip().splitlines()[-40:]) for result in failed
            )
            named = [line for r in failed for line in r.stderr.splitlines() if line.startswith(("ERROR: ", "FAIL: "))]
            return "", "\n".join([*named, said]) + (
                "\nFIX: read the failures above; run one file with "
                "PYTHONPYCACHEPREFIX=$(mktemp -d) python -B -m unittest tests/<area>/<feature>/test_<name>.py"
            )
        dirty = [(i, h, t) for i, (h, t, _) in enumerate(folders) if unit_home.written(h) or unit_home.left(t)]
        if dirty:  # each process's leftovers, and the modules among its own that leave them
            rerun = lambda cmd, env: run(cmd, env=env)  # noqa: E731 - unit_home's runner takes env positionally
            return "", "\n".join(unit_home.leaks(h, t, root, temp_base, rerun, modules=shards[i]) for i, h, t in dirty)
    stderr = "\n".join(result.stderr for result in results)
    save(times, {**load(times), **module_times(stderr)})
    counts = [int(found) for found in re.findall(r"^Ran (\d+) tests? in ", stderr, re.M)]
    ran = f"Ran {sum(counts)} tests in {wall:.3f}s ({len(shards)} processes)" if counts else "ok"
    timed = slowest(stderr)
    slow = "; slowest: " + ", ".join(f"{name} {seconds:.3f}s" for seconds, name in timed) if timed else ""
    # tests/repo/test_layout.py prints what should be fixed soon (big files, allowances) without failing.
    changed = unit_home.branch_files(run) if "layout warning: " in stderr else []
    return f"{ran}{unit_home.layout_note(stderr.splitlines(), changed)}{slow}", ""
