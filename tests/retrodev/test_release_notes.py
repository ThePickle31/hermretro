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
