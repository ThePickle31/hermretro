"""python tools/dev review (tools/dev/review.py): tiers by path, the findings and their answers, and a pass's
bookkeeping from prepare to record, in a throwaway repository with gh stubbed."""

import json
import re
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
import review_tier as tier  # noqa: E402

ISOLATED = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]


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

    def test_a_heading_that_isnt_a_finding_is_refused(self):
        with self.assertRaises(findings.FindingsError):
            findings.parse("## Major: a.py:1 x\n")
        with self.assertRaises(findings.FindingsError):
            findings.parse("nothing here\n")

    def test_every_finding_needs_an_answer_its_label_takes(self):
        parsed, _ = findings.parse("## Important: a.py:1 breaks\n## Nit: a.py:2 one\n")
        skeleton = findings.skeleton(parsed)
        with self.assertRaises(findings.FindingsError):
            findings.answers(parsed, skeleton)
        answered = skeleton.replace("breaks\nAnswer:", "breaks\nAnswer: wrong — the caller checks it").replace(
            "one\nAnswer:", "one\nAnswer: fixed"
        )
        done = findings.answers(parsed, answered)
        self.assertEqual([(a.answer, a.reason) for a in done], [("wrong", "the caller checks it"), ("fixed", "")])
        for bad in ("wrong", "noted"):  # a reason missing, an answer its label doesn't take
            with self.assertRaises(findings.FindingsError):
                findings.answers(parsed, skeleton.replace("breaks\nAnswer:", f"breaks\nAnswer: {bad}"))


