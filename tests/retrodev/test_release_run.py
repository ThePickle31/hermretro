"""release run: prepare, approve, land, the wait for CI and publish in one command, resumable, never publishing.

Against the temp origin of test_release with a fake GitHub that opens the version pull request, merges it for real
into the origin (as land's gh pr merge does) and answers CI as each test sets it.

Run alone: python -m unittest tests.retrodev.test_release_run
"""

import json
import re

from retrodev import release_verify, state

from tests.retrodev.fixture import git, parallel
from tests.retrodev.test_release import NEXT, PR, URL, WORDS, ReleaseCase, runs

load_tests = parallel

BRANCH = f"chore/release-{NEXT}"
GREEN = [{"name": "All checks pass", "state": "SUCCESS", "bucket": "pass", "link": ""}]
RED = [{"name": "All checks pass", "state": "FAILURE", "bucket": "fail", "link": "https://x/actions/runs/7/job/1"}]
RESUME = f"python tools/retrodev release run --version {NEXT} --owner-words 'make a release'"
RESUME_DRAFT = RESUME + " --draft"
AFTER = "0.0.3"  # the version release next moves dev to after NEXT
NEXT_PR = "41"
NEXT_BRANCH = f"chore/release-{AFTER}"


class RunCase(ReleaseCase):
    def setUp(self):
        super().setUp()
        self.clock = [0.0]
        self.fakes.update(sleep=self.tick, clock=lambda: self.clock[0])
        self.push_ci = runs("success")  # what CI says on the release commit once the pull request merges
        self.info: dict = {}
        self.gh.answers[("pr", "create")] = (0, f"https://github.com/o/r/pull/{PR}\n", "")
        self.gh.effects[("pr", "create")] = self.opened
        self.gh.answers[("pr", "ready", PR)] = (0, "", "")
        self.gh.effects[("pr", "ready", PR)] = lambda _args: self.view(isDraft=False)
        self.gh.answers[("pr", "merge", PR)] = (0, "", "")
        self.gh.effects[("pr", "merge", PR)] = self.squash
        self.gh.answers[("pr", "checks", PR)] = (0, json.dumps(GREEN), "")
        self.on_dev("docs/feature.md", "# A feature\n", "A feature for users")  # something to release
        git(self.main, "fetch", "-q", "origin")

    def tick(self, seconds: float) -> None:
        self.clock[0] += seconds

    def tree(self):
        return self.base / "hermretro-wt" / f"release-{NEXT}"

    def view(self, **info) -> None:
        self.info.update(info)
        self.gh.answers[("pr", "view", PR)] = (0, json.dumps(self.info), "")

    def opened(self, _args) -> None:
        """GitHub now knows the pushed release branch as #40, a draft into dev."""
        head = git(self.tree(), "rev-parse", "HEAD").strip()
        self.view(
            number=int(PR),
            title=f"Release {NEXT}",
            state="OPEN",
            isDraft=True,
            baseRefName="dev",
            headRefName=BRANCH,
            headRefOid=head,
            url=f"https://github.com/o/r/pull/{PR}",
            body="## Why\nA release.\n",
            statusCheckRollup=[],
        )

    def squash(self, args) -> None:
        other = self.base / "merger"
        if not other.exists():
            git(self.base, "clone", "-q", "-b", "dev", str(self.origin), str(other))
        git(other, "fetch", "-q", "origin")
        git(other, "reset", "-q", "--hard", "origin/dev")
        git(other, "merge", "-q", "--squash", f"origin/{BRANCH}")
        git(other, "commit", "-q", "-m", args[args.index("--subject") + 1])
        git(other, "push", "-q", "origin", "dev")
        git(other, "push", "-q", "origin", "--delete", BRANCH)
        sha = git(other, "rev-parse", "HEAD").strip()
        self.view(state="MERGED", mergeCommit={"oid": sha})
        self.ci(sha, self.push_ci)

    def release_run(self, *extra: str, as_json: bool = True):
        return self.run_cli("release", "run", "--owner-words", WORDS, *extra, as_json=as_json)

    def order(self, *prefixes: tuple) -> list[int]:
        """Where each gh call (by its argument prefix) first happened."""
        found = []
        for prefix in prefixes:
            hits = [n for n, call in enumerate(self.gh.calls) if tuple(call[: len(prefix)]) == prefix]
            self.assertTrue(hits, f"gh {' '.join(prefix)} never ran")
            found.append(hits[0])
        return found

    def snapshot(self) -> dict:
        """Every record and every ref here and on the origin."""
        records = {p: p.read_bytes() for p in sorted(state.root(self.main).rglob("*")) if p.is_file()}
        refs = git(self.main, "for-each-ref") + git(self.origin, "for-each-ref")
        return {"records": records, "refs": refs, "worktrees": git(self.main, "worktree", "list")}


