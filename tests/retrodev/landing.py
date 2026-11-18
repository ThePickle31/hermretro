"""A pull request ready to land, for the approve, land, answer and summary tests: a worktree whose commit passed
check and is pushed to the temp origin, a fake GitHub that knows it as #12 (and merges it for real into the origin
when asked), and a fake reviewer: a Hermes runner answering from a script, and the session database its audit reads.
"""

from __future__ import annotations

import io
import json

from retrodev import checks, config, output, repo, state

from tests.retrodev.fixture import RepoCase, git
from tests.retrodev.review.helpers import FakeHermes, make_db

PR = "12"
TITLE = "Change the value"
BRANCH = "feat/thing"
FINDING = {
    "severity": "medium",
    "file": "backend/library/core.py",
    "line": 1,
    "problem": "VALUE changed without a test",
    "fix": "add a test",
    "evidence": "core.py:1",
}
GREEN = [
    {
        "name": "All checks pass",
        "state": "SUCCESS",
        "bucket": "pass",
        "link": "https://github.com/o/r/actions/runs/99/job/1",
    },
    {
        "name": "unit (ubuntu)",
        "state": "SUCCESS",
        "bucket": "pass",
        "link": "https://github.com/o/r/actions/runs/99/job/2",
    },
    {"name": "acceptance (macos)", "state": "SKIPPED", "bucket": "skipping", "link": ""},
]
SESSIONS = [f"s{n}" for n in range(1, 9)]


def reply(sid: str, findings: int = 0) -> str:
    body = {"verdict": "findings" if findings else "clean", "findings": [FINDING] * findings, "checked": ["core.py"]}
    return f"Session: {sid}\n{json.dumps(body)}\nsession_id: {sid}\n"


class LandCase(RepoCase):
    def setUp(self):
        super().setUp()
        self.db = make_db(self.base / "reviewer" / "state.db", {sid: [] for sid in SESSIONS})
        self.hermes = FakeHermes()
        self.fakes.update(review_run=self.hermes, review_db=self.db, sleep=lambda _s: None)
        self.run_cli("config", "set", "review_profile", "rev")

    def reviewer(self, *outputs: str, on_call=None) -> FakeHermes:
        """The reviewer answers with these outputs in turn (a probe takes one: 'OK')."""
        self.hermes.outputs[:] = list(outputs)
        self.hermes.on_call = on_call
        return self.hermes

    def passed(self, tree):
        ctx = config.Context.make(tree, output.Out(stream=io.StringIO()))
        record = state.load_branch(self.main, BRANCH)
        record.update(passed_tree=repo.tree_digest(tree), passed_checks=sorted(checks.required(ctx)))
        state.save_branch(self.main, record)

    def publish(self, tree, **info) -> str:
        """Commit-passed-pushed: the head GitHub reports for #12 is this tree's head."""
        self.passed(tree)
        git(tree, "push", "-q", "origin", BRANCH)
        head = git(tree, "rev-parse", "HEAD").strip()
        record = state.load_branch(self.main, BRANCH)
        record.update(pushed=head, pr={"number": int(PR), "url": "https://github.com/o/r/pull/12", "head": head})
        state.save_branch(self.main, record)
        self.info.update(headRefOid=head, **info)
        self.answer_view()
        return head

    def answer_view(self) -> None:
        self.gh.answers[("pr", "view", PR)] = (0, json.dumps(self.info), "")

    def ci(self, jobs, code: int = 0) -> None:
        self.gh.answers[("pr", "checks", PR)] = (code, json.dumps(jobs), "")

    def open_pr(self, draft: bool = False, approve: bool = True):
        tree = self.worktree(BRANCH)
        self.commit(tree, "backend/library/core.py", "VALUE = 2\n", TITLE)
        self.info = {
            "number": int(PR),
            "title": TITLE,
            "state": "OPEN",
            "isDraft": draft,
            "baseRefName": "dev",
            "headRefName": BRANCH,
            "url": "https://github.com/o/r/pull/12",
            "body": "## Why\nThe value must be two.\n",
            "statusCheckRollup": [],
        }
        self.publish(tree)
        self.ci(GREEN)
        self.gh.answers[("pr", "ready", PR)] = (0, "", "")
        self.gh.answers[("pr", "merge", PR)] = (0, "", "")
        self.gh.effects[("pr", "merge", PR)] = self.squash
        if approve:
            code, out = self.run_cli("approve", PR, "--words", "looks good, merge it")
            self.assertEqual(code, 0, out)
        return tree

    def squash(self, args):
        """What GitHub does on gh pr merge --squash --delete-branch: one commit on dev, the branch deleted."""
        other = self.base / "merger"
        if not other.exists():
            git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(other))
        git(other, "fetch", "-q", "origin")
        git(other, "reset", "-q", "--hard", "origin/dev")
        git(other, "merge", "-q", "--squash", f"origin/{BRANCH}")
        git(other, "commit", "-q", "-m", args[args.index("--subject") + 1])
        git(other, "push", "-q", "origin", "dev")
        git(other, "push", "-q", "origin", "--delete", BRANCH)
        self.info.update(state="MERGED", mergeCommit={"oid": git(other, "rev-parse", "HEAD").strip()})
        self.answer_view()

    def land(self, *extra: str, as_json: bool = True):
        return self.run_cli("land", PR, "--ci-timeout", "0", *extra, as_json=as_json)

    def merges(self) -> list[list[str]]:
        return self.gh.called("pr", "merge")
