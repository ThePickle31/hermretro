"""land's CI and skip paths: the reviewer down, --no-review, CI failing, CI still running; status's next steps.

Run alone: python -m unittest tests.retrodev.test_land_ci
"""

import unittest

from retrodev import ci, status
from retrodev.review import records

from tests.retrodev.fixture import parallel
from tests.retrodev.landing import GREEN, PR, LandCase, reply

load_tests = parallel
RED = [
    {
        "name": "All checks pass",
        "state": "FAILURE",
        "bucket": "fail",
        "link": "https://github.com/o/r/actions/runs/77/job/1",
    },
    {
        "name": "unit (macos)",
        "state": "FAILURE",
        "bucket": "fail",
        "link": "https://github.com/o/r/actions/runs/77/job/3",
    },
    {"name": "lint", "state": "SUCCESS", "bucket": "pass", "link": ""},
]


class Skips(LandCase):
    def test_reviewer_down_skips_the_reviews_and_merges_on_green(self):
        self.open_pr()
        self.hermes.returncode = 1
        self.reviewer("Error: 429 Too Many Requests: rate limit reached\n")
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual(len(self.hermes.calls), 1, "only the probe")
        rec = records.load(self.main / ".git" / "retrodev" / "reviews", 12)
        self.assertIn("429", rec["skipped"]["reason"])
        self.assertEqual(len(self.merges()), 1)

    def test_no_review_profile_skips_without_starting_hermes(self):
        self.open_pr()
        self.run_cli("config", "set", "review_profile", "")
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual(self.hermes.calls, [])
        rec = records.load(self.main / ".git" / "retrodev" / "reviews", 12)
        self.assertEqual(rec["skipped"]["reason"], "no reviewer profile configured")

    def test_no_review_is_recorded_as_the_reason(self):
        self.open_pr()
        code, data = self.land("--no-review")
        self.assertEqual(code, 0, data)
        self.assertEqual(self.hermes.calls, [])
        rec = records.load(self.main / ".git" / "retrodev" / "reviews", 12)
        self.assertIn("--no-review", rec["skipped"]["reason"])


class CI(LandCase):
    def test_failing_ci_names_the_jobs_and_how_to_read_them_and_never_merges(self):
        self.open_pr()
        self.ci(RED, code=1)
        self.reviewer("OK\n", reply("s1"))
        code, data = self.land()
        self.assertEqual(code, 1, data)
        self.assertEqual(data["action"], "fix CI")
        self.assertEqual([job["name"] for job in data["failing"]], ["All checks pass", "unit (macos)"])
        self.assertIn("gh run view 77 --log-failed", data["error"]["fix"])
        self.assertEqual(self.merges(), [])
        # Run again once CI is green: the clean round at this head is not run again.
        self.ci(GREEN)
        self.hermes.calls.clear()
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual(self.hermes.calls, [])
        self.assertEqual(len(self.merges()), 1)

    def test_pending_ci_past_the_timeout_is_still_waiting(self):
        self.open_pr()
        self.ci([dict(GREEN[0], bucket="pending", state="IN_PROGRESS")] + GREEN[1:], code=8)
        self.reviewer("OK\n", reply("s1"))
        code, data = self.land()
        self.assertEqual(code, 2, data)
        self.assertEqual((data["action"], data["waiting"]), ("wait-ci", ["All checks pass"]))
        self.assertIn("land 12 again later", data["error"]["fix"])
        self.assertEqual(self.merges(), [])

    def test_a_head_that_moves_while_waiting_stops(self):
        self.open_pr()
        self.reviewer("OK\n", reply("s1"))
        real = self.gh.answers[("pr", "checks", PR)]

        def moved(_args):
            self.info["headRefOid"] = "f" * 40
            self.answer_view()

        self.gh.effects[("pr", "view", PR, "--json", "headRefOid,statusCheckRollup")] = moved
        code, data = self.land()
        self.assertEqual(code, 1, data)
        self.assertIn("moved", data["error"]["message"])
        self.assertEqual((self.merges(), self.gh.answers[("pr", "checks", PR)]), ([], real))


class Classify(unittest.TestCase):
    def test_required_jobs_must_be_reported_and_ignored_ones_never_count(self):
        need = ["All checks pass"]
        self.assertEqual(ci.classify([], need, [])[0], "pending")
        self.assertEqual(ci.classify(GREEN[1:], need, [])[2], ["All checks pass (not reported yet)"])
        self.assertEqual(ci.classify(GREEN, need, [])[0], "green")
        nightly = {"name": "nightly mac", "bucket": "pending"}
        self.assertEqual(ci.classify(GREEN + [nightly], need, ["nightly mac"])[0], "green")
        self.assertEqual(ci.classify(GREEN + [nightly], need, [])[0], "pending")
        self.assertEqual(ci.classify(RED, need, [])[0], "failing")

    def test_the_rollup_reads_like_gh_pr_checks(self):
        rollup = [
            {"name": "a", "status": "COMPLETED", "conclusion": "SUCCESS"},
            {"name": "b", "status": "IN_PROGRESS", "conclusion": ""},
            {"name": "c", "status": "COMPLETED", "conclusion": "SKIPPED"},
            {"context": "d", "state": "FAILURE"},
        ]
        self.assertEqual([j["bucket"] for j in ci.from_rollup(rollup)], ["pass", "pending", "skipping", "fail"])


class NextStep(unittest.TestCase):
    BASE = {"plan_approved": True, "checks_passed": True, "pr": 12, "head": "a", "pushed": "a", "ci": "passing"}

    def test_approve_land_and_answer(self):
        self.assertIn("approve 12 --words", status.next_step(dict(self.BASE)))
        self.assertIn("land 12", status.next_step(dict(self.BASE, approved={"words": "go"})))
        line = status.next_step(dict(self.BASE, approved={"words": "go"}, unanswered=[[1, 0], [1, 1]]))
        self.assertIn("answer 12 1 <index>", line)
        self.assertIn("2 open", line)


if __name__ == "__main__":
    unittest.main()
