"""release prepare, publish and verify against a temp origin with a main branch and a released tag, and a fake gh.

Run alone: python -m unittest tests.retrodev.test_release
"""

import json
import shlex
import unittest

from retrodev import release_verify, state

from tests.retrodev.fixture import RepoCase, git, parallel, write

load_tests = parallel

WORDS = "make a release"
PR = "40"
NEXT = "0.0.2"
URL = f"https://github.com/o/r/releases/tag/v{NEXT}"


def runs(conclusion: str | None, status: str = "completed") -> str:
    run = {"name": "All checks pass", "status": status, "conclusion": conclusion, "started_at": "2026-01-01T00:00:00Z"}
    return json.dumps({"check_runs": [run, {"name": "unit", "status": "completed", "conclusion": "failure"}]})


class ReleaseCase(RepoCase):
    def setUp(self):
        super().setUp()
        self.fakes["tmp_root"] = self.base  # throwaway checkouts inside the test's folder
        git(self.main, "tag", "-a", "v0.0.1", "-m", "Release 0.0.1")
        git(self.main, "push", "-q", "origin", "dev:main", "refs/tags/v0.0.1")
        self.gh.answers[("release", "view")] = (1, "", "release not found")
        self.gh.answers[("release", "create")] = (0, URL + "\n", "")

    def remote(self, ref: str) -> str:
        return git(self.origin, "rev-parse", "-q", "--verify", ref, check=False).strip()

    def merged_release(self, version: str = NEXT, pr: str | None = PR, words: str = WORDS) -> str:
        """The version pull request merged into origin/dev (as land leaves it), and the release recorded."""
        self.on_dev("plugin.yaml", f"version: {version.split('-rc.')[0]}\n", f"Release {version} (#{pr})")
        git(self.main, "fetch", "-q", "origin")
        sha = git(self.main, "rev-parse", "origin/dev").strip()
        record = {
            "version": version,
            "words": words,
            "at": "now",
            "rc": "-rc." in version,
            "pr": int(pr) if pr else None,
            "no_pr": not pr,  # what prepare records when it decided no version pull request was needed
        }
        state.save_release(self.main, record)
        if pr:
            self.gh.answers[("pr", "view", pr)] = (0, json.dumps({"state": "MERGED", "mergeCommit": {"oid": sha}}), "")
        self.ci(sha, runs("success"))
        return sha

    def ci(self, sha: str, answer: str) -> None:
        self.gh.answers[("api", f"repos/{{owner}}/{{repo}}/commits/{sha}/check-runs?per_page=100")] = (0, answer, "")

    def publish(self, version: str = NEXT, *extra: str):
        return self.run_cli("release", "publish", version, *extra, as_json=True)

    def failed_gates(self, data: dict) -> list[str]:
        return [gate["name"] for gate in data["gates"] if not gate["ok"]]


