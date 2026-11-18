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


def record(*rounds, skipped=None, head=None):
    rec = {"pr": 5, "rounds": list(rounds), "skipped": skipped, "probes": []}
    if head:
        rec["head"] = head
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
