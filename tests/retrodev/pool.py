"""How the retrodev tests run on threads: `parallel` (a module's load_tests), `alone` (a module that must run by
itself) and `one_pool` (the package's load_tests under discovery: one pool for every module). Each thread's test
reports into a recorder, replayed onto the real result in order afterwards. The environment the tests share
(fixture.shared_env) is set once around the pool, never per test. Each pooled item that leaves os.environ, the
working folder or sys.path changed fails, naming its module (a mutation the syntax guard cannot see).
"""

from __future__ import annotations

import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock
from unittest.suite import _ErrorHolder


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
SHARED = {"on": False}


class ParallelSuite(unittest.TestSuite):
    """Runs its items on threads: tests, or whole class suites (a class with shared fixtures runs its own tests in
    order on one thread, its setUpClass and tearDownClass around them). A TestSuite, so whatever walks a discovered
    suite (isinstance(item, unittest.TestSuite), then iterate) reaches its tests and their ids."""

    def run(self, result, debug=False):
        tests = list(self)
        if not tests:
            return result

        def one(test):
            recorded = _Recorded()
            module = _module(test)  # now: a TestSuite drops each test it has run, so afterwards it holds none
            before = _process_state()
            test(recorded)
            changed = _changed(before, _process_state())
            if changed:
                try:
                    raise AssertionError(
                        f"{module} (or a module on another thread meanwhile) changed process-wide state the pool's "
                        f"threads share: {'; '.join(changed)}\nFIX: set it only in the env= of the subprocesses it "
                        "starts (or pass cwd=), or make the module alone (load_tests = alone)"
                    )
                except AssertionError:
                    recorded.addError(_ErrorHolder(f"process state ({module})"), sys.exc_info())
            return recorded.calls

        from tests.retrodev.fixture import shared_env  # the fixture imports this module

        with mock.patch.dict(os.environ, shared_env(), clear=True):
            SHARED["on"] = True
            try:
                with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 2, len(tests))) as pool:
                    outcomes = list(pool.map(one, tests))
            finally:
                SHARED["on"] = False
        for calls in outcomes:
            for name, args in calls:
                method = getattr(result, name, None)
                if method is not None:
                    method(*args)
        return result


def _process_state() -> tuple:
    return dict(os.environ), os.getcwd(), list(sys.path)


def _changed(before: tuple, after: tuple) -> list[str]:
    (env, cwd, path), (env2, cwd2, path2) = before, after
    changed = [f"os.environ {key}" for key in sorted(set(env) | set(env2)) if env.get(key) != env2.get(key)]
    if cwd != cwd2:
        changed.append(f"working folder {cwd} -> {cwd2}")
    if path != path2:
        added = [p for p in path2 if path2.count(p) > path.count(p)]
        removed = [p for p in path if path.count(p) > path2.count(p)]
        changed.append(f"sys.path added {sorted(set(added))}, removed {sorted(set(removed))} (or reordered)")
    return changed


def _module(test) -> str:
    """The module of a pooled item (a test, or the first test of a class suite); read it before the item runs."""
    test = next(_flatten(test), None) if isinstance(test, unittest.BaseTestSuite) else test
    return type(test).__module__ if test is not None else "a pooled module"


def _flatten(suite):
    for item in suite:
        if isinstance(item, unittest.BaseTestSuite):
            yield from _flatten(item)
        else:
            yield item


def parallel(loader, tests, pattern):
    """A module's load_tests: its tests on threads (each RepoCase is independent)."""
    return ParallelSuite(list(_flatten(tests)))


class AloneSuite(unittest.TestSuite):
    """A module's tests that must not overlap any other (they change the process environment): load_tests = alone."""


def alone(loader, tests, pattern):
    return AloneSuite(tests)


def one_pool(found) -> unittest.TestSuite:
    """The package's load_tests (discovery): ONE pool for the whole package, so no module waits for its own slowest
    test while threads idle. Parallel modules give it each test; other modules each class, as one item (its tests
    share class fixtures, so they stay in order on one thread); `alone` modules run after the pool, by themselves."""

    def split(suite, pooled: list, rest: unittest.TestSuite) -> None:
        for item in suite:
            if isinstance(item, ParallelSuite):
                pooled += _flatten(item)
            elif isinstance(item, AloneSuite):
                rest.addTest(item)
            elif isinstance(item, unittest.TestSuite):
                if all(isinstance(test, unittest.TestCase) for test in item):
                    if item.countTestCases():
                        pooled.append(item)  # one class: its fixtures and order kept
                else:
                    split(item, pooled, rest)
            else:
                pooled.append(item)

    pooled: list = []
    rest = unittest.TestSuite()
    split(found, pooled, rest)
    pooled.sort(key=lambda item: not isinstance(item, unittest.TestSuite))  # whole classes first: the longest items
    return unittest.TestSuite([ParallelSuite(pooled), rest])
