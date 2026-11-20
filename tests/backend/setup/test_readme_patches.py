"""backend/setup/README.md "Tests" names every private provision name the tests reach into.

The tests patch and call `provision._node_platform`, `provision.subprocess` and a few more; a split of provision.py
that moves one of them silently stops the patch from applying. The README lists them so the split keeps them; this
keeps that list in step with the tests.

Run alone: python -m unittest tests.backend.setup.test_readme_patches
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
README = ROOT / "backend" / "setup" / "README.md"
# `provision._name` or `provision.subprocess`, and mock.patch.object(provision, "_name", ...).
USED = re.compile(r"\bprovision\.(_\w+|subprocess)\b|patch\.object\(provision, \"(_\w+)\"")


def used_names(texts: list[str]) -> set[str]:
    return {next(group for group in match.groups() if group) for text in texts for match in USED.finditer(text)}


def listed_names(readme: str) -> set[str]:
    tests = readme.split("## Tests", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"`provision\.(_\w+|subprocess)`", tests))


class ReadmePatches(unittest.TestCase):
    def test_the_readme_lists_every_private_name_the_tests_use(self):
        here = Path(__file__).resolve()
        texts = [
            path.read_text(encoding="utf-8")
            for path in sorted((ROOT / "tests" / "backend").rglob("test_*.py"))
            if path.resolve() != here
        ]
        used, listed = used_names(texts), listed_names(README.read_text(encoding="utf-8"))
        self.assertTrue(used, "no test reaches into provision: fix USED")
        self.assertEqual(
            sorted(used - listed),
            [],
            "\nFIX: name these in backend/setup/README.md, \"Tests\" (the tests patch or call them on provision)",
        )
        self.assertEqual(
            sorted(listed - used), [], "\nFIX: drop these from backend/setup/README.md, \"Tests\" (no test uses them)"
        )

    def test_a_patched_name_is_found(self):
        text = 'mock.patch.object(provision, "_node_platform", x); provision._pins(t); provision.subprocess.run'
        self.assertEqual(used_names([text]), {"_node_platform", "_pins", "subprocess"})
        self.assertEqual(used_names(["provision.host_target()", "a .provision.lock file"]), set())


if __name__ == "__main__":
    unittest.main()
