"""retrodev's own rules: what it may never do, the pure gates, and the next-step lines.

Run alone: python -m unittest tests.retrodev.test_rules
"""

import json
import unittest
from pathlib import Path

import retrodev
from retrodev import gates, github, status

SOURCE = Path(retrodev.__file__).parent
SECTIONS = ["Why", "What changed", "How verified", "Risk and rollback", "Not done"]
# Built by concatenation so this file holds none of them as written.
FORBIDDEN = [
    "--" + "force",
    "push " + "-f",
    "push" + '", "-f',
    ":" + "main",
    "push origin " + "main",
    "gateway " + "restart",
    "gateway" + "', '" + "restart",
]


# The one push that moves main: release publish's fast-forward of a green dev commit (<sha> onto main).
RELEASE_PUSH = ("release_publish.py", 'found.append({"run": ["git", "push", ctx.remote, f"{sha}' + ':' + 'main"]')


class NeverDoes(unittest.TestCase):
    def test_the_source_never_rewrites_remotes_pushes_to_main_or_restarts_hermes(self):
        hits = []
        for path in sorted(SOURCE.rglob("*.py")) + [SOURCE / "policy.toml"]:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if (path.name, line.strip()[: len(RELEASE_PUSH[1])]) == RELEASE_PUSH:
                    continue  # the release fast-forward, checked on its own below
                hits += [f"{path.name}:{number}: {word}" for word in FORBIDDEN if word in line]
        self.assertEqual(
            hits,
            [],
            "retrodev never force-pushes, never pushes to main (but for the release fast-forward in "
            "release_publish.py) and never restarts Hermes\nFIX: remove those lines",
        )

    def test_main_moves_only_in_the_release_module_and_only_by_one_plain_push(self):
        hits = []
        for path in sorted(SOURCE.rglob("*.py")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if ":" + "main" in line:
                    hits.append((path.name, number, line.strip()))
        self.assertEqual(len(hits), 1, hits)
        name, _number, line = hits[0]
        self.assertEqual(name, RELEASE_PUSH[0])
        self.assertTrue(line.startswith(RELEASE_PUSH[1]), line)

    def test_force_appears_nowhere_and_the_mac_never_pushes(self):
        hits = [
            f"{path.relative_to(SOURCE)}:{number}"
            for path in sorted(SOURCE.rglob("*"))
            if path.is_file() and path.suffix in (".py", ".toml", ".md")
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if "--" + "force" in line
        ]
        self.assertEqual(hits, [], "FIX: never a forced push or removal; remove those lines")
        self.assertNotIn("push", (SOURCE / "mac.py").read_text(encoding="utf-8").replace("pushes", ""))

    def test_the_package_marker_is_the_agreed_line(self):
        self.assertEqual(
            (SOURCE / "__init__.py").read_text(),
            '"""retrodev: the development CLI for hermretro (python tools/retrodev --help)."""\n',
        )

    def test_every_module_stays_under_400_lines(self):
        big = [p.name for p in SOURCE.glob("*.py") if p.read_text(encoding="utf-8").count("\n") > 400]
        self.assertEqual(big, [], "split the module by concern")


class Titles(unittest.TestCase):
    def test_a_plain_sentence_passes(self):
        self.assertEqual(gates.title_problems("Add retrodev, a development CLI"), [])

    def test_bad_titles_are_named(self):
        self.assertIn("period", gates.title_problems("Add a thing.")[0])
        self.assertIn("more than one line", gates.title_problems("Add\nthing")[0])
        self.assertIn("empty", gates.title_problems("  ")[0])


class Bodies(unittest.TestCase):
    def test_a_filled_in_body_passes(self):
        from tests.retrodev.fixture import GOOD_BODY

        self.assertEqual(gates.body_problems(GOOD_BODY, SECTIONS), [])

    def test_the_template_itself_is_refused_section_by_section(self):
        template = (Path(__file__).resolve().parents[2] / ".github" / "pull_request_template.md").read_text()
        problems = gates.body_problems(template, SECTIONS)
        self.assertEqual(sum("is empty" in p for p in problems), 5, problems)  # comments and [ ] boxes are not content
        self.assertTrue(any("agent" in p for p in problems))

    def test_a_missing_section_and_the_agent_line(self):
        problems = gates.body_problems("## Why\nBecause.\n", SECTIONS)
        self.assertIn("section '## What changed' is missing", problems)
        self.assertTrue(problems[-1].startswith("no line says an agent"))

    def test_lines_naming_the_agent(self):
        self.assertTrue(gates.names_agent("Made by an agent (Hermes) for the owner."))
        self.assertTrue(gates.names_agent("An agent wrote this change."))
        self.assertFalse(gates.names_agent("The agent half registers tools."))


class Branches(unittest.TestCase):
    def test_kind_and_topic(self):
        kinds = ["feat", "fix", "docs", "chore"]
        self.assertEqual(gates.parse_branch("feat/retrodev-core", kinds), ("feat", "retrodev-core"))
        for bad in ("feature/x", "feat/Upper", "feat", "feat/a/b"):
            with self.assertRaises(gates.Failure, msg=bad):
                gates.parse_branch(bad, kinds)


class NextStep(unittest.TestCase):
    BASE = {
        "needs_plan": True,
        "plan_approved": True,
        "checks_passed": True,
        "dirty": False,
        "pr": 7,
        "head": "a",
        "pushed": "a",
        "ci": "passing",
        "topic": "t",
    }

    def step(self, **change):
        return status.next_step({**self.BASE, **change})

    def test_each_stage_names_its_command(self):
        self.assertIn("plan approve t --words", self.step(plan_approved=False))
        self.assertEqual(self.step(checks_passed=False), "next: python tools/retrodev check")
        self.assertIn("git commit", self.step(dirty=True))
        self.assertIn("retrodev ship --title", self.step(pr=None))
        self.assertIn("pushes the new commits", self.step(head="b"))
        self.assertIn("gh pr checks 7 --watch", self.step(ci="pending"))
        self.assertIn("--log-failed", self.step(ci="failing"))
        self.assertIn("retrodev report", self.step())
        self.assertIn("retrodev start", self.step(protected=True))

    def test_a_small_change_needs_no_plan(self):
        self.assertEqual(
            self.step(needs_plan=False, plan_approved=False, checks_passed=False), "next: python tools/retrodev check"
        )


class CI(unittest.TestCase):
    def test_summary_words(self):
        self.assertEqual(github.ci_summary(None), "unknown")
        self.assertEqual(github.ci_summary([]), "none")
        self.assertEqual(github.ci_summary([{"bucket": "pass"}, {"bucket": "pending"}]), "pending")
        self.assertEqual(github.ci_summary([{"bucket": "pass"}, {"bucket": "fail"}]), "failing")
        self.assertEqual(github.ci_summary([{"bucket": "pass"}, {"bucket": "skipping"}]), "passing")
        self.assertEqual(github.pr_number("https://github.com/o/r/pull/42"), 42)

    def test_gh_pr_checks_json_is_read_on_failing_and_pending_exits(self):
        from types import SimpleNamespace

        from tests.retrodev.fixture import FakeGH

        failed = [{"name": "unit", "state": "FAILURE", "bucket": "fail", "link": "l"}]
        for code in (0, 1, 8):  # gh exits 1 when a check failed, 8 while some are pending
            ctx = SimpleNamespace(gh_runner=FakeGH({("pr", "checks"): (code, json.dumps(failed), "")}), top=".")
            self.assertEqual(github.checks(ctx, 3), failed, code)
            self.assertEqual(github.ci_summary(github.checks(ctx, 3)), "failing")
        for answer in ((1, "", "no checks reported"), (1, "not json", ""), (4, "[]", "auth")):
            ctx = SimpleNamespace(gh_runner=FakeGH({("pr", "checks"): answer}), top=".")
            self.assertIsNone(github.checks(ctx, 3), answer)


class Patterns(unittest.TestCase):
    def test_inputs_match_nested_files(self):
        from retrodev import repo

        self.assertTrue(repo.matches("backend/library/rpcs.py", ["backend/*/rpcs.py"]))
        self.assertTrue(repo.matches("tools/bundle/x/y.mjs", ["tools/bundle/*"]))
        self.assertFalse(repo.matches("docs/guide.md", ["*.py", "page/*"]))

    def test_check_py_rows_are_read(self):
        from retrodev import checks

        row = "FAILED  scan        11.6 s  verdict caution; installs would ask for confirmation:"
        self.assertEqual(checks.ROW.match(row).groups()[:3], ("FAILED", "scan", "11.6"))
        self.assertEqual(checks.ROW.match("     ok  unit         0.1 s  fine").group(2), "unit")
        self.assertIsNone(checks.ROW.match("         FIX: read the failures above"))


if __name__ == "__main__":
    unittest.main()
