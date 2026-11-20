"""The release body's system boxes (moved from test_release.py): the test swaps platform.system and
platform.machine, which every thread of the shared pool reads, so this module runs alone, after the pool
(tests/repo/test_pool_guard.py).

Run alone: python -m unittest tests.retrodev.test_release_alone
"""

import unittest
from unittest import mock

from retrodev import release

from tests.retrodev.fixture import alone
from tests.retrodev.test_release import NEXT, WORDS

load_tests = alone


class Body(unittest.TestCase):
    def test_the_release_body_ticks_the_system_the_checks_ran_on(self):
        with mock.patch("platform.system", return_value="Darwin"), mock.patch("platform.machine", return_value="arm64"):
            text = release.body(NEXT, "0.0.1", WORDS, False)
        self.assertIn("- [x] macOS (Apple Silicon / Intel): arm64", text)
        self.assertIn("- [ ] Linux", text)
        self.assertNotIn("- [x] Linux", text)
        with mock.patch("platform.system", return_value="Linux"), mock.patch("platform.machine", return_value="x86_64"):
            text = release.body(NEXT, "0.0.1", WORDS, False)
        self.assertIn("- [x] Linux", text)
        self.assertIn("- [ ] macOS (Apple Silicon / Intel)", text)
