"""release_notes.write: the pull requests since the last stable tag, grouped for users, and what was tested.

Against the temp origin of test_release (v0.0.1 tagged) with squash-style commits landed on dev and a fake GitHub
that names each one's branch.

Run alone: python -m unittest tests.retrodev.test_release_notes
"""

import io
import json

from retrodev import config, output, release_notes

from tests.retrodev.fixture import git, parallel
from tests.retrodev.test_release import ReleaseCase

load_tests = parallel


class Notes(ReleaseCase):
    def land(self, branch: str, path: str, subject: str, number: int) -> dict:
        self.on_dev(path, f"# {subject}\n", f"{subject} (#{number})")
        sha = git(self.base / "other", "rev-parse", "HEAD").strip()
        return {"headRefName": branch, "mergeCommit": {"oid": sha}}

    def write(self, merged: list[dict], checklist: str | None = None) -> str:
        self.gh.answers[("pr", "list", "--base")] = (0, json.dumps(merged), "")
        git(self.main, "fetch", "-q", "origin")
        ctx = config.Context.make(self.main, output.Out(stream=io.StringIO()), gh_runner=self.gh)
        sha = git(self.main, "rev-parse", "origin/dev").strip()
        return release_notes.write(ctx, "0.0.2", sha, "0.0.1", checklist)

    def test_changes_are_grouped_for_users_and_version_pull_requests_left_out(self):
        merged = [
            self.land("feat/shelf", "page/shelf.js", "Your games stand on the floor", 5),
            self.land("fix/label", "backend/library/x.py", "Labels say why there is no picture", 6),
            self.land("chore/trial-round", "tools/retrodev/x.py", "retrodev: fixes from a trial round", 7),
            self.land("docs/guide", "docs/dev/TESTING.md", "The testing guide names the tiers", 8),
            self.land("chore/release-0.0.2", "plugin.yaml", "Release 0.0.2", 9),
        ]
        notes = self.write(merged)
        new, fixes = notes.index("## New"), notes.index("## Fixes and improvements")
        behind = notes.index("<details><summary>Behind the scenes (2 changes")
        self.assertLess(new, notes.index("Your games stand on the floor"))
        self.assertLess(fixes, notes.index("Labels say why there is no picture"))
        self.assertLess(behind, notes.index("retrodev: fixes from a trial round"))
        self.assertLess(behind, notes.index("The testing guide names the tiers"))
        self.assertLess(notes.index("Labels say why"), behind, "user-facing changes come before the folded ones")
        self.assertNotIn("Release 0.0.2", notes)
        self.assertIn("## Updating", notes)
        self.assertIn("the update from v0.0.1", notes)
        self.assertIn("not needed", notes, "nothing in setup, the broker or the host code changed")

    def test_the_checklist_is_asked_for_when_setup_or_the_broker_changed_and_its_result_shown(self):
        merged = [self.land("fix/broker", "backend/broker/lane.py", "The broker restarts a stuck worker", 5)]
        notes = self.write(merged)
        self.assertIn("not run, though this release changes setup, the broker or the host code", notes)
        self.assertIn("`backend/broker/lane.py`", notes)
        notes = self.write(merged, checklist="passed on a MacBook Pro (M3), Hermes 0.24")
        self.assertIn("passed on a MacBook Pro (M3), Hermes 0.24", notes)
        self.assertNotIn("not run", notes)

    def test_trial_rounds_fold_into_one_line_and_folder_notes_are_not_user_changes(self):
        merged = [
            self.land(
                "fix/docs-trial-round-one",
                "page/a.js",
                "Pages and docs: fixes from the first round of fresh-agent trials",
                5,
            ),
            self.land(
                "fix/docs-trial-round-two",
                "page/b.js",
                "Pages and docs: fixes from the second round of fresh-agent trials",
                6,
            ),
            self.land("docs/setup-notes", "backend/setup/README.md", "The setup notes name the steps", 7),
        ]
        notes = self.write(merged)
        self.assertIn("- Pages and docs: fixes from 2 rounds of fresh-agent trials (#5, #6)", notes)
        self.assertNotIn("first round", notes)
        self.assertLess(notes.index("Behind the scenes"), notes.index("The setup notes name the steps"))
        self.assertIn("not needed", notes, "a README under backend/setup/ asks for no checklist")

    def test_shipped_skills_and_the_studio_profile_are_user_changes(self):
        merged = [
            self.land("fix/skill", "skills/authoring/SKILL.md", "The authoring skill names the palette limits", 5),
            self.land("fix/soul", "profile/SOUL.md", "The studio speaks more plainly", 6),
        ]
        notes = self.write(merged)
        self.assertLess(notes.index("## Fixes and improvements"), notes.index("The authoring skill names"))
        self.assertIn("The studio speaks more plainly", notes.split("<details>")[0])
        self.assertNotIn("Nothing that changes what you see", notes)

    def test_a_result_replaces_the_checklist_line_of_an_edited_draft_and_keeps_the_rest(self):
        body = "## New\n\n- A thing\n\nA hand-written note.\n\nReal-machine checklist (docs/dev/RELEASE-CHECKLIST.md): not run, though x\n"
        new = release_notes.with_result(body, "passed on a MacBook Pro (M3)")
        self.assertIn("A hand-written note.", new)
        self.assertIn("Real-machine checklist (docs/dev/RELEASE-CHECKLIST.md): passed on a MacBook Pro (M3)", new)
        self.assertNotIn("not run", new)
        self.assertIn("passed on", release_notes.with_result("## New\n- A thing\n", "passed on a MacBook"))

    def test_without_github_each_change_is_grouped_by_its_files(self):
        self.land("x", "page/a.js", "A page change", 5)
        self.land("x", "tests/repo/test_x.py", "A test change", 6)
        self.gh.answers[("pr", "list", "--base")] = (1, "", "HTTP 502")
        git(self.main, "fetch", "-q", "origin")
        ctx = config.Context.make(self.main, output.Out(stream=io.StringIO()), gh_runner=self.gh)
        ctx.fakes["sleep"] = lambda _s: None
        notes = release_notes.write(ctx, "0.0.2", git(self.main, "rev-parse", "origin/dev").strip(), "0.0.1", None)
        self.assertLess(notes.index("## Fixes and improvements"), notes.index("A page change"))
        self.assertLess(notes.index("Behind the scenes"), notes.index("A test change"))
        self.assertNotIn("## New", notes)
