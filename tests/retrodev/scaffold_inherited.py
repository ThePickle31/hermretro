"""The whole scaffold check on a copy whose page suite fails (review round 2 of #64, finding 0), run by
test_scaffold_tree.py (inherited_page_failure_skips_the_whole_check): an unrelated page failure the copy has
before `new` runs makes `check.py scaffold` and a direct run of the module report skipped ("fix page first"), not
failed; a page failure only `new` brings (a probe page test that fails once page/pages/rdtabs exists) fails.
"""

from __future__ import annotations

import sys

from tests.retrodev.tree_copy import git_ok, run

INNER = "RD_SCAFFOLD_INNER"  # the scaffold check run inside a copy: it does not run this probe again
MODULE = "tests.retrodev.test_scaffold_tree"
PROBE = "tests/page/rdprobe.test.mjs"
HEAD = (
    "// A probe page test the scaffold check's own regression test writes into its copy.\n"
    "import { test } from 'node:test'\nimport assert from 'node:assert/strict'\nimport { existsSync } from 'node:fs'\n\n"
)
UNRELATED = HEAD + "test('rdprobe', () => {\n  assert.fail('rdprobe: a page failure the tree has already')\n})\n"
BROUGHT = HEAD + (
    "test('rdprobe', () => {\n  assert.ok(!existsSync('page/pages/rdtabs'), 'rdprobe: the scaffolding broke page')\n})\n"
)


def inherited_page_failure_skips_the_whole_check(case, page_first: str, drop: tuple[str, ...]) -> None:
    _, tree, env = case.make_tree()
    inner = {key: value for key, value in env.items() if key not in drop} | {INNER: "1", "RD_SCAFFOLD_FULL": "1"}

    def probe(text: str, message: str) -> None:
        (tree / PROBE).write_text(text)
        for command in (["add", "-A"], ["commit", "-q", "-m", message]):
            git_ok(case, tree, env, command)

    probe(UNRELATED, "An unrelated page failure")
    checked = run([sys.executable, "-B", "tools/check.py", "scaffold"], tree, inner)
    said = checked.stdout + checked.stderr
    case.assertEqual(checked.returncode, 0, said)
    case.assertRegex(said, r"skipped  scaffold\s+[\d.]+ s  " + page_first.replace("(", r"\(").replace(")", r"\)"))
    direct = run([sys.executable, "-B", "-m", "unittest", "-v", MODULE], tree, inner)
    case.assertEqual(direct.returncode, 0, direct.stderr[-6000:])
    reason = page_first.removeprefix("skipped: ").replace("(", r"\(").replace(")", r"\)")
    case.assertRegex(direct.stderr, "skipped [\"']" + reason)  # quoted either way: the reason holds a quote
    case.assertNotIn(" ... FAIL", direct.stderr)

    probe(BROUGHT, "A page failure only the scaffolding brings")
    test = f"{MODULE}.GeneratedCodePassesTheRealChecks.test_tab_from_page_passes_its_own_checks_lint_and_bundle"
    brought = run([sys.executable, "-B", "-m", "unittest", test], tree, inner)
    case.assertNotEqual(brought.returncode, 0, brought.stderr[-6000:])
    case.assertIn("rdprobe: the scaffolding broke page", brought.stderr)
    case.assertNotIn(page_first.removeprefix("skipped: "), brought.stderr)