class Prepare(ReleaseCase):
    def test_no_release_without_the_owners_words(self):
        for words in ([], ["--owner-words", "  "], ["--owner-words", "ship the new page"]):
            code, data = self.run_cli("release", "prepare", *words, as_json=True)
            self.assertEqual(code, 3, data)
            self.assertIn("release", data["error"]["message"])
            self.assertIn("--owner-words", data["error"]["fix"])
        self.assertFalse((state.root(self.main) / "releases").exists())
        self.assertEqual(self.gh.calls, [])

    def test_prepare_bumps_only_the_version_checks_and_ships_the_release_pull_request(self):
        self.gh.answers[("pr", "create")] = (0, f"https://github.com/o/r/pull/{PR}\n", "")
        code, data = self.run_cli("release", "prepare", "--owner-words", WORDS, as_json=True)
        self.assertEqual(code, 0, data)
        self.assertEqual((data["version"], data["pr"]), (NEXT, int(PR)))
        tree = self.base / "hermretro-wt" / f"release-{NEXT}"
        self.assertEqual(git(tree, "branch", "--show-current").strip(), f"chore/release-{NEXT}")
        self.assertEqual(git(tree, "diff", "--name-only", "origin/dev", "HEAD").split(), ["plugin.yaml"])
        self.assertEqual((tree / "plugin.yaml").read_text(), f"version: {NEXT}\n")
        self.assertTrue(self.remote(f"refs/heads/chore/release-{NEXT}"), "the branch was pushed")
        create = self.gh.called("pr", "create")[0]
        self.assertEqual(create[create.index("--title") + 1], f"Release {NEXT}")
        self.assertEqual(create[create.index("--base") + 1], "dev")
        record = state.load_release(self.main, NEXT)
        self.assertEqual((record["words"], record["pr"]), (WORDS, int(PR)))
        ran = [entry.get("names", entry.get("script")) for entry in self.check_log()]
        self.assertIn([], ran)  # plugin.yaml changed: the clean install (its stand-in, no arguments)
        self.assertNotIn(["acceptance"], ran)  # only its version line: no real-engine run (checks_triggers)

    def test_a_reused_release_worktree_that_is_dirty_off_branch_or_carries_more_is_refused(self):
        self.gh.answers[("pr", "create")] = (0, f"https://github.com/o/r/pull/{PR}\n", "")
        tree = self.worktree(f"chore/release-{NEXT}")
        write(tree, "docs/guide.md", "# Unrelated work\n")  # dirty: commit -a would have taken it
        code, data = self.run_cli("release", "prepare", "--owner-words", WORDS, as_json=True)
        self.assertEqual(code, 1, data)
        self.assertIn("uncommitted changes", data["error"]["message"])
        self.assertIn("git worktree remove", data["error"]["fix"])
        self.commit(tree, "docs/guide.md", "# Unrelated work\n", "Unrelated")  # committed: still not a release
        code, data = self.run_cli("release", "prepare", "--owner-words", WORDS, as_json=True)
        self.assertEqual(code, 1, data)
        self.assertIn("more than plugin.yaml's version line (docs/guide.md", data["error"]["message"])
        git(tree, "switch", "-q", "-c", "feat/elsewhere", "origin/dev")  # the right folder, the wrong branch
        code, data = self.run_cli("release", "prepare", "--owner-words", WORDS, as_json=True)
        self.assertEqual(code, 1, data)
        self.assertIn(f"not chore/release-{NEXT}", data["error"]["message"])
        self.assertEqual(self.gh.called("pr", "create"), [])
        self.assertEqual(self.remote(f"refs/heads/chore/release-{NEXT}"), "", "nothing was pushed")

    def test_an_rc_is_numbered_after_the_last_candidate(self):
        git(self.main, "tag", f"v{NEXT}-rc.1", "HEAD")
        self.gh.answers[("pr", "create")] = (0, f"https://github.com/o/r/pull/{PR}\n", "")
        code, data = self.run_cli(
            "release", "prepare", "--rc", "--owner-words", "make a release candidate", as_json=True
        )
        self.assertEqual((code, data["version"]), (0, f"{NEXT}-rc.2"), data)


