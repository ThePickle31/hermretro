"""land and dev moving under a pull request: a merge conflict points to sync, and a head that only merged dev after
its review keeps that review (a small conflict resolution is recorded, a large one is reviewed).

Run alone: python -m unittest tests.retrodev.test_land_sync
"""

import json
import unittest

from retrodev import code_lines, land_carry, state
from retrodev.review import records

from tests.retrodev.fixture import git, parallel
from tests.retrodev.landing import BRANCH, GREEN, PR, TITLE, LandCase, reply

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

    def test_the_conflict_fix_ships_with_the_recorded_title_and_body(self):
        tree = self.open_pr()
        record = state.load_branch(self.main, BRANCH)
        body = str(self.main / "notes" / "pr" / "value.md")
        record.update(body=body, pr={**record["pr"], "title": "Change the value"})
        state.save_branch(self.main, record)
        self.gh.effects.clear()
        self.gh.answers[("pr", "merge", PR)] = (1, "", CONFLICT)
        self.reviewer("OK\n", reply("s1"))
        code, data = self.land()
        self.assertEqual(code, 1, data)
        self.assert_points_to_sync(data, tree)
        fix = data["error"]["fix"]
        self.assertIn(f"python tools/retrodev ship --title 'Change the value' --body {body},", fix)
        self.assertNotIn("<file>", fix)

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
    def reviewed_then_synced(self, resolve=None, change=None, dev_core="VALUE = 3\n"):
        """A clean round on #12 (CI still running), then dev moves and the branch syncs. ``resolve(tree)`` settles
        a conflict on core.py (dev makes it ``dev_core``); without it dev changes another file. ``change(tree)``
        makes the pull request's commit (default: open_pr's)."""
        tree = self.open_pr(change=change)
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
            self.on_dev("backend/library/core.py", dev_core)
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

    def noqa_conflict(self, extra: str = ""):
        """dev gives 24 bare noqa comments their reason while the branch changes the line beside them (a conflict
        on the whole hunk); the resolution keeps the branch's code with dev's comments, plus ``extra``."""
        bare = "".join(f"import m{n}  # noqa: E402\n" for n in range(24))
        reasoned = bare.replace("E402\n", "E402 - the repository root goes on sys.path first\n")
        self.on_dev("backend/library/core.py", "VALUE = 1\n" + bare, "Bare noqa comments")
        git(self.main, "fetch", "-q", "origin")  # the branch starts from this dev

        def change(tree):
            self.commit(tree, "backend/library/core.py", "VALUE = 2\n" + bare, TITLE)

        def resolve(tree):
            (tree / "backend" / "library" / "core.py").write_text("VALUE = 2\n" + reasoned + extra)
            git(tree, "add", "backend/library/core.py")

        return self.reviewed_then_synced(resolve, change, dev_core="VALUE = 1\n" + reasoned)

    def test_a_resolution_that_changes_only_comments_counts_no_lines(self):
        _tree, reviewed, head = self.noqa_conflict()
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual(self.hermes.calls, [], "24 comment-only lines: the review carries over, no new round")
        self.assertEqual(self.merged_at(), head)
        carried = self.review_record()["carried"]
        self.assertEqual([(c["head"], c["reviewed"], c["resolution_lines"]) for c in carried], [(head, reviewed, 0)])

    def test_a_resolution_that_adds_code_beside_the_comments_still_counts_it(self):
        _tree, _reviewed, head = self.noqa_conflict("".join(f"EXTRA_{n} = {n}  # new\n" for n in range(25)))
        self.reviewer("OK\n", reply("s2"))
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual(len(self.hermes.calls), 2, "25 lines of code: a probe, then round 2 on the merged head")
        self.assertNotIn("carried", self.review_record())

    def test_a_binary_conflict_kept_as_reviewed_still_needs_a_new_round(self):
        """Both sides change a binary file and sync keeps the branch's: the merged tree equals git's own merge
        (0 lines differ), but a binary conflict cannot be judged in lines, so it is reviewed."""
        self.binary_conflict_kept_as_ours("player/art.bin")

    def test_a_binary_conflict_on_a_non_ascii_name_still_needs_a_new_round(self):
        """git quotes a non-ASCII name (core.quotePath); the conflicted path must still be the real file, not a
        quoted name that matches nothing and so checks nothing."""
        self.binary_conflict_kept_as_ours("player/caf\u00e9.bin")

    def test_a_binary_conflict_on_a_name_with_a_double_quote_still_needs_a_new_round(self):
        self.binary_conflict_kept_as_ours('player/say "hi".bin')

    def binary_conflict_kept_as_ours(self, art):
        tree = self.open_pr(change=lambda t: self.commit_bytes(t, art, b"\x00\x01ours\x00" * 40))
        self.ci(PENDING, code=8)
        self.reviewer("OK\n", reply("s1"))
        self.assertEqual(self.land()[0], 2)
        other = self.base / "other"
        git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(other))
        self.commit_bytes(other, art, b"\x00\x02dev\x00" * 40)
        git(other, "push", "-q", "origin", "dev")
        self.assertEqual(self.run_cli("sync", cwd=tree)[0], 1)
        git(tree, "checkout", "--ours", "--", art)
        git(tree, "add", art)
        self.assertEqual(self.run_cli("sync", cwd=tree)[0], 0)
        head = self.publish(tree)
        self.ci(GREEN)
        self.hermes.calls.clear()
        self.reviewer("OK\n", reply("s2"))
        code, data = self.land()
        self.assertEqual(code, 0, data)
        self.assertEqual(len(self.hermes.calls), 2, "a probe, then round 2 on the merged head")
        self.assertEqual([r["sha"] for r in records.valid_rounds(self.review_record())][-1], head)
        self.assertNotIn("carried", self.review_record())

    def commit_bytes(self, tree, name, data):
        (tree / name).parent.mkdir(parents=True, exist_ok=True)
        (tree / name).write_bytes(data)
        git(tree, "add", "-A")
        git(tree, "commit", "-q", "-m", "Change the art")

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


