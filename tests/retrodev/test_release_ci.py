"""Release upgrade evidence uses full commits and only the trusted, successful dev push attempt."""

import io
import json

from retrodev import release_ci, release_publish, state
from retrodev.config import Context
from retrodev.output import Out

from tests.retrodev.fixture import git, parallel
from tests.retrodev.test_release import NEXT, RELEASES, ReleaseCase, published_release, runs

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
        self.published = release_ci.Baseline(TAG, self.old, immutable=True)
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
        self.reply(self.lookup, {"total_count": 1, "workflow_runs": [self.workflow]})
        self.reply(self.jobs, {"total_count": 1, "jobs": [self.job]})
        if restore_logs:
            self.gh.answers[self.logs] = (0, self.log, "")
        return release_ci.evidence(self.ctx, self.sha, self.published)

    def test_success_from_either_ci_job_records_the_runtime_and_full_shas(self):
        for name in release_ci.UPGRADE_JOBS:
            with self.subTest(name=name):
                self.job["name"] = name
                self.assertEqual(self.proof(), dict(run=123, attempt=2, job=456, baseline=self.old, hermes=HERMES))
        rec = state.load_release(self.main, NEXT) or {}
        result = release_publish.install_check(self.ctx, rec, self.sha, self.published)
        self.assertTrue(result["ok"], result)
        self.assertIn(HERMES, result["detail"])
        self.assertEqual(self.check_log(), [], "no duplicate local run")
        saved = state.load_release(self.main, NEXT) or {}
        self.assertEqual(saved["install"][self.sha]["source"], "ci")

    def test_mismatches_cannot_credit_an_upgrade(self):
        self.assertIsNone(release_ci.evidence(self.ctx, self.sha, self.published._replace(immutable=False)))
        for target, key, bad in (
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
        self.assertTrue(release_publish.install_check(self.ctx, rec, self.sha, self.published)["ok"])
        self.job["run_attempt"] = 1
        self.assertIsNone(self.proof())
        result = release_publish.install_check(self.ctx, rec, self.sha, self.published)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.check_log()[0]["script"], ["--update-from", self.old])
        saved = state.load_release(self.main, NEXT) or {}
        self.assertEqual(saved["install"][self.sha]["source"], "local")


class PreviousPublished(ReleaseCase):
    def test_fallback_uses_the_published_predecessor_instead_of_an_intervening_draft(self):
        old = self.remote(f"refs/tags/{TAG}^{{commit}}")
        draft = self.merged_release()
        draft_tag = f"v{NEXT}"
        git(self.main, "tag", "-a", draft_tag, draft, "-m", "Intervening draft")
        git(self.main, "push", "-q", "origin", f"{draft}:refs/heads/main", f"refs/tags/{draft_tag}")
        later = f"0.0.{3}"
        sha = self.merged_release(later)
        history = [[dict(published_release(draft_tag), draft=True, published_at=None)], [published_release(TAG)]]
        self.gh.answers[RELEASES] = (0, json.dumps(history), "")
        code, result = self.publish(later)
        self.assertEqual(code, 0, result)
        self.assertEqual(self.check_log()[0]["script"], ["--update-from", old])
        saved = state.load_release(self.main, later) or {}
        self.assertEqual(saved["install"][sha]["from"], TAG)

    def test_an_unconfirmed_upgrade_baseline_blocks_the_release(self):
        self.merged_release()
        main = self.remote("refs/heads/main")
        for response in ((1, "", "HTTP 403"), (0, "[[]]", ""), (0, '{"message":"bad shape"}', "")):
            self.gh.answers[RELEASES] = response
            code, result = self.publish()
            self.assertEqual(code, 1, result)
            assert isinstance(result, dict)
            self.assertIn("upgrade unverified", result["error"]["message"])
            self.assertEqual(self.remote("refs/heads/main"), main)
        self.assertEqual(self.gh.called("release", "create"), [])
        self.assertEqual(self.check_log(), [])
