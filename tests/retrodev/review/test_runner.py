"""The reviewer's command line, reply parsing and schema checks, the retry, and the provider probe."""

import json
import tempfile
import tomllib
import unittest
from pathlib import Path

import retrodev
from tests.retrodev.review.helpers import FakeHermes, fixture

from retrodev.review import runner

SETTINGS = {"profile": "reviewer"}
CLEAN = '{"verdict": "clean", "findings": [], "checked": ["x"]}'


def finding(**changes):
    item = {"severity": "low", "file": "a.py", "line": 3, "problem": "p", "fix": "f", "evidence": "e"}
    item.update(changes)
    return item


class Command(unittest.TestCase):
    def test_review_command(self):
        policy = tomllib.loads((Path(retrodev.__file__).resolve().parent / "policy.toml").read_text())["config"]
        # The reviewer's defaults are the policy's, so a model bump moves both and this test with them.
        self.assertEqual(
            (runner.DEFAULTS["provider"], runner.DEFAULTS["model"], runner.DEFAULTS["reasoning"]),
            (policy["review_provider"], policy["review_model"], policy["review_reasoning"]),
        )
        cmd = runner.command(SETTINGS, brief=Path("/r/brief.md"))
        self.assertEqual(
            cmd,
            [
                "hermes",
                "-p",
                "reviewer",
                "chat",
                "--ignore-user-config",
                "--query-file",
                "/r/brief.md",
                "--oneshot",
                "-Q",
                "--provider",
                policy["review_provider"],
                "-m",
                policy["review_model"],
                "--reasoning",
                policy["review_reasoning"],
                "-t",
                "file",
            ],
        )

    def test_resume_and_overrides(self):
        cmd = runner.command({**SETTINGS, "model": "m2", "provider": None}, query="again", resume="s1", reasoning="low")
        self.assertIn("--resume", cmd)
        self.assertEqual(cmd[cmd.index("--resume") + 1], "s1")
        self.assertEqual(cmd[cmd.index("-m") + 1], "m2")
        self.assertEqual(cmd[cmd.index("--provider") + 1], runner.DEFAULTS["provider"])
        self.assertEqual(cmd[cmd.index("--reasoning") + 1], "low")

    def test_no_profile_no_command(self):
        with self.assertRaises(ValueError):
            runner.command({}, query="x")


class Parse(unittest.TestCase):
    def test_real_round_with_findings(self):
        text = fixture("round1.out")
        result, errors = runner.parse(text)
        self.assertEqual(errors, [])
        self.assertEqual(result["verdict"], "findings")
        self.assertEqual([f["line"] for f in result["findings"]], [160, 253])
        self.assertTrue(runner.session_id(text).startswith("local-fa20d0"))

    def test_real_clean_round_with_shell_noise(self):
        text = "zle: widget not found\ngitstatus failed to initialize\n" + fixture("round3.out") + "\n[gitstatus] x\n"
        result, errors = runner.parse(text)
        self.assertEqual((errors, result["verdict"], result["findings"]), ([], "clean", []))

    def test_fenced_json_and_inner_braces(self):
        body = {"verdict": "findings", "findings": [finding(problem="uses {x} and {\"y\": 1}")], "checked": []}
        result, errors = runner.parse("Here you go:\n```json\n" + json.dumps(body) + "\n```\n")
        self.assertEqual(errors, [])
        self.assertEqual(result["findings"][0]["problem"], 'uses {x} and {"y": 1}')

    def test_schema_failures(self):
        cases = {
            "no JSON": "I could not finish the review.",
            "bad verdict": '{"verdict": "ok", "findings": []}',
            "clean with findings": json.dumps({"verdict": "clean", "findings": [finding()]}),
            "findings empty": '{"verdict": "findings", "findings": []}',
            "missing key": json.dumps({"verdict": "findings", "findings": [{"severity": "low", "file": "a"}]}),
            "bad severity": json.dumps({"verdict": "findings", "findings": [finding(severity="critical")]}),
            "line text": json.dumps({"verdict": "findings", "findings": [finding(line="12")]}),
            "findings not list": '{"verdict": "findings", "findings": {"a": 1}}',
        }
        for name, text in cases.items():
            with self.subTest(name):
                result, errors = runner.parse(text)
                self.assertIsNone(result)
                self.assertTrue(errors)

    def test_clean_without_findings_key_is_valid(self):
        self.assertEqual(runner.validate({"verdict": "clean"}), [])


