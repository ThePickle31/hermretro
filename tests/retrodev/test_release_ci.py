"""Release upgrade evidence uses full commits and only the trusted, successful dev push attempt."""

import io
import json

from retrodev import release_ci, release_publish, state
from retrodev.config import Context
from retrodev.output import Out

from tests.retrodev.fixture import git, parallel
from tests.retrodev.test_release import NEXT, ReleaseCase, runs

load_tests = parallel
SLUG = "o/r"
ROOT = f"repos/{SLUG}"
TAG = "v0.0.1"
HERMES = "a" * 40
STAMP = "2026-11-21T18:50:40.2939440Z "
GREEN = {"status": "completed", "conclusion": "success"}


class Evidence(ReleaseCase):
    def setUp(self):
        super().setUp()
        self.sha = self.merged_release()
        self.old = self.remote(f"refs/tags/{TAG}^{{commit}}")
        git(self.main, "remote", "add", "proof", f"https://github.com/{SLUG}.git")
        self.ctx = Context.make(self.main, Out(stream=io.StringIO()), gh_runner=self.gh, fakes=self.fakes)
        self.ctx.local["remote"] = "proof"
        self.release = {"tag_name": TAG, "draft": False, "prerelease": False, "published_at": "then", "immutable": True}
        self.workflow: dict = dict(
            GREEN,
            id=123,
            run_attempt=2,
            head_sha=self.sha,
            head_branch="dev",
            event="push",
            path=release_ci.WORKFLOW,
            repository={"full_name": SLUG},
            head_repository={"full_name": SLUG},
        )
        self.step: dict = dict(GREEN, name=release_ci.UPGRADE_STEP)
        self.job: dict = dict(
            GREEN,
            id=456,
            run_id=123,
            run_attempt=2,
            head_sha=self.sha,
            name=release_ci.UPGRADE_JOBS[0],
            steps=[self.step],
        )
        self.log = f"{STAMP}Hermes at {HERMES}\n{STAMP}upgrade evidence: {TAG} {self.old} -> {self.sha}\n"
        self.lookup = f"{ROOT}/actions/workflows/ci.yml/runs?branch=dev&event=push&head_sha={self.sha}"
        self.jobs = f"{ROOT}/actions/runs/123/attempts/2/jobs?per_page=100"
        self.logs = ("api", "--allow-escape-sequences", f"{ROOT}/actions/jobs/456/logs")

    def reply(self, path, document):
        self.gh.answers[("api", path)] = (0, json.dumps(document), "")

    def proof(self, *, restore_logs=True):
        self.reply(f"{ROOT}/releases/tags/{TAG}", self.release)
        self.reply(self.lookup, {"total_count": 1, "workflow_runs": [self.workflow]})
        self.reply(self.jobs, {"total_count": 1, "jobs": [self.job]})
        if restore_logs:
            self.gh.answers[self.logs] = (0, self.log, "")
        return release_ci.evidence(self.ctx, self.sha, TAG, self.old)

    def test_success_from_either_ci_job_records_the_runtime_and_full_shas(self):
        for name in release_ci.UPGRADE_JOBS:
            with self.subTest(name=name):
                self.job["name"] = name
                self.assertEqual(self.proof(), dict(run=123, attempt=2, job=456, baseline=self.old, hermes=HERMES))
        rec = state.load_release(self.main, NEXT) or {}
        result = release_publish.install_check(self.ctx, rec, self.sha, TAG)
        self.assertTrue(result["ok"], result)
        self.assertIn(HERMES, result["detail"])
        self.assertEqual(self.check_log(), [], "no duplicate local run")
        saved = state.load_release(self.main, NEXT) or {}
        self.assertEqual(saved["install"][self.sha]["source"], "ci")

    def test_mismatches_cannot_credit_an_upgrade(self):
        for target, key, bad in (
            (self.release, "draft", True),
            (self.release, "immutable", False),
            (self.workflow, "event", "pull_request"),
            (self.workflow, "path", ".github/workflows/nightly.yml"),
            (self.workflow, "head_sha", "b" * 40),
            (self.workflow, "head_repository", {"full_name": "fork/r"}),
            (self.workflow, "head_branch", "main"),
            (self.workflow, "conclusion", "failure"),
            (self.job, "run_attempt", 1),
            (self.job, "name", "Update from the tested dev base"),
            (self.job, "head_sha", "c" * 40),
            (self.step, "conclusion", "skipped"),
        ):
            with self.subTest(key=key, bad=bad):
                original = target[key]
                target[key] = bad
                self.assertIsNone(self.proof())
                target[key] = original
        good = self.log
        for missing in (good.replace(self.old, self.old[:10]), good.replace(self.old, "d" * 40), good * 2, ""):
            self.log = missing
            self.assertIsNone(self.proof())
        self.gh.answers[self.logs] = (1, "", "HTTP 404")
        self.assertIsNone(self.proof(restore_logs=False))

    def test_red_required_ci_stops_before_any_install_or_remote_write(self):
        self.ci(self.sha, runs("failure"))
        main = self.remote("refs/heads/main")
        self.assertEqual(self.publish()[0], 1)
        self.assertEqual(self.remote("refs/heads/main"), main)
        self.assertEqual(self.check_log(), [])
        self.assertEqual(self.gh.called("release", "create"), [])

    def test_incomplete_evidence_uses_the_local_upgrade_instead(self):
        self.assertIsNotNone(self.proof())
        rec = state.load_release(self.main, NEXT) or {}
        self.assertTrue(release_publish.install_check(self.ctx, rec, self.sha, TAG)["ok"])
        self.job["run_attempt"] = 1
        self.assertIsNone(self.proof())
        result = release_publish.install_check(self.ctx, rec, self.sha, TAG)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.check_log()[0]["script"], ["--update-from", self.old])
        saved = state.load_release(self.main, NEXT) or {}
        self.assertEqual(saved["install"][self.sha]["source"], "local")
