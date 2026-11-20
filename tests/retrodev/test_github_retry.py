"""github.gh retries a read-only call that failed the way a busy GitHub fails, and nothing else.

Run alone: python -m unittest tests.retrodev.test_github_retry
"""

import unittest
from pathlib import Path
from types import SimpleNamespace

from retrodev import github
from retrodev.output import Failure

from tests.retrodev.fixture import parallel

load_tests = parallel


class Answers:
    """A gh runner answering from a list, one answer per call; it records the calls."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, args, cwd):
        self.calls.append(list(args))
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


def context(runner) -> SimpleNamespace:
    said: list[str] = []
    out = SimpleNamespace(say=said.append, said=said)
    return SimpleNamespace(gh_runner=runner, fakes={"sleep": lambda _s: None}, top=Path("."), cwd=Path("."), out=out)


BUSY = (1, "", "HTTP 502: Bad Gateway (https://api.github.com/graphql)")
OK = (0, '{"state": "OPEN"}', "")


class Retry(unittest.TestCase):
    def test_a_read_only_call_is_retried_after_a_5xx_and_its_answer_counts(self):
        runner = Answers(BUSY, OK)
        ctx = context(runner)
        self.assertEqual(github.gh(ctx, ["pr", "view", "7", "--json", "state"]), OK)
        self.assertEqual(len(runner.calls), 2)
        self.assertIn("failed on GitHub's side", ctx.out.said[0])

    def test_it_gives_up_after_two_retries(self):
        runner = Answers(BUSY)
        with self.assertRaises(Failure):
            github.gh(context(runner), ["api", "repos/{owner}/{repo}/commits/abc/check-runs"])
        self.assertEqual(len(runner.calls), 3)

    def test_a_call_that_writes_or_a_real_refusal_is_never_retried(self):
        for args, answer in (
            (["pr", "create", "--title", "t"], BUSY),
            (["pr", "merge", "7", "--squash"], BUSY),
            (["api", "-X", "POST", "repos/{owner}/{repo}/issues"], BUSY),
            (["api", "repos/{owner}/{repo}/issues", "-f", "title=t"], BUSY),
            (["pr", "view", "7"], (1, "", "GraphQL: Could not resolve to a PullRequest with the number of 7.")),
        ):
            with self.subTest(args=args):
                runner = Answers(answer, OK)
                code, _out, _err = github.gh(context(runner), args, check=False)
                self.assertEqual((code, len(runner.calls)), (1, 1))


if __name__ == "__main__":
    unittest.main()
