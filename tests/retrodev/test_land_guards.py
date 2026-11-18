"""land's guards: an approval belongs to one pull request, the base is rechecked up to the merge, a review counts
only for the head it saw (round 3 accepts one head), and the steps after the merge resume.

Run alone: python -m unittest tests.retrodev.test_land_guards
"""

import json
import unittest

from retrodev import reviews, state
from retrodev.review import records

from tests.retrodev.fixture import git, parallel
from tests.retrodev.landing import BRANCH, GREEN, PR, LandCase, reply
from tests.retrodev.test_land_ci import RED

load_tests = parallel
ROOT = (".git", "retrodev", "reviews")


class Approval(LandCase):
    def test_a_replacement_pull_request_needs_its_own_approval(self):
        self.open_pr()  # #12, approved
        self.info.update(state="CLOSED")
        self.answer_view()
        # The same branch ships a replacement, #13 (ship records the new number in the branch record).
        self.info = dict(self.info, number=13, state="OPEN", url="https://github.com/o/r/pull/13")
        self.answer_view = lambda: self.gh.answers.__setitem__(("pr", "view", "13"), (0, json.dumps(self.info), ""))
        self.answer_view()
        for verb in ("checks", "merge", "ready"):
            self.gh.answers[("pr", verb, "13")] = self.gh.answers[("pr", verb, PR)]
        self.gh.effects[("pr", "merge", "13")] = self.squash
        record = state.load_branch(self.main, BRANCH)
        record["pr"] = {"number": 13, "url": self.info["url"], "head": self.info["headRefOid"]}
        state.save_branch(self.main, record)

        self.reviewer("OK\n", reply("s1"))
        code, data = self.run_cli("land", "13", "--ci-timeout", "0", as_json=True)
        self.assertEqual(code, 3, data)
        self.assertEqual([g["name"] for g in data["gates"] if not g["ok"]], ["owner approved"])
        self.assertIn("approve 13 --words", data["error"]["fix"])
        self.assertEqual((self.hermes.calls, self.merges()), ([], []))

        self.assertEqual(self.run_cli("approve", "13", "--words", "this one too")[0], 0)
        code, data = self.run_cli("land", "13", "--ci-timeout", "0", as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual([m[2] for m in self.merges()], ["13"])
        rec = records.load(self.main.joinpath(*ROOT), 13)
        self.assertEqual((rec["approval"]["pr"], rec["approval"]["words"]), (13, "this one too"))

    def test_ship_recording_another_pull_request_moves_the_approval_to_the_history(self):
        record = {"branch": BRANCH, "pr": {"number": 12}, "approval": {"pr": 12, "words": "go", "at": "t"}}
        reviews.record_pr(record, 12, "u12", "a", "T")  # a review-fix push to the same pull request keeps it
        self.assertEqual(record["approval"]["words"], "go")
        reviews.record_pr(record, 13, "u13", "b", "T")
        self.assertNotIn("approval", record)
        self.assertEqual([a["pr"] for a in record["approvals"]], [12])
        self.assertEqual(record["pr"]["number"], 13)


class Base(LandCase):
    def test_a_retarget_while_ci_runs_is_never_merged(self):
        self.open_pr()
        self.reviewer("OK\n", reply("s1"))

        def retarget(_args):
            self.info["baseRefName"] = "main"  # the head is unchanged: --match-head-commit would not stop it
            self.answer_view()

        self.gh.effects[("pr", "checks", PR)] = retarget
        code, data = self.land()
        self.assertEqual(code, 1, data)
        self.assertIn("goes into main", data["error"]["message"])
        self.assertIn("--base dev", data["error"]["fix"])
        self.assertEqual(self.merges(), [])

    def stopped_on_a_poll(self, change: dict, words: str) -> None:
        self.open_pr()
        self.ci([dict(GREEN[0], bucket="pending", state="IN_PROGRESS")] + GREEN[1:], code=8)
        self.reviewer("OK\n", reply("s1"))

        def later(_args):
            self.info.update(change)
            self.answer_view()

        self.gh.effects[("pr", "checks", PR)] = later
        ticks = iter(range(0, 10**6, 30))
        self.fakes["clock"] = lambda: next(ticks)
        code, data = self.land("--ci-timeout", "600")
        self.assertEqual(code, 1, data)
        self.assertIn(words, data["error"]["message"])
        self.assertEqual(len(self.gh.called("pr", "checks")), 1, "stopped on the next poll")
        self.assertEqual(self.merges(), [])

    def test_a_retarget_seen_on_a_ci_poll_stops_the_wait(self):
        self.stopped_on_a_poll({"baseRefName": "main"}, "goes into main")

    def test_a_close_seen_on_a_ci_poll_stops_the_wait(self):
        self.stopped_on_a_poll({"state": "CLOSED"}, "is closed")


class RoundThree(LandCase):
    def rounds(self, *verdicts: str) -> None:
        root = self.main.joinpath(*ROOT)
        for n, verdict in enumerate(verdicts, 1):
            body = json.loads(reply("x", 0 if verdict == "clean" else 1).splitlines()[1])
            records.add_round(root, 12, {"round": n, "sha": self.info["headRefOid"], "result": body, "void": False})
            if verdict != "clean":
                records.answer(12, n, 0, "fixed", repo=self.main, root=root, notes=self.base / "notes")

    def test_a_push_after_a_clean_round_three_needs_the_owner(self):
        tree = self.open_pr()
        self.rounds("findings", "findings", "clean")
        self.commit(tree, "docs/value.md", "# Two\n", "Unreviewed change")
        self.publish(tree)
        code, data = self.land()
        self.assertEqual(code, 3, data)
        self.assertEqual(data["action"], "reviews-exhausted")
        self.assertIn("--no-review", data["error"]["fix"])
        self.assertEqual((self.hermes.calls, self.merges()), ([], []))
        code, data = self.land("--no-review")  # the owner's call
        self.assertEqual(code, 0, data)
        self.assertEqual(len(self.merges()), 1)

    def test_round_three_fixes_are_accepted_once_and_a_later_push_needs_the_owner(self):
        tree = self.open_pr()
        self.rounds("findings", "findings")
        self.reviewer("OK\n", reply("s3", findings=1))
        self.assertEqual(self.land()[0], 1)
        self.commit(tree, "docs/value.md", "# Two\n", "Fix round 3")
        fixed = self.publish(tree)
        self.run_cli("answer", PR, "3", "0", "Fixed: the test")
        self.ci(RED, code=1)
        code, data = self.land()
        self.assertEqual((code, data["action"]), (1, "fix CI"), data)
        self.assertEqual(records.load(self.main.joinpath(*ROOT), 12)["accepted"]["head"], fixed)
        self.commit(tree, "docs/value.md", "# Two, fixed for CI\n", "Fix CI")
        self.publish(tree)
        self.ci(GREEN)
        self.hermes.calls.clear()
        code, data = self.land()
        self.assertEqual(code, 3, data)
        self.assertEqual(data["action"], "reviews-exhausted")
        self.assertEqual((self.hermes.calls, self.merges()), ([], []))


class Resume(LandCase):
    def test_a_failed_pull_after_the_merge_is_finished_by_the_next_land(self):
        tree = self.open_pr()
        self.reviewer("OK\n", reply("s1"))
        self.commit(self.main, "local.txt", "only here\n", "A local commit: dev cannot fast-forward")
        code, data = self.land()
        self.assertNotEqual(code, 0, data)
        self.assertEqual(len(self.merges()), 1)
        self.assertIn("land 12", data["error"]["fix"])
        self.assertTrue(tree.exists(), "nothing tidied before the main checkout is updated")

        # A dry run reports the steps left and does none of them.
        before = records.load(self.main.joinpath(*ROOT), 12)["landing"]
        code, data = self.land("--dry-run")
        self.assertEqual((code, data["action"], data["left"]), (0, "finish", ["pulled", "gc"]), data)
        self.assertTrue(tree.exists())
        self.assertEqual(records.load(self.main.joinpath(*ROOT), 12)["landing"], before)
        self.assertEqual(git(self.main, "log", "-1", "--format=%s").strip(), "A local commit: dev cannot fast-forward")

        git(self.main, "reset", "-q", "--hard", "HEAD~1")
        self.hermes.calls.clear()
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual(len(self.merges()), 1, "never merged again")
        self.assertEqual(self.hermes.calls, [])
        self.assertEqual(git(self.main, "log", "-1", "--format=%s").strip(), "Change the value (#12)")
        self.assertFalse(tree.exists())
        landing = records.load(self.main.joinpath(*ROOT), 12)["landing"]
        self.assertEqual((landing["pulled"], landing["gc"]), (True, True))
        code, out = self.land(as_json=False)  # finished: nothing left to do
        self.assertEqual(code, 0, out)
        self.assertIn("already merged", out)


class Summary(LandCase):
    def test_a_file_moved_out_of_a_restart_area_still_needs_the_restart(self):
        self.on_dev("skills/demo/SKILL.md", "# Demo\nA skill the gateway loads.\n")
        git(self.main, "fetch", "-q", "origin")

        def move(tree):  # the pull request's only change: a skill moved into docs/
            git(tree, "mv", "skills/demo/SKILL.md", "docs/demo.md")
            git(tree, "commit", "-q", "-m", "Move the demo skill")

        self.open_pr(change=move)
        code, data = self.run_cli("summary", PR, as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual((data["added"], data["changed"], data["removed"]), ({}, {}, {}), data)
        self.assertEqual(data["moved"], ["skills/demo/SKILL.md -> docs/demo.md"])
        self.assertIn("gateway", data["owner"])


if __name__ == "__main__":
    unittest.main()
