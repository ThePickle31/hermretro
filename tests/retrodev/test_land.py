"""approve, land and answer: the owner's approval, the gates, the review rounds, CI on the exact head, the merge.

Run alone: python -m unittest tests.retrodev.test_land
"""

import json
import shlex
import unittest

from retrodev import state
from retrodev.review import records

from tests.retrodev.fixture import git, parallel
from tests.retrodev.landing import BRANCH, PR, LandCase, reply

load_tests = parallel


class Approve(LandCase):
    def test_approve_records_the_words_and_head_and_readies_a_draft(self):
        self.open_pr(draft=True, approve=False)
        code, data = self.run_cli("approve", PR, "--words", "  ", as_json=True)
        self.assertEqual(code, 3, data)
        self.assertIn("exact words", data["error"]["message"])
        code, data = self.run_cli("approve", PR, "--words", "go ahead", as_json=True)
        self.assertEqual(code, 0, data)
        approval = state.load_branch(self.main, BRANCH)["approval"]
        self.assertEqual((approval["words"], approval["head"]), ("go ahead", self.info["headRefOid"]))
        self.assertEqual(self.gh.called("pr", "ready"), [["pr", "ready", PR]])
        self.assertTrue(data["readied"])


class Gates(LandCase):
    def test_no_approval_needs_the_owner(self):
        self.open_pr(approve=False)
        code, data = self.land()
        self.assertEqual(code, 3, data)
        self.assertEqual([g["name"] for g in data["gates"] if not g["ok"]], ["owner approved"])
        self.assertIn("approve 12 --words", data["error"]["fix"])
        self.assertEqual((self.hermes.calls, self.merges()), ([], []))

    def test_an_unpushed_head_and_a_failed_check_are_refused_together(self):
        tree = self.open_pr()
        self.commit(tree, "backend/library/core.py", "VALUE = 3\n", "Not pushed")
        code, data = self.land()
        self.assertEqual(code, 1, data)
        failed = [g["name"] for g in data["gates"] if not g["ok"]]
        self.assertEqual(failed, ["pull request head is this branch's head", "pushed", "checks passed on this tree"])
        self.assertEqual((self.hermes.calls, self.merges()), ([], []))

    def test_a_dry_run_shows_the_gates_and_the_next_step_and_changes_nothing(self):
        self.open_pr(draft=True)
        self.gh.calls.clear()
        code, out = self.land("--dry-run", as_json=False)
        self.assertEqual(code, 0, out)
        self.assertIn("would: probe the reviewer, then run review round 1", out)
        self.assertIn("a draft: land marks it ready", out)
        self.assertEqual({tuple(c[:2]) for c in self.gh.calls}, {("pr", "view")})
        self.assertEqual(self.hermes.calls, [])


