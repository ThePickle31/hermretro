"""land and dev moving under a pull request: a merge conflict points to sync, and a head that only merged dev after
its review keeps that review (a small conflict resolution is recorded, a large one is reviewed).

Run alone: python -m unittest tests.retrodev.test_land_sync
"""

import json
import unittest

from retrodev.review import records

from tests.retrodev.fixture import git, parallel
from tests.retrodev.landing import GREEN, PR, LandCase, reply

load_tests = parallel
PENDING = [{"name": "All checks pass", "state": "PENDING", "bucket": "pending", "link": ""}]
CONFLICT = "GraphQL: Pull Request has merge conflicts (mergePullRequest)"


class Conflicts(LandCase):
    def assert_points_to_sync(self, data, tree):
        self.assertEqual(data["action"], "sync", data)
        fix = data["error"]["fix"]
        self.assertIn(f"cd {tree} && python tools/retrodev sync", fix)
        self.assertIn("python tools/retrodev check", fix)
        self.assertIn("python tools/retrodev ship --title 'Change the value'", fix)
        self.assertIn(f"cd {self.main} && python tools/retrodev land {PR}", fix)

    def test_a_merge_refused_for_conflicts_says_sync_check_ship_land(self):
        tree = self.open_pr()
        self.gh.effects.clear()
        self.gh.answers[("pr", "merge", PR)] = (1, "", CONFLICT)
        self.reviewer("OK\n", reply("s1"))
        code, data = self.land()
        self.assertEqual(code, 1, data)
        self.assert_points_to_sync(data, tree)

    def test_a_conflicting_pull_request_is_reported_before_the_review_and_ci(self):
        tree = self.open_pr()
        self.info["mergeable"] = "CONFLICTING"
        self.answer_view()
        code, data = self.land()
        self.assertEqual(code, 1, data)
        self.assert_points_to_sync(data, tree)
        self.assertEqual((self.hermes.calls, self.merges(), self.gh.called("pr", "checks")), ([], [], []))

    def test_mergeable_unknown_keeps_going(self):
        self.open_pr()
        self.info["mergeable"] = "UNKNOWN"
        self.answer_view()
        self.reviewer("OK\n", reply("s1"))
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual(len(self.merges()), 1)


class DevMergedAfterReview(LandCase):
    def reviewed_then_synced(self, resolve=None):
        """A clean round on #12 (CI still running), then dev moves and the branch syncs. ``resolve(tree)`` settles
        a conflict on core.py (dev changes it too); without it dev changes another file."""
        tree = self.open_pr()
        self.ci(PENDING, code=8)
        self.reviewer("OK\n", reply("s1"))
        code, data = self.land()
        self.assertEqual((code, data["action"]), (2, "wait-ci"), data)
        reviewed = self.info["headRefOid"]
        if resolve is None:
            self.on_dev("docs/other.md", "# Other\n")
            code, out = self.run_cli("sync", cwd=tree)
            self.assertEqual(code, 0, out)
        else:
            self.on_dev("backend/library/core.py", "VALUE = 3\n")
            code, out = self.run_cli("sync", cwd=tree)
            self.assertEqual(code, 1, out)
            resolve(tree)
            code, out = self.run_cli("sync", cwd=tree)
            self.assertEqual(code, 0, out)
        head = self.publish(tree)
        self.assertNotEqual(head, reviewed)
        self.ci(GREEN)
        self.hermes.calls.clear()
        return tree, reviewed, head

    def review_record(self):
        return records.load(self.main / ".git" / "retrodev" / "reviews", 12)

    def merged_at(self) -> str:
        merge = self.merges()[-1]
        return merge[merge.index("--match-head-commit") + 1]

    def test_a_clean_merge_of_dev_keeps_the_clean_review(self):
        _tree, reviewed, head = self.reviewed_then_synced()
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual(self.hermes.calls, [], "no new round, not even a probe")
        self.assertEqual(self.merged_at(), head)
        carried = self.review_record()["carried"]
        self.assertEqual([(c["head"], c["reviewed"], c["resolution_lines"]) for c in carried], [(head, reviewed, 0)])

    def test_a_small_resolution_merges_and_is_recorded_for_the_summary(self):
        def resolve(tree):
            (tree / "backend" / "library" / "core.py").write_text("VALUE = 23\n")
            git(tree, "add", "backend/library/core.py")

        _tree, _reviewed, head = self.reviewed_then_synced(resolve)
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual(self.hermes.calls, [])
        self.assertEqual(self.merged_at(), head)
        lines = self.review_record()["carried"][-1]["resolution_lines"]
        self.assertTrue(0 < lines <= 20, lines)
        code, out = self.run_cli("summary", PR)
        self.assertIn(f"merge resolution, not reviewed: {lines} lines", out)

    def test_a_large_resolution_needs_a_new_round(self):
        def resolve(tree):
            extra = "".join(f"EXTRA_{n} = {n}\n" for n in range(30))
            (tree / "backend" / "library" / "core.py").write_text("VALUE = 23\n" + extra)
            git(tree, "add", "backend/library/core.py")

        _tree, _reviewed, head = self.reviewed_then_synced(resolve)
        self.reviewer("OK\n", reply("s2"))
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual(len(self.hermes.calls), 2, "a probe, then round 2 on the merged head")
        self.assertEqual([r["sha"] for r in records.valid_rounds(self.review_record())][-1], head)
        self.assertNotIn("carried", self.review_record())

    def test_the_head_accepted_after_round_three_carries_over_a_dev_merge(self):
        tree = self.open_pr()
        root = self.main / ".git" / "retrodev" / "reviews"
        for n in (1, 2):
            entry = {"round": n, "sha": self.info["headRefOid"], "result": json.loads(reply("x", 1).splitlines()[1])}
            records.add_round(root, 12, entry)
            records.answer(12, n, 0, "fixed", repo=self.main, root=root, notes=self.base / "notes")
        self.ci(PENDING, code=8)
        self.reviewer("OK\n", reply("s3", findings=1))
        self.assertEqual(self.land()[0], 1)
        self.commit(tree, "docs/value.md", "# Two\n", "Document the value")
        self.publish(tree)
        self.run_cli("answer", PR, "3", "0", "Fixed: docs/value.md")
        code, data = self.land()
        self.assertEqual((code, data["review_action"]), (2, "fix-then-merge"), data)
        self.on_dev("docs/other.md", "# Other\n")
        self.assertEqual(self.run_cli("sync", cwd=tree)[0], 0)
        head = self.publish(tree)
        self.ci(GREEN)
        self.hermes.calls.clear()
        code, data = self.land()
        self.assertEqual((code, data["review_action"]), (0, "fix-then-merge"), data)
        self.assertEqual((self.hermes.calls, self.merged_at()), ([], head))

    def test_a_commit_of_its_own_after_the_review_is_reviewed_even_with_a_sync(self):
        tree = self.open_pr()
        self.ci(PENDING, code=8)
        self.reviewer("OK\n", reply("s1"))
        self.assertEqual(self.land()[0], 2)
        self.commit(tree, "backend/library/core.py", "VALUE = 4\n", "Change it again")
        self.on_dev("docs/other.md", "# Other\n")
        self.assertEqual(self.run_cli("sync", cwd=tree)[0], 0)
        self.publish(tree)
        self.ci(GREEN)
        self.hermes.calls.clear()
        self.reviewer("OK\n", reply("s2"))
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual(len(self.hermes.calls), 2, "a probe, then round 2")


if __name__ == "__main__":
    unittest.main()