class Flow(RunCase):
    def test_with_draft_one_command_takes_the_owners_words_to_the_draft_in_order_and_never_publishes(self):
        code, data = self.release_run("--draft")
        self.assertEqual(code, 0, data)
        self.assertEqual([s["step"] for s in data["run_steps"]], ["prepare", "approve", "land", "wait", "publish"])
        merge = self.info["mergeCommit"]["oid"]
        api = ("api", f"repos/{{owner}}/{{repo}}/commits/{merge}/check-runs?per_page=100")
        steps = self.order(("pr", "create"), ("pr", "ready", PR), ("pr", "merge", PR), api, ("release", "create"))
        self.assertEqual(steps, sorted(steps), self.gh.calls)
        self.assertEqual(self.gh.called("release", "edit"), [], "never published")
        self.assertIn("--draft", self.gh.called("release", "create")[0])
        self.assertEqual((data["url"], data["next"]), (URL, RESUME), "the same run without --draft publishes")
        self.assertEqual(self.gh.called("pr", "create", "--draft", "--base", "dev", "--head", NEXT_BRANCH), [])
        self.assertEqual((self.remote("refs/heads/main"), self.remote(f"refs/tags/v{NEXT}^{{commit}}")), (merge, merge))
        approval = json.loads((state.root(self.main) / "reviews" / f"{PR}.json").read_text())["approval"]
        self.assertEqual((approval["words"], approval["pr"]), (WORDS, int(PR)))
        ran = [entry.get("names") for entry in self.check_log()]
        self.assertNotIn(["acceptance"], ran, "a version-only branch needs no real-engine run")

    def test_a_rerun_after_each_stop_resumes_where_it_stopped(self):
        self.gh.answers[("pr", "create")] = (1, "", "HTTP 502")  # 1: ship fails inside prepare
        code, data = self.release_run("--draft")
        self.assertEqual(code, 1, data)
        self.assertIn(RESUME_DRAFT, data["error"]["fix"])
        self.assertTrue(state.load_release(self.main, NEXT)["run"], "the release is recorded before any step")
        self.gh.answers[("pr", "create")] = (0, f"https://github.com/o/r/pull/{PR}\n", "")
        self.gh.answers[("pr", "checks", PR)] = (0, json.dumps(RED), "")  # 2: land stops on red CI
        code, data = self.release_run("--draft")
        self.assertEqual(code, 1, data)
        self.assertIn(RESUME_DRAFT, data["error"]["fix"])
        self.assertEqual(self.gh.called("pr", "merge"), [])
        self.gh.answers[("pr", "checks", PR)] = (0, json.dumps(GREEN), "")
        self.push_ci = runs(None, "in_progress")  # 3: the push run on the release commit is still running
        code, data = self.release_run("--draft")
        self.assertEqual(code, 2, data)
        self.assertEqual(data["error"]["fix"], f"run it again later: {RESUME_DRAFT} (it resumes here)")
        merge = self.info["mergeCommit"]["oid"]
        self.ci(merge, runs("success"))
        self.gh.answers[("release", "create")] = (1, "", "HTTP 502")  # 4: publish stops after the tag
        code, data = self.release_run("--draft")
        self.assertEqual(code, 1, data)
        self.assertIn(RESUME_DRAFT, data["error"]["fix"])
        self.gh.answers[("release", "create")] = (0, URL + "\n", "")
        code, data = self.release_run("--draft")
        self.assertEqual((code, data.get("url")), (0, URL), data)
        self.gh.answers[("release", "view")] = (0, URL + "\n", "")  # gh's --jq .url
        code, data = self.release_run("--draft")  # 5: everything is done: the same draft again, nothing new
        self.assertEqual((code, data.get("url")), (0, URL), data)
        self.assertEqual(len(self.gh.called("pr", "create")), 2, "one failed, one opened; never a second release")
        self.assertEqual((len(self.gh.called("pr", "ready")), len(self.gh.called("pr", "merge"))), (1, 1))
        self.assertEqual(len(self.gh.called("release", "create")), 2)
        self.assertEqual(self.gh.called("release", "edit"), [])
        self.assertEqual(sorted(p.name for p in (state.root(self.main) / "releases").glob("*.json")), [f"{NEXT}.json"])
        self.assertEqual(self.remote(f"refs/tags/v{NEXT}^{{commit}}"), merge)

    def test_the_release_approval_covers_only_the_version_line_also_when_land_runs_on_its_own(self):
        self.gh.answers[("pr", "checks", PR)] = (0, json.dumps(RED), "")  # land stops on red CI, after the approval
        code, data = self.release_run()
        self.assertEqual(code, 1, data)
        approval = json.loads((state.root(self.main) / "reviews" / f"{PR}.json").read_text())["approval"]
        self.assertEqual((approval["scope"], approval["version"]), ("release", NEXT))
        tree = self.tree()
        self.commit(tree, "docs/extra.md", "# Extra\n", "An unrelated change")  # pushed after release run stopped
        git(tree, "push", "-q", "origin", BRANCH)
        self.view(headRefOid=git(tree, "rev-parse", "HEAD").strip())
        self.gh.answers[("pr", "checks", PR)] = (0, json.dumps(GREEN), "")
        self.run_cli("check", cwd=tree)  # what is pushed passed the checks: only the release scope can stop it
        code, data = self.run_cli("land", PR, as_json=True)
        self.assertEqual(code, 3, data)
        scope = [gate for gate in data["gates"] if gate["name"] == "release approval covers this head"]
        self.assertTrue(scope and not scope[0]["ok"], data["gates"])
        self.assertIn("changes more", scope[0]["message"])
        self.assertEqual(self.gh.called("pr", "merge"), [], "nothing merged on the release words")

    def test_the_release_approval_is_limited_even_when_marking_it_ready_fails(self):
        self.gh.answers[("pr", "ready", PR)] = (1, "", "HTTP 502")  # GitHub fails right after the approval is saved
        self.gh.effects.pop(("pr", "ready", PR), None)
        code, data = self.release_run()
        self.assertEqual(code, 1, data)
        approval = json.loads((state.root(self.main) / "reviews" / f"{PR}.json").read_text())["approval"]
        self.assertEqual((approval["scope"], approval["version"]), ("release", NEXT), "limited from the start")
        tree = self.tree()
        self.commit(tree, "docs/extra.md", "# Extra\n", "An unrelated change")
        git(tree, "push", "-q", "origin", BRANCH)
        self.view(headRefOid=git(tree, "rev-parse", "HEAD").strip(), isDraft=False)
        self.run_cli("check", cwd=tree)
        code, data = self.run_cli("land", PR, as_json=True)
        self.assertEqual(code, 3, data)
        self.assertEqual(self.gh.called("pr", "merge"), [], "nothing merged on the release words")

    def test_a_version_only_pull_request_passes_whatever_git_colours(self):
        git(self.main, "config", "color.ui", "always")  # diffs read for the version check must stay plain
        code, data = self.release_run("--draft")
        self.assertEqual(code, 0, data)
        ran = [entry.get("names") for entry in self.check_log()]
        self.assertNotIn(["acceptance"], ran, "still a version-only branch")

    def test_no_version_pull_request_skips_approve_and_land(self):
        self.on_dev("plugin.yaml", f"version: {NEXT}\n", "An earlier candidate bumped it")
        git(self.main, "fetch", "-q", "origin")
        head = git(self.main, "rev-parse", "origin/dev").strip()
        self.ci(head, runs("success"))
        code, data = self.release_run("--draft")
        self.assertEqual(code, 0, data)
        self.assertEqual([s["status"].split(":")[0] for s in data["run_steps"][1:3]], ["skipped", "skipped"])
        self.assertEqual((self.gh.called("pr", "view"), self.gh.called("pr", "merge")), ([], []))
        self.assertEqual(self.remote(f"refs/tags/v{NEXT}^{{commit}}"), head)


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