class CodeLines(unittest.TestCase):
    def test_comments_and_whitespace_never_count(self):
        self.assertEqual(code_lines.changed("a.py", "x = 1  # noqa: E402\n", "x  =  1  # noqa: E402 - why\n"), 0)
        self.assertEqual(code_lines.changed("a.py", "s = '#'\n", "s = '#' # a note\n\n# more\n"), 0)
        self.assertEqual(code_lines.changed("a.py", "s = '# a'\n", "s = '# b'\n"), 2, "a string is code")
        self.assertEqual(code_lines.changed("a.mjs", "f() // old\n", "f() // new\n"), 0)
        self.assertEqual(code_lines.changed("a.mjs", "u = 'http://a'\n", "u = 'http://b'\n"), 2)
        self.assertEqual(code_lines.changed("a.md", "# Title\n", "# Other\n"), 2, "only code files have comments")


class MergeTreeOutput(unittest.TestCase):
    OID = "0" * 40

    def test_reads_the_tree_and_the_conflicted_paths_as_they_are(self):
        out = f"{self.OID}\0player/caf\u00e9.bin\0say \"hi\".bin\0\0" + "1\0say \"hi\".bin\0CONFLICT (binary)\0msg\n\0"
        parsed = land_carry.merge_tree_output(1, out)
        self.assertEqual(parsed, (self.OID, ["player/caf\u00e9.bin", 'say "hi".bin']))
        self.assertEqual(land_carry.merge_tree_output(0, self.OID + "\0"), (self.OID, []))

    def test_anything_it_cannot_read_is_none_so_a_review_is_due(self):
        for code, out in [
            (1, self.OID + "\n\"player/caf\\303\\251.bin\"\n"),  # without -z: quoted, newline separated
            (1, self.OID + "\0"),  # a conflict with no path
            (1, self.OID + "\0a.bin\0"),  # no messages section
            (0, self.OID + "\0a.bin\0"),  # clean, yet paths follow
            (2, self.OID + "\0"),
            (0, "not-a-tree\0"),
            (0, ""),
        ]:
            with self.subTest(out=out):
                self.assertIsNone(land_carry.merge_tree_output(code, out))