class Pass(unittest.TestCase):
    """prepare, take and record in a throwaway repository: a bare origin with dev, and a branch's worktree."""

    def setUp(self):
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
        (self.root / "backend").mkdir()
        (self.root / "backend" / "thing.py").write_text("X = 1\n")
        self.commit("thing")
        self.git(self.root, "push", "--quiet", "-u", "origin", "feat/thing")
        self.body = "## Summary\nA thing.\n\n## Why\nIt was missing.\n\n## Review\nUnder review.\n"
        patcher = mock.patch.object(review, "gh", self.fake_gh)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.review = review.Review(self.root)
        self.review.folder.mkdir(parents=True)
        (self.review.folder / "decisions.md").write_text("Approved: the thing.\n")
        self.addCleanup(lambda: shutil.rmtree(self.review.checkout(1), ignore_errors=True))

    def git(self, cwd: Path, *args: str) -> str:
        done = subprocess.run(["git", *ISOLATED, *args], cwd=cwd, capture_output=True, text=True)
        if done.returncode:
            raise AssertionError(f"git {' '.join(args)}: {done.stderr}")
        return done.stdout

    def commit(self, message: str) -> None:
        self.git(self.root, "add", "-A")
        self.git(self.root, "commit", "--quiet", "-m", message)

    def fake_gh(self, _root, *args: str) -> str:
        if args[:2] == ("pr", "view"):
            return json.dumps({"title": "feat(thing): a thing", "body": self.body})
        if args[:2] == ("pr", "edit"):
            self.body = Path(args[args.index("--body-file") + 1]).read_text()
            return ""
        raise AssertionError(args)

    def write_findings(self, n: int, text: str) -> None:
        (self.review.pass_folder(n) / "findings.md").write_text(text)

    def test_a_pass_from_prepare_to_record(self):
        said = self.review.prepare(1)
        self.assertIn("tier standard", said)
        brief = (self.review.pass_folder(1) / "brief.md").read_text()
        self.assertNotRegex(brief, r"\{\{\w+\}\}")
        head = self.git(self.root, "rev-parse", "HEAD").strip()
        self.assertIn(head, brief)
        self.assertIn("> A thing.", brief)
        checkout = self.review.checkout(1)
        self.assertEqual(self.git(checkout, "rev-parse", "HEAD").strip(), head, "pinned to the pushed head")
        self.write_findings(1, "## Important: backend/thing.py:1 X is wrong\nhow\n## Nit: backend/thing.py:1 name\n")
        self.review.take(1)
        self.assertFalse(checkout.exists(), "the reviewers' checkout goes")
        answers = self.review.pass_folder(1) / "answers.md"
        with self.assertRaises(findings.FindingsError):
            self.review.record(1, "gpt-6.2-sol")
        answers.write_text(
            answers.read_text()
            .replace("wrong\nAnswer:", "wrong\nAnswer: fixed")
            .replace("name\nAnswer:", "name\nAnswer: declined — the name matches its caller's")
        )
        (self.root / "backend" / "thing.py").write_text("X = 2\n")
        self.commit("fix")
        self.git(self.root, "push", "--quiet")
        said = self.review.record(1, "gpt-6.2-sol")
        self.assertIn("pass 2", said)
        self.assertIn("Tier standard · pass 1 (gpt-6.2-sol): 1 Important fixed, 1 Nit declined.", self.body)
        self.assertIn("the name matches its caller's", self.body)
        self.assertTrue(self.body.startswith("## Summary\nA thing."), "the rest of the body stays")
        self.assertEqual(self.review.status().splitlines()[-1], "Next: pass 2")

        self.review.prepare(2)
        brief = (self.review.pass_folder(2) / "brief.md").read_text()
        self.assertIn(f"git diff {head}..", brief)
        self.assertIn("what changed since pass 1", brief)
        self.assertIn(str(self.review.pass_folder(1)), brief, "earlier passes' findings")
        shutil.rmtree(self.review.checkout(2), ignore_errors=True)

    def test_prepare_refuses_what_it_cannot_pin(self):
        (self.review.folder / "decisions.md").unlink()
        with self.assertRaisesRegex(review.ReviewError, "decisions.md is missing"):
            self.review.prepare(1)
        (self.review.folder / "decisions.md").write_text("ok\n")
        (self.root / "backend" / "thing.py").write_text("X = 3\n")
        with self.assertRaisesRegex(review.ReviewError, "uncommitted"):
            self.review.prepare(1)
        self.commit("more")
        with self.assertRaisesRegex(review.ReviewError, "not pushed"):
            self.review.prepare(1)
        with self.assertRaisesRegex(review.ReviewError, "stops after pass 3"):
            self.review.prepare(4)

    def test_a_later_pass_of_documentation_alone_is_not_needed(self):
        self.review.prepare(1)
        self.write_findings(1, "## Important: backend/thing.py:1 X\nhow\n")
        self.review.take(1)
        (self.review.pass_folder(1) / "answers.md").write_text("## Important: backend/thing.py:1 X\nAnswer: fixed\n")
        self.review.record(1, "gpt-6.2-sol")
        (self.root / "README.md").write_text("# more\n")
        self.commit("docs")
        self.git(self.root, "push", "--quiet")
        with self.assertRaisesRegex(review.ReviewError, "documentation alone"):
            self.review.prepare(2)


class Fill(unittest.TestCase):
    def test_a_value_keeps_its_own_braces_and_an_unknown_key_is_refused(self):
        self.assertEqual(review.fill("a {{x}} b", {"x": "{{y}}"}), "a {{y}} b")
        with self.assertRaises(review.ReviewError):
            review.fill("{{missing}}", {})

    def test_the_review_section_is_replaced_and_the_rest_kept(self):
        body = "## Summary\nS\n\n## Review\nUnder review.\n\n## Notes\nN\n"
        new = review.replace_section(body, "Review", "Tier light · not reviewed")
        self.assertEqual(re.findall(r"(?m)^## \w+", new), ["## Summary", "## Review", "## Notes"])
        self.assertIn("## Review\nTier light · not reviewed\n", new)
        self.assertIn("## Notes\nN", new)


if __name__ == "__main__":
    unittest.main()