class Interrupted(ReleaseCase):
    """A prepare stopped after recording its branch, before its pull request number (check or ship failed)."""

    BRANCH = f"chore/release-{NEXT}"

    def land(self) -> str:
        """The version pull request squash-merged into origin/dev (as land's gh merge leaves it), then dev moves on."""
        self.on_dev("plugin.yaml", f"version: {NEXT}\n", f"Release {NEXT} (#{PR})")
        merge = git(self.base / "other", "rev-parse", "HEAD").strip()
        self.gh.answers[("pr", "view", PR)] = (0, json.dumps({"state": "MERGED", "mergeCommit": {"oid": merge}}), "")
        self.ci(merge, runs("success"))
        self.on_dev("docs/later.md", "# Later\n")
        self.ci(git(self.base / "other", "rev-parse", "HEAD").strip(), runs("success"))
        return merge

    def test_the_printed_recovery_resumes_prepare_and_publish_takes_the_merge_commit(self):
        self.gh.answers[("pr", "create")] = (1, "", "HTTP 502")
        code, data = self.run_cli("release", "prepare", "--owner-words", WORDS, as_json=True)
        self.assertEqual(code, 1, data)
        record = state.load_release(self.main, NEXT)
        self.assertEqual((record["branch"], record["pr"], record["no_pr"]), (self.BRANCH, None, False))
        fix = data["error"]["fix"]
        recovery = f"python tools/retrodev release prepare --version {NEXT} --owner-words 'make a release'"
        self.assertIn(recovery, fix)
        code, data = self.publish()
        self.assertEqual((code, self.failed_gates(data)), (1, ["release pull request merged"]), data)
        self.assertIn("did not finish", data["gates"][1]["message"])
        self.assertIn(recovery, data["error"]["fix"])
        self.gh.answers[("pr", "create")] = (0, f"https://github.com/o/r/pull/{PR}\n", "")
        code, data = self.run_cli(*shlex.split(recovery)[2:], as_json=True)  # follow it, as printed
        self.assertEqual((code, data.get("pr")), (0, int(PR)), data)
        self.assertEqual(state.load_release(self.main, NEXT)["pr"], int(PR))
        merge = self.land()
        code, data = self.publish()
        self.assertEqual(code, 0, data)
        self.assertEqual((data["sha"], self.remote("refs/heads/main")), (merge, merge))
        self.assertEqual(self.remote(f"refs/tags/v{NEXT}^{{commit}}"), merge)

    def test_publish_finds_the_pull_request_by_its_branch_and_keeps_it(self):
        record = {"version": NEXT, "words": WORDS, "at": "now", "rc": False, "branch": self.BRANCH, "pr": None}
        state.save_release(self.main, record)
        code, data = self.publish()  # no pull request from the branch yet: refused, never dev's head
        self.assertEqual((code, self.failed_gates(data)), (1, ["release pull request merged"]), data)
        self.assertIn(f"release prepare --version {NEXT}", data["error"]["fix"])
        self.assertNotIn("sha", state.load_release(self.main, NEXT), "nothing was pinned")
        merge = self.land()  # shipped and landed by hand meanwhile
        listed = [{"number": int(PR), "state": "MERGED", "mergeCommit": {"oid": merge}}]
        self.gh.answers[("pr", "list", "--head", self.BRANCH, "--state", "all")] = (0, json.dumps(listed), "")
        code, data = self.publish()
        self.assertEqual((code, data.get("sha")), (0, merge), data)
        self.assertEqual(state.load_release(self.main, NEXT)["pr"], int(PR))

    def test_prepare_again_after_the_merge_records_the_pull_request_not_no_pr(self):
        state.save_release(self.main, {"version": NEXT, "words": WORDS, "at": "now", "branch": self.BRANCH, "pr": None})
        merge = self.land()  # dev now says the version: without the record, prepare would see no pull request needed
        listed = [{"number": 39, "state": "CLOSED"}, {"number": int(PR), "state": "MERGED"}]
        self.gh.answers[("pr", "list", "--head", self.BRANCH, "--state", "all")] = (0, json.dumps(listed), "")
        code, data = self.run_cli("release", "prepare", "--version", NEXT, "--owner-words", WORDS, as_json=True)
        self.assertEqual((code, data.get("pr"), data.get("resumed")), (0, int(PR), True), data)
        self.assertFalse(state.load_release(self.main, NEXT)["no_pr"])
        self.assertEqual(self.publish()[1].get("sha"), merge)


