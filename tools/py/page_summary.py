"""check.py page's summary line: how many files ran, and how many checks passed and failed in them.

`node --test` counts each scenario file on tests/page/harness.mjs as one test, however many checks it makes; the
harness ends each such file with '<file>: N passed, M failed'. So the checks are those lines' numbers plus the
tests of the files without such a line (the source-level node:test files, one count per test()).
"""

from __future__ import annotations

import re

HARNESS_LINE = re.compile(r"^(\S+\.test\.mjs): (\d+) passed, (\d+) failed$", re.M)
NODE_COUNT = re.compile(r"^ℹ (pass|fail) (\d+)$", re.M)


def summary(output: str, files: int) -> str:
    """'N files, M checks passed, K failed' from `node --test`'s output over ``files`` files."""
    node = {name: int(count) for name, count in NODE_COUNT.findall(output)}
    harness = [(int(passed), int(failed)) for _file, passed, failed in HARNESS_LINE.findall(output)]
    # Each harness file is one node test: passing when its own line says 0 failed.
    passing_files = sum(1 for _passed, failed in harness if not failed)
    failing_files = len(harness) - passing_files
    passed = node.get("pass", 0) - passing_files + sum(passed for passed, _failed in harness)
    failed = node.get("fail", 0) - failing_files + sum(failed for _passed, failed in harness)
    return f"{files} files, {max(passed, 0)} checks passed, {max(failed, 0)} failed"
