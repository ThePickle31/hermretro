"""A whole round with a fake Hermes and a crafted session database: reviewed, skipped, void, retried."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests.retrodev.review.helpers import FakeHermes, fixture, make_db, make_repo

from retrodev.review import records, round

REMOTE = "abc\trefs/heads/dev"


class RunRound(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="retrodev-round-"))
        cls.info = make_repo(cls.tmp)
        cls.repo = cls.info["repo"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="reviews-", dir=self.tmp))
        self.notes = self.root / "notes"
        self.db = self.root / "state.db"

    def go(self, fake, sessions, **kw):
        make_db(self.db, sessions)
        return round.run_round(
            self.repo,
            7,
            "HEAD",
            {"profile": "rev"},
            title="Use b",
            goal="g",
            run=fake,
            probe={"available": True, "reason": "ok", "seconds": 1.0},
            ls_remote=lambda _r, _b: REMOTE,
            root=self.root,
            notes=self.notes,
            db=self.db,
            **kw,
        )

    def reads(self):
        rev = self.root / "7" / "round1"
        return [
            ("read_file", {"path": str(rev / "review" / "brief.md")}),
            ("search_files", {"pattern": "B", "path": str(rev / "src")}),
        ]

    def test_reviewed_with_findings(self):
        fake = FakeHermes(fixture("round1.out"))
        sid = "local-fa20d033c476b69a4212305ef6e5baa0254c78674617f0df564b5451e4e63a7b"
        result = self.go(fake, {sid: self.reads()})
        self.assertEqual((result["status"], result["round"], result["action"]), ("reviewed", 1, "fix"))
        self.assertTrue(result["audit"]["ok"])
        self.assertEqual(len(result["result"]["findings"]), 2)
        self.assertEqual(fake.calls[0]["cwd"], self.root / "7" / "round1")
        rec = records.load(self.root, 7)
        self.assertEqual(rec["rounds"][0]["session_ids"], [sid])
        self.assertTrue(Path(rec["rounds"][0]["output"]).is_file())
        self.assertTrue((self.notes / "pr7.md").is_file())

    def test_write_voids_and_reruns_once(self):
        rev = self.root / "7" / "round1"
        outputs = [
            "Session: bad\n{\"verdict\": \"clean\", \"findings\": []}\nsession_id: bad\n",
            "Session: good\n{\"verdict\": \"clean\", \"findings\": []}\nsession_id: good\n",
        ]
        fake = FakeHermes(*outputs)
        result = self.go(
            fake, {"bad": [("write_file", {"path": str(rev / "src" / "a.py"), "content": ""})], "good": self.reads()}
        )
        self.assertEqual((result["status"], result["action"]), ("reviewed", "merge"))
        self.assertEqual(len(result["attempts"]), 2)
        self.assertFalse(result["attempts"][0]["audit"]["ok"])
        rec = records.load(self.root, 7)
        self.assertEqual([r["void"] for r in rec["rounds"]], [True, False])
        self.assertIsNone(rec["rounds"][0]["result"])

    def test_a_run_without_a_session_id_voids_the_round_even_if_its_retry_succeeds(self):
        fake = FakeHermes(
            "no session and no json",  # its tool calls are unknown
            "Session: good\n{\"verdict\": \"clean\", \"findings\": []}\nsession_id: good\n",
            "Session: good2\n{\"verdict\": \"clean\", \"findings\": []}\nsession_id: good2\n",
        )
        result = self.go(fake, {"good": self.reads(), "good2": self.reads()})
        first = result["attempts"][0]["audit"]
        self.assertFalse(first["ok"])
        self.assertIn("printed no session id", " ".join(first["violations"]))
        self.assertEqual((result["status"], result["action"]), ("reviewed", "merge"))  # the rerun was audited

    def test_void_twice_needs_the_owner(self):
        def tamper(_cmd, cwd):
            (cwd / "src" / "README.md").write_text("changed by the reviewer\n")

        fake = FakeHermes(
            "Session: s\n{\"verdict\": \"clean\"}", "Session: s\n{\"verdict\": \"clean\"}", on_call=tamper
        )
        result = self.go(fake, {"s": self.reads()})
        self.assertEqual((result["status"], result["action"]), ("void", "needs-owner"))
        self.assertIn("the round's src/ export changed", result["audit"]["violations"])

    def test_invalid_json_after_retry_needs_the_owner(self):
        fake = FakeHermes("Session: s\nno json", "Session: s\nstill none")
        result = self.go(fake, {"s": self.reads()})
        self.assertEqual((result["status"], result["action"]), ("invalid", "needs-owner"))
        self.assertIn("--resume", fake.calls[1]["cmd"])

    def test_skipped_without_profile_or_provider(self):
        result = round.run_round(self.repo, 7, "HEAD", {}, root=self.root, notes=self.notes, run=FakeHermes())
        self.assertEqual((result["status"], result["action"]), ("skipped", "merge-on-green"))
        self.assertEqual(records.load(self.root, 7)["skipped"]["reason"], "no reviewer profile configured")
        down = FakeHermes("Error: 429 rate limit", returncode=1)
        result = round.run_round(self.repo, 8, "HEAD", {"profile": "rev"}, root=self.root, notes=self.notes, run=down)
        self.assertEqual(result["status"], "skipped")
        self.assertIn("429", records.load(self.root, 8)["skipped"]["reason"])
        self.assertEqual(len(down.calls), 1)  # only the probe ran


if __name__ == "__main__":
    unittest.main()