class Publish(ReleaseCase):
    def test_a_release_without_words_is_refused(self):
        code, data = self.publish()
        self.assertEqual(code, 3, data)
        self.assertIn("owner asked for this release", self.failed_gates(data))

    def test_an_unmerged_release_pull_request_waits(self):
        self.merged_release()
        self.gh.answers[("pr", "view", PR)] = (0, json.dumps({"state": "OPEN", "mergeCommit": None}), "")
        code, data = self.publish()
        self.assertEqual((code, self.failed_gates(data)), (2, ["release pull request merged"]), data)
        self.assertIn(f"land {PR}", data["error"]["fix"])

    def test_red_or_running_ci_on_the_release_commit_is_refused(self):
        sha = self.merged_release()
        self.ci(sha, runs("failure"))
        code, data = self.publish()
        self.assertEqual((code, self.failed_gates(data)), (1, [f"CI green on {sha[:9]}"]), data)
        self.ci(sha, runs(None, "in_progress"))
        self.assertEqual(self.publish()[0], 2)
        self.assertEqual(self.remote("refs/heads/main"), self.remote("refs/tags/v0.0.1^{commit}"))

    def test_main_that_cannot_fast_forward_needs_the_owner(self):
        self.merged_release()
        other = self.base / "other"
        git(other, "fetch", "-q", "origin")
        git(other, "switch", "-q", "-c", "hotfix", "origin/main")
        self.commit(other, "docs/hot.md", "# Hot\n", "Hotfix on main")
        git(other, "push", "-q", "origin", "hotfix:main")
        code, data = self.publish()
        self.assertEqual((code, self.failed_gates(data)), (3, ["main fast-forwards"]), data)
        self.assertEqual(self.gh.called("release", "create"), [])

    def test_dry_run_prints_every_command_and_changes_nothing(self):
        sha = self.merged_release()
        before = self.remote("refs/heads/main")
        code, data = self.publish(NEXT, "--dry-run")
        self.assertEqual(code, 0, data)
        self.assertEqual(
            data["commands"],
            [
                f"HERMES_RELEASE=1 git push origin {sha}:main",
                f"git tag -a v{NEXT} {sha} -m 'Release {NEXT}'",
                f"git push origin refs/tags/v{NEXT}",
                f"gh release create v{NEXT} --verify-tag --notes-file "
                + str(state.root(self.main) / "releases" / f"{NEXT}-notes.md")
                + " --draft",
            ],
        )
        self.assertEqual((self.remote("refs/heads/main"), self.remote(f"refs/tags/v{NEXT}")), (before, ""))
        self.assertEqual(git(self.main, "tag", "-l", f"v{NEXT}").strip(), "")
        self.assertEqual((self.gh.called("release", "create"), self.check_log()), ([], []))

    def test_publish_fast_forwards_main_tags_and_drafts_then_resumes_without_repeating(self):
        sha = self.merged_release()
        code, data = self.publish()
        self.assertEqual(code, 0, data)
        self.assertEqual(self.remote("refs/heads/main"), sha)
        self.assertEqual(self.remote(f"refs/tags/v{NEXT}^{{commit}}"), sha)
        self.assertEqual(git(self.origin, "cat-file", "-t", f"v{NEXT}").strip(), "tag", "annotated")
        create = self.gh.called("release", "create")
        notes_file = state.root(self.main) / "releases" / f"{NEXT}-notes.md"
        self.assertEqual(create[0][-3:], ["--notes-file", str(notes_file), "--draft"])
        notes = notes_file.read_text()
        self.assertIn("## Updating", notes)
        self.assertIn("Real-machine checklist (docs/dev/RELEASE-CHECKLIST.md): not needed", notes)
        self.assertNotIn(f"Release {NEXT}", notes, "the version pull request is left out")
        self.assertEqual(data["url"], URL)
        self.assertEqual(self.check_log()[0]["script"], ["--update-from", "v0.0.1"])  # from the last release
        self.assertEqual(self.check_log()[0]["head"], sha)
        self.assertEqual([p.name for p in self.base.glob("rd-*")], [], "the throwaway checkout is gone")
        self.gh.answers[("release", "view")] = (0, json.dumps({"url": URL}), "")
        code, again = self.publish()
        self.assertEqual(code, 0, again)
        self.assertEqual(len(self.gh.called("release", "create")), 1, "nothing is done twice")
        self.assertEqual(len(self.check_log()), 1, "the update check's pass is kept for this commit")

    def test_the_owners_checklist_result_goes_into_the_notes(self):
        self.merged_release()
        code, data = self.publish(NEXT, "--checklist", "passed on a MacBook Pro (M3)")
        self.assertEqual(code, 0, data)
        notes = (state.root(self.main) / "releases" / f"{NEXT}-notes.md").read_text()
        self.assertIn("Real-machine checklist (docs/dev/RELEASE-CHECKLIST.md): passed on a MacBook Pro (M3)", notes)
        self.assertEqual(state.load_release(self.main, NEXT)["checklist"], "passed on a MacBook Pro (M3)")

    def test_a_checklist_result_given_after_the_draft_goes_into_its_notes(self):
        self.merged_release()
        self.assertEqual(self.publish()[0], 0)  # the draft, "not needed"
        tag = f"v{NEXT}"
        drafted = (state.root(self.main) / "releases" / f"{NEXT}-notes.md").read_text() + "\nA hand-written note.\n"
        self.gh.answers[("release", "view", tag, "--json", "url")] = (0, json.dumps({"url": URL}), "")
        self.gh.answers[("release", "view", tag, "--json", "body")] = (0, drafted, "")
        self.gh.answers[("release", "edit")] = (0, "", "")
        code, data = self.publish(NEXT, "--checklist", "passed on a MacBook Pro (M3)")
        self.assertEqual(code, 0, data)
        edit = self.gh.called("release", "edit", tag, "--notes")
        self.assertEqual(len(edit), 1, self.gh.calls)
        self.assertIn("RELEASE-CHECKLIST.md): passed on a MacBook Pro (M3)", edit[0][-1])
        self.assertIn("A hand-written note.", edit[0][-1])
        self.assertNotIn("not needed", edit[0][-1])

    def test_a_retry_after_dev_moves_releases_the_commit_the_first_publish_chose(self):
        sha = self.merged_release(pr=None)  # no version pull request: the release commit is dev's head
        self.gh.answers[("release", "create")] = (1, "", "HTTP 502")  # stopped after the tag was pushed
        code, data = self.publish()
        self.assertEqual(code, 1, data)
        self.assertEqual(self.remote(f"refs/tags/v{NEXT}^{{commit}}"), sha)
        self.assertEqual(state.load_release(self.main, NEXT)["sha"], sha, "kept before any step ran")
        self.on_dev("docs/later.md", "# Later\n")  # dev moves on before the retry
        moved = git(self.base / "other", "rev-parse", "HEAD").strip()
        self.ci(moved, runs("success"))
        self.gh.answers[("release", "create")] = (0, URL + "\n", "")
        code, data = self.publish()
        self.assertEqual(code, 0, data)
        self.assertEqual((data["sha"], self.remote("refs/heads/main")), (sha, sha))
        self.assertEqual(state.load_release(self.main, NEXT)["approved"]["sha"], sha)

    def test_a_retry_before_tagging_keeps_the_chosen_commit_too(self):
        sha = self.merged_release(pr=None)
        self.ci(sha, runs(None, "in_progress"))
        self.assertEqual(self.publish()[0], 2)  # waits for CI, nothing done yet
        self.on_dev("docs/later.md", "# Later\n")
        self.ci(git(self.base / "other", "rev-parse", "HEAD").strip(), runs("success"))
        self.ci(sha, runs("success"))
        code, data = self.publish()
        self.assertEqual((code, data.get("sha")), (0, sha), data)
        self.assertEqual(self.remote(f"refs/tags/v{NEXT}^{{commit}}"), sha)

    def test_a_release_candidate_tags_dev_and_leaves_main_alone(self):
        version = f"{NEXT}-rc.1"
        sha = self.merged_release(version, pr=None, words="make a release candidate")
        main = self.remote("refs/heads/main")
        code, data = self.publish(version)
        self.assertEqual(code, 0, data)
        self.assertEqual(self.remote("refs/heads/main"), main)
        self.assertEqual(self.remote(f"refs/tags/v{version}^{{commit}}"), sha)
        self.assertEqual(self.gh.called("release", "create")[0][-2:], ["--draft", "--prerelease"])
        self.assertFalse(any(":main" in command for command in data["commands"]))


