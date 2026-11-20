"""release run without --draft: release verify --publish, then release next moves dev to the next version.

Against the temp origin of test_release with the fake GitHub of test_release_run; the next version's pull request
is #41, merged for real into the origin.

Run alone: python -m unittest tests.retrodev.test_release_next
"""

import json

from retrodev import release_verify, state

from tests.retrodev.fixture import git, parallel
from tests.retrodev.test_release import NEXT, PR, URL, WORDS, runs
from tests.retrodev.test_release_run import BRANCH, GREEN, RED, RESUME, RunCase

load_tests = parallel

AFTER = "0.0.3"  # the version release next moves dev to after NEXT
NEXT_PR = "41"
NEXT_BRANCH = f"chore/release-{AFTER}"


class Publishes(RunCase):
    """Without --draft: release verify --publish, then release next moves dev on (its pull request is #41)."""

    def setUp(self):
        super().setUp()
        self.next_info: dict = {}
        self.gh.effects[("pr", "create")] = self.created
        self.gh.answers[("pr", "ready", NEXT_PR)] = (0, "", "")
        self.gh.effects[("pr", "ready", NEXT_PR)] = lambda _args: self.next_view(isDraft=False)
        self.gh.answers[("pr", "merge", NEXT_PR)] = (0, "", "")
        self.gh.effects[("pr", "merge", NEXT_PR)] = self.squash_next
        self.gh.answers[("pr", "checks", NEXT_PR)] = (0, json.dumps(GREEN), "")
        self.gh.effects[("release", "create")] = self.drafted
        self.gh.answers[("release", "edit")] = (0, "", "")

    def created(self, args) -> None:
        head = args[args.index("--head") + 1]
        if head == BRANCH:
            self.gh.answers[("pr", "create")] = (0, f"https://github.com/o/r/pull/{PR}\n", "")
            self.opened(args)
            return
        self.gh.answers[("pr", "create")] = (0, f"https://github.com/o/r/pull/{NEXT_PR}\n", "")
        tree = self.base / "hermretro-wt" / f"release-{AFTER}"
        self.next_view(
            number=int(NEXT_PR),
            title=args[args.index("--title") + 1],
            state="OPEN",
            isDraft=True,
            baseRefName="dev",
            headRefName=head,
            headRefOid=git(tree, "rev-parse", "HEAD").strip(),
            url=f"https://github.com/o/r/pull/{NEXT_PR}",
            body="## Why\nThe next version.\n",
            statusCheckRollup=[],
        )

    def next_view(self, **info) -> None:
        self.next_info.update(info)
        self.gh.answers[("pr", "view", NEXT_PR)] = (0, json.dumps(self.next_info), "")
        self.gh.answers[("pr", "view", NEXT_PR, "--json", "state")] = (0, self.next_info.get("state", "") + "\n", "")

    def squash_next(self, args) -> None:
        other = self.base / "merger"
        if not other.exists():
            git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(other))
        git(other, "fetch", "-q", "origin")
        git(other, "reset", "-q", "--hard", "origin/dev")
        git(other, "merge", "-q", "--squash", f"origin/{NEXT_BRANCH}")
        git(other, "commit", "-q", "-m", args[args.index("--subject") + 1])
        git(other, "push", "-q", "origin", "dev")
        git(other, "push", "-q", "origin", "--delete", NEXT_BRANCH)
        self.next_view(state="MERGED", mergeCommit={"oid": git(other, "rev-parse", "HEAD").strip()})

    def drafted(self, args) -> None:
        """The draft exists now: verify reads it (a draft until gh release edit --draft=false)."""
        tag = args[2]
        view = {"tagName": tag, "isDraft": True, "isPrerelease": False, "body": "## Changes\n- A thing", "url": URL}
        self.gh.answers[("release", "view", tag, "--json", release_verify.FIELDS)] = (0, json.dumps(view), "")
        self.gh.answers[("release", "view", tag, "--json", "url")] = (0, json.dumps({"url": URL}), "")

    def dev_version(self) -> str:
        git(self.main, "fetch", "-q", "origin")
        return git(self.main, "show", "origin/dev:plugin.yaml").strip()

    def test_one_command_publishes_then_dev_moves_to_the_next_version(self):
        code, data = self.release_run()
        self.assertEqual(code, 0, data)
        steps = [s["step"] for s in data["run_steps"]]
        self.assertEqual(steps, ["prepare", "approve", "land", "wait", "publish", "verify", "next"], data)
        self.assertEqual(self.gh.called("release", "edit"), [["release", "edit", f"v{NEXT}", "--draft=false"]])
        self.assertEqual(data["url"], URL)
        installs = [entry for entry in self.check_log() if entry.get("script")]
        self.assertEqual(len(installs), 1, "verify reused publish's update check on the same commit")
        self.assertEqual(self.dev_version(), f"version: {AFTER}")
        create = self.gh.called("pr", "create")[-1]
        self.assertEqual(create[create.index("--title") + 1], f"Version {AFTER} for the next release")
        approval = json.loads((state.root(self.main) / "reviews" / f"{NEXT_PR}.json").read_text())["approval"]
        self.assertEqual((approval["scope"], approval["version"], approval["words"]), ("release", AFTER, WORDS))
        self.assertTrue(state.load_release(self.main, NEXT)["next"]["merged"])
        self.assertIsNone(state.load_release(self.main, AFTER), "no owner's words are recorded for the next one")

        code, data = self.release_run("--version", AFTER)  # straight away: only the version moved since
        self.assertEqual(code, 1, data)
        self.assertIn(f"nothing to release: origin/dev has no change since v{NEXT}", data["error"]["message"])

        self.on_dev("docs/more.md", "# More\n", "More for users")  # the next release: dev's head, no pull request
        git(self.main, "fetch", "-q", "origin")
        head = git(self.main, "rev-parse", "origin/dev").strip()
        self.ci(head, runs("success"))
        creates = len(self.gh.called("pr", "create"))
        code, data = self.run_cli("release", "run", "--owner-words", "release it", "--draft", as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["version"], AFTER)
        self.assertEqual([s["status"].split(":")[0] for s in data["run_steps"][1:3]], ["skipped", "skipped"])
        self.assertEqual(len(self.gh.called("pr", "create")), creates, "no version pull request")
        self.assertEqual(self.remote(f"refs/tags/v{AFTER}^{{commit}}"), head)

    def test_a_stop_after_publishing_resumes_at_the_next_version(self):
        self.gh.answers[("pr", "checks", NEXT_PR)] = (0, json.dumps(RED), "")  # the next-version land stops
        code, data = self.release_run()
        self.assertEqual(code, 1, data)
        self.assertIn("released, but dev did not move to the next version", data["error"]["message"])
        self.assertIn(RESUME, data["error"]["fix"])
        self.assertEqual(len(self.gh.called("release", "edit")), 1, "published before the next step")
        self.gh.answers[("pr", "checks", NEXT_PR)] = (0, json.dumps(GREEN), "")
        code, data = self.release_run()  # without the printed --version: a new release, and nothing is new
        self.assertEqual(code, 1, data)
        self.assertIn("nothing to release", data["error"]["message"])
        self.assertIn("release next --owner-words", data["error"]["fix"])
        code, data = self.release_run("--version", NEXT)  # the printed command
        self.assertEqual(code, 0, data)
        self.assertEqual(len(self.gh.called("release", "edit")), 1, "never published twice")
        self.assertEqual(len([c for c in self.gh.called("pr", "create") if NEXT_BRANCH in c]), 1, "the same #41")
        self.assertEqual(self.dev_version(), f"version: {AFTER}")

    def test_an_open_next_version_pull_request_is_used_or_closed_when_another_version_is_named(self):
        self.gh.answers[("pr", "checks", NEXT_PR)] = (0, json.dumps(RED), "")
        self.assertEqual(self.release_run()[0], 1)  # released; #41 open for AFTER
        open41 = [{"number": int(NEXT_PR), "state": "OPEN", "mergeCommit": None}]
        self.gh.answers[("pr", "list", "--head", NEXT_BRANCH)] = (0, json.dumps(open41), "")
        self.on_dev("docs/more.md", "# More\n", "More for users")
        code, data = self.run_cli("release", "prepare", "--owner-words", "release it", as_json=True)
        self.assertEqual((code, data.get("pr"), data.get("resumed")), (0, int(NEXT_PR), True), data)
        self.assertEqual(len([c for c in self.gh.called("pr", "create") if NEXT_BRANCH in c]), 1, "never twice")
        self.gh.answers[("pr", "close", NEXT_PR)] = (0, "", "")
        self.gh.answers[("pr", "create")] = (1, "", "stop here")  # only the closing is under test
        self.release_run("--version", "0.1.0")
        close = self.gh.called("pr", "close", NEXT_PR)
        self.assertEqual(len(close), 1, self.gh.calls)
        self.assertIn("--delete-branch", close[0])
        self.assertTrue(state.load_release(self.main, NEXT)["next"]["closed"])

    def test_a_failed_push_run_is_rerun_once_then_the_release_stops(self):
        self.push_ci = runs("failure")
        failed = json.dumps([{"databaseId": 7, "conclusion": "failure", "event": "push"}])
        self.gh.answers[("run", "list")] = (0, failed, "")
        self.gh.answers[("run", "rerun")] = (0, "", "")
        merged = lambda: self.info["mergeCommit"]["oid"]  # noqa: E731 - read when the rerun is asked
        self.gh.effects[("run", "rerun")] = lambda _args: self.ci(merged(), runs("success"))
        code, data = self.release_run("--draft")
        self.assertEqual(code, 0, data)
        self.assertEqual(self.gh.called("run", "rerun"), [["run", "rerun", "7", "--failed"]])
        self.setUp()
        self.push_ci = runs("failure")
        self.gh.answers[("run", "list")] = (0, failed, "")
        self.gh.answers[("run", "rerun")] = (0, "", "")  # the rerun fails as well
        code, data = self.release_run("--draft")
        self.assertEqual(code, 1, data)
        self.assertEqual(len(self.gh.called("run", "rerun")), 1, "once only")
        self.assertEqual(self.gh.called("release", "create"), [])

    def test_a_pull_request_github_opened_while_failing_is_picked_up(self):
        def fail_but_open(args):
            self.created(args)
            self.gh.answers[("pr", "create")] = (1, "", "HTTP 502: Bad Gateway")
            found = [dict(self.info, number=int(PR))]
            self.gh.answers[("pr", "list", "--head", BRANCH, "--state", "open")] = (0, json.dumps(found), "")

        self.gh.effects[("pr", "create")] = fail_but_open
        code, data = self.release_run("--draft")
        self.assertEqual(code, 0, data)
        self.assertEqual(len(self.gh.called("pr", "create")), 1)