class Rounds(LandCase):
    def test_findings_stop_unanswered_block_then_answers_and_a_new_head_bring_the_merge(self):
        tree = self.open_pr()
        first = self.info["headRefOid"]
        self.reviewer("OK\n", reply("s1", findings=2))
        code, data = self.land()
        self.assertEqual(code, 1, data)
        self.assertEqual((data["action"], data["round"], len(data["findings"])), ("fix", 1, 2))
        self.assertEqual(self.merges(), [])
        self.assertEqual(len(self.hermes.calls), 2, "a probe, then the round")

        self.hermes.calls.clear()
        code, out = self.land(as_json=False)  # nothing answered yet: nothing runs
        self.assertEqual(code, 1, out)
        self.assertIn("findings not answered yet: round 1 finding 0, round 1 finding 1", out)
        self.assertEqual(self.hermes.calls, [])

        self.commit(tree, "docs/value.md", "# Two\n", "Document the value")
        second = self.publish(tree)
        self.assertEqual(self.run_cli("answer", PR, "1", "0", "Fixed in the test commit")[0], 0)
        code, out = self.run_cli("answer", PR, "1", "1", "")
        self.assertEqual(code, 1, out)
        self.assertEqual(self.run_cli("answer", PR, "1", "--all", "Fixed: docs/value.md")[0], 0)
        code, data = self.land()  # an ordinary change: round 1's fixes merge (test_land_depth has the other cases)
        self.assertEqual(code, 0, data)
        merge = self.merges()
        self.assertEqual(len(merge), 1)
        self.assertEqual(merge[0][merge[0].index("--match-head-commit") + 1], second)
        self.assertNotEqual(first, second)
        self.assertIn("--squash", merge[0])
        self.assertIn("--delete-branch", merge[0])
        self.assertEqual(merge[0][merge[0].index("--subject") + 1], "Change the value (#12)")
        rec = records.load(self.main / ".git" / "retrodev" / "reviews", 12)
        self.assertEqual([r["round"] for r in records.valid_rounds(rec)], [1])
        self.assertEqual(rec["merged"]["head"], second)
        self.assertEqual(rec["approval"]["words"], "looks good, merge it")

        # The main checkout took the merge; the finished worktree, its branch and record are gone.
        self.assertEqual(git(self.main, "log", "-1", "--format=%s").strip(), "Change the value (#12)")
        self.assertFalse(tree.exists())
        self.assertEqual(git(self.main, "branch", "--list", BRANCH), "")
        self.assertFalse(state.branch_path(self.main, BRANCH).exists())
        self.assertTrue((self.main / "notes" / "reviews" / "pr12.md").is_file())

        code, data = self.run_cli("summary", PR, as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["added"], {"docs/": ["docs/value.md"]})
        self.assertEqual(data["changed"], {"backend/library/": ["backend/library/core.py"]})
        self.assertEqual(data["removed"], {})
        self.assertEqual([(r["round"], r["findings"], r["answered"]) for r in data["reviews"]["rounds"]], [(1, 2, 2)])
        self.assertEqual(len(data["fixed"]), 2)
        self.assertEqual(data["ci"]["summary"], "passing")
        self.assertEqual(list(data["owner"]), ["gateway"])
        code, out = self.run_cli("summary", PR)
        for heading in ("Added", "Changed", "Fixed", "Removed", "Reviews:", "CI: passing", "The owner:"):
            self.assertIn(heading, out)
        self.assertIn("restarts the Hermes gateway", out)

    def test_the_fix_steps_ship_with_the_recorded_title_and_a_custom_body_path(self):
        self.open_pr()
        record = state.load_branch(self.main, BRANCH)
        custom = str(self.base / "bodies" / "my body.md")
        record["body"] = custom
        record["pr"]["title"] = "Change the value"
        state.save_branch(self.main, record)
        self.reviewer("OK\n", reply("s1", findings=1))
        code, out = self.land(as_json=False)
        self.assertEqual(code, 1, out)
        step = next(line for line in out.splitlines() if "tools/retrodev ship" in line)
        self.assertIn(shlex.join(["--title", "Change the value", "--body", custom]), step)

    def test_round_three_findings_merge_once_answered_without_a_fourth_round(self):
        tree = self.open_pr()
        root = self.main / ".git" / "retrodev" / "reviews"
        for n, sha in ((1, self.info["headRefOid"]), (2, self.info["headRefOid"])):
            entry = {"round": n, "sha": sha, "result": json.loads(reply("x", 1).splitlines()[1]), "void": False}
            records.add_round(root, 12, entry)
            records.answer(12, n, 0, "fixed", repo=self.main, root=root, notes=self.base / "notes")
        self.reviewer("OK\n", reply("s3", findings=1))
        code, data = self.land()
        self.assertEqual((code, data["action"], data["round"], data["last_round"]), (1, "fix", 3, True))
        self.commit(tree, "docs/value.md", "# Two\n", "Document the value")
        head = self.publish(tree)
        self.run_cli("answer", PR, "3", "0", "Fixed: the test")
        self.hermes.calls.clear()
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual(self.hermes.calls, [], "no 4th round, not even a probe")
        self.assertEqual(data["review_action"], "fix-then-merge")
        self.assertEqual(self.merges()[0][self.merges()[0].index("--match-head-commit") + 1], head)

    def test_a_void_round_twice_needs_the_owner(self):
        tree = self.open_pr()

        def tamper(cmd, _cwd):
            if "--query-file" in cmd:
                (tree / "stray.txt").write_text(f"written by the reviewer {len(self.hermes.calls)}\n")

        self.reviewer("OK\n", reply("s1"), reply("s2"), on_call=tamper)
        code, data = self.land()
        self.assertEqual(code, 3, data)
        self.assertEqual(data["action"], "needs-owner")
        self.assertIn("files of the pull request's worktree", data["error"]["message"])
        (tree / "stray.txt").unlink()
        self.hermes.calls.clear()
        code, data = self.land()
        self.assertEqual((code, self.hermes.calls, self.merges()), (3, [], []))

    def test_other_worktrees_changing_during_a_round_do_not_void_it(self):
        self.open_pr()
        other = self.worktree("docs/other")

        def busy(cmd, _cwd):
            (other / f"work{len(self.hermes.calls)}.md").write_text("another agent\n")

        self.reviewer("OK\n", reply("s1"), on_call=busy)
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual(len(self.merges()), 1)


if __name__ == "__main__":
    unittest.main()