class Verify(ReleaseCase):
    def released(self, body: str = "## Changes\n- A thing") -> str:
        sha = self.merged_release()
        self.assertEqual(self.publish()[0], 0)
        self.clear_log()
        view = {"tagName": f"v{NEXT}", "isDraft": True, "isPrerelease": False, "body": body, "url": URL}
        self.gh.answers[("release", "view", f"v{NEXT}", "--json", release_verify.FIELDS)] = (0, json.dumps(view), "")
        self.gh.answers[("release", "edit")] = (0, "", "")
        return sha

    def test_verify_checks_the_draft_and_publishes_only_when_asked(self):
        self.released()
        code, data = self.run_cli("release", "verify", NEXT, as_json=True)
        self.assertEqual((code, data["published"]), (0, False), data)
        self.assertEqual(self.check_log(), [], "publish's update check on this commit counts: it runs once")
        update = [gate for gate in data["gates"] if gate["name"] == "update from the last release"][0]
        self.assertIn("release publish's run", update["message"])
        record = state.load_release(self.main, NEXT)
        record["install"] = {}  # nothing kept (an older record): verify runs it
        state.save_release(self.main, record)
        self.assertEqual(self.run_cli("release", "verify", NEXT, as_json=True)[0], 0)
        self.assertEqual(self.check_log()[0]["script"], ["--update-from", "v0.0.1"])
        self.assertEqual(self.gh.called("release", "edit"), [])
        code, out = self.run_cli("release", "verify", NEXT, "--publish")
        self.assertEqual(code, 0, out)
        self.assertIn("immutable", out)
        self.assertEqual(self.gh.called("release", "edit"), [["release", "edit", f"v{NEXT}", "--draft=false"]])

    def test_publish_needs_the_owners_words(self):
        self.released()
        record = state.load_release(self.main, NEXT)
        del record["words"]
        state.save_release(self.main, record)
        code, data = self.run_cli("release", "verify", NEXT, "--publish", as_json=True)
        self.assertEqual((code, self.failed_gates(data)), (3, ["owner asked for this release"]), data)
        self.assertEqual(self.gh.called("release", "edit"), [])
        self.assertEqual(self.run_cli("release", "verify", NEXT, as_json=True)[0], 0, "read-only verify still works")

    def test_publish_needs_ci_green_on_the_tagged_commit(self):
        sha = self.released()
        self.ci(sha, runs("failure"))
        code, data = self.run_cli("release", "verify", NEXT, "--publish", as_json=True)
        self.assertEqual((code, self.failed_gates(data)), (1, [f"CI green on {sha[:9]}"]), data)
        self.assertEqual(self.gh.called("release", "edit"), [])

    def test_a_hand_made_candidate_draft_or_a_moved_tag_is_never_published(self):
        version = f"{NEXT}-rc.1"
        sha = self.merged_release(version, pr=None, words="make a release candidate")
        git(self.main, "tag", f"v{version}", sha)  # made by hand: release publish never ran
        git(self.main, "push", "-q", "origin", f"refs/tags/v{version}")
        view = {"tagName": f"v{version}", "isDraft": True, "isPrerelease": True, "body": "- A thing", "url": URL}
        self.gh.answers[("release", "view", f"v{version}", "--json", release_verify.FIELDS)] = (0, json.dumps(view), "")
        self.gh.answers[("release", "edit")] = (0, "", "")
        code, data = self.run_cli("release", "verify", version, "--publish", as_json=True)
        self.assertEqual((code, self.failed_gates(data)), (3, ["release publish approved this commit"]), data)
        record = state.load_release(self.main, version)
        record["approved"] = {"sha": sha, "at": "then"}  # publish approved sha; then the tag moves to a later commit
        state.save_release(self.main, record)
        self.on_dev("docs/later.md", "# Later\n")
        later = git(self.base / "other", "rev-parse", "HEAD").strip()
        git(self.main, "fetch", "-q", "origin")
        git(self.main, "tag", "-f", f"v{version}", later)
        git(self.main, "push", "-q", "-f", "origin", f"refs/tags/v{version}")
        self.ci(later, runs("success"))
        code, data = self.run_cli("release", "verify", version, "--publish", as_json=True)
        self.assertEqual(code, 3, data)
        self.assertIn("release publish approved this commit", self.failed_gates(data))
        self.assertEqual(self.gh.called("release", "edit"), [])

    def test_empty_notes_or_a_tag_off_mains_head_are_refused(self):
        self.released(body="  ")
        self.on_dev("docs/later.md", "# Later\n")
        other = self.base / "other"
        git(other, "push", "-q", "origin", "dev:main")  # main moved past the tag
        code, data = self.run_cli("release", "verify", NEXT, "--publish", as_json=True)
        self.assertEqual(code, 1, data)
        self.assertEqual(self.failed_gates(data), ["notes", "tag is main's head"])
        self.assertEqual(self.gh.called("release", "edit"), [])


if __name__ == "__main__":
    unittest.main()