class Refused(RunCase):
    def version_pr(self, files: dict) -> str:
        """#40 open from the release branch with these files committed; the release recorded as prepare leaves it."""
        tree = self.worktree(BRANCH)
        for name, text in files.items():
            self.commit(tree, name, text, f"Release {NEXT}")
        git(tree, "push", "-q", "origin", BRANCH)
        record = {"version": NEXT, "words": WORDS, "at": "now", "rc": False, "branch": BRANCH, "pr": int(PR)}
        state.save_release(self.main, dict(record, no_pr=False, run={"at": "now"}))
        self.opened(None)
        return tree

    def test_a_version_pull_request_that_changes_more_than_the_version_line_is_never_approved(self):
        cases = {
            "another file": {"plugin.yaml": f"version: {NEXT}\n", "docs/extra.md": "# Extra\n"},
            "another plugin.yaml line": {"plugin.yaml": f"version: {NEXT}\nname: other\n"},
        }
        for name, files in cases.items():
            with self.subTest(name):
                self.setUp()
                self.version_pr(files)
                code, data = self.release_run()
                self.assertEqual(code, 3, data)
                self.assertIn("changes more than plugin.yaml's version line", data["error"]["message"])
                self.assertIn(RESUME, data["error"]["fix"])
                self.assertEqual((self.gh.called("pr", "ready"), self.gh.called("pr", "merge")), ([], []))
                self.assertNotIn("approval", state.load_branch(self.main, BRANCH))

    def assert_dry(self, text: str) -> None:
        """Every retrodev command in ``text`` (each `python tools/retrodev ...` up to the next `;` or line end) keeps
        --dry-run, except read-only ones."""
        for found in re.findall(r"python tools/retrodev [^;\n]*", text):
            if found.split()[2] in ("status", "report", "summary"):
                continue
            self.assertIn("--dry-run", found, f"a dry run printed a real command: {found}")

    def test_a_version_pull_request_that_sets_another_version_is_never_approved(self):
        self.version_pr({"plugin.yaml": "version: 9.9.9\n"})  # one line changed, but not to the release's version
        code, data = self.release_run()
        self.assertEqual(code, 3, data)
        self.assertIn(f"sets version 9.9.9, not {NEXT}", data["error"]["message"])
        self.assertIn(RESUME, data["error"]["fix"])
        self.assertEqual((self.gh.called("pr", "ready"), self.gh.called("pr", "merge")), ([], []))
        self.assertNotIn("approval", state.load_branch(self.main, BRANCH))

    def test_a_dry_run_changes_nothing_and_every_command_it_prints_keeps_dry_run(self):
        before = self.snapshot()
        code, out = self.release_run("--dry-run", as_json=False)  # nothing started yet
        self.assertEqual(code, 0, out)
        self.assertIn(f"would run: release prepare for {NEXT}", out)
        self.assert_dry(out)
        self.assertEqual((self.snapshot(), self.gh.calls), (before, []))
        self.version_pr({"plugin.yaml": f"version: {NEXT}\n"})  # open and version-only: would approve and land
        before = self.snapshot()
        code, out = self.release_run("--dry-run", as_json=False)
        self.assertEqual(code, 0, out)
        self.assertIn(f"would run: approve #{PR} with the owner's release words", out)
        self.assertIn(f"would run: python tools/retrodev land {PR} --dry-run", out)
        self.assert_dry(out)
        self.assertEqual(self.snapshot(), before)
        self.setUp()
        self.version_pr({"plugin.yaml": f"version: {NEXT}\n", "docs/extra.md": "# Extra\n"})
        code, out = self.release_run("--dry-run", as_json=False)
        self.assertEqual(code, 3, out)
        for text in (out, self.release_run("--dry-run")[1]["error"]["fix"]):
            self.assertIn("tools/retrodev release run", text)
            self.assert_dry(text)
        for verb in (("pr", "ready"), ("pr", "merge"), ("pr", "create"), ("release", "create"), ("release", "edit")):
            self.assertEqual(self.gh.called(*verb), [], verb)
