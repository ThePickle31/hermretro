"""The parts of python tools/dev review: a change's tier by path (review_tier.py), the findings and their answers
(review_findings.py), and a pull request body's sections (review_pr.py)."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "dev"))

import review_findings as findings  # noqa: E402 - tools/dev goes on sys.path first
import review_pr  # noqa: E402
import review_tier as tier  # noqa: E402


def changed(*paths: str, lines: int = 1) -> list:
    return [tier.Changed(path, lines) for path in paths]


class Tiers(unittest.TestCase):
    def test_markdown_and_tests_alone_are_light(self):
        self.assertEqual(
            tier.judge(changed("README.md", "tests/repo/test_x.py", ".github/CONTRIBUTING.md")).tier, "light"
        )

    def test_markdown_an_agent_acts_on_is_not(self):
        for path in (
            "skills/setup/SKILL.md",
            ".agents/skills/x/SKILL.md",
            "AGENTS.md",
            "profile/SOUL.md",
            "tools/review/rules.md",
        ):
            self.assertEqual(tier.judge(changed(path)).tier, "standard", path)

    def test_a_sensitive_path_makes_the_change_sensitive_whatever_else_it_holds(self):
        judged = tier.judge(changed("README.md", "backend/broker/client.py", "tools/ci/changes.py"))
        self.assertEqual(judged.tier, "sensitive")
        self.assertEqual(judged.reasons, ("the broker and its handshake", "CI and the update and install checks"))

    def test_size_alone_is_sensitive_without_generated_files(self):
        self.assertEqual(tier.judge(changed("backend/library/a.py", lines=1001)).tier, "sensitive")
        self.assertEqual(tier.judge(changed("backend/library/a.py", "desktop/plugin.js", lines=900)).tier, "standard")

    def test_later_commits(self):
        self.assertEqual(tier.later(changed("README.md")), tier.NOTHING)
        self.assertEqual(tier.later(changed("README.md", "tests/a.py")), tier.TESTS)
        self.assertEqual(tier.later(changed("skills/setup/SKILL.md")), tier.PASS, "agent-facing Markdown is read again")
        self.assertEqual(tier.later(changed("tests/backend/setup/x.py", "backend/setup/provision.py")), tier.PASS)

    def test_numstat(self):
        text = "3\t1\tbackend/a.py\0-\t-\tplayer/skin.webp\0"
        self.assertEqual(tier.numstat(text), [tier.Changed("backend/a.py", 4), tier.Changed("player/skin.webp", 0)])

    def test_the_readme_names_every_sensitive_path(self):
        readme = (ROOT / "tools" / "review" / "README.md").read_text(encoding="utf-8")
        for pattern, _reason in tier.SENSITIVE_PATHS:
            self.assertIn(f"`{pattern.removesuffix('*')}`", readme, pattern)


class Findings(unittest.TestCase):
    TEXT = (
        "## Important: a.py:1 breaks\nhow\n## Nit: a.py:2 one\n## Nit: a.py:3 two\n## Nit: a.py:4 three\n"
        "## Nit: a.py:5 four\n## Pre-existing: b.py:9 old\n"
    )

    def test_headings_become_findings_and_nits_past_three_drop(self):
        parsed, dropped = findings.parse(self.TEXT)
        self.assertEqual([f.label for f in parsed], ["Important", "Nit", "Nit", "Nit", "Pre-existing"])
        self.assertEqual(dropped, 1)
        self.assertEqual(findings.parse("No findings.\n"), ([], 0))

    def test_a_heading_that_isnt_a_finding_or_is_one_twice_is_refused(self):
        for text in ("## Major: a.py:1 x\n", "nothing here\n", "## Nit: a.py:1 x\n## Nit: a.py:1 x\n"):
            with self.subTest(text=text), self.assertRaises(findings.FindingsError):
                findings.parse(text)

    def test_a_heading_in_an_example_the_evidence_quotes_is_no_finding(self):
        text = "## Important: a.py:1 breaks\nThe body can hold:\n\n~~~~markdown\n## Verification\nx\n~~~~\n"
        parsed, _ = findings.parse(text)
        self.assertEqual([f.heading for f in parsed], ["## Important: a.py:1 breaks"])

    def test_every_finding_needs_an_answer_its_label_takes(self):
        parsed, _ = findings.parse("## Important: a.py:1 breaks\n## Nit: a.py:2 one\n")
        with self.assertRaises(findings.FindingsError):
            findings.answers(parsed, findings.skeleton(parsed))
        answered = (
            "## Important: a.py:1 breaks\nAnswer: wrong — the caller checks it\n## Nit: a.py:2 one\nAnswer: fixed\n"
        )
        done = findings.answers(parsed, answered)
        self.assertEqual([(a.answer, a.reason) for a in done], [("wrong", "the caller checks it"), ("fixed", "")])
        for bad in ("wrong", "noted"):  # a reason missing, an answer its label doesn't take
            with self.subTest(bad=bad), self.assertRaises(findings.FindingsError):
                findings.answers(parsed, answered.replace("wrong — the caller checks it", bad))


class Sections(unittest.TestCase):
    def test_a_heading_in_fenced_code_is_no_heading(self):
        body = "## Summary\nS\n```\n## Review\nan example\n```\n\n## Review\nUnder review."
        self.assertIn("an example", review_pr.section(body, "Summary"))
        new = review_pr.replace_section(body, "Review", "Pass 1, standard (m): no findings.")
        self.assertIn("```\n## Review\nan example\n```", new, "the example stays")
        self.assertTrue(new.endswith("## Review\nPass 1, standard (m): no findings.\n"))
        self.assertEqual(new.count("\n## Review\n"), 2, "one section and the example, not a third")

    def test_a_longer_fence_holds_a_shorter_one(self):
        body = "## Summary\nS\n````\n```\n## Review\nexample\n```\n````\n\n## Review\nUnder review.\n"
        self.assertIn("example", review_pr.section(body, "Summary"))
        new = review_pr.replace_section(body, "Review", "Pass 1, standard (m): no findings.")
        self.assertIn("```\n## Review\nexample\n```\n````", new, "the example stays whole")
        self.assertTrue(new.endswith("## Review\nPass 1, standard (m): no findings.\n"))

    def test_inline_code_of_three_backticks_opens_no_fence(self):
        body = "## Verification\n```git diff``` showed it.\n```git status``` was clean.\n\n## Review\nUnder review.\n"
        new = review_pr.replace_section(body, "Review", "Pass 1, standard (m): no findings.")
        self.assertEqual(new.count("## Review"), 1)
        self.assertNotIn("Under review.", new)

    def test_the_last_section_without_a_newline_is_replaced_not_added(self):
        new = review_pr.replace_section("## Summary\nS\n\n## Review", "Review", "Tier light · not reviewed.")
        self.assertEqual(new, "## Summary\nS\n\n## Review\nTier light · not reviewed.\n")

    def test_the_other_sections_stay(self):
        body = "## Summary\nS\n\n## Review\nUnder review.\n\n## Notes\nN\n"
        new = review_pr.replace_section(body, "Review", "x")
        self.assertEqual(new, "## Summary\nS\n\n## Review\nx\n\n## Notes\nN\n")


if __name__ == "__main__":
    unittest.main()
