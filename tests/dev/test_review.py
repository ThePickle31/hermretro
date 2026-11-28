"""python tools/dev review (tools/dev/review.py): tiers by path, the findings and their answers, the pull request's
sections, and a pass's bookkeeping from prepare to record, in a throwaway repository with gh stubbed and git kept
away from the developer's own configuration."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "dev"))

import review  # noqa: E402 - tools/dev goes on sys.path first
import review_findings as findings  # noqa: E402
import review_pr  # noqa: E402
import review_tier as tier  # noqa: E402

# Every git, the command's own included: none of the developer's configuration, hooks or signing.
GIT_ENVIRONMENT = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_COUNT": "4",
    "GIT_CONFIG_KEY_0": "user.name",
    "GIT_CONFIG_VALUE_0": "Test",
    "GIT_CONFIG_KEY_1": "user.email",
    "GIT_CONFIG_VALUE_1": "test@example.invalid",
    "GIT_CONFIG_KEY_2": "core.hooksPath",
    "GIT_CONFIG_VALUE_2": os.devnull,
    "GIT_CONFIG_KEY_3": "commit.gpgSign",
    "GIT_CONFIG_VALUE_3": "false",
}


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

    def test_the_last_section_without_a_newline_is_replaced_not_added(self):
        new = review_pr.replace_section("## Summary\nS\n\n## Review", "Review", "Tier light · not reviewed.")
        self.assertEqual(new, "## Summary\nS\n\n## Review\nTier light · not reviewed.\n")

    def test_the_other_sections_stay(self):
        body = "## Summary\nS\n\n## Review\nUnder review.\n\n## Notes\nN\n"
        new = review_pr.replace_section(body, "Review", "x")
        self.assertEqual(new, "## Summary\nS\n\n## Review\nx\n\n## Notes\nN\n")


class Pass(unittest.TestCase):
    """prepare, take and record in a throwaway repository: a bare origin with dev, and a branch's worktree."""

    def setUp(self):
        inherited = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        environment = mock.patch.dict(os.environ, {**inherited, **GIT_ENVIRONMENT}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        self.origin, self.root = base / "origin.git", base / "work"
        self.git(base, "init", "--quiet", "--bare", str(self.origin))
        self.git(base, "init", "--quiet", "-b", "dev", str(self.root))
        shutil.copytree(ROOT / "tools" / "review", self.root / "tools" / "review")
        (self.root / "AGENTS.md").write_text("# guide\n")
        (self.root / ".gitignore").write_text("notes/\n")
        self.commit("start")
        self.git(self.root, "remote", "add", "origin", str(self.origin))
        self.git(self.root, "push", "--quiet", "-u", "origin", "dev")
        self.git(self.root, "checkout", "--quiet", "-b", "feat/thing")
        self.write("backend/thing.py", "X = 1\n")
        self.push("thing")
        self.body = "## Summary\nA thing.\n\n## Why\nIt was missing.\n\n## Review\nUnder review.\n"
        self.gh_fails = False
        patcher = mock.patch.object(review, "gh", self.fake_gh)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.review = review.Review(self.root)
        self.review.folder.mkdir(parents=True)
        (self.review.folder / "decisions.md").write_text("Approved: the thing.\n")
        for n in range(1, 4):
            self.addCleanup(shutil.rmtree, self.review.checkout(n), True)

    def git(self, cwd: Path, *args: str) -> str:
        done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
        if done.returncode:
            raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
        return done.stdout

    def write(self, rel: str, text: str) -> None:
        (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.root / rel).write_text(text)

    def commit(self, message: str) -> None:
        self.git(self.root, "add", "-A")
        self.git(self.root, "commit", "--quiet", "-m", message)

    def push(self, message: str) -> None:
        self.commit(message)
        self.git(self.root, "push", "--quiet", "-u", "origin", "HEAD")

    def fake_gh(self, _root, *args: str) -> str:
        if self.gh_fails:
            raise review.ReviewError("gh: no network")
        if args[:2] == ("pr", "view"):
            return json.dumps({"title": "feat(thing): a thing", "body": self.body})
        if args[:2] == ("pr", "edit"):
            self.body = Path(args[args.index("--body-file") + 1]).read_text()
            return ""
        raise AssertionError(args)

    def fill_answers(self, n: int, given: list[str]) -> None:
        """Fill the answers.md take generated, its blank answers in order, as the author does."""
        path = self.review.pass_folder(n) / "answers.md"
        lines, answers = path.read_text().splitlines(), iter(given)
        blanks = [i for i, line in enumerate(lines) if line == "Answer:"]
        self.assertEqual(len(blanks), len(given), "one blank answer per finding")
        for i in blanks:
            lines[i] = f"Answer: {next(answers)}"
        path.write_text("\n".join(lines) + "\n")

    def run_pass(self, n: int, found: str, answers: str, model: str = "gpt-6.2-sol") -> str:
        """Prepare pass n, write its findings and answers as a reviewer and the author would, and record it."""
        self.review.prepare(n)
        (self.review.pass_folder(n) / "findings.md").write_text(found)
        self.review.take(n)
        (self.review.pass_folder(n) / "answers.md").write_text(answers)
        return self.review.record(n, model)

    def test_a_pass_from_prepare_to_record(self):
        self.assertIn("tier standard", self.review.prepare(1))
        brief = (self.review.pass_folder(1) / "brief.md").read_text()
        self.assertNotRegex(brief, r"\{\{\w+\}\}")
        head = self.git(self.root, "rev-parse", "HEAD").strip()
        self.assertIn(head, brief)
        self.assertIn("> A thing.", brief)
        checkout = self.review.checkout(1)
        self.assertEqual(self.git(checkout, "rev-parse", "HEAD").strip(), head, "pinned to the pushed head")
        (self.review.pass_folder(1) / "findings.md").write_text(
            "## Important: backend/thing.py:1 X is wrong\nhow\n## Nit: backend/thing.py:1 name\n"
        )
        self.review.take(1)
        self.assertFalse(checkout.exists(), "the reviewers' checkout goes")
        with self.assertRaises(findings.FindingsError):
            self.review.record(1, "gpt-6.2-sol")
        self.fill_answers(1, ["fixed", "declined — the name matches its caller's"])
        self.write("backend/thing.py", "X = 2\n")
        self.push("fix")
        self.assertIn("Pass 2 is due", self.review.record(1, "gpt-6.2-sol"))
        self.assertIn("Pass 1, standard (gpt-6.2-sol): 1 Important fixed, 1 Nit declined.", self.body)
        self.assertIn("the name matches its caller's", self.body)
        self.assertTrue(self.body.startswith("## Summary\nA thing."), "the rest of the body stays")
        self.assertTrue(self.review.status().endswith("Pass 2 is due: prepare --pass 2."))
        self.review.prepare(2)
        brief = (self.review.pass_folder(2) / "brief.md").read_text()
        self.assertIn(f"git diff {head}..", brief)
        self.assertIn("what changed since pass 1", brief)
        self.assertIn(str(self.review.pass_folder(1)), brief, "earlier passes' findings")

    def test_commits_no_answer_accounts_for_need_a_pass(self):
        self.review.prepare(1)
        self.write("backend/other.py", "Y = 1\n")  # pushed while the reviewer read the pinned head
        self.push("more")
        (self.review.pass_folder(1) / "findings.md").write_text("No findings.\n")
        self.review.take(1)
        self.assertIn("Pass 2 is due", self.review.record(1, "gpt-6.2-sol"))

    def test_a_fixed_nit_alone_needs_no_pass(self):
        self.review.prepare(1)
        (self.review.pass_folder(1) / "findings.md").write_text("## Nit: backend/thing.py:1 name\n")
        self.review.take(1)
        (self.review.pass_folder(1) / "answers.md").write_text("## Nit: backend/thing.py:1 name\nAnswer: fixed\n")
        self.write("backend/thing.py", "X_NAMED = 1\n")
        self.push("nit")
        self.assertIn("No other pass is due", self.review.record(1, "gpt-6.2-sol"))
        with self.assertRaisesRegex(review.ReviewError, "no pass is due"):
            self.review.prepare(2)

    def test_a_fixed_nit_does_not_answer_an_unrelated_commit_pushed_meanwhile(self):
        self.review.prepare(1)
        self.write("backend/other.py", "Y = 1\n")  # pushed while the reviewer read the pinned head
        self.push("unrelated")
        (self.review.pass_folder(1) / "findings.md").write_text("## Nit: backend/thing.py:1 name\n")
        self.review.take(1)
        self.fill_answers(1, ["fixed"])
        self.write("backend/thing.py", "X_NAMED = 1\n")
        self.push("nit")
        self.assertIn("Pass 2 is due", self.review.record(1, "gpt-6.2-sol"))

    def test_each_pass_keeps_its_own_tier_and_the_cap_is_told_apart(self):
        self.run_pass(1, "## Important: backend/thing.py:1 X\n", "## Important: backend/thing.py:1 X\nAnswer: fixed\n")
        self.write("backend/broker/client.py", "Z = 1\n")
        self.push("broker")
        self.review.prepare(2)
        for name in ("findings.md", "security-findings.md"):
            (self.review.pass_folder(2) / name).write_text("No findings.\n")
        self.review.take(2)
        self.review.record(2, "gpt-6.2-sol", "gpt-daybreak-blue-latest")
        self.assertIn("Pass 1, standard (gpt-6.2-sol): 1 Important fixed · pass 2, sensitive", self.body)
        self.assertEqual(
            review.Review.next_step((4, tier.PASS)).split(":")[1].strip(), "a pass 4 only when the owner asks."
        )
        self.assertIn("the review is over", review.Review.next_step((5, tier.PASS)))

    def test_a_fixed_important_in_documentation_alone_needs_no_pass(self):
        self.review.prepare(1)
        (self.review.pass_folder(1) / "findings.md").write_text("## Important: README.md:1 false\n")
        self.review.take(1)
        (self.review.pass_folder(1) / "answers.md").write_text("## Important: README.md:1 false\nAnswer: fixed\n")
        self.write("README.md", "# true\n")
        self.push("docs")
        self.assertIn("No other pass is due", self.review.record(1, "gpt-6.2-sol"))

    def test_a_tests_only_pass_reads_the_tests_alone(self):
        self.run_pass(1, "## Important: backend/thing.py:1 X\n", "## Important: backend/thing.py:1 X\nAnswer: fixed\n")
        self.write("tests/test_thing.py", "def test(): pass\n")
        self.write("README.md", "# notes\n")
        self.push("tests")
        self.review.prepare(2)
        brief = (self.review.pass_folder(2) / "brief.md").read_text()
        self.assertIn("the tests changed since pass 1, alone", brief)
        self.assertIn(" -- tests/`", brief)

    def test_a_sensitive_path_added_later_brings_a_security_review(self):
        self.run_pass(1, "## Important: backend/thing.py:1 X\n", "## Important: backend/thing.py:1 X\nAnswer: fixed\n")
        self.write("backend/broker/client.py", "Z = 1\n")
        self.push("broker")
        self.assertIn("security-brief.md", self.review.prepare(2))
        self.assertEqual(json.loads((self.review.pass_folder(2) / "pass.json").read_text())["tier"], "sensitive")

    def test_a_failed_publish_leaves_the_pass_unrecorded_and_its_retry_keeps_its_head(self):
        self.review.prepare(1)
        (self.review.pass_folder(1) / "findings.md").write_text("No findings.\n")
        self.review.take(1)
        head = self.git(self.root, "rev-parse", "HEAD").strip()
        self.gh_fails = True
        with self.assertRaises(review.ReviewError):
            self.review.record(1, "gpt-6.2-sol")
        self.assertEqual(self.review.recorded(), [])
        self.write("backend/later.py", "W = 1\n")
        self.push("later")
        self.gh_fails = False
        self.assertIn(
            "Pass 2 is due", self.review.record(1, "gpt-6.2-sol"), "the commit after the attempt is unanswered"
        )
        self.assertEqual(self.review.recorded()[0]["recorded_head"], head)

    def test_a_failed_prepare_leaves_no_checkout(self):
        self.gh_fails = True
        with self.assertRaises(review.ReviewError):
            self.review.prepare(1)
        self.assertFalse(self.review.checkout(1).exists())
        self.gh_fails = False
        self.review.prepare(1)
        self.assertTrue(self.review.checkout(1).exists())

    def test_a_light_change_says_so_in_its_review_section(self):
        self.git(self.root, "rm", "--quiet", "backend/thing.py")
        self.write("README.md", "# docs\n")
        self.push("docs only")
        self.assertIn("Tier light", self.review.prepare(1))
        self.assertTrue(self.body.endswith("## Review\nTier light · not reviewed.\n"))
        self.assertIn("Tier light", self.review.status())

    def test_prepare_refuses_what_it_cannot_pin(self):
        (self.review.folder / "decisions.md").unlink()
        with self.assertRaisesRegex(review.ReviewError, "decisions.md is missing"):
            self.review.prepare(1)
        (self.review.folder / "decisions.md").write_text("ok\n")
        self.write("backend/thing.py", "X = 3\n")
        with self.assertRaisesRegex(review.ReviewError, "uncommitted"):
            self.review.prepare(1)
        self.commit("more")
        with self.assertRaisesRegex(review.ReviewError, "not pushed"):
            self.review.prepare(1)
        for n in (0, -1, 5):
            with self.subTest(n=n), self.assertRaisesRegex(review.ReviewError, "numbered 1 to 3"):
                self.review.prepare(n, over_cap=True)
        with self.assertRaisesRegex(review.ReviewError, "stops after pass 3"):
            self.review.prepare(4)


class Fill(unittest.TestCase):
    def test_a_value_keeps_its_own_braces_and_an_unknown_key_is_refused(self):
        self.assertEqual(review.fill("a {{x}} b", {"x": "{{y}}"}), "a {{y}} b")
        with self.assertRaises(review.ReviewError):
            review.fill("{{missing}}", {})


if __name__ == "__main__":
    unittest.main()
