"""land's review depth: one round, a second for a [land] second_round file, the round after a high finding.

Run alone: python -m unittest tests.retrodev.test_land_depth
"""

import json
import tomllib
import unittest

from retrodev.review import records

from tests.retrodev.fixture import git, parallel
from tests.retrodev.landing import FINDING, GREEN, PR, TITLE, LandCase, reply

load_tests = parallel

ROOT = (".git", "retrodev", "reviews")
PENDING = [dict(GREEN[0], state="IN_PROGRESS", bucket="pending")]


def rated(sid: str, *severities: str) -> str:
    """A reviewer's reply with one finding of each severity."""
    found = [dict(FINDING, severity=severity) for severity in severities]
    body = {"verdict": "findings", "findings": found, "checked": ["core.py"]}
    return f"Session: {sid}\n{json.dumps(body)}\nsession_id: {sid}\n"


class Depth(LandCase):
    def record(self) -> dict:
        return records.load(self.main.joinpath(*ROOT), 12)

    def brief(self) -> str:
        return (self.hermes.calls[-1]["cwd"] / "review" / "brief.md").read_text()

    def fix(self, tree, round_no: int, count: int = 1, text: str = "# Two\n") -> str:
        """The fixes of a round: a commit, pushed with a passing check, and an answer to each finding."""
        self.commit(tree, "docs/value.md", text, "Fix the findings")
        head = self.publish(tree)
        for index in range(count):
            self.assertEqual(self.run_cli("answer", PR, str(round_no), str(index), "Fixed: docs/value.md")[0], 0)
        return head

    def test_an_ordinary_change_merges_on_round_one_fixes_without_a_second_reviewer(self):
        tree = self.open_pr()
        self.reviewer("OK\n", reply("s1", findings=2))
        code, data = self.land()
        self.assertEqual((code, data["action"], data["round"], data["last_round"]), (1, "fix", 1, True), data)
        self.assertIn("ROUND 1 of 1 (the last)", self.brief())
        self.assertIn("give each its true severity", self.brief())
        head = self.fix(tree, 1, count=2)
        self.hermes.calls.clear()
        code, data = self.land()
        self.assertEqual((code, data["review_action"], data["review_depth"]["rounds"]), (0, "fix-then-merge", 1), data)
        self.assertEqual(self.hermes.calls, [], "no second round, not even a probe")
        self.assertEqual(self.merges()[0][self.merges()[0].index("--match-head-commit") + 1], head)
        rec = self.record()
        self.assertEqual((rec["accepted"]["head"], rec["accepted"]["round"]), (head, 1))
        self.assertIn("Review depth: one round", (self.main / "notes" / "reviews" / "pr12.md").read_text())

    def test_a_second_round_file_gets_round_two_which_reviews_the_fixes(self):
        name = self.second_round_name()
        tree = self.open_pr(change=lambda t: self.commit(t, name, "export const probe = 1\n", TITLE))
        self.reviewer("OK\n", reply("s1", findings=1))
        code, data = self.land()
        self.assertEqual((code, data["action"], data["last_round"]), (1, "fix", False), data)
        self.assertIn("ROUND 1 of 2.", self.brief())
        self.assertEqual(self.record()["depth"]["rounds"], 2)
        self.assertIn(name, self.record()["depth"]["why"])
        self.fix(tree, 1)
        self.reviewer("OK\n", reply("s2", findings=1))
        code, data = self.land()
        self.assertEqual((code, data["action"], data["round"], data["last_round"]), (1, "fix", 2, True), data)
        self.assertIn("ROUND 2 of 2 (the last)", self.brief())
        self.assertIn("round1-fixes.patch", self.brief())
        call = self.hermes.calls[-1]
        self.assertTrue(str(call["cmd"][call["cmd"].index("--query-file") + 1]).startswith(str(call["cwd"])))
        answers = (call["cwd"] / "review" / "round1-findings-and-answers.txt").read_text()
        self.assertIn("Fixed: docs/value.md", answers)
        head = self.fix(tree, 2, text="# Three\n")
        self.hermes.calls.clear()
        code, data = self.land()
        self.assertEqual((code, data["review_action"], self.hermes.calls), (0, "fix-then-merge", []), data)
        self.assertEqual((self.record()["accepted"]["head"], self.record()["accepted"]["round"]), (head, 2))

    def test_a_high_finding_adds_the_round_that_reviews_its_fix(self):
        tree = self.open_pr()
        self.reviewer("OK\n", rated("s1", "medium", "high"))
        code, data = self.land()
        self.assertEqual((code, data["action"], data["last_round"]), (1, "fix", False), data)
        self.assertEqual(data["review_depth"]["rounds"], 2, "the answer names the depth after the round")
        self.assertEqual(self.record()["depth"]["rounds"], 2)
        self.assertIn("round 1 had a high-severity finding", self.record()["depth"]["why"])
        self.fix(tree, 1, count=2)
        self.reviewer("OK\n", reply("s2"))
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual([entry["round"] for entry in records.valid_rounds(self.record())], [1, 2])

    def test_low_findings_deferred_without_a_push_merge(self):
        self.open_pr()
        self.reviewer("OK\n", rated("s1", "low", "low"))
        self.assertEqual(self.land()[0], 1)
        self.assertEqual(self.run_cli("answer", PR, "1", "--all", "Deferred: notes/friction.md")[0], 0)
        self.hermes.calls.clear()
        code, data = self.land()
        self.assertEqual((code, data["review_action"], self.hermes.calls), (0, "fix-then-merge", []), data)

    def test_findings_above_low_that_are_only_disputed_get_a_round_to_judge_the_answers(self):
        self.open_pr()
        self.reviewer("OK\n", rated("s1", "low", "medium"))
        self.assertEqual(self.land()[0], 1)
        self.assertEqual(self.run_cli("answer", PR, "1", "--all", "Wrong: the test exists, see its output")[0], 0)
        code, out = self.land("--dry-run", as_json=False)
        self.assertIn("would: probe the reviewer, then run review round 2", out)
        self.reviewer("OK\n", reply("s2"))
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual([entry["round"] for entry in records.valid_rounds(self.record())], [1, 2])
        self.assertIn("ROUND 2 of 2 (the last)", self.brief())

    def test_a_push_after_the_accepted_head_is_reviewed_instead_of_stopping_for_the_owner(self):
        tree = self.open_pr()
        self.reviewer("OK\n", reply("s1", findings=1))
        self.assertEqual(self.land()[0], 1)
        accepted = self.fix(tree, 1)
        self.ci(PENDING, code=8)
        code, data = self.land()
        self.assertEqual((code, data["review_action"]), (2, "fix-then-merge"), data)
        self.assertEqual(self.record()["accepted"]["head"], accepted)
        self.commit(tree, "docs/value.md", "# Two, fixed for CI\n", "Fix CI")
        head = self.publish(tree)
        self.ci(GREEN)
        self.reviewer("OK\n", reply("s2"))
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual([entry["sha"] for entry in records.valid_rounds(self.record())][-1], head)

    def test_a_dry_run_says_the_depth_and_records_nothing(self):
        self.open_pr()
        code, out = self.land("--dry-run", as_json=False)
        self.assertEqual(code, 0, out)
        self.assertIn("review depth: one round", out)
        code, data = self.land("--dry-run")
        self.assertEqual((code, data["review_depth"]["rounds"]), (0, 1), data)
        self.assertNotIn("depth", self.record())

    def second_round_name(self) -> str:
        policy = tomllib.loads((self.main / "tools" / "retrodev" / "policy.toml").read_text(encoding="utf-8"))
        return policy["land"]["second_round"][0].replace("*", "probe.js")

    def test_a_second_round_file_first_added_by_the_round_two_fixes_is_reviewed(self):
        tree = self.open_pr()
        self.reviewer("OK\n", reply("s1", findings=1))
        self.assertEqual(self.land()[0], 1)
        self.assertEqual(self.run_cli("answer", PR, "1", "0", "Wrong: the test exists, see its output")[0], 0)
        self.reviewer("OK\n", reply("s2", findings=1))  # the judging round finds something else
        code, data = self.land()
        self.assertEqual((code, data["round"], data["last_round"]), (1, 2, True), data)
        name = self.second_round_name()
        self.commit(tree, name, "export const probe = 1\n", "Fix round 2, and touch a second-round file")
        head = self.publish(tree)
        self.assertEqual(self.run_cli("answer", PR, "2", "0", "Fixed: the test")[0], 0)
        code, out = self.land("--dry-run", as_json=False)
        self.assertIn(f"another round: it now changes {name}", out)
        self.assertIn("would: probe the reviewer, then run review round 3", out)
        self.reviewer("OK\n", reply("s3"))
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual(records.valid_rounds(self.record())[-1]["sha"], head, "round 3 saw the new file")

    def test_a_push_that_changes_nothing_of_the_pull_request_is_no_fix_for_a_disputed_finding(self):
        tree = self.open_pr()
        self.reviewer("OK\n", reply("s1", findings=1))
        self.assertEqual(self.land()[0], 1)
        self.assertEqual(self.run_cli("answer", PR, "1", "0", "Wrong: the test exists, see its output")[0], 0)
        git(tree, "commit", "-q", "--allow-empty", "-m", "Nothing")
        self.publish(tree)
        code, out = self.land("--dry-run", as_json=False)
        self.assertIn("would: probe the reviewer, then run review round 2", out)
        self.on_dev("docs/other.md", "# Other\n")  # a clean merge of dev changes the tree, not the patch
        self.assertEqual(self.run_cli("sync", cwd=tree)[0], 0)
        self.publish(tree)
        self.assertTrue(self.land("--dry-run")[1]["review_depth"]["same_patch"])
        self.reviewer("OK\n", reply("s2"))
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual([entry["round"] for entry in records.valid_rounds(self.record())], [1, 2])


if __name__ == "__main__":
    unittest.main()