class RunReview(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="retrodev-runner-"))
        self.addCleanup(__import__("shutil").rmtree, self.tmp)
        self.brief = self.tmp / "round1" / "review" / "brief.md"

    def test_valid_first_time(self):
        fake = FakeHermes("Session: s1\n" + CLEAN + "\nsession_id: s1\n")
        out = self.tmp / "round1.out"
        reply = runner.run_review(SETTINGS, self.brief, self.tmp / "round1", out, fake)
        self.assertEqual((reply["result"]["verdict"], reply["session_ids"], len(fake.calls)), ("clean", ["s1"], 1))
        self.assertEqual(fake.calls[0]["cwd"], self.tmp / "round1")
        self.assertEqual(fake.calls[0]["timeout"], 2400)
        self.assertIn(CLEAN, out.read_text())

    def test_invalid_reply_is_asked_once_more_in_the_same_session(self):
        fake = FakeHermes("Session: s1\nSorry, here are thoughts.\nsession_id: s1\n", "Session: s1\n" + CLEAN)
        out = self.tmp / "round1.out"
        reply = runner.run_review(SETTINGS, self.brief, self.tmp, out, fake)
        self.assertEqual(reply["result"]["verdict"], "clean")
        retry = fake.calls[1]["cmd"]
        self.assertEqual(retry[retry.index("--resume") + 1], "s1")
        self.assertNotIn("--query-file", retry)
        text = out.read_text()
        self.assertIn("Sorry", text)
        self.assertIn("===== retry", text)

    def test_no_session_id_reruns_the_brief_then_gives_up(self):
        fake = FakeHermes("garbage", "more garbage")
        reply = runner.run_review(SETTINGS, self.brief, self.tmp, self.tmp / "o.out", fake)
        self.assertIsNone(reply["result"])
        self.assertTrue(reply["errors"])
        self.assertEqual(len(fake.calls), 2)
        self.assertIn("--query-file", fake.calls[1]["cmd"])

    def test_timeout_is_not_retried(self):
        fake = FakeHermes("Session: s1\npartial", timed_out=True, returncode=-1)
        reply = runner.run_review({**SETTINGS, "timeout": 5}, self.brief, self.tmp, self.tmp / "o.out", fake)
        self.assertIsNone(reply["result"])
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("timed out after 5 s", reply["errors"][0])


class Probe(unittest.TestCase):
    def test_ok(self):
        fake = FakeHermes("Session: s\nOK\n\nsession_id: s\n")
        probe = runner.probe(SETTINGS, fake)
        self.assertTrue(probe["available"])
        cmd = fake.calls[0]["cmd"]
        self.assertEqual(cmd[cmd.index("--reasoning") + 1], "low")
        self.assertEqual(fake.calls[0]["timeout"], 90)

    def test_unavailable(self):
        cases = {
            "rate limit": ("Error: 429 Too Many Requests: rate limit reached", 1, False),
            "quota": ("You have exceeded your usage quota.", 0, False),
            "unauthorized": ("HTTP 401 unauthorized: token expired", 1, False),
            "other reply": ("Session: s\nHello! How can I help?\n", 0, False),
            "silence": ("", 0, True),
        }
        for name, (out, code, timed_out) in cases.items():
            with self.subTest(name):
                probe = runner.probe(SETTINGS, FakeHermes(out, returncode=code, timed_out=timed_out))
                self.assertFalse(probe["available"])
                self.assertTrue(probe["reason"])
        reason = runner.probe(SETTINGS, FakeHermes("429 rate limit", returncode=1))["reason"]
        self.assertIn("provider unavailable", reason)

    def test_no_profile_skips_without_running(self):
        fake = FakeHermes("OK")
        self.assertEqual(runner.probe({}, fake)["reason"], "no reviewer profile configured")
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
