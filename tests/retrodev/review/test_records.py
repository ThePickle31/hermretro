"""Review records, answers, the readable copy, and what landing does next."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests.retrodev.review.helpers import make_repo

from retrodev.review import records

FINDING = {"severity": "medium", "file": "a.py", "line": 1, "problem": "p", "fix": "f", "evidence": "e"}


def rnd(n, sha, verdict="findings", void=False, stopped=None):
    result = {"verdict": verdict, "findings": [FINDING] if verdict == "findings" else [], "checked": []}
    entry = {"round": n, "sha": sha, "result": None if void else result, "void": void, "answers": {}}
    if stopped:
        entry["stopped"] = stopped
    return entry


LOW = dict(FINDING, severity="low")


def low(n, sha):
    entry = rnd(n, sha)
    entry["result"]["findings"] = [LOW, LOW]
    return entry


def record(*rounds, skipped=None, head=None, accepted=None, depth=None):
    rec = {"pr": 5, "rounds": list(rounds), "skipped": skipped, "probes": []}
    if depth is not None:
        rec["depth"] = {"rounds": depth, "why": "a test"}
    if head:
        rec["head"] = head
    if accepted:
        rec["accepted"] = accepted
    return rec


class NextAction(unittest.TestCase):
    def test_table(self):
        table = [
            ("no rounds yet", record(), True, None, "review"),
            ("skipped", record(skipped={"reason": "no reviewer profile configured"}), False, None, "merge-on-green"),
            ("clean, CI green", record(rnd(1, "a", "clean")), True, "a", "merge"),
            ("clean, CI not green", record(rnd(1, "a", "clean")), False, "a", "wait-ci"),
            ("clean, then a push", record(rnd(1, "a", "clean")), True, "b", "review"),
            ("findings, nothing pushed", record(rnd(1, "a")), True, "a", "fix"),
            ("findings, fixes pushed", record(rnd(1, "a")), True, "b", "review"),
            ("fixes pushed, from the record", record(rnd(1, "a"), head="b"), True, None, "review"),
            ("round 2 findings, fixed", record(rnd(1, "a"), rnd(2, "b")), True, "c", "review"),
            ("round 3 findings", record(rnd(1, "a"), rnd(2, "b"), rnd(3, "c")), True, "c", "fix-then-merge"),
            ("round 3 findings, fixed", record(rnd(1, "a"), rnd(2, "b"), rnd(3, "c")), True, "d", "fix-then-merge"),
            ("round 3 clean", record(rnd(1, "a"), rnd(2, "b"), rnd(3, "c", "clean")), True, "c", "merge"),
            (
                "round 3 clean, then a push",
                record(rnd(1, "a"), rnd(2, "b"), rnd(3, "c", "clean")),
                True,
                "d",
                "reviews-exhausted",
            ),
            (
                "round 3 fixes accepted, this head",
                record(rnd(1, "a"), rnd(2, "b"), rnd(3, "c"), accepted={"head": "d"}),
                True,
                "d",
                "fix-then-merge",
            ),
            (
                "round 3 fixes accepted, then a push",
                record(rnd(1, "a"), rnd(2, "b"), rnd(3, "c"), accepted={"head": "d"}),
                True,
                "e",
                "reviews-exhausted",
            ),
            ("void rounds do not count", record(rnd(1, "a"), rnd(2, "b", void=True)), True, "b", "review"),
            (
                "void twice",
                record(rnd(1, "a", void=True), rnd(1, "a", void=True, stopped="x")),
                True,
                "a",
                "needs-owner",
            ),
        ]
        for name, rec, green, head, want in table:
            with self.subTest(name):
                self.assertEqual(records.next_action(rec, green, head=head), want)

    def test_depth_table(self):
        one = {"head": "b", "round": 1}
        table = [
            ("one round: findings, nothing pushed", record(rnd(1, "a"), depth=1), "a", "fix"),
            ("one round: fixes pushed", record(rnd(1, "a"), depth=1), "b", "fix-then-merge"),
            ("one round: only low findings, nothing pushed", record(low(1, "a"), depth=1), "a", "fix-then-merge"),
            ("one round: accepted, this head", record(rnd(1, "a"), depth=1, accepted=one), "b", "fix-then-merge"),
            ("one round: accepted, then a push", record(rnd(1, "a"), depth=1, accepted=one), "c", "review"),
            (
                "the push's round has findings: its fixes are accepted anew",
                record(rnd(1, "a"), rnd(2, "c"), depth=1, accepted=one),
                "d",
                "fix-then-merge",
            ),
            ("one round: clean, then a push", record(rnd(1, "a", "clean"), depth=1), "b", "review"),
            ("two rounds: round 1 fixes pushed", record(rnd(1, "a"), depth=2), "b", "review"),
            ("two rounds: round 2 fixes pushed", record(rnd(1, "a"), rnd(2, "b"), depth=2), "c", "fix-then-merge"),
            (
                "three rounds ran, the head moved past the accepted one",
                record(rnd(1, "a"), rnd(2, "b"), rnd(3, "c"), depth=1, accepted={"head": "d", "round": 3}),
                "e",
                "reviews-exhausted",
            ),
            ("a depth nobody can read is the hard limit", record(rnd(1, "a"), depth="x"), "b", "review"),
            ("a depth over the hard limit is the hard limit", record(rnd(1, "a"), rnd(2, "b"), depth=9), "c", "review"),
        ]
        for name, rec, head, want in table:
            with self.subTest(name):
                self.assertEqual(records.next_action(rec, True, head=head), want)

    def test_a_head_reviewed_itself_wins_over_a_carry_made_for_it_and_stale_carries_do_not_count(self):
        # Accepted "b" was synced to "c" (carried), then a round reviewed "c" directly and found it clean.
        rec = record(rnd(1, "a"), rnd(2, "c", "clean"), depth=2, accepted={"head": "b", "round": 1})
        rec["carried"] = [{"head": "c", "reviewed": "b", "resolution_lines": 0}]
        self.assertEqual(records.reviewed_as(rec, "c"), "c")
        self.assertEqual(records.next_action(rec, True, head="c"), "merge")
        self.assertEqual(records.next_action(rec, False, head="c"), "wait-ci")
        rec["carried"].append({"head": "d", "reviewed": "b", "resolution_lines": 0})  # points past the clean head
        self.assertEqual(records.reviewed_as(rec, "d"), "d")
        rec["carried"].append({"head": "e", "reviewed": "c", "resolution_lines": 0})
        self.assertEqual(records.next_action(rec, True, head="e"), "merge")

    def test_a_second_round_file_no_round_saw_gets_the_head_reviewed_whatever_stands_for_it(self):
        clean = record(rnd(1, "a", "clean"), depth=1)
        clean["carried"] = [{"head": "b", "reviewed": "a", "resolution_lines": 0}]
        self.assertEqual(records.next_action(clean, True, head="b"), "merge")
        clean["depth"]["unseen"] = ["page/app/update/flow.js"]
        self.assertEqual(records.next_action(clean, True, head="b"), "review")
        self.assertEqual(records.next_action(clean, True, head="a"), "merge", "the reviewed head itself")
        accepted = record(rnd(1, "a"), depth=1, accepted={"head": "b", "round": 1})
        accepted["depth"]["unseen"] = ["x"]
        self.assertEqual(records.next_action(accepted, True, head="b"), "review")
        spent = record(rnd(1, "a"), rnd(2, "b"), rnd(3, "c", "clean"), depth=1)
        spent["depth"]["unseen"] = ["x"]
        self.assertEqual(records.next_action(spent, True, head="d"), "reviews-exhausted")

    def test_a_push_with_the_same_patch_is_no_fix(self):
        rec = record(rnd(1, "a"), depth=1)
        rec["depth"]["same_patch"] = True
        self.assertEqual(records.next_action(rec, True, head="b"), "fix")
        rec["depth"]["same_patch"] = False
        self.assertEqual(records.next_action(rec, True, head="b"), "fix-then-merge")

    def test_an_acceptance_belongs_to_its_round_and_older_records_mean_round_three(self):
        old = record(rnd(1, "a"), rnd(2, "b"), rnd(3, "c"), accepted={"head": "d"})
        self.assertEqual(records.accepted_head(old), "d")
        self.assertIsNone(records.accepted_head(record(rnd(1, "a"), rnd(2, "b"), accepted={"head": "d"})))
        self.assertIsNone(records.accepted_head(record(rnd(1, "a"), rnd(2, "c"), accepted={"head": "b", "round": 1})))
        self.assertEqual(records.depth(record(rnd(1, "a"))), records.MAX_ROUNDS)


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="retrodev-records-"))
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root, self.notes = self.tmp / "reviews", self.tmp / "notes"

    def test_round_answer_and_mirror(self):
        records.add_round(self.root, 5, rnd(1, "abcdef1234"), self.notes)
        rec = records.answer(
            5, 1, 0, "Fixed in 1234567: the test now fails on the old code.", root=self.root, notes=self.notes
        )
        self.assertEqual(rec["rounds"][0]["answers"], {"0": "Fixed in 1234567: the test now fails on the old code."})
        self.assertEqual(records.load(self.root, 5), rec)
        md = (self.notes / "pr5.md").read_text()
        self.assertIn("## Round 1: findings", md)
        self.assertIn("Fixed in 1234567", md)
        earlier, last = records.earlier_inputs(rec)
        self.assertEqual(last, "abcdef1234")
        self.assertIn("Author's answer: Fixed in 1234567", earlier[1])
        with self.assertRaises(IndexError):
            records.answer(5, 1, 3, "x", root=self.root, notes=self.notes)
        with self.assertRaises(KeyError):
            records.answer(5, 2, 0, "x", root=self.root, notes=self.notes)

    def test_skip_is_recorded_and_cleared_by_a_round(self):
        rec = records.mark_skipped(self.root, 5, "provider unavailable (429)", self.notes)
        self.assertEqual(records.next_action(rec, True), "merge-on-green")
        self.assertIn("Reviews skipped: provider unavailable (429)", (self.notes / "pr5.md").read_text())
        rec = records.add_round(self.root, 5, rnd(1, "a", "clean"))
        self.assertIsNone(rec["skipped"])
        self.assertEqual(records.next_round(rec), 2)

    def test_notes_go_to_the_main_checkout(self):
        repo = make_repo(self.tmp)["repo"]
        self.assertEqual(records.notes_dir(repo), repo.resolve() / "notes" / "reviews")


if __name__ == "__main__":
    unittest.main()
